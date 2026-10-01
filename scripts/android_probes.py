#!/usr/bin/env python3
"""Build one-question Swift packages for Android and compare each outcome with its source.

Each directory under scripts/probes/android/ is a one-file package asking one question,
such as "does `import UIKit` build?". expectations.json records what a primary source says:

    pass    the probe must build; if it does not, the run fails
    fail    the probe must not build; if it does, the run fails. When error_contains is
            set, a compiler error with a source location must contain it, so a broken
            toolchain cannot pass for the claimed failure
    record  no primary source settles the question: the outcome is recorded, never judged

    python3 scripts/android_probes.py --list
    python3 scripts/android_probes.py --swift "$(which swift)" --swift-sdk "$SWIFT_SDK_ID" \\
        [--triple aarch64-unknown-linux-android28] [--json probes.json] [--probe NAME ...]

Progress goes to stderr; the Markdown table on stdout is meant for $GITHUB_STEP_SUMMARY.
Exit status: 0 every pass/fail expectation held, 1 one did not,
2 bad arguments, no swift, or a malformed expectations.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PROBES = Path(__file__).resolve().parent / "probes" / "android"
EXPECTS = ("pass", "fail", "record")
KEYS = {"question", "expect", "error_contains", "twin", "source"}
DEFAULT_TIMEOUT = 900.0
MAX_EXCERPT = 240

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# A diagnostic with a source location, in either build system's format:
#   native:     /path/File.swift:2:8: error: no such module 'UIKit'
#   swiftbuild: error: /path/File.swift:2:8 unable to resolve module dependency: 'UIKit'
LOCATION = re.compile(r"[^\s/\\:]+\.(?:swift|h|c|modulemap):\d+:\d+")
DIRECTORIES = re.compile(r"(?:[A-Za-z]:)?(?:[/\\][^\s/\\:]+)+[/\\](?=[^\s/\\:]+:\d+:\d+)")


@dataclass(frozen=True)
class Expectation:
    probe: str
    question: str
    expect: str
    error_contains: str | None
    twin: str | None
    source: str


@dataclass
class Build:
    result: str  # pass | fail | error (timed out or could not run)
    errors: list[str]
    excerpt: str | None
    seconds: float


def load_expectations(root: Path = PROBES) -> dict[str, Expectation]:
    """Parse expectations.json; raises ValueError when it is missing or malformed."""
    path = root / "expectations.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{path} not found") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: {error}") from None
    if not isinstance(data, dict) or not data:
        raise ValueError(f"{path}: expected a non-empty object mapping probe names to expectations")
    expectations: dict[str, Expectation] = {}
    for name, entry in data.items():
        if not isinstance(entry, dict) or set(entry) != KEYS:
            raise ValueError(f"{name}: needs exactly the keys {', '.join(sorted(KEYS))}")
        for key in ("question", "expect", "source"):
            if not isinstance(entry[key], str) or not entry[key].strip():
                raise ValueError(f"{name}: {key} must be a non-empty string")
        for key in ("error_contains", "twin"):
            if entry[key] is not None and (not isinstance(entry[key], str) or not entry[key]):
                raise ValueError(f"{name}: {key} must be null or a non-empty string")
        expectations[name] = Expectation(
            name, entry["question"], entry["expect"], entry["error_contains"], entry["twin"], entry["source"]
        )
    return expectations


def problems(root: Path, expectations: dict[str, Expectation]) -> list[str]:
    """Disagreements between expectations.json and the probe directories, and within the file."""
    found: list[str] = []
    directories = {path.name for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")}
    for name in sorted(directories - set(expectations)):
        found.append(f"{name}: probe directory without an entry in expectations.json")
    for name, expectation in sorted(expectations.items()):
        if name not in directories:
            found.append(f"{name}: no probe directory")
        elif not (root / name / "Package.swift").is_file():
            found.append(f"{name}: no Package.swift")
        if expectation.expect not in EXPECTS:
            found.append(f"{name}: expect must be one of {', '.join(EXPECTS)}, not {expectation.expect!r}")
        if expectation.error_contains is not None and expectation.expect != "fail":
            found.append(f"{name}: error_contains only applies to expect: fail")
        if not re.fullmatch(r"https?://\S+", expectation.source):
            found.append(f"{name}: source must be a URL")
        if expectation.twin is not None:
            twin = expectations.get(expectation.twin)
            if expectation.twin == name:
                found.append(f"{name}: a probe cannot be its own twin")
            elif twin is None:
                found.append(f"{name}: twin {expectation.twin} is not a probe")
            elif twin.twin != name:
                found.append(f"{name}: twin {expectation.twin} does not name {name} back")
    return found


def swift_version(swift: str) -> str:
    try:
        result = subprocess.run([swift, "--version"], capture_output=True, text=True, errors="replace", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"unknown ({error})"
    lines = [line.strip() for line in (result.stdout + result.stderr).splitlines() if line.strip()]
    return next((line for line in lines if "Swift version" in line), lines[0] if lines else "unknown")


def error_lines(output: str) -> list[str]:
    lines = (ANSI.sub("", line).strip() for line in output.splitlines())
    return [line for line in lines if "error:" in line]


def located(errors: list[str]) -> list[str]:
    return [line for line in errors if LOCATION.search(line)]


def excerpt(errors: list[str], output: str) -> str:
    """The most useful error line, without directories, so runner paths stay out of reports."""
    candidates = located(errors) or errors
    if candidates:
        line = candidates[0]
    else:
        tail = [line.strip() for line in ANSI.sub("", output).splitlines() if line.strip()]
        line = tail[-1] if tail else "build failed without output"
    line = DIRECTORIES.sub("", line)
    home = os.path.expanduser("~")
    if len(home) > 1:
        line = line.replace(home, "~")
    return line if len(line) <= MAX_EXCERPT else line[: MAX_EXCERPT - 1] + "…"


def build(swift: str, directory: Path, swift_sdk: str, triple: str | None, scratch: Path, timeout: float) -> Build:
    command = [swift, "build", "--package-path", str(directory), "--swift-sdk", swift_sdk]
    if triple:
        command += ["--triple", triple]
    command += ["--scratch-path", str(scratch)]
    started = time.monotonic()
    try:
        result = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return Build("error", [], f"timed out after {timeout:g} s", time.monotonic() - started)
    except OSError as error:
        return Build("error", [], f"could not run {swift}: {error}", time.monotonic() - started)
    seconds = time.monotonic() - started
    output = f"{result.stdout}\n{result.stderr}"
    errors = error_lines(output)
    if result.returncode == 0:
        return Build("pass", errors, None, seconds)
    return Build("fail", errors, excerpt(errors, output), seconds)


def judge(expectation: Expectation, outcome: Build) -> tuple[str, str | None]:
    """(status, reason): status is ok, mismatch or recorded."""
    if expectation.expect == "record":
        return "recorded", None
    if outcome.result == "error":
        return "mismatch", outcome.excerpt
    if outcome.result != expectation.expect:
        return "mismatch", f"expected {expectation.expect}, got {outcome.result}"
    if expectation.expect == "fail" and expectation.error_contains:
        haystack = located(outcome.errors) or outcome.errors
        if not any(expectation.error_contains in line for line in haystack):
            return "mismatch", f"failed, but no compiler error contains {expectation.error_contains!r}"
    return "ok", None


def ndk_revision(env: Mapping[str, str] = os.environ) -> str | None:
    """The NDK the build would use: ANDROID_NDK_ROOT first, as Swift Build reads it, then ANDROID_NDK_HOME."""
    for variable in ("ANDROID_NDK_ROOT", "ANDROID_NDK_HOME"):
        value = env.get(variable)
        if not value:
            continue
        try:
            text = (Path(value) / "source.properties").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return f"unknown ({variable} has no source.properties)"
        fields = dict(
            (key.strip(), item.strip()) for key, _, item in (line.partition("=") for line in text.splitlines()) if item
        )
        revision, release = fields.get("Pkg.Revision"), fields.get("Pkg.ReleaseName")
        if revision and release:
            return f"{release} ({revision})"
        return revision or release or f"unknown ({variable})"
    return None


def run_url(env: Mapping[str, str] = os.environ) -> str | None:
    parts = [env.get(name) for name in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID")]
    return f"{parts[0]}/{parts[1]}/actions/runs/{parts[2]}" if all(parts) else None


def cell(text: str, code: bool = False) -> str:
    """Escape text for a table cell; inside a code span, backticks become quotes."""
    text = text.replace("\n", " ").replace("|", "\\|")
    return text.replace("`", "'") if code else text


def markdown(rows: list[dict], context: dict) -> str:
    lines = [
        "## Android compile probes",
        "",
        f"Swift `{cell(context['swift_version'], code=True)}`, SDK `{cell(context['swift_sdk'], code=True)}`, "
        f"triple `{cell(context['triple'] or 'SDK default', code=True)}`, "
        f"NDK `{cell(context['ndk'] or 'not found', code=True)}`.",
        "",
        "| Probe | Question | Expected | Result | Status | First error |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        status = "**mismatch**" if row["status"] == "mismatch" else row["status"]
        error = f"`{cell(row['error'], code=True)}`" if row["error"] else ""
        lines.append(
            f"| `{row['probe']}` | {cell(row['question'])} | {row['expected']} | {row['result']} | {status} | {error} |"
        )
    counts = {status: sum(row["status"] == status for row in rows) for status in ("ok", "recorded", "mismatch")}
    lines += [
        "",
        f"{len(rows)} probes: {counts['ok']} as the source says, {counts['recorded']} recorded, "
        f"{counts['mismatch']} mismatched.",
    ]
    for row in rows:
        if row["status"] == "mismatch":
            lines.append(f"- `{row['probe']}`: {cell(row['reason'] or 'mismatch')} (claim: {row['source']})")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--swift", default="swift", help="swift driver of the toolchain that matches the SDK")
    parser.add_argument("--swift-sdk", help="Swift SDK id for `swift build --swift-sdk`")
    parser.add_argument("--triple", help="explicit `--triple`, e.g. aarch64-unknown-linux-android28")
    parser.add_argument("--json", type=Path, help="write the results to this file")
    parser.add_argument("--probe", nargs="+", action="extend", metavar="NAME", help="build only these probes")
    parser.add_argument("--list", action="store_true", help="list the probes without building")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="seconds allowed per probe build")
    parser.add_argument("--root", type=Path, default=PROBES, help="probe directory (default: %(default)s)")
    args = parser.parse_args(argv)

    try:
        expectations = load_expectations(args.root)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    issues = problems(args.root, expectations)
    for issue in issues:
        print(f"error: {issue}", file=sys.stderr)
    if issues:
        return 2
    selected = list(expectations)
    if args.probe:
        unknown = sorted(set(args.probe) - set(expectations))
        if unknown:
            print(f"error: unknown probe: {', '.join(unknown)}", file=sys.stderr)
            return 2
        selected = [name for name in expectations if name in args.probe]

    if args.list:
        width = max(len(name) for name in selected)
        for name in selected:
            expectation = expectations[name]
            twin = f"  (twin: {expectation.twin})" if expectation.twin else ""
            print(f"{name:<{width}}  {expectation.expect:<6}  {expectation.question}{twin}")
        return 0
    if not args.swift_sdk:
        parser.error("--swift-sdk is required unless --list is given")
    if shutil.which(args.swift) is None:
        print(f"error: {args.swift} not found; pass the toolchain's driver with --swift", file=sys.stderr)
        return 2

    context = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "swift_version": swift_version(args.swift),
        "swift_sdk": args.swift_sdk,
        "triple": args.triple,
        "ndk": ndk_revision(),
        "run_url": run_url(),
    }
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="android-probes-") as scratch:
        for name in selected:
            expectation = expectations[name]
            print(f"building {name} ...", file=sys.stderr, flush=True)
            outcome = build(args.swift, args.root / name, args.swift_sdk, args.triple, Path(scratch) / name, args.timeout)
            status, reason = judge(expectation, outcome)
            detail = f": {reason}" if reason else ""
            print(f"  {outcome.result}, {status} ({outcome.seconds:.0f} s){detail}", file=sys.stderr, flush=True)
            rows.append({
                "probe": name,
                "question": expectation.question,
                "expected": expectation.expect,
                "result": outcome.result,
                "status": status,
                "reason": reason,
                "error": outcome.excerpt,
                "seconds": round(outcome.seconds, 1),
                "swift_version": context["swift_version"],
                "swift_sdk": args.swift_sdk,
                "triple": args.triple,
                "ndk": context["ndk"],
                "twin": expectation.twin,
                "source": expectation.source,
            })

    sys.stdout.write(markdown(rows, context))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({**context, "results": rows}, indent=2) + "\n", encoding="utf-8")
    return 1 if any(row["status"] == "mismatch" for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())

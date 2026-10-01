#!/usr/bin/env python3
"""Report which Swift and Android tools this machine has, and what it can verify.

Read-only: it runs only the version and list commands in ALLOWED, each with a short
timeout, and reads environment variables and NDK `source.properties` files.
It installs, downloads and changes nothing; `next_steps` describes what to do,
and nothing here runs it. The one side effect: `adb devices` starts the adb
server if it is not already running.

    python3 scripts/toolchain_report.py                  # Markdown, starting "# Toolchain report"
    python3 scripts/toolchain_report.py --format json

Verdicts:
    can_typecheck_apple     macOS with a working `xcodebuild`
    can_build_android       an open-source Swift toolchain, an installed Swift SDK for Android
                            built for exactly that toolchain, and an Android NDK
    can_run_android_tests   all of that, plus `adb` and a device or emulator in `adb devices`

Versions to install are in references/versions.md; this script names none.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

# The only commands this script may run. Anything else raises before a process starts.
ALLOWED: dict[str, tuple[tuple[str, ...], ...]] = {
    "swift": (("--version",), ("sdk", "list")),
    "xcodebuild": (("-version",),),
    "swiftly": (("--version",), ("list",)),
    "java": (("-version",),),
    "adb": (("version",), ("devices",)),
    "skip": (("version",),),
    "gradle": (("--version",),),
}
TIMEOUT = 20  # seconds per command
NDK_VARIABLES = ("ANDROID_NDK_HOME", "ANDROID_NDK_ROOT", "ANDROID_NDK_LATEST_HOME")
SDK_VARIABLES = ("ANDROID_HOME", "ANDROID_SDK_ROOT")
ARTICLE = "https://www.swift.org/documentation/articles/swift-sdk-for-android-getting-started.html"
NO_SDKS = "No Swift SDKs are currently installed."


@dataclass
class Output:
    command: str
    found: bool
    ok: bool
    text: str


Runner = Callable[..., subprocess.CompletedProcess]
Which = Callable[[str], "str | None"]


def run(tool: str, *arguments: str, runner: Runner | None = None, which: Which | None = None) -> Output:
    """Run one allowlisted command; a missing tool or a timeout is reported, not raised."""
    if arguments not in ALLOWED.get(tool, ()):
        raise ValueError(f"`{tool} {' '.join(arguments)}` is not on the read-only allowlist")
    runner = subprocess.run if runner is None else runner
    which = shutil.which if which is None else which
    command = " ".join((tool, *arguments))
    path = which(tool)
    if path is None:
        return Output(command, False, False, "")
    try:
        result = runner([path, *arguments], capture_output=True, text=True, errors="replace", timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return Output(command, True, False, f"timed out after {TIMEOUT} s")
    except OSError as error:
        return Output(command, True, False, str(error))
    text = f"{result.stdout or ''}\n{result.stderr or ''}".strip()
    return Output(command, True, result.returncode == 0, text)


def first_line(text: str, containing: str = "") -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    matching = [line for line in lines if containing in line]
    return (matching or lines or [None])[0]


def version_key(version: str) -> tuple[int, ...]:
    """6.4 and 6.4.0 compare equal."""
    numbers = [int(part) for part in version.split(".")]
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)


def parse_swift(text: str) -> dict:
    line = first_line(text, "Swift version")
    tag = re.search(r"\((swift-[^\s)]+)\)", line or "")
    version = re.search(r"Swift version (\d+(?:\.\d+)*)", line or "")
    if tag:
        kind = "open source"
    elif line and "swiftlang-" in line:
        kind = "Xcode"
    else:
        kind = "unknown"
    return {
        "version_line": line,
        "version": version.group(1) if version else None,
        "tag": tag.group(1) if tag else None,
        "kind": kind,
    }


def sdk_tag(sdk_id: str) -> str | None:
    """swift-6.4.0-RELEASE_android -> swift-6.4.0-RELEASE (older ids end in -android-<n>)."""
    match = re.match(r"^(swift-.+?)[_-]android(?:[_-].*)?$", sdk_id)
    return match.group(1) if match else None


def tag_version(tag: str | None) -> str | None:
    match = re.match(r"^swift-(\d+(?:\.\d+)*)-RELEASE$", tag or "")
    return match.group(1) if match else None


def matches_host(sdk_id: str, swift: dict) -> bool:
    tag = sdk_tag(sdk_id)
    if tag is None:
        return False
    if swift["tag"]:
        return tag == swift["tag"]
    version = tag_version(tag)
    return bool(version and swift["version"] and version_key(version) == version_key(swift["version"]))


def read_ndk(path: str) -> dict:
    """What an NDK's source.properties says, read-only."""
    info: dict = {"path": path, "exists": Path(path).is_dir(), "revision": None, "release": None}
    try:
        text = (Path(path) / "source.properties").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return info
    for line in text.splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "Pkg.Revision":
            info["revision"] = value.strip()
        elif key.strip() == "Pkg.ReleaseName":
            info["release"] = value.strip()
    return info


def describe_ndk(info: dict | None) -> str:
    if not info:
        return "not found"
    if not info["exists"]:
        return f"`{info['path']}` (missing)"
    label = ", ".join(part for part in (info["release"], info["revision"]) if part) or "no source.properties"
    return f"`{info['path']}` ({label})"


def find_ndk(env: Mapping[str, str]) -> tuple[dict | None, str | None]:
    """The NDK a build would use and where it came from.

    Swift Build, SwiftPM's default build system from Swift 6.4, reads ANDROID_NDK_ROOT
    before ANDROID_NDK_HOME and otherwise looks in $ANDROID_HOME/ndk; the SDK's own
    setup script reads ANDROID_NDK_HOME. Both should name the same NDK.
    """
    for variable in ("ANDROID_NDK_ROOT", "ANDROID_NDK_HOME"):
        if env.get(variable):
            return read_ndk(env[variable]), variable
    for variable in SDK_VARIABLES:
        base = Path(env[variable]) / "ndk" if env.get(variable) else None
        if base and base.is_dir():
            installed = [read_ndk(str(path)) for path in sorted(base.iterdir()) if path.is_dir()]
            installed = [info for info in installed if info["revision"]]
            if installed:
                newest = max(installed, key=lambda info: version_key(re.sub(r"[^\d.]", "", info["revision"]) or "0"))
                return newest, f"{variable}/ndk"
    return None, None


def parse_devices(text: str) -> list[dict]:
    devices = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and not line.startswith(("List of devices", "*")):
            devices.append({"serial": parts[0], "state": parts[1]})
    return devices


def collect(
    env: Mapping[str, str] | None = None,
    runner: Runner | None = None,
    which: Which | None = None,
    system: str | None = None,
) -> dict:
    env = os.environ if env is None else env
    system = system or platform.system()

    def call(tool: str, *arguments: str) -> Output:
        return run(tool, *arguments, runner=runner, which=which)

    swift_out = call("swift", "--version")
    swift = {"found": swift_out.found, **parse_swift(swift_out.text if swift_out.ok else "")}
    sdk_out = call("swift", "sdk", "list") if swift_out.ok else Output("swift sdk list", False, False, "")
    sdks = [
        line.strip()
        for line in sdk_out.text.splitlines()
        if sdk_out.ok and line.strip() and line.strip() != NO_SDKS and not line.lstrip().startswith(("warning:", "error:"))
    ]
    android_sdks = [sdk for sdk in sdks if "android" in sdk.lower()]
    matching = [sdk for sdk in android_sdks if matches_host(sdk, swift)]

    xcode_out = call("xcodebuild", "-version") if system == "Darwin" else Output("xcodebuild -version", False, False, "")
    swiftly_out = call("swiftly", "--version")
    swiftly_list = call("swiftly", "list") if swiftly_out.ok else Output("swiftly list", False, False, "")
    java_out = call("java", "-version")
    adb_out = call("adb", "version")
    devices_out = call("adb", "devices") if adb_out.ok else Output("adb devices", False, False, "")
    devices = parse_devices(devices_out.text) if devices_out.ok else []
    ready = [device for device in devices if device["state"] == "device"]
    skip_out = call("skip", "version")
    gradle_out = call("gradle", "--version")

    environment = {name: env.get(name) for name in (*NDK_VARIABLES, *SDK_VARIABLES)}
    ndk_by_variable = {name: read_ndk(env[name]) for name in NDK_VARIABLES if env.get(name)}
    ndk, ndk_source = find_ndk(env)
    ndk_ok = bool(ndk and ndk["exists"] and ndk["revision"])
    ndk_conflict = bool(
        env.get("ANDROID_NDK_ROOT")
        and env.get("ANDROID_NDK_HOME")
        and os.path.realpath(env["ANDROID_NDK_ROOT"]) != os.path.realpath(env["ANDROID_NDK_HOME"])
    )

    can_typecheck_apple = system == "Darwin" and xcode_out.ok
    can_build_android = swift["kind"] == "open source" and bool(matching) and ndk_ok
    can_run_android_tests = can_build_android and adb_out.ok and bool(ready)

    steps: list[str] = []
    if not swift_out.found:
        steps.append("Install a Swift toolchain with swiftly: https://www.swift.org/install/")
    elif not swift_out.ok:
        steps.append(f"`swift --version` failed ({first_line(swift_out.text) or 'no output'}); fix the toolchain on PATH.")
    elif swift["kind"] == "Xcode":
        steps.append(
            "Xcode's `swift` cannot use the Swift SDK for Android: install the open-source toolchain with swiftly, "
            "at the version in references/versions.md, and put it first on PATH."
        )
    elif swift["kind"] == "unknown":
        steps.append(
            "`swift --version` names no release tag, so the Swift SDK for Android cannot be matched to it; "
            "use a release toolchain from swiftly."
        )
    if swift["kind"] == "open source" and not android_sdks:
        steps.append(f"Install the Swift SDK for Android for `{swift['tag']}` with `swift sdk install` and its checksum: {ARTICLE}")
    elif swift["kind"] == "open source" and not matching:
        steps.append(
            f"No installed Android SDK ({', '.join(android_sdks)}) matches `{swift['tag']}`; the versions must match "
            "exactly, so install the matching SDK or switch toolchains with `swiftly use`."
        )
    if not ndk:
        steps.append(f"Download the Android NDK that the getting-started article names and set ANDROID_NDK_HOME to it: {ARTICLE}")
    elif not ndk_ok:
        steps.append(f"{ndk_source} points at {describe_ndk(ndk)}, which is not an NDK; point it at an unpacked NDK.")
    if ndk_conflict:
        steps.append(
            "ANDROID_NDK_ROOT and ANDROID_NDK_HOME name different NDKs; Swift Build reads ANDROID_NDK_ROOT first, "
            "so point both at the NDK you mean to use."
        )
    if not adb_out.found:
        steps.append("Install the Android SDK platform-tools to get `adb`, needed to run tests on a device or emulator.")
    elif adb_out.ok and not ready:
        waiting = ", ".join(f"{device['serial']} ({device['state']})" for device in devices)
        steps.append(
            "Start an emulator or connect a device with USB debugging, then check `adb devices`"
            + (f"; listed but not ready: {waiting}." if waiting else ".")
        )
    if not java_out.ok:
        steps.append("Install a JDK if you build the Kotlin side with Gradle or use swift-java (`java -version` failed).")
    if system == "Darwin" and not xcode_out.ok:
        steps.append("Install Xcode and select it with `xcode-select` to typecheck the Apple samples.")
    if not steps:
        steps.append("Nothing is missing for building and testing on Android here.")

    def version_of(output: Output, containing: str = "") -> str | None:
        return first_line(output.text, containing) if output.ok else None

    return {
        "system": system,
        "swift": swift,
        "swift_sdks": sdks,
        "android_sdks": android_sdks,
        "android_sdks_matching_host": matching,
        "xcode": xcode_version(xcode_out.text) if xcode_out.ok else None,
        "swiftly": version_of(swiftly_out),
        "swiftly_toolchains": output_lines(swiftly_list) if swiftly_list.ok else [],
        "environment": environment,
        "ndk_by_variable": ndk_by_variable,
        "ndk": ndk,
        "ndk_source": ndk_source,
        "java": first_line(java_out.text) if java_out.ok else None,
        "adb": version_of(adb_out, "Android Debug Bridge"),
        "devices": devices,
        "skip": version_of(skip_out),
        "gradle": version_of(gradle_out, "Gradle"),
        "can_typecheck_apple": can_typecheck_apple,
        "can_build_android": can_build_android,
        "can_run_android_tests": can_run_android_tests,
        "next_steps": steps,
    }


def xcode_version(text: str) -> str | None:
    """'Xcode 27.1' and 'Build version 27A9269' become 'Xcode 27.1 (27A9269)'."""
    name = first_line(text, "Xcode")
    build = re.search(r"Build version (\S+)", text)
    return f"{name} ({build.group(1)})" if name and build else name


def output_lines(output: Output) -> list[str]:
    return [line.strip() for line in output.text.splitlines() if line.strip()]


def markdown(report: dict) -> str:
    def code(value: str | None) -> str:
        return f"`{value}`" if value else "not found"

    def escape(value: str) -> str:
        return value.replace("|", "\\|")

    swift = report["swift"]
    swift_cell = code(swift["version_line"])
    if swift["version_line"]:
        swift_cell += f" ({swift['kind']} toolchain)"
    environment = report["environment"]
    rows = [
        ("Swift", swift_cell),
        ("Swift SDKs", ", ".join(code(sdk) for sdk in report["swift_sdks"]) or "none"),
        ("Android SDK matching the toolchain", ", ".join(code(sdk) for sdk in report["android_sdks_matching_host"]) or "none"),
        ("Xcode", report["xcode"] or ("not found" if report["system"] == "Darwin" else "not on macOS")),
        ("swiftly", report["swiftly"] or "not found"),
        ("swiftly toolchains", ", ".join(code(line) for line in report["swiftly_toolchains"]) or "none"),
        ("NDK a build would use", describe_ndk(report["ndk"]) + (f" via {report['ndk_source']}" if report["ndk_source"] else "")),
    ]
    for name, value in environment.items():
        detail = report["ndk_by_variable"].get(name)
        rows.append((name, describe_ndk(detail) if detail else (code(value) if value else "not set")))
    devices = ", ".join(f"{device['serial']} ({device['state']})" for device in report["devices"])
    rows += [
        ("Java", code(report["java"])),
        ("adb", code(report["adb"])),
        ("Devices and emulators", devices or "none"),
        ("Skip", code(report["skip"])),
        ("Gradle", code(report["gradle"])),
    ]
    lines = ["# Toolchain report", "", "| Check | Found |", "| --- | --- |"]
    lines += [f"| {name} | {escape(value)} |" for name, value in rows]
    lines += ["", "## Verdict", "", "| This machine can | |", "| --- | --- |"]
    for label, key in (
        ("Typecheck the Apple samples", "can_typecheck_apple"),
        ("Build for Android", "can_build_android"),
        ("Run tests on an Android device or emulator", "can_run_android_tests"),
    ):
        lines.append(f"| {label} | {'yes' if report[key] else 'no'} |")
    lines += ["", "## Next steps", ""]
    lines += [f"{number}. {step}" for number, step in enumerate(report["next_steps"], start=1)]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)
    report = collect()
    sys.stdout.write(json.dumps(report, indent=2) + "\n" if args.format == "json" else markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())

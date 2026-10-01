#!/usr/bin/env python3
"""Typecheck every tagged code block in the skills and references.

Every ```swift and ```kotlin block starts with a tag on its first line:

    // typecheck: shared             pure Swift that must build for Apple platforms *and* Android.
                                     Typechecked here for macOS; compiled for Android with --android.
    // typecheck: ios<N>             Apple-only Swift; must compile for iOS N and, above IOS_FLOOR,
                                     fail for the iOS release before N (18 before 26), which checks
                                     the availability claim.
    // typecheck: none — <reason>    cannot be checked by this repository (Kotlin, SkipFuse, JNI glue…);
                                     the reason says why, so the gap stays visible.

`, continues the block above` after `shared` or `ios<N>` compiles the block
together with the one before it; an `ios<N>` block may continue a `shared` one
(shared code plus the iOS side compiles for iOS), never the other way round.
```json blocks must parse.
A macOS typecheck proves only that the Swift is well formed on Apple platforms:
Objective-C interop, a single Foundation module and Combine all exist there.
What holds on Android is decided by the --android run in CI.

    python3 scripts/typecheck_samples.py                 # macOS and iOS checks
    python3 scripts/typecheck_samples.py --list          # what would be checked
    python3 scripts/typecheck_samples.py --android \\
        --swift "$SWIFT" --swift-sdk "$SDK" [--triple aarch64-unknown-linux-android28]
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCK = re.compile(r"^```(swift|kotlin|json)\n(.*?)^```", re.S | re.M)
TAG = re.compile(
    r"^// typecheck: (?:(?P<shared>shared)|ios(?P<ios>\d+)|none — (?P<reason>.+?))"
    r"(?P<continues>, continues the block above)?\s*$"
)
# The oldest iOS a sample may target: @Observable and the Observation framework need 17.
IOS_FLOOR = 17
# Highest iOS a sample may target while CI's macos-latest runs Xcode 26.x (checked 2026-10-01).
CI_IOS_CEILING = 26
MACOS_TARGET = 14
MIN_REASON = 8
# iOS went from 18 straight to 26; the compiler treats 19–25 as 26, so "one below 26" is 18.
SKIPPED_IOS = range(19, 26)


def previous_ios(version: int) -> int:
    below = version - 1
    while below in SKIPPED_IOS:
        below -= 1
    return below


@dataclass
class Block:
    source: Path
    index: int
    language: str
    kind: str  # shared | ios | none | json
    ios: int | None
    reason: str | None
    code: str
    line: int


def tagged_blocks(paths: list[Path]) -> tuple[list[Block], list[str]]:
    """All checkable blocks, plus problems (untagged or malformed blocks)."""
    found: list[Block] = []
    problems: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        previous: str | None = None
        previous_kind: str | None = None
        for index, match in enumerate(BLOCK.finditer(text), start=1):
            language, code = match.group(1), match.group(2)
            line = text.count("\n", 0, match.start()) + 1
            label = f"{display(path)}:{line}"
            if language == "json":
                found.append(Block(path, index, language, "json", None, None, code, line))
                previous = None
                continue
            first, _, body = code.partition("\n")
            if first.startswith("// swift-tools-version"):
                # A manifest keeps its tools-version line first; the tag goes on the line after it.
                second, _, rest = body.partition("\n")
                first, body = second, first + "\n" + rest
            tag = TAG.match(first)
            if not tag:
                problems.append(f"{label}: {language} block without a `// typecheck:` tag")
                previous = None
                continue
            if tag.group("reason") is not None:
                reason = tag.group("reason").strip()
                if len(reason) < MIN_REASON:
                    problems.append(f"{label}: `none` needs a reason of at least {MIN_REASON} characters")
                found.append(Block(path, index, language, "none", None, reason, body, line))
                previous = None
                continue
            if language != "swift":
                problems.append(f"{label}: only Swift can be typechecked here; tag {language} blocks `none — <reason>`")
                previous = None
                continue
            kind = "shared" if tag.group("shared") else "ios"
            ios = int(tag.group("ios")) if tag.group("ios") else None
            if tag.group("continues"):
                # Platform code may build on a shared block (shared + iOS compiles for iOS);
                # shared code may not build on iOS-only code.
                allowed = {"shared": {"shared"}, "ios": {"shared", "ios"}}[kind]
                if previous is None or previous_kind not in allowed:
                    problems.append(f"{label}: `{kind}` cannot continue a `{previous_kind or 'untagged'}` block")
                    previous = None
                    continue
                body = previous + "\n" + body
            found.append(Block(path, index, language, kind, ios, None, body, line))
            previous, previous_kind = body, kind
    return found, problems


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def documents(root: Path = ROOT) -> list[Path]:
    """Root references, skill-only references and every SKILL.md (synced copies are checked once, at the root)."""
    shared = {path.name for path in (root / "references").glob("*.md")}
    paths = sorted((root / "references").glob("*.md"))
    for skill in sorted((root / "skills").iterdir()):
        if not skill.is_dir():
            continue
        paths.append(skill / "SKILL.md")
        paths.extend(path for path in sorted((skill / "references").glob("*.md")) if path.name not in shared)
    return [path for path in paths if path.is_file()]


def host_arch() -> str:
    return "arm64" if platform.machine() in ("arm64", "aarch64") else "x86_64"


def typecheck_apple(code: str, sdk: str, target: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as directory:
        file = Path(directory) / "Sample.swift"
        file.write_text(code, encoding="utf-8")
        return subprocess.run(
            ["xcrun", "--sdk", sdk, "swiftc", "-typecheck", "-swift-version", "6", "-target", target, str(file)],
            capture_output=True,
            text=True,
        )


def check_apple(blocks: list[Block]) -> int:
    if shutil.which("xcrun") is None:
        print("xcrun not found: the macOS and iOS checks need Xcode", file=sys.stderr)
        return 3
    failures = 0
    for block in blocks:
        label = f"{display(block.source)}:{block.line}"
        if block.kind == "shared":
            result = typecheck_apple(block.code, "macosx", f"{host_arch()}-apple-macos{MACOS_TARGET}")
            if result.returncode != 0:
                failures += 1
                print(f"FAIL {label}: shared block does not typecheck for macOS {MACOS_TARGET}\n{result.stderr}")
                continue
            print(f"ok   {label}: shared (macOS {MACOS_TARGET}; Android is checked with --android)")
        elif block.kind == "ios":
            ios = block.ios or 0
            target = f"{host_arch()}-apple-ios{ios}.0-simulator"
            result = typecheck_apple(block.code, "iphonesimulator", target)
            if result.returncode != 0:
                failures += 1
                print(f"FAIL {label}: does not compile for iOS {ios}\n{result.stderr}")
                continue
            if ios > IOS_FLOOR:
                lower = previous_ios(ios)
                below = typecheck_apple(block.code, "iphonesimulator", f"{host_arch()}-apple-ios{lower}.0-simulator")
                if below.returncode == 0:
                    failures += 1
                    print(f"FAIL {label}: also compiles for iOS {lower}; lower its tag")
                    continue
            print(f"ok   {label}: iOS {ios}")
    return 1 if failures else 0


ANDROID_PACKAGE = """// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Samples",
    platforms: [.macOS(.v14), .iOS(.v17)],
    targets: [
{targets}
    ]
)
"""


def write_android_package(blocks: list[Block], directory: Path) -> dict[str, Block]:
    targets: dict[str, Block] = {}
    for number, block in enumerate(blocks, start=1):
        name = f"Sample{number:03d}"
        source = directory / "Sources" / name
        source.mkdir(parents=True)
        (source / f"{name}.swift").write_text(block.code, encoding="utf-8")
        targets[name] = block
    lines = ",\n".join(f'        .target(name: "{name}")' for name in targets)
    (directory / "Package.swift").write_text(ANDROID_PACKAGE.replace("{targets}", lines), encoding="utf-8")
    return targets


def check_android(blocks: list[Block], swift: str, swift_sdk: str, triple: str | None, keep: Path | None) -> int:
    shared = [block for block in blocks if block.kind == "shared"]
    if not shared:
        print("no shared blocks to compile for Android")
        return 0
    directory = Path(tempfile.mkdtemp(prefix="android-samples-")) if keep is None else keep
    if keep is not None:
        if keep.exists():
            shutil.rmtree(keep)
        keep.mkdir(parents=True)
    targets = write_android_package(shared, directory)
    command = [swift, "build", "--package-path", str(directory), "--swift-sdk", swift_sdk]
    if triple:
        command += ["--triple", triple]
    failures = 0
    for name, block in targets.items():
        label = f"{display(block.source)}:{block.line}"
        result = subprocess.run(command + ["--target", name], capture_output=True, text=True)
        if result.returncode != 0:
            failures += 1
            print(f"FAIL {label}: shared block does not compile for Android ({swift_sdk})\n{result.stdout}{result.stderr}")
            continue
        print(f"ok   {label}: Android ({swift_sdk}{', ' + triple if triple else ''})")
    if keep is None:
        shutil.rmtree(directory, ignore_errors=True)
    return 1 if failures else 0


def check_json(blocks: list[Block]) -> int:
    failures = 0
    for block in blocks:
        if block.kind != "json":
            continue
        try:
            json.loads(block.code)
        except json.JSONDecodeError as error:
            failures += 1
            print(f"FAIL {display(block.source)}:{block.line}: JSON does not parse: {error}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help="Markdown files; defaults to every reference and SKILL.md")
    parser.add_argument("--list", action="store_true", help="List the tagged blocks without compiling")
    parser.add_argument("--android", action="store_true", help="Compile the shared blocks for Android instead")
    parser.add_argument("--swift", default="swift", help="swift driver of the toolchain that matches the SDK")
    parser.add_argument("--swift-sdk", help="Swift SDK id or target triple accepted by `swift build --swift-sdk`")
    parser.add_argument("--triple", help="Explicit `--triple`, e.g. aarch64-unknown-linux-android28")
    parser.add_argument("--keep", type=Path, help="Keep the generated Android package here")
    args = parser.parse_args(argv)

    blocks, problems = tagged_blocks(args.files or documents())
    for problem in problems:
        print(f"FAIL {problem}")
    if args.list:
        for block in blocks:
            detail = {"shared": "shared", "ios": f"iOS {block.ios}", "none": f"none — {block.reason}", "json": "json"}
            print(f"{display(block.source)}:{block.line}: {block.language} {detail[block.kind]}")
        return 1 if problems else 0
    status = 1 if problems else 0
    status = max(status, check_json(blocks))
    if args.android:
        if not args.swift_sdk:
            parser.error("--android needs --swift-sdk")
        return max(status, check_android(blocks, args.swift, args.swift_sdk, args.triple, args.keep))
    return max(status, check_apple([block for block in blocks if block.kind in ("shared", "ios")]))


if __name__ == "__main__":
    sys.exit(main())

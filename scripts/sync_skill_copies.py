#!/usr/bin/env python3
"""Copy canonical references and scripts into each skill that uses them.

Each skill must work when installed alone, so shared files live in two places:
the canonical copy at the repository root and a copy inside every skill that
needs it. Edit the root copy, then run this script. `--check` fails when a copy
has drifted, which is what CI runs.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALL_SKILLS = [
    "swift-android-architecture",
    "swift-android-sdk",
]

COPIES: dict[str, list[str]] = {
    "references/sources.md": ALL_SKILLS,
    "references/recommendation-format.md": ALL_SKILLS,
    "references/official-skip-skills.md": ALL_SKILLS,
    "references/versions.md": ALL_SKILLS,
    "references/bridge-surface.md": ALL_SKILLS,
    "references/ci.md": ALL_SKILLS,
    "references/measured-behavior.md": ALL_SKILLS,
    "scripts/android_scan.py": ALL_SKILLS,
    "scripts/toolchain_report.py": ALL_SKILLS,
}


def planned() -> list[tuple[Path, Path]]:
    pairs = []
    for relative, skills in COPIES.items():
        for skill in skills:
            pairs.append((ROOT / relative, ROOT / "skills" / skill / relative))
    return pairs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="Report drift without writing")
    args = parser.parse_args(argv)

    drifted = []
    missing = []
    for source, destination in planned():
        if not source.exists():
            missing.append(source.relative_to(ROOT))
            continue
        if destination.exists() and filecmp.cmp(source, destination, shallow=False):
            continue
        drifted.append(destination.relative_to(ROOT))
        if not args.check:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    for path in sorted(set(missing)):
        print(f"missing canonical file: {path}")
    if args.check:
        for path in drifted:
            print(f"out of sync: {path}")
        if drifted or missing:
            print("run: python3 scripts/sync_skill_copies.py")
            return 1
        print("all skill copies in sync")
        return 0
    print(f"updated {len(drifted)} file(s)")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())

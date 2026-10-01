#!/usr/bin/env python3
"""Build one installable `.skill` archive per skill for a GitHub release.

A `.skill` file is a zip of the skill folder, the format skill-creator's
package_skill.py produces. Evals and their fixture projects are left out: they
exist to benchmark the skill, not to run it.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {"__pycache__", ".DS_Store"}


def package(skill: Path, output: Path) -> Path:
    archive = output / f"{skill.name}.skill"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(skill.rglob("*")):
            relative = path.relative_to(skill.parent)
            if path.is_dir() or EXCLUDED_PARTS & set(relative.parts) or path.suffix == ".pyc":
                continue
            if len(relative.parts) > 1 and relative.parts[1] == "evals":
                continue
            bundle.write(path, relative)
    return archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", default=str(ROOT / "dist"), help="Directory for the archives")
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for skill in sorted((ROOT / "skills").iterdir()):
        if (skill / "SKILL.md").is_file():
            print(package(skill, output))
    return 0


if __name__ == "__main__":
    sys.exit(main())

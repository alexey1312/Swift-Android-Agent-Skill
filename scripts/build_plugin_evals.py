#!/usr/bin/env python3
"""Stage the plugin with its skill-creator evals as a `claude plugin eval` suite.

`skills/*/evals/evals.json` stays the single source of the cases. This script
writes a copy of the plugin *without* any `evals/` directory — the expectations
are the answer key, and an agent that can read its skill's directory must not
find them there — and puts the generated suite next to it:

    <out>/.claude-plugin/plugin.json   generated: lists exactly the staged skills
    <out>/skills/<skill>/              copied, minus evals/
    <out>/evals/<skill>--<case>/
        case.yaml                      prompt, tools, graders (JSON, which is YAML)
        scaffold.sh                    copies the fixture into the run's workspace
        fixture/<Project>/             from skills/<skill>/evals/files/

Plan-only cases get read-only tools plus Bash and are graded on the final
message; cases that ask for an edit also get Edit and Write and are graded on
the file, final message or trace each expectation is about (EDIT_FOCUS), plus
regex checks on the files they should leave behind.
Every case carries a low-weight check that the trace never touches an answer
key. Run it outside the repository so nothing above the stage leads back to
the expectations.

Users of these skills normally have Skip's official skills installed too, so the
benchmark compares two stages that both carry them — Skip's skills alone, and
Skip's skills plus these — each run with `--ablation none`:

    skip=~/.claude/plugins/cache/skiptools-skills
    python3 scripts/build_plugin_evals.py "$TMPDIR/sa-skip-only" --without-own-skills \\
        --extra-skills "$skip"/skip-app-design/*/skills --extra-skills "$skip"/skip-testing-deployment/*/skills
    python3 scripts/build_plugin_evals.py "$TMPDIR/sa-skip-plus-ours" \\
        --extra-skills "$skip"/skip-app-design/*/skills --extra-skills "$skip"/skip-testing-deployment/*/skills
    claude plugin eval "$TMPDIR/sa-skip-plus-ours" --ablation none --trust-plugin --scaffold \\
        --allow-tools Bash Edit Write --model "$AGENT_MODEL" --judge-model "$JUDGE_MODEL" \\
        --no-publish --max-cost-usd 14
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "swift-android-"
SCHEMA_VERSION = "1.1"
EDIT_MARKERS = ("Fix it", "fix it", "Clean up", "apply what's safe", "Just do it", "Go ahead")
READ_TOOLS = ["Read", "Glob", "Grep", "Skill", "Bash"]
EDIT_TOOLS = READ_TOOLS + ["Edit", "Write"]
# Plan-only cases cannot modify anything (no Edit or Write), so this expectation
# would be a constant pass that only dilutes the score.
STRUCTURAL = "No file in the project copy was modified."
ANSWER_KEY = r"graders/|case\.yaml|evals\.json"

# What the judge reads for each expectation of an edit case: the final message, the whole
# trace (only for "did it run a check"), or the file the expectation is about. Reading
# a file instead of the trace keeps the skill text the agent loaded out of the judge's view.
LAST, TRACE = "last_message", "trace"


def file_focus(path: str) -> dict:
    return {"source": "file", "path": path}


EDIT_FOCUS: dict[str, list] = {
    "make-shared-target-android-ready": [
        file_focus("Notes/Sources/NotesShared/NoteListViewModel.swift"),
        file_focus("Notes/Sources/NotesShared/NoteListViewModel.swift"),
        file_focus("Notes/Sources/NotesShared/NoteListViewModel.swift"),
        LAST,
        TRACE,
    ],
    "dlopen-observation-crash": [
        file_focus("WeatherCore/android/app/build.gradle.kts"),
        LAST,
        LAST,
        LAST,
    ],
}

JUDGE_PREAMBLE = (
    "Grade this one criterion. Judge the substance, not the wording: examples, sources and "
    "figures in parentheses show what counts and need not appear word for word, unless the "
    "criterion says the work must cite or state them. A criterion that says the work does not "
    "do something passes when the work does not do it. A hedged or partial version of the "
    "criterion's core claim fails.\n\nCriterion: "
)

# End-state checks for the cases that ask for an edit: (file in the workspace, pattern, match).
FILE_CHECKS: dict[str, list[tuple[str, str, str]]] = {
    "make-shared-target-android-ready": [
        # The shared view model is Observation-based and imports no Apple UI framework or Combine.
        ("Notes/Sources/NotesShared/NoteListViewModel.swift", r"@Observable", "contains"),
        ("Notes/Sources/NotesShared/NoteListViewModel.swift",
         r"import\s+(?:SwiftUI|UIKit|Combine)\b", "not_contains"),
        # Calls through the singleton are gone; a default argument that names it is still injection.
        ("Notes/Sources/NotesShared/NoteListViewModel.swift", r"Analytics\.shared\.track", "not_contains"),
    ],
    "dlopen-observation-crash": [
        # The Swift runtime reaches the APK: linked statically, or its libraries copied next to the app's.
        ("WeatherCore/android/app/build.gradle.kts",
         r"static-swift-stdlib|static-stdlib|libswiftCore|libswiftObservation|swift-resources|\*\.so", "contains"),
        ("WeatherCore/android/app/build.gradle.kts", r"libc\+\+_shared", "contains"),
    ],
}

SCAFFOLD = """#!/bin/bash
# Runs in the eval's empty workspace; copies this case's fixture into it.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -R "$here/fixture/." .
"""


def load_cases(root: Path = ROOT) -> list[dict]:
    cases = []
    for path in sorted(root.glob("skills/*/evals/evals.json")):
        skill = path.parts[-3]
        for item in json.loads(path.read_text(encoding="utf-8"))["evals"]:
            cases.append({**item, "skill": skill})
    return cases


def is_edit(case: dict) -> bool:
    return any(marker in case["prompt"] for marker in EDIT_MARKERS)


def case_id(case: dict) -> str:
    return f"{case['skill'].removeprefix(PREFIX)}--{case['name']}"


def case_definition(case: dict) -> dict:
    edit = is_edit(case)
    graders = []
    focus = EDIT_FOCUS.get(case["name"]) if edit else None
    if edit and (focus is None or len(focus) != len(case["expectations"])):
        raise ValueError(f"{case['name']}: give every expectation of an edit case a focus in EDIT_FOCUS")
    for index, expectation in enumerate(case["expectations"], start=1):
        if not edit and expectation == STRUCTURAL:
            continue
        graders.append({
            "type": "llm",
            "name": f"e{index:02d}",
            "criteria": JUDGE_PREAMBLE + expectation,
            "focus": focus[index - 1] if focus else LAST,
        })
    for number, (file, pattern, match) in enumerate(FILE_CHECKS.get(case["name"], []), start=1):
        graders.append({"type": "regex", "name": f"file{number:02d}", "target": {"source": "file", "path": file},
                        "pattern": pattern, "match": match})
    graders.append({"type": "regex", "name": "no-answer-key", "target": "trace", "pattern": ANSWER_KEY,
                    "match": "not_contains", "weight": 0.01})
    definition = {
        "schema_version": SCHEMA_VERSION,
        "name": case_id(case),
        "description": case["expected_output"],
        "tags": [case["skill"].removeprefix(PREFIX), "edit" if edit else "plan"],
        "execution": {
            "prompt": case["prompt"].replace("evals/files/", "./"),
            "max_turns": 40 if edit else 30,
            "timeout_seconds": 900,
            "allowed_tools": EDIT_TOOLS if edit else READ_TOOLS,
        },
        "graders": graders,
    }
    if case["files"]:
        definition["context"] = {"scaffold_script": "scaffold.sh"}
    return definition


def skill_directories(directory: Path) -> list[Path]:
    """Skill folders (holding a SKILL.md) directly under `directory`, or `directory` itself."""
    if (directory / "SKILL.md").is_file():
        return [directory]
    return sorted(path for path in directory.iterdir() if (path / "SKILL.md").is_file())


def stage_plugin(out: Path, root: Path = ROOT, extra: list[Path] | None = None, own: bool = True) -> list[str]:
    skills_out = out / "skills"
    skills_out.mkdir(parents=True)
    ignore = shutil.ignore_patterns("evals", "__pycache__", ".DS_Store")
    staged: list[str] = []
    if own:
        for skill in sorted((root / "skills").iterdir()):
            if (skill / "SKILL.md").is_file():
                shutil.copytree(skill, skills_out / skill.name, ignore=ignore)
                staged.append(skill.name)
    for directory in extra or []:
        for skill in skill_directories(directory):
            if skill.name in staged:
                raise ValueError(f"two staged skills are named {skill.name}")
            shutil.copytree(skill, skills_out / skill.name, ignore=ignore)
            staged.append(skill.name)
        for licence in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
            for candidate in (directory / licence, directory.parent / licence, directory.parent.parent / licence):
                if candidate.is_file():
                    shutil.copy2(candidate, out / f"LICENSE-{directory.parent.name}")
                    break
    if not staged:
        raise ValueError("nothing to stage: no own skills and no --extra-skills")
    plugin = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    manifest = {
        "name": plugin["name"] if own else "skip-official-skills-only",
        "version": plugin["version"],
        "description": "Staged for claude plugin eval; not for distribution.",
        "skills": [f"./skills/{name}" for name in staged],
    }
    (out / ".claude-plugin").mkdir()
    (out / ".claude-plugin" / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(root / "LICENSE", out / "LICENSE")
    return staged


def build(out: Path, root: Path = ROOT, only: list[str] | None = None,
          extra: list[Path] | None = None, own: bool = True) -> list[str]:
    if out.exists():
        shutil.rmtree(out)
    stage_plugin(out, root, extra, own)
    cases = load_cases(root)
    if only:
        wanted = set(only)
        unknown = wanted - {case["name"] for case in cases} - {case_id(case) for case in cases}
        if unknown:
            raise ValueError(f"unknown case(s): {', '.join(sorted(unknown))}")
        cases = [case for case in cases if case["name"] in wanted or case_id(case) in wanted]
    written = []
    for case in cases:
        directory = out / "evals" / case_id(case)
        directory.mkdir(parents=True)
        (directory / "case.yaml").write_text(json.dumps(case_definition(case), indent=2) + "\n", encoding="utf-8")
        if case["files"]:
            (directory / "scaffold.sh").write_text(SCAFFOLD, encoding="utf-8")
            for relative in case["files"]:
                source = root / "skills" / case["skill"] / relative
                destination = directory / "fixture" / source.name
                if source.is_dir():
                    shutil.copytree(source, destination)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
        written.append(case_id(case))
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path, help="stage directory, outside the repository")
    parser.add_argument("--only", action="append", default=[],
                        help="stage only these cases (name or <skill>--<name>); repeatable or comma-separated")
    parser.add_argument("--extra-skills", action="append", type=Path, default=[],
                        help="also stage the skill folders under this directory (e.g. an installed plugin's skills/)")
    parser.add_argument("--without-own-skills", action="store_true",
                        help="stage only the --extra-skills, still with this repository's cases")
    args = parser.parse_args(argv)
    out = args.out.resolve()
    if out == ROOT or ROOT in out.parents:
        print("build_plugin_evals: stage outside the repository, or the answer key is reachable from it",
              file=sys.stderr)
        return 2
    only = [name.strip() for item in args.only for name in item.split(",") if name.strip()]
    try:
        cases = build(out, only=only or None, extra=[path.expanduser() for path in args.extra_skills],
                      own=not args.without_own_skills)
    except ValueError as error:
        print(f"build_plugin_evals: {error}", file=sys.stderr)
        return 2
    print(f"staged {len(cases)} cases in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

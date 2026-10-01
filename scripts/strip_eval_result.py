#!/usr/bin/env python3
"""Reduce a `claude plugin eval --json` result to what a benchmark commit may hold.

Kept: scores, pass/fail and judge votes per criterion, turns, cost and duration per run,
the suite's ablation, threshold and concurrency, and each criterion's text.
Dropped: transcripts and grader evidence (they quote the agent and the skill),
trace paths and the stage root (local paths), the prompt, and the agent and judge
model ids (pushed files name models only through $AGENT_MODEL and $JUDGE_MODEL).

    python3 scripts/strip_eval_result.py "$TMPDIR/stage.json" benchmarks/<date>/<stage>.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RUN_KEYS = ("score", "passed", "turns", "costUsd", "judgeCostUsd", "durationSeconds", "error")
GRADER_KEYS = ("name", "passed", "weight", "judgeVotes")
SUITE_KEYS = ("ablation", "threshold", "concurrency")
TOP_KEYS = ("schemaVersion", "claudeVersion", "startedAt", "durationSeconds", "costUsd", "partial", "aggregates")
LOCAL_PATH = re.compile(r"(?:/Users|/home|/private|/var/folders|/tmp)/[^\s\"']*")
MODEL_ID = re.compile(r"claude-(?:opus|sonnet|haiku|fable)[\w.-]*", re.I)


def scrub(value):
    """Replace local paths and model ids inside any string the result keeps."""
    if isinstance(value, str):
        return MODEL_ID.sub("<model>", LOCAL_PATH.sub("<path>", value))
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items()}
    return value


def strip_grader(grader: dict) -> dict:
    return {key: grader[key] for key in GRADER_KEYS if key in grader}


def strip_run(run: dict) -> dict:
    kept = {key: run[key] for key in RUN_KEYS if key in run}
    kept["graders"] = [strip_grader(grader) for grader in run.get("graders", [])]
    return kept


def strip_case(case: dict) -> dict:
    criteria = []
    for grader in case.get("graders", []):
        item = {key: grader[key] for key in ("name", "type", "weight") if key in grader}
        if "criteria" in grader:
            item["criteria"] = grader["criteria"].split("Criterion: ", 1)[-1]
        if "pattern" in grader:
            item["pattern"] = grader["pattern"]
            item["match"] = grader.get("match")
        criteria.append(item)
    return {
        "name": case["name"],
        "aggregates": case.get("aggregates", {}),
        "graders": criteria,
        "arms": {arm: [strip_run(run) for run in runs] for arm, runs in case.get("arms", {}).items()},
    }


def strip(result: dict) -> dict:
    stripped = {key: result[key] for key in TOP_KEYS if key in result}
    suite = result.get("suite", {})
    stripped["suite"] = {key: suite[key] for key in SUITE_KEYS if key in suite}
    stripped["suite"]["plugins"] = [
        {key: plugin[key] for key in ("name", "version") if key in plugin} for plugin in suite.get("plugins", [])
    ]
    stripped["cases"] = [strip_case(case) for case in result.get("cases", [])]
    return scrub(stripped)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="the runner's --json output")
    parser.add_argument("destination", type=Path, help="where to write the stripped result")
    args = parser.parse_args(argv)
    result = json.loads(args.source.read_text(encoding="utf-8"))
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(json.dumps(strip(result), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

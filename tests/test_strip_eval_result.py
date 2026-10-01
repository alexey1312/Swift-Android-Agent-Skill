"""Tests for scripts/strip_eval_result.py."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import strip_eval_result as stripper  # noqa: E402

# Built from pieces so this file itself never holds a local path or a model id
# (test_repository's publication test scans every tracked file).
HOME = "/" + "Users/someone"
AGENT = "claude-" + "opus-5-5"
JUDGE = "claude-" + "sonnet-5-5"

RESULT = {
    "schemaVersion": 1,
    "claudeVersion": "2.1.285",
    "startedAt": "2026-10-01T17:34:38.269Z",
    "durationSeconds": 204,
    "costUsd": 1.85,
    "partial": False,
    "suite": {
        "root": "/private/var/folders/xy/T/stage",
        "ablation": "none",
        "modelOverride": AGENT,
        "judgeModel": JUDGE,
        "threshold": 0,
        "concurrency": 4,
        "plugins": [{"name": "swift-android-skills", "version": "1.0.0", "path": HOME + "/stage"}],
    },
    "cases": [
        {
            "name": "architecture--route",
            "promptMarkdown": "Look at ./TripNotes",
            "graders": [
                {"type": "llm", "name": "e01", "criteria": "Grade this one criterion.\n\nCriterion: Recommends X.",
                 "focus": "last_message"},
                {"type": "regex", "name": "file01", "pattern": "@Observable", "match": "contains"},
            ],
            "arms": {
                "with": [
                    {
                        "score": 0.5, "passed": False, "turns": 5, "costUsd": 0.3, "judgeCostUsd": 0.06,
                        "durationSeconds": 57, "error": None, "tracePath": "/private/tmp/e-1/out/trace.jsonl",
                        "graders": [
                            {"name": "e01", "passed": True, "weight": 1, "judgeVotes": ["PASS", "PASS", "PASS"],
                             "evidence": f"The agent wrote to {HOME}/project and used {AGENT}"},
                        ],
                    }
                ]
            },
            "aggregates": {"score": 0.5, "passRate": 0},
        }
    ],
    "aggregates": {"casesTotal": 1, "overallScore": 0.5},
}


class StripTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stripped = stripper.strip(json.loads(json.dumps(RESULT)))
        self.text = json.dumps(self.stripped)

    def test_no_paths_model_ids_evidence_or_prompts_survive(self) -> None:
        for leaked in (HOME, "/private/", AGENT, JUDGE, "evidence", "tracePath",
                       "promptMarkdown", "modelOverride", "judgeModel"):
            with self.subTest(leaked):
                self.assertNotIn(leaked, self.text)

    def test_scores_votes_and_costs_are_kept(self) -> None:
        run = self.stripped["cases"][0]["arms"]["with"][0]
        self.assertEqual(run["score"], 0.5)
        self.assertEqual(run["judgeCostUsd"], 0.06)
        self.assertEqual(run["graders"][0]["judgeVotes"], ["PASS", "PASS", "PASS"])
        self.assertEqual(self.stripped["suite"], {"ablation": "none", "threshold": 0, "concurrency": 4,
                                                  "plugins": [{"name": "swift-android-skills", "version": "1.0.0"}]})

    def test_criteria_text_is_kept_without_the_judge_preamble(self) -> None:
        criteria = self.stripped["cases"][0]["graders"]
        self.assertEqual(criteria[0]["criteria"], "Recommends X.")
        self.assertEqual(criteria[1]["pattern"], "@Observable")

    def test_main_writes_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "in.json"
            source.write_text(json.dumps(RESULT), encoding="utf-8")
            destination = Path(directory) / "out" / "result.json"
            self.assertEqual(stripper.main([str(source), str(destination)]), 0)
            self.assertNotIn(HOME, destination.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

"""Tests for scripts/build_plugin_evals.py."""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_plugin_evals as builder  # noqa: E402


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name) / "stage"
        cls.cases = builder.build(cls.out)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_every_skill_creator_case_is_staged_once(self) -> None:
        self.assertEqual(len(self.cases), len(builder.load_cases()))
        self.assertEqual(len(self.cases), len(set(self.cases)))

    def test_no_answer_key_inside_the_staged_plugin(self) -> None:
        self.assertEqual(list((self.out / "skills").rglob("evals")), [])
        self.assertTrue((self.out / "skills" / "swift-android-architecture" / "SKILL.md").is_file())

    def test_staged_manifest_lists_exactly_the_staged_skills(self) -> None:
        manifest = json.loads((self.out / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        staged = sorted(path.name for path in (self.out / "skills").iterdir())
        self.assertEqual(sorted(Path(p).name for p in manifest["skills"]), staged)

    def test_case_files_parse_and_carry_graders(self) -> None:
        for name in self.cases:
            with self.subTest(name):
                case = json.loads((self.out / "evals" / name / "case.yaml").read_text(encoding="utf-8"))
                self.assertEqual(case["name"], name)
                self.assertTrue(case["execution"]["prompt"].strip())
                self.assertNotIn("evals/files/", case["execution"]["prompt"])
                kinds = [grader["type"] for grader in case["graders"]]
                self.assertIn("llm", kinds)
                self.assertEqual(case["graders"][-1]["name"], "no-answer-key")

    def test_fixture_cases_have_a_scaffold_and_the_fixture(self) -> None:
        for case in builder.load_cases():
            directory = self.out / "evals" / builder.case_id(case)
            with self.subTest(builder.case_id(case)):
                self.assertEqual((directory / "scaffold.sh").exists(), bool(case["files"]))
                for relative in case["files"]:
                    self.assertTrue((directory / "fixture" / Path(relative).name).exists())

    def test_plan_cases_cannot_edit_and_drop_the_structural_expectation(self) -> None:
        for case in builder.load_cases():
            definition = builder.case_definition(case)
            tools = definition["execution"]["allowed_tools"]
            criteria = " ".join(g.get("criteria", "") for g in definition["graders"])
            with self.subTest(builder.case_id(case)):
                if builder.is_edit(case):
                    self.assertIn("Edit", tools)
                else:
                    self.assertNotIn("Edit", tools)
                    self.assertNotIn("Write", tools)
                    self.assertNotIn(builder.STRUCTURAL, criteria)

    def test_file_checks_point_at_fixture_files(self) -> None:
        by_name = {case["name"]: case for case in builder.load_cases()}
        for name, checks in builder.FILE_CHECKS.items():
            case = by_name[name]
            for file, pattern, _ in checks:
                with self.subTest(name=name, file=file):
                    re.compile(pattern)
                    self.assertTrue((ROOT / "skills" / case["skill"] / "evals" / "files" / file).is_file())

    def test_edit_cases_focus_on_existing_files(self) -> None:
        for case in builder.load_cases():
            if not builder.is_edit(case):
                continue
            focus = builder.EDIT_FOCUS[case["name"]]
            with self.subTest(case["name"]):
                self.assertEqual(len(focus), len(case["expectations"]))
                for item in focus:
                    if isinstance(item, dict):
                        fixture = ROOT / "skills" / case["skill"] / "evals" / "files" / item["path"]
                        self.assertTrue(fixture.is_file(), item["path"])

    def test_every_focus_and_check_belongs_to_a_real_case(self) -> None:
        names = {case["name"] for case in builder.load_cases()}
        self.assertLessEqual(set(builder.EDIT_FOCUS), names)
        self.assertLessEqual(set(builder.FILE_CHECKS), names)

    def test_refuses_to_stage_inside_the_repository(self) -> None:
        self.assertEqual(builder.main([str(ROOT / "build-stage")]), 2)


class StageOptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        extra = self.base / "other-plugin" / "skills" / "other-skill"
        extra.mkdir(parents=True)
        (extra / "SKILL.md").write_text("---\nname: other-skill\ndescription: x\n---\n", encoding="utf-8")
        (self.base / "other-plugin" / "LICENSE").write_text("Apache-2.0\n", encoding="utf-8")
        self.extra = self.base / "other-plugin" / "skills"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_only_selects_cases_by_name_or_id(self) -> None:
        first = builder.load_cases()[0]
        written = builder.build(self.base / "stage", only=[first["name"]])
        self.assertEqual(written, [builder.case_id(first)])
        written = builder.build(self.base / "stage", only=[builder.case_id(first)])
        self.assertEqual(written, [builder.case_id(first)])

    def test_unknown_only_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            builder.build(self.base / "stage", only=["no-such-case"])

    def test_extra_skills_are_staged_next_to_ours(self) -> None:
        builder.build(self.base / "stage", extra=[self.extra])
        staged = sorted(path.name for path in (self.base / "stage" / "skills").iterdir())
        self.assertIn("other-skill", staged)
        self.assertIn("swift-android-sdk", staged)
        self.assertTrue((self.base / "stage" / "LICENSE-other-plugin").is_file())

    def test_without_own_skills_stages_only_the_extra_ones(self) -> None:
        cases = builder.build(self.base / "stage", extra=[self.extra], own=False)
        staged = sorted(path.name for path in (self.base / "stage" / "skills").iterdir())
        self.assertEqual(staged, ["other-skill"])
        self.assertEqual(len(cases), len(builder.load_cases()))
        manifest = json.loads((self.base / "stage" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertNotEqual(manifest["name"], "swift-android-skills")


if __name__ == "__main__":
    unittest.main()

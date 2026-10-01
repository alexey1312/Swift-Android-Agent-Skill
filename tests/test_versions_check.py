"""Tests for scripts/versions_check.py; upstream answers come from canned JSON, never the network."""

from __future__ import annotations

import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import versions_check as check  # noqa: E402

WORKFLOW = ROOT / ".github" / "workflows" / "android.yml"
SKIP_URL = check.GITHUB_LATEST.format(repo="skiptools/skip")
JAVA_URL = check.GITHUB_LATEST.format(repo="swiftlang/swift-java")
ACTION_URL = check.GITHUB_LATEST.format(repo="skiptools/swift-android-action")
# Newest last on purpose is not assumed: 6.4.0 sits in the middle.
RELEASES = [
    {"name": "6.3.3", "tag": "swift-6.3.3-RELEASE", "platforms": [{"platform": "android-sdk", "checksum": "c633"}]},
    {"name": "6.4.0", "tag": "swift-6.4.0-RELEASE", "platforms": [
        {"name": "Ubuntu 24.04", "platform": "Linux"},
        {"name": "Android SDK", "platform": "android-sdk", "checksum": "c640", "archs": ["x86_64", "arm64"]},
    ]},
    {"name": "6.2", "tag": "swift-6.2-RELEASE", "platforms": []},
]
UPSTREAM = {
    check.SWIFT_RELEASES: RELEASES,
    SKIP_URL: {"tag_name": "1.9.12"},
    JAVA_URL: {"tag_name": "0.6.0"},
    ACTION_URL: {"tag_name": "v2.9.5"},
}
PINS = {
    "checked": "2026-10-01",
    "swift-release": "6.4.0",
    "swift-android-sdk-checksum": "c640",
    "skip-release": "1.9.12",
    "swift-java-release": "0.6.0",
    "swift-android-action-release": "v2.9.5",
}


class Workspace:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def versions(self, pins: object, before: str = "# Versions\n\nIntro.\n\n", after: str = "") -> Path:
        path = self.directory / "versions.md"
        path.write_text(f"{before}```json\n{json.dumps(pins, indent=2)}\n```\n{after}", encoding="utf-8")
        return path

    def upstream(self, responses: dict) -> Path:
        path = self.directory / "upstream.json"
        path.write_text(json.dumps(responses), encoding="utf-8")
        return path


class ReadPinsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Workspace(Path(self.temp.name))

    def test_reads_only_the_first_json_block(self) -> None:
        path = self.workspace.versions(PINS, after='\n```json\n{"swift-release": "1.0"}\n```\n')
        self.assertEqual(check.read_pins(path), PINS)

    def test_missing_or_malformed_files_are_errors(self) -> None:
        directory = Path(self.temp.name)
        cases = {
            "missing": directory / "nope.md",
            "no block": directory / "plain.md",
            "bad json": directory / "bad.md",
            "nested": directory / "nested.md",
            "empty": directory / "empty.md",
        }
        cases["no block"].write_text("# Versions\n\n| a | b |\n", encoding="utf-8")
        cases["bad json"].write_text("```json\n{\"swift-release\": 6.4.0}\n```\n", encoding="utf-8")
        cases["nested"].write_text('```json\n{"swift": {"release": "6.4.0"}}\n```\n', encoding="utf-8")
        cases["empty"].write_text("```json\n{}\n```\n", encoding="utf-8")
        for label, path in cases.items():
            with self.subTest(label):
                with self.assertRaises(check.PinsError):
                    check.read_pins(path)
                error = io.StringIO()
                with redirect_stdout(io.StringIO()), redirect_stderr(error):
                    self.assertEqual(check.main(["--versions", str(path), "--offline", str(self.workspace.upstream({}))]), 2)
                self.assertIn("error:", error.getvalue())


class CheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Workspace(Path(self.temp.name))

    def run_check(self, pins: dict, upstream: dict = UPSTREAM) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(io.StringIO()):
            code = check.main([
                "--versions", str(self.workspace.versions(pins)),
                "--offline", str(self.workspace.upstream(upstream)),
            ])
        return code, output.getvalue()

    def row(self, table: str, pin: str) -> str:
        return next(line for line in table.splitlines() if line.startswith(f"| `{pin}` |"))

    def test_everything_current_exits_zero(self) -> None:
        code, table = self.run_check(PINS)
        self.assertEqual(code, 0)
        self.assertTrue(table.startswith("## Version pins\n"))
        self.assertIn("last checked by hand on 2026-10-01", table)
        self.assertNotIn("`checked`", table, "the date is not a pin")
        for pin in ("swift-release", "swift-android-sdk-checksum", "skip-release", "swift-java-release", "swift-android-action-release"):
            with self.subTest(pin):
                self.assertTrue(self.row(table, pin).endswith("| current |"))

    def test_a_moved_pin_exits_one(self) -> None:
        code, table = self.run_check({**PINS, "skip-release": "1.9.11", "swift-release": "6.3.3", "swift-android-sdk-checksum": "c633"})
        self.assertEqual(code, 1)
        self.assertIn("| `skip-release` | `1.9.11` | `1.9.12` | **moved** |", table)
        self.assertIn("| `swift-release` | `6.3.3` | `6.4.0` | **moved** |", table)
        self.assertIn("| `swift-android-sdk-checksum` | `c633` | `c640` | **moved** |", table)
        self.assertIn("Moved: ", table)

    def test_latest_swift_is_the_highest_version_not_the_last_entry(self) -> None:
        self.assertEqual(check.latest_swift_release(RELEASES)["name"], "6.4.0")

    def test_equivalent_spellings_are_current(self) -> None:
        self.assertTrue(check.same_version("6.4", "6.4.0"))
        self.assertTrue(check.same_version("2.9.5", "v2.9.5"))
        self.assertFalse(check.same_version("6.4.0", "6.4.1"))
        code, _ = self.run_check({**PINS, "swift-release": "6.4", "swift-android-action-release": "2.9.5"})
        self.assertEqual(code, 0)

    def test_unknown_keys_are_listed_but_never_fail(self) -> None:
        code, table = self.run_check({**PINS, "ndk": "r30"})
        self.assertEqual(code, 0)
        self.assertIn("| `ndk` | `r30` |  | not checked |", table)

    def test_a_failed_lookup_exits_three_unless_something_moved(self) -> None:
        without_skip = {url: body for url, body in UPSTREAM.items() if url != SKIP_URL}
        code, table = self.run_check(PINS, without_skip)
        self.assertEqual(code, 3)
        self.assertIn("error: no canned response", self.row(table, "skip-release"))
        code, _ = self.run_check({**PINS, "swift-java-release": "0.5.1"}, without_skip)
        self.assertEqual(code, 1)

    def test_malformed_upstream_answers_are_errors(self) -> None:
        broken = {**UPSTREAM, check.SWIFT_RELEASES: {"not": "a list"}, JAVA_URL: {"message": "Not Found"}}
        code, table = self.run_check(PINS, broken)
        self.assertEqual(code, 3)
        self.assertIn("error:", self.row(table, "swift-release"))
        self.assertIn("error:", self.row(table, "swift-java-release"))


class RequestTests(unittest.TestCase):
    def test_token_goes_to_the_github_api_only(self) -> None:
        env = {"GITHUB_TOKEN": "secret-token"}
        github = check.request_for(SKIP_URL, env)
        self.assertEqual(github.get_header("Authorization"), "Bearer secret-token")
        self.assertEqual(github.get_header("Accept"), "application/vnd.github+json")
        swift = check.request_for(check.SWIFT_RELEASES, env)
        self.assertIsNone(swift.get_header("Authorization"))
        self.assertIsNone(check.request_for(SKIP_URL, {}).get_header("Authorization"))
        self.assertTrue(github.get_header("User-agent"))


@unittest.skipUnless((ROOT / "references" / "versions.md").is_file(), "references/versions.md not written yet")
class RepositoryPinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pins = check.read_pins(ROOT / "references" / "versions.md")

    def test_every_pin_is_one_the_script_checks(self) -> None:
        known = set(check.SWIFT_PINS) | set(check.GITHUB_PINS) | check.NOT_PINS
        self.assertEqual(set(self.pins) - known, set())
        self.assertRegex(self.pins.get("checked", ""), r"^20\d\d-\d\d-\d\d$")

    @unittest.skipUnless(WORKFLOW.is_file(), "android.yml not written yet")
    def test_the_android_workflow_uses_the_pinned_values(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        swift = self.pins["swift-release"]
        self.assertRegex(workflow, rf'SWIFT_VERSION: "{re.escape(swift)}"')
        self.assertIn(f"swift-{swift}-RELEASE_android.artifactbundle.tar.gz", workflow)
        if "swift-android-sdk-checksum" in self.pins:
            self.assertIn(f"--checksum {self.pins['swift-android-sdk-checksum']}", workflow)
        if "swift-android-action-release" in self.pins:
            uses = re.findall(r"uses: skiptools/swift-android-action@([0-9a-f]{40}) # (\S+)", workflow)
            self.assertTrue(uses, "the action is pinned to a full commit SHA with its tag in a comment")
            self.assertEqual({tag for _, tag in uses}, {self.pins["swift-android-action-release"]})


if __name__ == "__main__":
    unittest.main()

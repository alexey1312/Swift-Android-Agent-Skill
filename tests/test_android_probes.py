"""Tests for scripts/android_probes.py and the probes it builds; no Swift toolchain needed.

Builds run against a stub `swift` script written to a temporary directory,
which prints what a real toolchain would and logs its arguments.
"""

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

import android_probes  # noqa: E402

PROBES = ROOT / "scripts" / "probes" / "android"
SDK = "swift-6.4.0-RELEASE_android"
TRIPLE = "aarch64-unknown-linux-android28"

STUB = """#!{python}
import json, os, sys, time
config = json.loads({config!r})
args = sys.argv[1:]
with open(config["log"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")
if args == ["--version"]:
    print("Swift version 6.4 (swift-6.4.0-RELEASE)")
    print("Target: x86_64-unknown-linux-gnu")
    sys.exit(0)
if args[:1] == ["build"]:
    package = args[args.index("--package-path") + 1]
    name = os.path.basename(package.rstrip("/"))
    time.sleep(config.get("sleep", 0))
    failure = config["failures"].get(name)
    if failure is None:
        print("Build complete!")
        sys.exit(0)
    sys.stdout.write("Building for debugging...\\n")
    sys.stderr.write(failure.replace("PACKAGE", package))
    sys.exit(1)
sys.exit(64)
"""

# The same missing module, as each SwiftPM build system reports it (swiftbuild colours even when piped).
NATIVE_UIKIT = (
    "error: emit-module command failed with exit code 1 (use -v to see invocation)\n"
    "PACKAGE/Sources/Breaks/Breaks.swift:1:8: error: no such module 'UIKit'\n"
    "1 | import UIKit\n"
    "  |        `- error: no such module 'UIKit'\n"
)
SWIFTBUILD_UIKIT = (
    "error: \x1b[1mPACKAGE/Sources/Breaks/Breaks.swift:1:8 unable to resolve module dependency: 'UIKit'\x1b[0m\n"
    "error: SwiftDriver Breaks normal x86_64 com.apple.xcode.tools.swift.compiler failed with a nonzero exit code. "
    "Command line: swiftc -module-name Breaks PACKAGE/Sources/Breaks/Breaks.swift\n"
    "error: Build failed\n"
)
NO_SDK = "error: No Swift SDK found matching query 'swift-6.4.0-RELEASE_android'\n"

EXPECTATIONS = {
    "builds": {
        "question": "Does the ladder build?", "expect": "pass", "error_contains": None,
        "twin": "breaks", "source": "https://example.com/ladder",
    },
    "breaks": {
        "question": "Does import UIKit build?", "expect": "fail", "error_contains": "'UIKit'",
        "twin": "builds", "source": "https://example.com/uikit",
    },
    "unknown": {
        "question": "Does import Combine build?", "expect": "record", "error_contains": None,
        "twin": None, "source": "https://example.com/combine",
    },
}


def make_root(directory: Path, expectations: dict | None = None) -> Path:
    root = directory / "probes"
    root.mkdir()
    expectations = EXPECTATIONS if expectations is None else expectations
    (root / "expectations.json").write_text(json.dumps(expectations), encoding="utf-8")
    for name in expectations:
        (root / name).mkdir()
        (root / name / "Package.swift").write_text("// swift-tools-version: 6.0\n", encoding="utf-8")
    return root


def make_stub(directory: Path, failures: dict[str, str], sleep: float = 0) -> tuple[Path, Path]:
    log = directory / "swift.log"
    config = json.dumps({"failures": failures, "log": str(log), "sleep": sleep})
    stub = directory / "swift"
    stub.write_text(STUB.format(python=sys.executable, config=config), encoding="utf-8")
    stub.chmod(0o755)
    return stub, log


def logged_calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


class RepositoryProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.expectations = android_probes.load_expectations(PROBES)

    def test_expectations_agree_with_the_probe_directories(self) -> None:
        self.assertEqual(android_probes.problems(PROBES, self.expectations), [])
        directories = sorted(path.name for path in PROBES.iterdir() if path.is_dir() and not path.name.startswith("."))
        self.assertEqual(directories, sorted(self.expectations))

    def test_each_probe_is_a_one_file_package(self) -> None:
        for name in self.expectations:
            with self.subTest(name):
                manifest = (PROBES / name / "Package.swift").read_text(encoding="utf-8")
                self.assertTrue(manifest.startswith("// swift-tools-version: 6.0\n"))
                self.assertIn(f'name: "{name}"', manifest)
                targets = [path for path in (PROBES / name / "Sources").iterdir() if path.is_dir()]
                self.assertEqual(len(targets), 1)
                target = targets[0].name
                self.assertIn(f'.target(name: "{target}")', manifest)
                self.assertEqual(sorted(path.name for path in targets[0].iterdir()), [f"{target}.swift"])
                source = (targets[0] / f"{target}.swift").read_text(encoding="utf-8")
                self.assertRegex(source.splitlines()[0], r"^// (Does|Do) .+\?$", "first line states the question")

    def test_twins_point_both_ways_and_differ(self) -> None:
        for name, expectation in self.expectations.items():
            if expectation.twin is None:
                continue
            with self.subTest(name):
                twin = self.expectations[expectation.twin]
                self.assertEqual(twin.twin, name)
                self.assertNotEqual(twin.expect, expectation.expect, "a twin pair contrasts two outcomes")

    def test_sources_are_urls(self) -> None:
        for name, expectation in self.expectations.items():
            with self.subTest(name):
                self.assertRegex(expectation.source, r"^https://\S+$")

    def test_fail_probes_say_which_error_they_expect(self) -> None:
        # Without error_contains, a toolchain that cannot build anything would confirm every "fail".
        for name, expectation in self.expectations.items():
            with self.subTest(name):
                self.assertIn(expectation.expect, android_probes.EXPECTS)
                if expectation.expect == "fail":
                    self.assertTrue(expectation.error_contains)
                else:
                    self.assertIsNone(expectation.error_contains)

    def test_list_names_every_probe_without_building(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = android_probes.main(["--list", "--swift", "/nonexistent/swift"])
        self.assertEqual(code, 0)
        listed = [line.split()[0] for line in output.getvalue().splitlines()]
        self.assertEqual(listed, list(self.expectations))


class ExpectationValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def problems_for(self, expectations: dict) -> list[str]:
        root = make_root(self.directory, expectations)
        return android_probes.problems(root, android_probes.load_expectations(root))

    def test_the_fixture_is_valid(self) -> None:
        self.assertEqual(self.problems_for(EXPECTATIONS), [])

    def test_one_sided_twin(self) -> None:
        broken = json.loads(json.dumps(EXPECTATIONS))
        broken["builds"]["twin"] = "unknown"
        self.assertTrue(any("does not name builds back" in problem for problem in self.problems_for(broken)))

    def test_unknown_expect_source_and_misplaced_error_contains(self) -> None:
        broken = json.loads(json.dumps(EXPECTATIONS))
        broken["unknown"].update(expect="maybe", source="skip.dev somewhere", error_contains="x")
        problems = self.problems_for(broken)
        self.assertTrue(any("expect must be one of" in problem for problem in problems))
        self.assertTrue(any("source must be a URL" in problem for problem in problems))
        self.assertTrue(any("error_contains only applies" in problem for problem in problems))

    def test_directories_must_match_entries(self) -> None:
        root = make_root(self.directory)
        (root / "stray").mkdir()
        (root / "builds" / "Package.swift").unlink()
        problems = android_probes.problems(root, android_probes.load_expectations(root))
        self.assertIn("stray: probe directory without an entry in expectations.json", problems)
        self.assertIn("builds: no Package.swift", problems)

    def test_malformed_file_is_a_usage_error(self) -> None:
        root = make_root(self.directory)
        (root / "expectations.json").write_text('{"builds": {"expect": "pass"}}', encoding="utf-8")
        with self.assertRaises(ValueError):
            android_probes.load_expectations(root)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(android_probes.main(["--root", str(root), "--swift-sdk", SDK]), 2)


class RunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.root = make_root(self.directory)

    def run_probes(self, failures: dict[str, str], *extra: str) -> tuple[int, str, dict | None, list[list[str]]]:
        stub, log = make_stub(self.directory, failures)
        report_path = self.directory / "probes.json"
        for leftover in (log, report_path):
            leftover.unlink(missing_ok=True)
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(io.StringIO()):
            code = android_probes.main([
                "--root", str(self.root), "--swift", str(stub), "--swift-sdk", SDK, "--triple", TRIPLE,
                "--json", str(report_path), *extra,
            ])
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
        return code, output.getvalue(), report, logged_calls(log)

    def rows(self, report: dict) -> dict[str, dict]:
        return {row["probe"]: row for row in report["results"]}

    def test_outcomes_that_match_the_sources_exit_zero(self) -> None:
        code, markdown, report, _ = self.run_probes({"breaks": NATIVE_UIKIT, "unknown": NO_SDK})
        self.assertEqual(code, 0)
        rows = self.rows(report)
        self.assertEqual({name: row["status"] for name, row in rows.items()},
                         {"builds": "ok", "breaks": "ok", "unknown": "recorded"})
        self.assertEqual(rows["breaks"]["result"], "fail")
        self.assertEqual(rows["breaks"]["expected"], "fail")
        self.assertEqual(rows["breaks"]["error"], "Breaks.swift:1:8: error: no such module 'UIKit'")
        self.assertIsNone(rows["builds"]["error"])
        for row in rows.values():
            self.assertEqual(row["swift_version"], "Swift version 6.4 (swift-6.4.0-RELEASE)")
            self.assertEqual((row["swift_sdk"], row["triple"]), (SDK, TRIPLE))
        self.assertEqual(report["swift_sdk"], SDK)
        self.assertRegex(report["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue(markdown.startswith("## Android compile probes\n"))
        self.assertIn("| `breaks` | Does import UIKit build? | fail | fail | ok |", markdown)

    def test_swiftbuild_wording_satisfies_error_contains_too(self) -> None:
        code, _, report, _ = self.run_probes({"breaks": SWIFTBUILD_UIKIT})
        self.assertEqual(code, 0)
        error = self.rows(report)["breaks"]["error"]
        self.assertEqual(error, "error: Breaks.swift:1:8 unable to resolve module dependency: 'UIKit'")
        self.assertNotIn("\x1b", error)
        self.assertNotIn(self.temp.name, json.dumps(report), "no temporary or runner paths in the report")

    def test_a_pass_probe_that_fails_is_a_mismatch(self) -> None:
        code, markdown, report, _ = self.run_probes({"builds": NATIVE_UIKIT, "breaks": NATIVE_UIKIT})
        self.assertEqual(code, 1)
        self.assertEqual(self.rows(report)["builds"]["status"], "mismatch")
        self.assertIn("**mismatch**", markdown)
        self.assertIn("https://example.com/ladder", markdown)

    def test_a_fail_probe_that_builds_is_a_mismatch(self) -> None:
        code, _, report, _ = self.run_probes({})
        self.assertEqual(code, 1)
        self.assertEqual(self.rows(report)["breaks"]["reason"], "expected fail, got pass")

    def test_failing_for_another_reason_is_a_mismatch(self) -> None:
        code, _, report, _ = self.run_probes({"breaks": NO_SDK})
        self.assertEqual(code, 1)
        self.assertIn("no compiler error contains", self.rows(report)["breaks"]["reason"])

    def test_unlocated_lines_do_not_satisfy_error_contains(self) -> None:
        # A driver line can mention the name while the real diagnostic is about something else.
        other = (
            "PACKAGE/Sources/Breaks/Breaks.swift:3:1: error: expected declaration\n"
            "error: SwiftDriver Breaks failed. Command line: swiftc -module-alias Kit='UIKit'\n"
        )
        code, _, report, _ = self.run_probes({"breaks": other})
        self.assertEqual(code, 1)
        self.assertEqual(self.rows(report)["breaks"]["status"], "mismatch")

    def test_record_never_fails(self) -> None:
        for failures in ({"breaks": NATIVE_UIKIT}, {"breaks": NATIVE_UIKIT, "unknown": NO_SDK}):
            with self.subTest(failures=sorted(failures)):
                code, _, report, _ = self.run_probes(failures)
                self.assertEqual(code, 0)
                self.assertEqual(self.rows(report)["unknown"]["status"], "recorded")

    def test_build_command_line(self) -> None:
        _, _, _, calls = self.run_probes({"breaks": NATIVE_UIKIT})
        self.assertIn(["--version"], calls)
        builds = [call for call in calls if call[:1] == ["build"]]
        self.assertEqual(len(builds), 3)
        call = next(call for call in builds if call[2].endswith("builds"))
        self.assertEqual(call[:7], ["build", "--package-path", str(self.root / "builds"), "--swift-sdk", SDK, "--triple", TRIPLE])
        self.assertEqual(call[7], "--scratch-path")
        self.assertFalse(Path(call[8]).is_relative_to(self.root), "build products stay out of the probes")

    def test_without_triple_none_is_passed(self) -> None:
        stub, log = make_stub(self.directory, {})
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            android_probes.main(["--root", str(self.root), "--swift", str(stub), "--swift-sdk", SDK, "--probe", "builds"])
        build = next(call for call in logged_calls(log) if call[:1] == ["build"])
        self.assertNotIn("--triple", build)

    def test_probe_subset_and_unknown_names(self) -> None:
        code, _, report, calls = self.run_probes({"breaks": NATIVE_UIKIT}, "--probe", "breaks")
        self.assertEqual(code, 0)
        self.assertEqual([row["probe"] for row in report["results"]], ["breaks"])
        self.assertEqual(len([call for call in calls if call[:1] == ["build"]]), 1)
        code, _, report, _ = self.run_probes({}, "--probe", "nope")
        self.assertEqual(code, 2)

    def test_usage_errors_exit_two(self) -> None:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                android_probes.main(["--root", str(self.root)])
            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(
                android_probes.main(["--root", str(self.root), "--swift", "/nonexistent/swift", "--swift-sdk", SDK]), 2
            )

    def test_a_timeout_is_an_error_not_the_claimed_failure(self) -> None:
        stub, _ = make_stub(self.directory, {}, sleep=5)
        outcome = android_probes.build(str(stub), self.root / "breaks", SDK, TRIPLE, self.directory / "scratch", 0.5)
        self.assertEqual(outcome.result, "error")
        self.assertIn("timed out", outcome.excerpt)
        expectations = android_probes.load_expectations(self.root)
        self.assertEqual(android_probes.judge(expectations["breaks"], outcome)[0], "mismatch")
        self.assertEqual(android_probes.judge(expectations["unknown"], outcome)[0], "recorded")


class HelperTests(unittest.TestCase):
    def test_markdown_escapes_cells(self) -> None:
        row = {
            "probe": "p", "question": "Does `a | b` build?", "expected": "fail", "result": "fail",
            "status": "ok", "reason": None, "error": "x.swift:1:1: error: `a` | b", "source": "https://example.com",
        }
        context = {"swift_version": "Swift version 6.4", "swift_sdk": SDK, "triple": None, "ndk": None}
        table = android_probes.markdown([row], context)
        line = next(line for line in table.splitlines() if line.startswith("| `p`"))
        self.assertIn("Does `a \\| b` build?", line)
        self.assertIn("`x.swift:1:1: error: 'a' \\| b`", line)
        self.assertEqual(len(re.findall(r"(?<!\\)\|", line)), 7)

    def test_ndk_revision_prefers_android_ndk_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for name, release, revision in (("r30", "r30", "30.0.14904198"), ("r27", "r27d", "27.3.13750724")):
                ndk = Path(directory) / name
                ndk.mkdir()
                (ndk / "source.properties").write_text(
                    f"Pkg.Desc = Android NDK\nPkg.Revision = {revision}\nPkg.ReleaseName = {release}\n", encoding="utf-8"
                )
            both = {"ANDROID_NDK_ROOT": str(Path(directory) / "r27"), "ANDROID_NDK_HOME": str(Path(directory) / "r30")}
            self.assertEqual(android_probes.ndk_revision(both), "r27d (27.3.13750724)")
            self.assertEqual(android_probes.ndk_revision({"ANDROID_NDK_HOME": both["ANDROID_NDK_HOME"]}), "r30 (30.0.14904198)")
            self.assertIsNone(android_probes.ndk_revision({}))

    def test_run_url(self) -> None:
        env = {"GITHUB_SERVER_URL": "https://github.com", "GITHUB_REPOSITORY": "o/r", "GITHUB_RUN_ID": "42"}
        self.assertEqual(android_probes.run_url(env), "https://github.com/o/r/actions/runs/42")
        self.assertIsNone(android_probes.run_url({}))


if __name__ == "__main__":
    unittest.main()

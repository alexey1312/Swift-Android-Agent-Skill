"""Tests for scripts/toolchain_report.py; every command and environment variable is faked."""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import toolchain_report as report  # noqa: E402

XCODE_SWIFT = (
    "swift-driver version: 1.168.6 Apple Swift version 6.4 (swiftlang-6.4.0.34.1 clang-2100.3.34.1)\n"
    "Target: arm64-apple-macosx27.0.0\n"
)
LINUX_SWIFT = "Swift version 6.4 (swift-6.4.0-RELEASE)\nTarget: x86_64-unknown-linux-gnu\n"
MACOS_OPEN_SOURCE_SWIFT = "Apple Swift version 6.4.0 (swift-6.4.0-RELEASE)\nTarget: arm64-apple-macosx26.0\n"
ALL_TOOLS = set(report.ALLOWED)


class FakeRunner:
    """Stands in for subprocess.run: canned (exit code, stdout, stderr) per command, and a call log."""

    def __init__(self, outputs: dict[tuple[str, ...], object]) -> None:
        self.outputs = outputs
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        result = self.outputs.get((Path(argv[0]).name, *argv[1:]), (127, "", "not configured"))
        if isinstance(result, BaseException):
            raise result
        code, stdout, stderr = result
        return subprocess.CompletedProcess(argv, code, stdout, stderr)


def which_for(tools: set[str]):
    return lambda tool: f"/fake/bin/{tool}" if tool in tools else None


def make_ndk(parent: Path, name: str, revision: str, release: str) -> Path:
    path = parent / name
    path.mkdir(parents=True)
    (path / "source.properties").write_text(
        f"Pkg.Desc = Android NDK\nPkg.Revision = {revision}\nPkg.ReleaseName = {release}\n", encoding="utf-8"
    )
    return path


def ready_outputs(swift: str = LINUX_SWIFT, sdks: str = "swift-6.4.0-RELEASE_android\n") -> dict:
    return {
        ("swift", "--version"): (0, swift, ""),
        ("swift", "sdk", "list"): (0, sdks, ""),
        ("xcodebuild", "-version"): (0, "Xcode 27.1\nBuild version 27A9269\n", ""),
        ("swiftly", "--version"): (0, "1.2.0\n", ""),
        ("swiftly", "list"): (0, "Installed release toolchains\n----------------------------\nSwift 6.4.0 (in use) (default)\n", ""),
        ("java", "-version"): (0, "", 'openjdk version "17.0.20" 2026-07-21\nOpenJDK Runtime Environment\n'),
        ("adb", "version"): (0, "Android Debug Bridge version 1.0.41\nVersion 36.0.0-13206524\n", ""),
        ("adb", "devices"): (0, "List of devices attached\nemulator-5554\tdevice\n\n", ""),
        ("skip", "version"): (0, "Skip version 1.9.12\n", ""),
        ("gradle", "--version"): (0, "\n------------------------------------------------------------\nGradle 9.1\n", ""),
    }


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.r30 = make_ndk(self.directory, "android-ndk-r30", "30.0.14904198", "r30")

    def collect(self, outputs: dict, env: dict, system: str = "Linux", tools: set[str] = ALL_TOOLS) -> dict:
        return report.collect(env=env, runner=FakeRunner(outputs), which=which_for(tools), system=system)

    def test_ready_linux_host_can_build_and_run_android_tests(self) -> None:
        env = {"ANDROID_NDK_HOME": str(self.r30), "ANDROID_NDK_ROOT": str(self.r30)}
        result = self.collect(ready_outputs(), env)
        self.assertEqual(result["swift"]["kind"], "open source")
        self.assertEqual(result["swift"]["tag"], "swift-6.4.0-RELEASE")
        self.assertEqual(result["android_sdks_matching_host"], ["swift-6.4.0-RELEASE_android"])
        self.assertEqual((result["ndk"]["release"], result["ndk"]["revision"]), ("r30", "30.0.14904198"))
        self.assertEqual(result["ndk_source"], "ANDROID_NDK_ROOT")
        self.assertFalse(result["can_typecheck_apple"])
        self.assertTrue(result["can_build_android"])
        self.assertTrue(result["can_run_android_tests"])
        self.assertEqual(result["next_steps"], ["Nothing is missing for building and testing on Android here."])
        self.assertEqual(result["java"], 'openjdk version "17.0.20" 2026-07-21')
        self.assertEqual(result["gradle"], "Gradle 9.1")
        self.assertEqual(result["skip"], "Skip version 1.9.12")
        self.assertIsNone(result["xcode"], "xcodebuild is not run off macOS")

    def test_xcode_toolchain_typechecks_apple_but_cannot_use_the_android_sdk(self) -> None:
        outputs = ready_outputs(swift=XCODE_SWIFT, sdks="swift-6.4.0-RELEASE_android\n")
        outputs[("java", "-version")] = (1, "", "The operation couldn't be completed. Unable to locate a Java Runtime.\n")
        result = self.collect(outputs, {"ANDROID_NDK_HOME": str(self.r30)}, system="Darwin", tools={"swift", "xcodebuild", "java"})
        self.assertEqual(result["swift"]["kind"], "Xcode")
        self.assertEqual(result["xcode"], "Xcode 27.1 (27A9269)")
        self.assertTrue(result["can_typecheck_apple"])
        self.assertFalse(result["can_build_android"])
        self.assertFalse(result["can_run_android_tests"])
        steps = " ".join(result["next_steps"])
        self.assertIn("Xcode's `swift` cannot use the Swift SDK for Android", steps)
        self.assertIn("adb", steps)
        self.assertIn("JDK", steps)

    def test_open_source_toolchain_on_macos_counts(self) -> None:
        result = self.collect(ready_outputs(swift=MACOS_OPEN_SOURCE_SWIFT), {"ANDROID_NDK_HOME": str(self.r30)}, system="Darwin")
        self.assertEqual(result["swift"]["kind"], "open source")
        self.assertTrue(result["can_typecheck_apple"])
        self.assertTrue(result["can_build_android"])

    def test_sdk_for_another_toolchain_does_not_count(self) -> None:
        sdks = "swift-6.3.3-RELEASE_android\nswift-6.4.0-RELEASE_static-linux-0.1.0\n"
        result = self.collect(ready_outputs(sdks=sdks), {"ANDROID_NDK_HOME": str(self.r30)})
        self.assertEqual(result["android_sdks"], ["swift-6.3.3-RELEASE_android"])
        self.assertEqual(result["android_sdks_matching_host"], [])
        self.assertFalse(result["can_build_android"])
        self.assertTrue(any("must match" in step and "swift-6.4.0-RELEASE" in step for step in result["next_steps"]))

    def test_no_sdk_and_no_ndk(self) -> None:
        outputs = ready_outputs(sdks="No Swift SDKs are currently installed.\n")
        result = self.collect(outputs, {})
        self.assertEqual(result["swift_sdks"], [])
        self.assertIsNone(result["ndk"])
        self.assertFalse(result["can_build_android"])
        steps = " ".join(result["next_steps"])
        self.assertIn("swift sdk install", steps)
        self.assertIn("ANDROID_NDK_HOME", steps)

    def test_nothing_installed(self) -> None:
        result = self.collect({}, {}, tools=set())
        self.assertFalse(result["swift"]["found"])
        self.assertFalse(result["can_typecheck_apple"] or result["can_build_android"] or result["can_run_android_tests"])
        self.assertIn("swiftly", result["next_steps"][0])

    def test_devices_must_be_ready(self) -> None:
        env = {"ANDROID_NDK_HOME": str(self.r30)}
        for listing, waiting in (("List of devices attached\n\n", None), ("List of devices attached\nR58M123\tunauthorized\n", "R58M123 (unauthorized)")):
            with self.subTest(listing=listing):
                outputs = ready_outputs()
                outputs[("adb", "devices")] = (0, listing, "")
                result = self.collect(outputs, env)
                self.assertTrue(result["can_build_android"])
                self.assertFalse(result["can_run_android_tests"])
                step = next(step for step in result["next_steps"] if "emulator" in step)
                if waiting:
                    self.assertIn(waiting, step)

    def test_ndk_variables_that_disagree_are_flagged(self) -> None:
        r27 = make_ndk(self.directory, "27.3.13750724", "27.3.13750724", "r27d")
        result = self.collect(ready_outputs(), {"ANDROID_NDK_HOME": str(self.r30), "ANDROID_NDK_ROOT": str(r27)})
        self.assertEqual(result["ndk"]["release"], "r27d", "Swift Build reads ANDROID_NDK_ROOT first")
        self.assertTrue(any("different NDKs" in step for step in result["next_steps"]))
        self.assertEqual(set(result["ndk_by_variable"]), {"ANDROID_NDK_HOME", "ANDROID_NDK_ROOT"})

    def test_side_by_side_ndks_under_android_home(self) -> None:
        sdk = self.directory / "sdk"
        make_ndk(sdk / "ndk", "27.3.13750724", "27.3.13750724", "r27d")
        make_ndk(sdk / "ndk", "29.0.14206865", "29.0.14206865", "r29")
        result = self.collect(ready_outputs(), {"ANDROID_HOME": str(sdk)})
        self.assertEqual(result["ndk"]["revision"], "29.0.14206865")
        self.assertEqual(result["ndk_source"], "ANDROID_HOME/ndk")

    def test_a_variable_pointing_nowhere_is_not_an_ndk(self) -> None:
        result = self.collect(ready_outputs(), {"ANDROID_NDK_HOME": str(self.directory / "missing")})
        self.assertFalse(result["can_build_android"])
        self.assertTrue(any("not an NDK" in step for step in result["next_steps"]))

    def test_timeouts_and_crashes_are_reported_not_raised(self) -> None:
        outputs = ready_outputs()
        outputs[("gradle", "--version")] = subprocess.TimeoutExpired(["gradle"], report.TIMEOUT)
        outputs[("skip", "version")] = OSError("exec format error")
        result = self.collect(outputs, {"ANDROID_NDK_HOME": str(self.r30)})
        self.assertIsNone(result["gradle"])
        self.assertIsNone(result["skip"])
        self.assertTrue(result["can_build_android"])

    def test_markdown_and_json(self) -> None:
        result = self.collect(ready_outputs(), {"ANDROID_NDK_HOME": str(self.r30)})
        text = report.markdown(result)
        self.assertTrue(text.startswith("# Toolchain report\n"))
        self.assertIn("## Verdict", text)
        self.assertIn("| Build for Android | yes |", text)
        self.assertIn("## Next steps", text)
        json.loads(json.dumps(result))


class ParsingTests(unittest.TestCase):
    def test_sdk_ids(self) -> None:
        self.assertEqual(report.sdk_tag("swift-6.4.0-RELEASE_android"), "swift-6.4.0-RELEASE")
        self.assertEqual(report.sdk_tag("swift-6.2-RELEASE-android-0.1"), "swift-6.2-RELEASE")
        self.assertEqual(report.sdk_tag("swift-6.1-RELEASE-android-24-0.1"), "swift-6.1-RELEASE")
        self.assertEqual(report.sdk_tag("swift-DEVELOPMENT-SNAPSHOT-2026-09-21-a_android"), "swift-DEVELOPMENT-SNAPSHOT-2026-09-21-a")
        self.assertIsNone(report.sdk_tag("aarch64-unknown-linux-android28"))

    def test_versions_match_with_or_without_a_patch_number(self) -> None:
        untagged = {"tag": None, "version": "6.4"}
        self.assertTrue(report.matches_host("swift-6.4.0-RELEASE_android", untagged))
        self.assertFalse(report.matches_host("swift-6.4.1-RELEASE_android", untagged))
        tagged = report.parse_swift(LINUX_SWIFT)
        self.assertTrue(report.matches_host("swift-6.4.0-RELEASE_android", tagged))
        self.assertFalse(report.matches_host("swift-6.4-RELEASE_android", tagged), "tags must match exactly")


class ReadOnlyTests(unittest.TestCase):
    EXPECTED_ALLOWLIST = {
        "swift": {("--version",), ("sdk", "list")},
        "xcodebuild": {("-version",)},
        "swiftly": {("--version",), ("list",)},
        "java": {("-version",)},
        "adb": {("version",), ("devices",)},
        "skip": {("version",)},
        "gradle": {("--version",)},
    }

    def test_the_allowlist_holds_only_version_and_list_commands(self) -> None:
        # Widening it is a deliberate change to this test, not a side effect.
        self.assertEqual({tool: set(arguments) for tool, arguments in report.ALLOWED.items()}, self.EXPECTED_ALLOWLIST)

    def test_anything_else_is_refused_before_a_process_starts(self) -> None:
        runner = FakeRunner({})
        for tool, arguments in (("swift", ("build",)), ("swift", ("sdk", "install", "x")), ("swiftly", ("install", "latest")),
                                ("adb", ("install", "app.apk")), ("rm", ("-rf", "/")), ("sh", ("-c", "true"))):
            with self.subTest(tool=tool, arguments=arguments):
                with self.assertRaises(ValueError):
                    report.run(tool, *arguments, runner=runner, which=which_for(ALL_TOOLS | {"rm", "sh"}))
        self.assertEqual(runner.calls, [])

    def test_every_command_run_is_allowlisted_with_a_short_timeout(self) -> None:
        for system in ("Darwin", "Linux"):
            for format_ in ("markdown", "json"):
                with self.subTest(system=system, format=format_):
                    runner = FakeRunner(ready_outputs())
                    with mock.patch.object(report.subprocess, "run", runner), \
                            mock.patch.object(report.shutil, "which", which_for(ALL_TOOLS)), \
                            mock.patch.object(report.platform, "system", return_value=system), \
                            redirect_stdout(io.StringIO()):
                        self.assertEqual(report.main(["--format", format_]), 0)
                    self.assertTrue(runner.calls)
                    for argv, kwargs in runner.calls:
                        tool, arguments = Path(argv[0]).name, tuple(argv[1:])
                        self.assertIn(arguments, self.EXPECTED_ALLOWLIST[tool], argv)
                        self.assertLessEqual(kwargs.get("timeout", 10**6), 30, argv)
                        self.assertFalse(kwargs.get("shell", False), argv)

    def test_the_source_starts_processes_only_through_run(self) -> None:
        source = (ROOT / "scripts" / "toolchain_report.py").read_text(encoding="utf-8")
        for forbidden in ("os.system", "Popen", "shell=True", "check_output", "check_call", "os.exec", "os.spawn",
                          "urlopen", "unlink(", "rmtree", "write_text", "mkdir("):
            with self.subTest(forbidden):
                self.assertNotIn(forbidden, source)
        self.assertEqual(len(re.findall(r"\brunner\(", source)), 1, "one call site starts processes")


if __name__ == "__main__":
    unittest.main()

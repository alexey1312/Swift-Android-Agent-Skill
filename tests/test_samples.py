from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("typecheck_samples", ROOT / "scripts" / "typecheck_samples.py")
assert SPEC and SPEC.loader
typecheck_samples = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = typecheck_samples
SPEC.loader.exec_module(typecheck_samples)


def extract(text: str):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "doc.md"
        path.write_text(text, encoding="utf-8")
        return typecheck_samples.tagged_blocks([path])


class ExtractionTests(unittest.TestCase):
    def test_tags_continuations_and_reasons(self) -> None:
        blocks, problems = extract(
            "```swift\n// typecheck: shared\nlet a = 1\n```\n"
            "```swift\n// typecheck: shared, continues the block above\nlet b = a\n```\n"
            "```swift\n// typecheck: ios18\nlet c = 1\n```\n"
            "```kotlin\n// typecheck: none — Kotlin is not compiled here\nval d = 1\n```\n"
            "```json\n{\"e\": 1}\n```\n"
        )
        self.assertEqual(problems, [])
        self.assertEqual([b.kind for b in blocks], ["shared", "shared", "ios", "none", "json"])
        self.assertIn("let a = 1", blocks[1].code)
        self.assertIn("let b = a", blocks[1].code)
        self.assertEqual(blocks[2].ios, 18)

    def test_untagged_and_malformed_blocks_are_problems(self) -> None:
        _, problems = extract(
            "```swift\nlet fragment = 1\n```\n"
            "```kotlin\n// typecheck: shared\nval x = 1\n```\n"
            "```swift\n// typecheck: none — tiny\nlet y = 1\n```\n"
            "```swift\n// typecheck: shared, continues the block above\nlet z = 1\n```\n"
        )
        self.assertEqual(len(problems), 4)

    def test_shared_cannot_continue_ios_but_ios_can_continue_shared(self) -> None:
        _, problems = extract(
            "```swift\n// typecheck: ios18\nlet a = 1\n```\n"
            "```swift\n// typecheck: shared, continues the block above\nlet b = a\n```\n"
        )
        self.assertEqual(len(problems), 1)
        blocks, problems = extract(
            "```swift\n// typecheck: shared\nlet a = 1\n```\n"
            "```swift\n// typecheck: ios18, continues the block above\nlet b = a\n```\n"
        )
        self.assertEqual(problems, [])
        self.assertIn("let a = 1", blocks[1].code)

    def test_a_manifest_keeps_its_tools_version_line_first(self) -> None:
        blocks, problems = extract(
            "```swift\n// swift-tools-version: 6.0\n// typecheck: none — a package manifest\nimport PackageDescription\n```\n"
        )
        self.assertEqual(problems, [])
        self.assertEqual(blocks[0].kind, "none")
        self.assertTrue(blocks[0].code.startswith("// swift-tools-version: 6.0"))

    def test_the_release_before_26_is_18(self) -> None:
        self.assertEqual(typecheck_samples.previous_ios(26), 18)
        self.assertEqual(typecheck_samples.previous_ios(18), 17)
        self.assertEqual(typecheck_samples.previous_ios(27), 26)

    def test_android_package_has_one_target_per_shared_block(self) -> None:
        blocks, _ = extract(
            "```swift\n// typecheck: shared\nlet a = 1\n```\n"
            "```swift\n// typecheck: ios18\nlet b = 1\n```\n"
            "```swift\n// typecheck: shared\nlet c = 1\n```\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            targets = typecheck_samples.write_android_package(
                [b for b in blocks if b.kind == "shared"], Path(directory)
            )
            manifest = (Path(directory) / "Package.swift").read_text(encoding="utf-8")
        self.assertEqual(len(targets), 2)
        self.assertEqual(manifest.count(".target(name:"), 2)


class RepositoryBlockTests(unittest.TestCase):
    def test_every_block_in_the_repository_is_tagged(self) -> None:
        # An untagged block would silently escape every check.
        _, problems = typecheck_samples.tagged_blocks(typecheck_samples.documents())
        self.assertEqual(problems, [])

    def test_ios_tags_stay_between_the_floor_and_the_ci_ceiling(self) -> None:
        blocks, _ = typecheck_samples.tagged_blocks(typecheck_samples.documents())
        for block in blocks:
            if block.kind == "ios":
                with self.subTest(f"{block.source.name}:{block.line}"):
                    self.assertGreaterEqual(block.ios, typecheck_samples.IOS_FLOOR)
                    self.assertLessEqual(block.ios, typecheck_samples.CI_IOS_CEILING)

    def test_json_blocks_parse(self) -> None:
        blocks, _ = typecheck_samples.tagged_blocks(typecheck_samples.documents())
        self.assertEqual(typecheck_samples.check_json(blocks), 0)


@unittest.skipUnless(shutil.which("xcrun"), "needs Xcode")
class TypecheckTests(unittest.TestCase):
    def test_reference_samples_typecheck_on_apple_platforms(self) -> None:
        self.assertEqual(typecheck_samples.main([]), 0)


if __name__ == "__main__":
    unittest.main()

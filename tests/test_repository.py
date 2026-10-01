from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SKILLS = sorted(path.name for path in (ROOT / "skills").iterdir() if path.is_dir())
OWN_PREFIX = "swift-android-"
# Names that start with the prefix but are not skills of this repository.
NOT_SKILLS = {"swift-android-skills", "swift-android-action", "swift-android-examples",
              "swift-android-sdk-checksum", "swift-android-action-release", "swift-android-agent-skill"}
OFFICIAL_SKIP_SKILLS = {
    "skip-app-walkthrough", "skip-project-creation", "building-skip-ui", "skip-fuse",
    "skip-lite-transpilation", "skip-frameworks", "skip-icons", "skip-localization",
    "skip-testing", "skip-ui-automation", "skip-deployment",
}
# A version that will rot: dotted releases of tools, and any NDK, API level or JDK number.
# "Swift 6 language mode" stays allowed; "Swift 6.4", "NDK r30" and "API 28" do not.
VERSION = re.compile(
    r"\b(?:Swift|Skip|swift-java|Xcode|Gradle|Kotlin)\s+\d+\.\d+(?:\.\d+)?\b"
    r"|\b(?:NDK|API level|API|JDK|Java|minSdk)\s+r?\d+[a-z]?\b"
)
TEXT_SUFFIXES = {".md", ".py", ".json", ".yml", ".yaml", ".swift", ".kt", ".kts", ".txt", ".sh", ".svg", ".toml"}


def frontmatter(skill: str) -> dict[str, str]:
    text = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert match, f"{skill}: missing frontmatter"
    fields: dict[str, str] = {}
    current = None
    for line in match.group(1).splitlines():
        if re.match(r"^[a-z_-]+:", line):
            key, _, value = line.partition(":")
            current = key.strip()
            fields[current] = value.strip()
        elif current:
            fields[current] = (fields[current] + " " + line.strip()).strip()
    if fields.get("description", "").startswith(">-"):
        fields["description"] = fields["description"][2:].strip()
    return fields


def body(skill: str) -> str:
    text = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    return re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)


def tracked_text_files() -> list[Path]:
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                            cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        paths = [path for path in ROOT.rglob("*") if ".git" not in path.parts]
    else:
        paths = [ROOT / line for line in result.stdout.splitlines()]
    return [path for path in paths if path.is_file() and path.suffix in TEXT_SUFFIXES]


class ManifestTests(unittest.TestCase):
    def test_json_manifests_parse(self) -> None:
        for relative in (
            ".claude-plugin/plugin.json",
            ".claude-plugin/marketplace.json",
            ".cursor-plugin/plugin.json",
            "package.json",
        ):
            with self.subTest(relative):
                json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_every_manifest_lists_every_skill(self) -> None:
        plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        cursor = json.loads((ROOT / ".cursor-plugin/plugin.json").read_text(encoding="utf-8"))
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        for name, paths in (
            ("plugin.json", plugin["skills"]),
            ("cursor plugin.json", cursor["skills"]),
            ("package.json", package["pi"]["skills"]),
        ):
            with self.subTest(name):
                self.assertEqual(sorted(Path(p).name for p in paths), SKILLS)
                for path in paths:
                    self.assertTrue((ROOT / path / "SKILL.md").is_file(), path)

    def test_versions_agree(self) -> None:
        plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        cursor = json.loads((ROOT / ".cursor-plugin/plugin.json").read_text(encoding="utf-8"))
        entry = next(p for p in marketplace["plugins"] if p["name"] == plugin["name"])
        self.assertEqual(marketplace["version"], plugin["version"])
        self.assertEqual(entry["version"], plugin["version"])
        self.assertEqual(cursor["version"], plugin["version"])
        openai = (ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn(f'version: "{plugin["version"]}"', openai)
        for skill in SKILLS:
            self.assertIn(f"  - {skill}\n", openai)


class SkillTests(unittest.TestCase):
    def test_frontmatter(self) -> None:
        for skill in SKILLS:
            with self.subTest(skill):
                fields = frontmatter(skill)
                self.assertEqual(set(fields), {"name", "description"})
                self.assertEqual(fields.get("name"), skill)
                description = fields.get("description", "")
                self.assertGreater(len(description), 200)
                self.assertLessEqual(len(description), 1024)
                self.assertTrue(description.startswith("Use this skill when"))
                self.assertIn("Not for", description)

    def test_referenced_files_exist(self) -> None:
        pattern = re.compile(r"`((?:references|scripts)/[\w./-]+\.(?:md|py|swift|json))")
        for skill in SKILLS:
            directory = ROOT / "skills" / skill
            for document in [directory / "SKILL.md", *sorted((directory / "references").glob("*.md"))]:
                text = document.read_text(encoding="utf-8")
                for relative in set(pattern.findall(text)):
                    with self.subTest(file=str(document.relative_to(ROOT)), reference=relative):
                        in_skill = (directory / relative).is_file()
                        in_skill_references = (directory / "references" / Path(relative).name).is_file()
                        in_repository = (ROOT / relative).is_file()
                        self.assertTrue(in_skill or in_skill_references or in_repository, relative)

    def test_sibling_references_named_in_prose_exist(self) -> None:
        pattern = re.compile(r"`([a-z-]+\.md)`")
        for skill in SKILLS:
            references = ROOT / "skills" / skill / "references"
            names = {path.name for path in references.glob("*.md")}
            for document in [ROOT / "skills" / skill / "SKILL.md", *sorted(references.glob("*.md"))]:
                for name in set(pattern.findall(document.read_text(encoding="utf-8"))):
                    with self.subTest(file=str(document.relative_to(ROOT)), reference=name):
                        self.assertTrue(name in names or (ROOT / name).is_file(), name)

    def test_skill_names_referenced_in_docs_exist(self) -> None:
        pattern = re.compile(r"\bswift-android-[a-z-]+[a-z]\b")
        documents = [*(ROOT / "skills").rglob("*.md"), *(ROOT / "references").glob("*.md"),
                     ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "CHECKS.md", ROOT / "scripts/android_scan.py"]
        for path in documents:
            if not path.is_file():
                continue
            text = re.sub(r"https?://\S+|[\w.-]+/swift-android-[\w.-]+", "", path.read_text(encoding="utf-8"))
            for name in set(pattern.findall(text)) - NOT_SKILLS:
                with self.subTest(file=str(path.relative_to(ROOT)), name=name):
                    self.assertIn(name, SKILLS)

    def test_official_skip_skills_named_in_descriptions_are_real(self) -> None:
        # The "Not for" clauses route work to Skip's skills by name; a typo would route nowhere.
        candidates = re.compile(r"\b(?:skip|building-skip)-[a-z-]+[a-z]\b")
        for skill in SKILLS:
            description = frontmatter(skill)["description"]
            for name in set(candidates.findall(description)):
                with self.subTest(skill=skill, name=name):
                    self.assertIn(name, OFFICIAL_SKIP_SKILLS)

    def test_official_skills_reference_lists_all_eleven(self) -> None:
        text = (ROOT / "references" / "official-skip-skills.md").read_text(encoding="utf-8")
        for name in OFFICIAL_SKIP_SKILLS:
            with self.subTest(name):
                self.assertIn(f"`{name}`", text)
        self.assertRegex(text, r"github\.com/skiptools/skills/(?:blob|tree)/[0-9a-f]{40}/")

    def test_skill_bodies_leave_version_numbers_to_versions_md(self) -> None:
        # Versions rot fastest; SKILL.md points at references/versions.md instead of repeating them.
        for skill in SKILLS:
            with self.subTest(skill):
                self.assertEqual(VERSION.findall(body(skill)), [])
                self.assertIn("versions.md", body(skill))

    def test_copies_in_sync(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/sync_skill_copies.py"), "--check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)


class SourceRuleTests(unittest.TestCase):
    def test_measured_claims_point_at_measured_sections(self) -> None:
        measured = (ROOT / "references" / "measured-behavior.md").read_text(encoding="utf-8")
        sections = {}
        for match in re.finditer(r"^## (M\d+)\b.*?(?=^## |\Z)", measured, re.S | re.M):
            sections[match.group(1)] = re.search(r"Status:\**\s*measured", match.group(0)) is not None
        claim = re.compile(r"\*Measured\* (M\d+)|Measured: (M\d+)")
        documents = [*(ROOT / "skills").rglob("*.md"), *(ROOT / "references").glob("*.md"), ROOT / "CHECKS.md",
                     ROOT / "README.md", ROOT / "scripts" / "android_scan.py"]
        for path in documents:
            if not path.is_file() or path.name == "measured-behavior.md":
                continue
            for match in claim.findall(path.read_text(encoding="utf-8")):
                section = match[0] or match[1]
                with self.subTest(file=str(path.relative_to(ROOT)), section=section):
                    self.assertIn(section, sections)
                    self.assertTrue(sections[section], f"{section} is cited as measured but not marked measured")

    def test_versions_md_dates_every_row(self) -> None:
        text = (ROOT / "references" / "versions.md").read_text(encoding="utf-8")
        rows = [line for line in text.splitlines()
                if line.startswith("|") and not set(line) <= set("|- :") and "As of" not in line]
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(row[:60]):
                self.assertRegex(row, r"20\d\d-\d\d-\d\d")


class SetupCommandTests(unittest.TestCase):
    def test_sdk_setup_commands_are_the_ones_ci_runs(self) -> None:
        # The SDK skill repeats swift.org's commands; CI runs the same lines, so a moved checksum fails here.
        setup = (ROOT / "skills/swift-android-sdk/references/sdk-setup.md").read_text(encoding="utf-8")
        section = setup.split("## swift.org's commands", 1)[1]
        block = re.search(r"```bash\n(.*?)```", section, re.S)
        self.assertIsNotNone(block)
        workflow = {line.strip() for line in (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8").splitlines()}
        commands = [line.strip() for line in block.group(1).splitlines() if line.strip()]
        self.assertTrue(any(line.startswith("swift sdk install") for line in commands))
        for line in commands:
            if line.startswith("swiftly "):
                continue  # CI pins the toolchain version instead of `latest`
            with self.subTest(line):
                self.assertIn(line, workflow)

    def test_ci_pins_the_toolchain_the_sdk_url_names(self) -> None:
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        version = re.search(r'SWIFT_VERSION: "([\d.]+)"', workflow).group(1)
        self.assertIn(f"swift-{version}-release/android-sdk/swift-{version}-RELEASE/", workflow)
        self.assertIn(f"SWIFT_SDK_ID: swift-{version}-RELEASE_android", workflow)


class PublicationTests(unittest.TestCase):
    def test_no_model_ids_or_local_paths_in_files(self) -> None:
        # Pushed files name models through $AGENT_MODEL / $JUDGE_MODEL, and never a local home directory.
        model = re.compile(r"claude-(?:opus|sonnet|haiku|fable)|gpt-\d|gemini-\d", re.I)
        local = re.compile(r"/Users/[A-Za-z]|/home/runner/work/.+/swift-android/")
        for path in tracked_text_files():
            if path.resolve() == Path(__file__).resolve():
                continue  # this file spells the patterns out
            text = path.read_text(encoding="utf-8", errors="replace")
            with self.subTest(str(path.relative_to(ROOT))):
                self.assertIsNone(model.search(text), "model id")
                self.assertIsNone(local.search(text), "local path")


class EvalTests(unittest.TestCase):
    def test_every_skill_has_skill_creator_evals(self) -> None:
        for skill in SKILLS:
            with self.subTest(skill):
                directory = ROOT / "skills" / skill / "evals"
                evals = json.loads((directory / "evals.json").read_text(encoding="utf-8"))
                self.assertEqual(evals["skill_name"], skill)
                ids = [item["id"] for item in evals["evals"]]
                names = [item["name"] for item in evals["evals"]]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertEqual(len(names), len(set(names)))
                for item in evals["evals"]:
                    self.assertTrue(item["expectations"])
                    for relative in item["files"]:
                        self.assertTrue((ROOT / "skills" / skill / relative).exists(), relative)

    def test_eval_expectations_carry_no_version_numbers(self) -> None:
        # Versions move; an expectation that pins one fails for the wrong reason a month later.
        for skill in SKILLS:
            evals = json.loads((ROOT / "skills" / skill / "evals" / "evals.json").read_text(encoding="utf-8"))
            for item in evals["evals"]:
                for expectation in item["expectations"]:
                    with self.subTest(skill=skill, case=item["name"]):
                        self.assertIsNone(VERSION.search(expectation), expectation)

    def test_trigger_evals_mix_positive_and_negative(self) -> None:
        for skill in SKILLS:
            with self.subTest(skill):
                path = ROOT / "skills" / skill / "evals" / "trigger-evals.json"
                items = json.loads(path.read_text(encoding="utf-8"))
                self.assertGreaterEqual(len(items), 16)
                positives = sum(item["should_trigger"] for item in items)
                self.assertGreaterEqual(positives, 6)
                self.assertGreaterEqual(len(items) - positives, 6)


if __name__ == "__main__":
    unittest.main()

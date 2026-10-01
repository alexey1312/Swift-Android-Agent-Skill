# Agent guidance

This repository contains Agent Skills that advise on and change Swift code meant to run on Android:
choosing the route, a shared Swift core under native Kotlin and Compose UI,
and the Swift SDK for Android with swift-java.
They work next to Skip's official skills (`skiptools/skills`), not instead of them.

- **Phase 1 stays read-only.**
  `android_scan.py` and `toolchain_report.py` never write to the scanned project or the machine;
  `test_scan_does_not_modify_files` and the toolchain report's command allowlist guard them.
  Installing a toolchain, an SDK or an NDK is a Phase 2 change that needs approval.
- **Every rule cites a source.**
  A scanner rule's `source` names a page (`skip.dev › …`, `docs.swift.org › …`, `swift.org › …`),
  a forum thread with its date (`Swift Forums › … (YYYY-MM-DD)`),
  a file in a repository (`GitHub › owner/repo …`),
  or a CI measurement (`Measured: M<n>`); the metadata test enforces the format.
- **Only Android CI measures.**
  A statement is *Measured* only if `.github/workflows/android.yml` produced it
  and `references/measured-behavior.md` records the run URL, date, SDK and NDK
  under a section marked `Status: measured`; a test enforces it.
  A macOS typecheck proves the Swift is well formed on Apple platforms, nothing more:
  Objective-C interop, one Foundation module and Combine all exist there.
- **Samples are tagged.**
  Every Swift or Kotlin block in a skill or reference starts with
  `// typecheck: shared` (built for Apple platforms here and for Android in CI),
  `// typecheck: ios<N>` (compiles for iOS N, fails for the release before it, N ≤ the CI ceiling),
  or `// typecheck: none — <reason>`.
  Run `python3 scripts/typecheck_samples.py`.
- **The skills' own code scans clean.**
  `OwnAdviceTests` scans every `shared` block as shared code; only `info` findings may remain.
- **Shared files have one source.**
  Edit `references/*.md` and `scripts/{android_scan,toolchain_report}.py` at the root,
  then run `python3 scripts/sync_skill_copies.py`; never edit the copies inside `skills/`.
- **Versions live in one place.**
  Every version, URL, checksum, API level and size goes in `references/versions.md`
  with the date it was checked and how to re-check it.
  The one exception is the SDK skill's `sdk-setup.md`,
  which repeats swift.org's install commands verbatim;
  a test keeps them identical to the ones `android.yml` runs.
  SKILL.md bodies and eval expectations carry no version numbers (a test checks both).
- **Skip's official skills own Skip's ground.**
  Route project creation, `skip.yml`, SwiftUI on Android, icons, localization,
  test runners and store release to them by name.
  Where they disagree with skip.dev, say so in `references/official-skip-skills.md`,
  pinned to a commit, with a way to re-check.
- **Licences.**
  skip.dev documentation is CC-BY-SA-4.0: paraphrase it, quote at most one attributed sentence.
  Forum posts: quote at most one sentence, with the author's handle and the date,
  and present a single team's report as a report.
  Do not copy third-party code; link it pinned to a commit.
  Actions without a licence are only referenced with `uses:`.
- **No model ids and no local paths** in any file.
  Commands name models through `$AGENT_MODEL` and `$JUDGE_MODEL`; a test enforces both.
- **Scanner changes need tests** for a positive and a negative case, a guard case when relevant,
  and a row in `CHECKS.md`.
- **Behavior changes need evals.**
  Each skill keeps skill-creator evals in `skills/<skill>/evals/`
  (`evals.json` with fixture projects under `files/`, and `trigger-evals.json`).
  Re-run them before claiming an improvement (`CONTRIBUTING.md`);
  `scripts/package_skills.py` leaves `evals/` out of release archives.
- **Keep SKILL.md descriptions between 200 and 1024 characters**,
  starting with "Use this skill when" and naming what the skill is not for;
  `name` equals the directory name.
- **Markdown uses semantic line breaks**: one sentence per line, breaks at clause boundaries,
  never inside code, tables or frontmatter.
- Keep the plugin version identical in `.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json` and `agents/openai.yaml`.
  A GitHub release is cut by pushing a matching `vX.Y.Z` tag.
- Run before completing a change:

  ```bash
  python3 scripts/sync_skill_copies.py --check
  python3 -m unittest discover -s tests -v
  python3 scripts/typecheck_samples.py
  swift test --package-path samples/SharedCore
  ```

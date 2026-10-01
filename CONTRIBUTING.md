# Contributing

Thanks for helping keep these skills accurate.
Swift on Android moves fast — the SDK, Skip and swift-java all ship every few weeks —
so the most valuable contributions are re-checks.

## Good contributions

- **Re-checked versions.**
  Every row of `references/versions.md` says when it was checked and how to re-check it.
  Update the value and the date together; the weekly `drift` job in `android.yml` flags what moved.
- **Measurements on Android.**
  A new compile probe under `scripts/probes/android/` with its expectation,
  or a test in `samples/SharedCore` that runs on the emulator,
  turns a cited claim into a measured one.
  Record the run in `references/measured-behavior.md` (run URL, date, SDK, NDK, runner).
- **Scanner rules.**
  Add a `Rule` to `scripts/android_scan.py` with a source,
  a positive and a negative test in `tests/test_android_scan.py`
  (and a guard case if `#if` can hide the pattern),
  and a row in `CHECKS.md`; then run `python3 scripts/sync_skill_copies.py`.
- **False positives** found on real projects, with a minimal reproduction.
- **Evals** for behavior the skills get wrong:
  a case in `skills/<skill>/evals/evals.json` with a small fixture project,
  or a query in `trigger-evals.json`.
  Queries that belong to Skip's official skills make good negatives.

## Rules

- Guidance traces to skip.dev, swift.org or docs.swift.org, a repository file, a forum thread,
  or an Android CI run. Label anything else as *inference*.
- skip.dev is CC-BY-SA-4.0: paraphrase; quote at most one sentence, attributed.
- Third-party code is linked, pinned to a commit, never copied.
- No third-party Python dependencies.
- No model ids and no local paths in any file.

## Evaluating a change

The skills are developed with Anthropic's
[skill-creator](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator):
run each eval with and without the skill, grade the expectations,
aggregate a benchmark, and review outputs in its viewer.
Trigger accuracy is tuned with its `run_loop` against `trigger-evals.json`
(run it with one worker: parallel workers share one commands directory
and report false negatives).
Keep workspaces outside the repository (`*-workspace/` is ignored).

People who use these skills usually have Skip's official skills installed as well,
so the benchmark compares two stages that both carry Skip's skills —
Skip's alone, and Skip's plus these —
built by `scripts/build_plugin_evals.py` outside the repository
(the expectations are the answer key, so neither stage contains `evals/`):

```bash
skip="$HOME/.claude/plugins/cache/skiptools-skills"
extra=(--extra-skills "$skip"/skip-app-design/*/skills --extra-skills "$skip"/skip-testing-deployment/*/skills)
python3 scripts/build_plugin_evals.py "$TMPDIR/sa-skip-only" --without-own-skills "${extra[@]}"
python3 scripts/build_plugin_evals.py "$TMPDIR/sa-skip-plus-ours" "${extra[@]}"
for stage in sa-skip-only sa-skip-plus-ours; do
  claude plugin eval "$TMPDIR/$stage" --ablation none --trust-plugin --scaffold \
    --allow-tools Bash Edit Write --model "$AGENT_MODEL" --judge-model "$JUDGE_MODEL" \
    --no-publish --max-cost-usd 14 --json "$TMPDIR/$stage.json"
done
```

Disable the user-scope copies of Skip's plugins while it runs
(`claude plugin disable skip-app-design@skiptools-skills` and the same for `skip-testing-deployment`),
so neither stage loads them twice, and enable them afterwards.
Set `AGENT_MODEL` to the model under test and `JUDGE_MODEL` to the grader,
and keep both fixed across runs you compare.
`--no-publish` keeps the HTML report local; without it the report is published.
The runner's `costUsd` leaves out the judge,
so set `--max-cost-usd` to about two thirds of the real budget.
Use `--only <case>` for a pilot.
Before trusting a run, read a few failing transcripts:
a grader can be wrong as easily as an agent.

## Checks

```bash
python3 scripts/sync_skill_copies.py --check
python3 -m unittest discover -s tests -v
python3 scripts/typecheck_samples.py
swift test --package-path samples/SharedCore
python3 scripts/toolchain_report.py --format markdown
```

Android builds, probes and emulator tests run only in CI (`.github/workflows/android.yml`),
unless `toolchain_report.py` says this machine can build for Android.

## Releasing

1. Bump the version in `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
   `.cursor-plugin/plugin.json` and `agents/openai.yaml` (the tests check they agree)
   and merge it to `main`.
2. Tag that commit and push the tag:

   ```bash
   git tag v1.0.0 && git push origin v1.0.0
   ```

The `Release` workflow refuses a tag that does not match the plugin version,
re-runs the tests, builds one `.skill` archive per skill with
`scripts/package_skills.py`, and publishes a GitHub release.

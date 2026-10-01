# Benchmark — 2026-10-01

Ten cases, run with `claude plugin eval` on plugin version **1.0.0** (commit `23525f8`),
Claude Code 2.1.285.
People who use these skills usually have Skip's official skills installed too,
so both stages carry Skip's eleven skills (`skiptools/skills` at `0399f0a`):
**Skip only**, and **Skip plus these two**.
Each stage ran with `--ablation none`,
with the user-scope copies of Skip's plugins disabled so neither stage loaded them twice.
One agent model and a separate, smaller judge model, both fixed for the whole run;
three runs per case and stage, three judge votes per criterion.
607 s and 762 s at four runs in parallel per stage,
**$37.57** — $27.88 for the agents and $9.69 for the judge —
after a four-case pilot that cost $5.25.

```bash
skip="$HOME/.claude/plugins/cache/skiptools-skills"
extra=(--extra-skills "$skip"/skip-app-design/*/skills --extra-skills "$skip"/skip-testing-deployment/*/skills)
python3 scripts/build_plugin_evals.py "$TMPDIR/sa-skip-only" --without-own-skills "${extra[@]}"
python3 scripts/build_plugin_evals.py "$TMPDIR/sa-skip-plus-ours" "${extra[@]}"
claude plugin eval "$TMPDIR/sa-skip-only" --ablation none --trust-plugin --scaffold \
  --allow-tools Bash Edit Write --model "$AGENT_MODEL" --judge-model "$JUDGE_MODEL" \
  --no-publish --runs 3 -j 4 --max-cost-usd 13 --threshold 0
claude plugin eval "$TMPDIR/sa-skip-plus-ours" --ablation none --trust-plugin --scaffold \
  --allow-tools Bash Edit Write --model "$AGENT_MODEL" --judge-model "$JUDGE_MODEL" \
  --no-publish --runs 3 -j 4 --max-cost-usd 15 --threshold 0
```

`skip-only.json` and `skip-plus-ours.json` are the runner's results reduced by `scripts/strip_eval_result.py`:
scores, every judge vote, turns and cost per run — no transcripts, local paths or model ids.
`pilot-*.json` are the pilot's.

| Case | Skip only | Skip + these | Δ |
| --- | --- | --- | --- |
| `compose-never-updates` | 0.47 (0/3) | **1.00** (3/3) | **+0.53** |
| `platform-pay-boundary` | 0.39 (0/3) | **0.94** (2/3) | **+0.55** |
| `make-shared-target-android-ready` | 0.46 (0/3) | **0.88** (1/3) | **+0.42** |
| `stale-viewmodel-in-compose` | 0.60 (0/3) | **1.00** (3/3) | **+0.40** |
| `apk-size` | 0.47 (0/3) | **0.87** (2/3) | **+0.40** |
| `call-swift-from-kotlin-without-skip` | 0.53 (0/3) | **0.87** (1/3) | **+0.33** |
| `route-for-existing-ios-app` | 0.62 (0/3) | **0.90** (1/3) | **+0.29** |
| `dlopen-observation-crash` | 0.83 (0/3) | **1.00** (3/3) | **+0.17** |
| `setup-swift-sdk` | 0.28 (0/3) | **1.00** (1/1 graded) | **+0.72** |
| `fuse-or-lite-new-app` | **0.50** (0/3) | 0.39 (0/3) | −0.11 |
| **Mean** | 0.515 | **0.885** | **+0.37** |

Scores are the mean share of criteria passed; the count is runs that passed every criterion.
The runner itself reports 0.818 for the second stage,
because it scores the two `setup-swift-sdk` runs it never graded as zero (below).

## Read the failures before citing these numbers

- **Two runs were not graded.**
  The second stage reached its cost ceiling while `setup-swift-sdk` runs 2 and 3 were in flight,
  so the runner skipped their paid graders (`skipped: cost ceiling`) and scored them 0.
  The table uses the one graded run; counting the two as zero gives 0.818.
- **On "Fuse or Lite?" these skills never loaded.**
  In all six `fuse-or-lite-new-app` runs Skip's own `skip-fuse` answered,
  whose description claims "deciding between Lite and Fuse for a new app".
  It recommended Fuse for this team every time —
  but without skip.dev's own recommendation, without slower builds among the costs,
  and without noticing that it tells agents to default to Lite (`official-skip-skills.md`).
  Both stages therefore measured the same skill; the −0.11 is run-to-run variation.
  This is the trigger collision the design review predicted.
  The architecture skill's description is at its length limit,
  so the case stays as it is until trigger evals show a better description.
- **Real failures with the skills** (three runs):
  one `make-shared-target-android-ready` run left three `Analytics.shared.track` calls in the view model;
  another could not build — the eval sandbox blocks `swift build` — and did not fall back to a typecheck,
  which both skills now tell it to do;
  and `fuse-or-lite-new-app` above.
- **Judge or criterion errors** (five, all reading the final message):
  `route-for-existing-ios-app` run 2 contrasts its route with "a Skip Fuse app with SwiftUI on both platforms" — the trade-off the criterion asks for;
  `apk-size` run 2 notes the listing already ships only `arm64-v8a`, so ABI splits save nothing yet — correct, and the criterion has been reworded to accept it;
  the same run attributes and dates every borrowed size and says to measure the compressed APK;
  `call-swift-from-kotlin-without-skip` runs 2 and 3 pin swift-java because it is pre-1.0,
  naming the version with a dated source — the criterion's "instead of asserting a version" was read as forbidding any version,
  and has been reworded.
  Counting these five as passes gives **0.916** for the second stage.
- **Left as failed, though debatable:**
  `platform-pay-boundary` run 2 injects the Google Pay client where the checkout screen is built rather than at app startup,
  arguing that Google Pay needs an `Activity`.
- **The first stage was not re-read**; its scores are as graded.

## What the Δ measures

The value of adding these skills to Skip's official ones,
for prompts about sharing Swift with Android and building it with the Swift SDK —
not a comparison with no skills at all.
The largest gains are where Skip's skills say nothing:
Combine and streams at the boundary, Compose lifetimes, platform services, packaging the runtime, swift-java.

## Cost

| | Agents | Judge | Total |
| --- | --- | --- | --- |
| Pilot, 4 cases × 1 run × 2 stages | $4.18 | $1.07 | $5.25 |
| Full, 10 cases × 3 runs × 2 stages | $27.88 | $9.69 | $37.57 |

The runner's cost ceiling is checked before each run starts,
so runs already in flight finish past it: the second stage's agents cost $15.76 against a ceiling of $15.
`costUsd` leaves out the judge (`CONTRIBUTING.md`).

## Not measured

- Trigger accuracy: `trigger-evals.json` has not been run through skill-creator's `run_loop`.
- Other agent models.
- The edit cases ran in a sandbox without an Android toolchain;
  nothing an agent wrote was built for Android in this benchmark.

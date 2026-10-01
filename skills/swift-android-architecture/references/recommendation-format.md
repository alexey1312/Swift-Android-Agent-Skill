# Recommendation format

Use this shape for every recommendation,
whether it comes from the scanner or from reading code.
Each item has a stable ID the developer can approve,
and nothing changes until they do.

## Per item

```markdown
### AND-03 · Import FoundationNetworking where the API client uses URLSession

- **Finding:** `AND005:Sources/TripCore/APIClient.swift:12` — `URLSession.shared.data(for:)` with no `FoundationNetworking` import
- **What breaks on Android:** the file does not compile there;
  URLSession and its types live in a separate module off Apple platforms.
- **Route:** shared core under native Compose UI (`swift-android-architecture` › Routes)
- **Source:** docs.swift.org › Building for Android; skip.dev › Porting
- **Owner:** `swift-android-sdk` (portability)
- **Change:** add the `#if canImport(FoundationNetworking)` import ladder at the top of the file.
- **Verifiable here?** macOS typecheck only — it cannot show the Android failure;
  the Android compile runs in CI (`references/ci.md`).
- **Risk:** low — no behavior change on iOS.
- **Verify:** `swift build --swift-sdk <android sdk>` in CI; rescan, `AND005` gone.
- **Status:** proposed
```

## Rules

- **IDs are stable** across a session (`AND-01`, `AND-02`, …).
  A scanner finding keeps its own ID (`AND005:path:line`) in the *Finding* line.
- **One source per item:** a skip.dev, swift.org or docs.swift.org page,
  a repository file, a forum thread with its date, or a measured section (`Measured: M<n>`).
  Version-sensitive facts link `versions.md` and say "as of" the date there.
  If the advice is your own reasoning, label it *inference* and say what it rests on.
  A single team's experience report (`sources.md` › The Polymarket report) is labelled as a report.
- **Name the owner.**
  When the fix is Skip's ground — `skip.yml`, SwiftUI views on Android, icons, localization,
  test runners, store release — the owner is the official Skip skill that covers it
  (`official-skip-skills.md`), not this one.
- **Say what can be verified here.**
  Run `python3 scripts/toolchain_report.py` first.
  Without an Android SDK and NDK, nothing about Android is verified on this machine:
  a macOS typecheck is not an Android build, and an Android build is not a run.
  Items that need a device, an emulator, Android Studio or a Play upload say so.
- **Order:** route and blockers, then what stops compiling on Android,
  then the boundary (shared targets, platform services, view models),
  then crossing to Kotlin and object lifetimes,
  then build, CI and size.
- **Status values:** `proposed`, `approved`, `applied`, `verified`, `blocked`
  (with the reason), `declined`, `kept` (left as is, with the reason).
- **Batch approval is fine** when the developer names it ("apply AND-01 to AND-05").
  "Make it build for Android" before a plan exists means: produce the plan.

## Report skeleton

```markdown
# Swift on Android — <project>

Toolchain: <toolchain_report.py summary> · Route: <route> · Shared targets: <names>
Scan: android_scan <version>, <n> files, <n> findings above info

## Summary
<What should run on Android, by which route, what blocks it now, what this machine can verify.>

## Route and blockers
## Compile on Android
## Boundary
## Crossing to Kotlin and lifetimes
## Build, CI and size
## Kept as is
## Not verified
```

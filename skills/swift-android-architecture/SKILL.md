---
name: swift-android-architecture
description: >-
  Use this skill when Swift code from an iOS app should also run on Android:
  choosing the route (Skip Fuse with SwiftUI on both platforms, a shared Swift
  core under native Kotlin/Compose UI via skip export, Skip Lite, or the bare
  Swift SDK), auditing a Swift package for what blocks
  Android (UIKit, SwiftUI or MapKit in shared targets, Combine at the Kotlin
  boundary, URLSession without FoundationNetworking, the Objective-C
  runtime), and designing the shared core: platform services as Swift
  protocols implemented in Kotlin, @Observable view models with an input enum,
  AsyncStream instead of publishers, closures Skip can bridge, stale state and
  zombie subscriptions when Compose keeps a Swift view model alive, Android
  tests on every pull request. Not for scaffolding a Skip project, skip.yml
  options, SwiftUI views on Android, icons, localization or store release
  (skip-project-creation, skip-fuse, building-skip-ui, skip-icons,
  skip-localization, skip-deployment), or toolchain and packaging problems
  (swift-android-sdk).
---

# Swift on Android: architecture

Decide what to share, and which compiler runs it on Android, before any code moves.
Share everything that is not UI or a platform SDK.
Make each platform capability a Swift protocol that each app implements natively.
Keep view models plain `@Observable` state machines,
and let the Android side own their lifetime explicitly.

A production app built this way —
about 170,000 lines of shared Swift under a native Compose UI —
is described in the Polymarket report (`references/sources.md`).
Skip's official skills cover the Skip project itself;
this skill covers the decision, the shared core and the boundary,
and says where those skills disagree with skip.dev (`references/official-skip-skills.md`).

- Routes and their trade-offs: `references/routes.md`
- The boundary and platform services: `references/boundary.md`
- View models: `references/view-models.md`
- Lifetimes under Compose: `references/compose-lifetime.md`
- The export loop and CI: `references/aar-workflow.md`
- What crosses to Kotlin: `references/bridge-surface.md`
- CI recipes: `references/ci.md`
- Versions, sizes and dates: `references/versions.md`
- What CI measured: `references/measured-behavior.md`
- Skip's skills, and where they disagree with skip.dev: `references/official-skip-skills.md`
- Plan format: `references/recommendation-format.md`
- Citations: `references/sources.md`
- A starter shared core with tests: `samples/SharedCore` in this skill's repository

## Contract

- **Phase 1 is read-only.**
  Scanning, the toolchain report, reading code and writing the plan change nothing.
- **No edits without approval of item IDs** (`references/recommendation-format.md`).
  "Make it work on Android" before a plan exists is a request for the plan.
- **This machine decides what can be verified.**
  Run `python3 scripts/toolchain_report.py` first.
  Without an Android Swift SDK and an NDK nothing about Android is verified here;
  installing them, or running `skip checkup`, changes the machine and needs approval.
- **Cite a source for every item:** a skip.dev, swift.org or docs.swift.org page,
  a repository file, a forum thread with its date, or a measured section of `measured-behavior.md`.
  Versions and sizes come from `references/versions.md`, with its date.
  One team's experience is a report, not a rule.
  Anything else is labelled *inference*.
- **Report verification honestly.**
  A build for macOS or iOS proves nothing about Android:
  Objective-C interop, a single Foundation module and Combine all exist there.
  An Android build proves it compiles;
  only tests on an emulator or a device prove behavior, and only what they assert.

## 1. Choose the route

| Route | Shared | Android UI | How Swift reaches Android | Who owns it |
| --- | --- | --- | --- | --- |
| Skip Fuse app | models, logic and SwiftUI | SwiftUI rendered as Compose by Skip | natively compiled Swift, bridged by Skip | Skip's skills (`skip-fuse`, `building-skip-ui`) |
| Shared core, native UI | models, networking, view models | Kotlin and Compose written by the Android team | Skip native modules exported as Android libraries | this skill |
| Skip Lite | as Fuse | as Fuse | Swift transpiled to Kotlin source | Skip's `skip-lite-transpilation` |
| Bare SDK | a Swift library | anything | Swift SDK for Android, swift-java or JNI | `swift-android-sdk` |

- **skip.dev recommends native (Fuse) modules for most apps**
  (skip.dev › Modes; skip.dev › Project Types).
  Skip's own agent skills tell agents to default to Lite;
  follow the documentation unless one of Lite's real advantages decides it
  (`references/routes.md`; `references/official-skip-skills.md`).
- **Pick a shared core under native UI** when an Android team will write Compose,
  when an Android app already exists,
  or when each platform should look and behave natively.
  **Pick a Fuse app** when one Swift team builds both apps from SwiftUI.
  **Pick the bare SDK** when there is no Skip in the project
  and the Swift is a library behind a small API.
- One app can mix routes per module (skip.dev › Modes);
  say which route each module takes.

## 2. What blocks sharing

```bash
python3 scripts/toolchain_report.py --format markdown
python3 scripts/android_scan.py <project-root> --route shared-core --format markdown
python3 scripts/android_scan.py <project-root> --route shared-core --format json > "$TMPDIR/android-scan.json"
```

- `--route` is one of `fuse-app`, `shared-core`, `lite`, `bare-sdk`;
  severities change with it (Combine is a blocker without Skip and information in a Fuse app).
  `--shared <target>` names targets to treat as shared when no `skip.yml` says so;
  with none, the scan is a survey of what could be shared.
- The scanner understands `#if` guards: code under `#if os(iOS)` or `#if canImport(UIKit)` is not flagged.
  Its matches are heuristics; read the code before a finding becomes an item.
  Rules and sources: `CHECKS.md` in this skill's repository.
- **Subclassing `NSObject` is not a blocker** —
  Foundation on other platforms provides it without an Objective-C runtime.
  `@objc`, `#selector`, key-value observing and swizzling are (rule `AND008`).
- Check every dependency's Android build before planning around it:
  Swift Package Index reports Android compatibility per package (`references/sources.md`).

## 3. The boundary

- **Split the package** into shared targets and iOS-only targets.
  Shared targets import Foundation, Observation and portable packages, nothing else;
  UIKit, SwiftUI (outside a Fuse UI module), MapKit, PassKit and other platform SDKs stay on the iOS side
  (`references/boundary.md`).
- **Make each platform capability a Swift protocol** in the shared code —
  payments, analytics, storage, notifications, authentication —
  implemented natively on each side and passed in when the app starts.
  Prefer initializer injection; a dependency-injection library is optional.
- How the Kotlin implementation reaches Swift depends on the route and the bridge;
  check it against `references/bridge-surface.md`, not memory.

## 4. View models

- A view model is a plain `@Observable` class:
  an `Input` enum in, observable state out, navigation through injected callbacks,
  no UIKit or SwiftUI (`references/view-models.md`).
  The same instance can drive SwiftUI, UIKit and Compose.
- Migrate `ObservableObject` and `@Published` one screen at a time.
- Keep Combine out of anything Kotlin sees:
  expose `async` functions and `AsyncStream` instead (rule `AND011`).
- `samples/SharedCore` holds a tested version of this pattern;
  its tests pass on an Android emulator (*Measured* M4).

## 5. Crossing to Kotlin

- Keep the public surface small and boring:
  value types, `async` functions, streams, and closures within the bridge's limits
  (`references/bridge-surface.md`; rules `AND011`, `AND012`).
- In a Fuse module, `#if !SKIP` code is compiled for Android too;
  use `#if !os(Android)` for iOS-only code (rule `AND010`).
- A Fuse module that uses `@Observable` must import SkipFuse,
  or Compose is not told about changes (rule `AND009`; Skip's `skip-fuse` owns the details).
- `skip.yml` options belong to Skip's `skip-fuse` skill.

## 6. Lifetimes under Compose

- Compose decides when objects are kept and reused, and Android's garbage collector decides
  when a Swift-backed object goes away.
  Never use `deinit` as a teardown hook on Android (`references/compose-lifetime.md`).
- Create one view model per navigation entry or presentation,
  and close it explicitly — cancel its tasks and subscriptions —
  when that entry leaves the back stack or the screen leaves composition.
- Stale data and subscriptions that outlive their screen are the symptoms;
  the Polymarket report describes both and the fix.

## 7. The export loop and CI

- Each shared module is exported as an Android library and consumed by Gradle
  like any other dependency (`references/aar-workflow.md`).
  Re-export after every Swift change; transitive Android dependencies go into the app's Gradle file.
- Gate every pull request that touches shared code:
  run the shared tests on an Android emulator and build the Android app
  (`references/ci.md`).
  A scan with `--fail-on high` catches a UIKit import before the build does.

## 8. Costs to plan for

- **App size:** the Swift runtime and Foundation ship inside the app;
  the figures in `references/versions.md` are reports, dated — measure your own.
- **Debugging:** no Swift breakpoints in Android Studio;
  LLDB works from the command line and VS Code (`references/versions.md`).
- **The export step** sits between a Swift edit and the Android build.
- **Closures** are the hardest part of the boundary; prefer `async` and streams.

## Workflow

### Phase 1 — Recommend

1. **Preflight.**
   `python3 scripts/toolchain_report.py`; the project's own agent instructions
   (`AGENTS.md`, `CLAUDE.md`); every `Package.swift` and `Skip/skip.yml`.
   Report what this machine can verify in the plan's header.
2. **Scan** with the route that fits (or a survey without one) and read what it found.
3. **Plan** with `references/recommendation-format.md`:
   route and blockers first, then what stops compiling on Android,
   then the boundary and view models,
   then crossing to Kotlin and lifetimes,
   then the export loop, CI and size.
   Name the owner of each item: this skill, `swift-android-sdk`, or one of Skip's skills.
4. **Ask** which item IDs to apply.

### Phase 2 — Apply and verify

1. Apply approved items only, one group at a time; change only what they name.
2. Build for Apple platforms after each group (`swift build`, or the project's own command).
   Where a sandbox blocks `swift build`, typecheck the changed files with `swiftc -typecheck`
   and say which check ran.
3. Re-run `android_scan.py`; the resolved findings should be gone.
4. Build for Android where `toolchain_report.py` says it can, or say which CI job will;
   behavior is verified only by tests that ran on an emulator or a device.
5. Update each item's status and hand back the report, with what was *not verified*.

## Guardrails

- Do not move UI or platform SDK code into shared targets.
- Do not expose Combine publishers to Kotlin.
- Do not rely on `deinit` or garbage collection for teardown on Android.
- Do not claim Android behavior from a macOS or iOS build.
- Do not run `skip init`, `skip checkup`, `skip android sdk install`, `swiftly install`
  or any download in Phase 1.
- Do not copy third-party code; link it pinned to a commit.
- Do not override Skip's skills on Skip's ground; route the item to them.

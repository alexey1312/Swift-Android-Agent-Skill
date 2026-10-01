# Measured behavior

What this repository's Android CI (`.github/workflows/android.yml`) actually measured.
A skill or rule may say *Measured* only by naming a section here whose status is `measured`;
a test enforces it.
Each section records the run, the date, the Swift version, the SDK, the NDK and the runner,
so a later run can be compared with it.
Everything else in the skills is cited, not measured.

## Scope

- **Measured here:** whether code compiles and links for Android with a given SDK, NDK, architecture and API level,
  and what tests assert when they run on an Android emulator.
- **Not measured here:** Skip's bridging and `skip export`, Compose recomposition,
  garbage-collection timing, Android Studio, app size on a device, behavior on physical devices.
  Those claims stay cited (`sources.md`).
- A macOS or iOS typecheck proves nothing about Android and is never recorded here.

## The run

- **Run:** <https://github.com/alexey1312/Swift-Android-Agent-Skill/actions/runs/36900287334>, 2026-10-01.
- **Runner:** `ubuntu-latest` = Ubuntu 24.04, image `20260927.320.1`.
- **Swift:** 6.4.0 (`swift-6.4-RELEASE`), installed with swiftly; SDK `swift-6.4.0-RELEASE_android`,
  installed with `swift sdk install` and its checksum (`versions.md`).
- **Compile matrix:** NDK r30 (`30.0.16248370`, downloaded as swift.org says) for aarch64 at API 28 and 23 and x86_64 at API 28;
  the image's own NDKs, 27.3 (`27.3.13750724`, its default) and 29.0 (`29.0.14206865`), for aarch64 at API 28.
- **Emulator:** `skiptools/swift-android-action` v2.9.5 with Swift 6.4.0, API 28, x86_64, the image's NDK 27.3.

## M1 · Installing the SDK as swift.org's article says

- **Status:** measured — run 36900287334, 2026-10-01, Swift 6.4.0, SDK `swift-6.4.0-RELEASE_android`, NDK r30, Ubuntu 24.04.
- **Question:** do the article's commands (swiftly, `swift sdk install` with the checksum, NDK r30) work on `ubuntu-latest`?
- **Probe:** the install steps of `android.yml` › `compile`, then the article's Hello World verbatim.
- **Result:** yes.
  The toolchain, the SDK (checksum verified by `swift sdk install`) and NDK r30 installed in every row,
  and the article's Hello World built as a `--static-swift-stdlib` executable for `x86_64` and `aarch64` at API 23.
  Running it on a device was not part of the step.

## M2 · The skills' shared samples build for Android

- **Status:** measured — run 36900287334, 2026-10-01, Swift 6.4.0, SDK `swift-6.4.0-RELEASE_android`, NDK r30, 27.3 and 29.0, Ubuntu 24.04.
- **Question:** does every `// typecheck: shared` block in the references compile for Android?
- **Probe:** `python3 scripts/typecheck_samples.py --android …` in `android.yml` › `compile`.
- **Result:** every shared block compiled in all five rows
  (aarch64 at API 23 and 28, x86_64 at API 28; NDK r30, 27.3 and 29.0).

## M3 · What does and does not compile for Android

- **Status:** measured — run 36900287334, 2026-10-01, Swift 6.4.0, SDK `swift-6.4.0-RELEASE_android`, NDK r30, 27.3 and 29.0, Ubuntu 24.04.
- **Question:** the outcomes behind scanner rules `AND001`, `AND003`, `AND005`, `AND006` and `AND008`.
- **Probe:** `scripts/probes/android/` with `scripts/android_probes.py`; expectations in `expectations.json`.
- **Result:** identical in all five rows.

| Probe | Result | First error |
| --- | --- | --- |
| `URLSession.shared` without `FoundationNetworking` | fails | `type 'URLSession' (aka 'AnyObject') has no member 'shared'` |
| the same with the `canImport(FoundationNetworking)` import | builds | — |
| `import UIKit` | fails | `no such module 'UIKit'` |
| `import SwiftUI` | fails | `no such module 'SwiftUI'` |
| `import Combine` | fails | `no such module 'Combine'` |
| `import OSLog` (no Skip) | fails | `no such module 'OSLog'` |
| `import Darwin` | fails | `no such module 'Darwin'` |
| the `canImport` ladder with `Android` | builds | — |
| `@objc` with `#selector` | fails | `Objective-C interoperability is disabled` |
| a plain `NSObject` subclass | builds | — |
| an `@Observable` class | builds | — |
| `DispatchQueue.main.async` | builds | — |

The `URLSession` error names `shared`, not the missing import —
the confusing message skip.dev's porting guide warns about.
`OSLog` exists in Skip modules because SkipFuse provides it; the bare SDK has none.
That `DispatchQueue.main.async` compiles says nothing about which Android thread runs it.

## M4 · The shared-core sample's tests on an emulator

- **Status:** measured — run 36900287334, 2026-10-01, Swift 6.4.0, SDK `swift-6.4.0-RELEASE_android`, NDK 27.3, Ubuntu 24.04, emulator API 28 x86_64.
- **Question:** do observation tracking, stream cancellation, JSON and ISO 8601 dates,
  FileManager, ICU formatting and `URLRequest` behave on Android as on the host?
- **Probe:** `samples/SharedCore` tests, `android.yml` › `emulator`.
- **Result:** all 15 XCTest tests passed on the emulator:
  `withObservationTracking` fired on a view model's state change;
  an `AsyncStream` built from a callback API delivered values and ran its termination handler on cancellation;
  JSON round-tripped with ISO 8601 dates;
  `DateFormatter` formatted with locale data (ICU);
  a temporary file round-tripped through `FileManager`;
  a `URLRequest` was built through `FoundationNetworking`;
  the view models handled inputs, called their navigation callbacks and recorded analytics.
  The action built the tests with dynamic linking and pushed the runtime libraries itself.

## M5 · NDK, API level and the SDK selector

- **Status:** measured — run 36900287334, 2026-10-01, Swift 6.4.0, SDK `swift-6.4.0-RELEASE_android`, NDK r30, 27.3 and 29.0, Ubuntu 24.04.
- **Question:** does the 6.4 SDK need NDK r30, or does the runner's NDK work;
  does API 23 build where API 28 does;
  does the older `--swift-sdk <triple>` selector still work without the setup script?
- **Probe:** the `compile` matrix, its Hello World step and its selector step.
- **Result:**
  - With NDK r30, everything built at API 23 and 28, for aarch64 and x86_64, including static executables.
  - With NDK 27.3 and 29.0, libraries, probes and samples compiled,
    but linking a `--static-swift-stdlib` executable failed in both:
    `ld.lld: error: undefined symbol: std::__ndk1::__hash_memory(void const*, unsigned long)`,
    referenced from the SDK's static `libswiftCore.a`.
    The static runtime needs the C++ library of the NDK it was built with — r30 for this SDK.
  - The older selector, `swift build --swift-sdk aarch64-unknown-linux-android28` (and the other rows' triples),
    compiled `samples/SharedCore` in all five rows without running `setup-android-sdk.sh`.
    That step builds a library; linking through the older selector was not measured.

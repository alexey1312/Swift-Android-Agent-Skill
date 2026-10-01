# Android compile probes

Each directory here is a one-file Swift package that asks one question about the Swift SDK for Android,
such as whether `import UIKit` builds
or whether `URLSession` resolves without `FoundationNetworking`.
`expectations.json` records, for each probe,
the outcome a primary source states and the URL of that source.
`scripts/android_probes.py` builds every probe for Android and compares the outcome with the source.

## The probes

| Probe | Question | Expect | Twin | Source |
| --- | --- | --- | --- | --- |
| `urlsession-without-foundationnetworking` | `URLSession` with only `import Foundation` | fail | `urlsession-with-ladder` | [Skip: porting packages](https://skip.dev/blog/android-native-swift-packages/) |
| `urlsession-with-ladder` | `URLSession` behind `#if canImport(FoundationNetworking)` | pass | `urlsession-without-foundationnetworking` | [docs.swift.org: Building for Android](https://docs.swift.org/latest/documentation/swiftandroid/buildingforandroid) |
| `uikit-import` | `import UIKit` | fail | — | [Android vision: non-goals](https://github.com/swiftlang/swift-evolution/blob/807b844be42db582e434d1667fc907ae7a7a8775/visions/android.md#non-goals) |
| `swiftui-import` | `import SwiftUI` | fail | — | [Android vision: non-goals](https://github.com/swiftlang/swift-evolution/blob/807b844be42db582e434d1667fc907ae7a7a8775/visions/android.md#non-goals) |
| `combine-import` | `import Combine` | record | `observation` | [swift.org: Exploring the Swift SDK for Android](https://www.swift.org/blog/exploring-the-swift-sdk-for-android/) |
| `observation` | an `@Observable` class | pass | `combine-import` | [swift-android-examples: hello-swift-java](https://github.com/swiftlang/swift-android-examples/blob/92a181a10af2e8b50b05783035d3ae1cc98326da/hello-swift-java/README.md#crash-library-not-found) |
| `objc-selector` | `@objc` and `#selector` | fail | `nsobject-subclass` | [Swift compiler: Objective-C interop only on Darwin](https://github.com/swiftlang/swift/blob/swift-6.4.0-RELEASE/lib/Frontend/CompilerInvocation.cpp#L1652-L1654) |
| `nsobject-subclass` | a plain `NSObject` subclass, no `@objc` | record | `objc-selector` | [swift-corelibs-foundation README](https://github.com/swiftlang/swift-corelibs-foundation/blob/swift-6.4.0-RELEASE/README.md) |
| `darwin-import` | `import Darwin` | fail | `libc-ladder` | [Skip: porting packages](https://skip.dev/blog/android-native-swift-packages/) |
| `libc-ladder` | the `Darwin` / `Android` / `Glibc` import ladder | pass | `darwin-import` | [docs.swift.org: Porting Swift Packages](https://docs.swift.org/latest/documentation/swiftandroid/portingpackages) |
| `oslog-import` | `import OSLog` with a `Logger`, without Skip | record | — | [Skip: sharing a Swift model layer](https://skip.dev/blog/shared-swift-model/) |
| `dispatch-main` | `DispatchQueue.main.async` | record | — | [swift.org: Exploring the Swift SDK for Android](https://www.swift.org/blog/exploring-the-swift-sdk-for-android/) |

## What the fields mean

- `expect: pass` — a source says it builds;
  if it does not, the run fails.
- `expect: fail` — a source says it does not build;
  if it builds, the run fails.
- `expect: record` — no primary source states the outcome,
  so the run records it and never fails on it.
  Use `record` whenever a source only implies the answer.
- `error_contains` — for `fail` probes only:
  text that a compiler error with a source location must contain,
  so a probe that fails for another reason,
  such as a missing SDK or a broken NDK,
  does not confirm the claim.
  Keep it to the quoted name (`'UIKit'`):
  building for a macOS host,
  Swift Build, SwiftPM's default build system from Swift 6.4, reports a missing module as
  `unable to resolve module dependency: 'UIKit'`,
  while the native build system says `no such module 'UIKit'`.
- `twin` — the probe that asks the contrasting question;
  twins name each other and expect different outcomes.
- `source` — the URL of the claim the probe tests.

## Running

```sh
python3 scripts/android_probes.py --list
python3 scripts/android_probes.py --swift "$(which swift)" --swift-sdk <sdk-id> \
  --triple aarch64-unknown-linux-android28 --json probes.json
```

The table on stdout is Markdown for `$GITHUB_STEP_SUMMARY`;
progress goes to stderr.
The exit status is 0 when every `pass` and `fail` expectation held,
1 when one did not,
and 2 for bad arguments, a missing `swift` or a malformed `expectations.json`.
Build products go to a temporary scratch directory,
never into the probe directories.
Without an Android toolchain,
`python3 scripts/toolchain_report.py` says what is missing.

CI runs the probes in every row of the `compile` job in `.github/workflows/android.yml`,
appends the table to the job summary
and keeps the JSON as an artifact.

## Adding a probe

1. Create `<name>/Package.swift` (tools version 6.0, one target)
   and `<name>/Sources/<Target>/<Target>.swift`,
   whose first line states the question as a comment.
2. Add an entry to `expectations.json`:
   `record` unless a primary source states the outcome,
   and `error_contains` on every `fail`.
3. Run `python3 -m unittest tests/test_android_probes.py`.

## From a probe result to a claim

A probe result is not yet a claim.
A skill, a reference or a scanner rule may cite `Measured: M<n>`
only after CI recorded the result in `references/measured-behavior.md`:
a section `M<n>` whose status is `measured`,
with the run URL, the date, the Swift SDK and the NDK.
The job summary's recap table and the probe JSON carry those fields.
Until then, cite the source from `expectations.json` instead.
A macOS or iOS build of a probe proves nothing about Android.

# SharedCore

A starter template for the shared-core pattern:
models, networking and `@Observable` view models live in Swift,
while each platform keeps its own UI —
SwiftUI on iOS,
Kotlin and Jetpack Compose on Android.
It is also this repository's runtime probe:
CI builds it for Android and runs its tests on an emulator.

## What it demonstrates

| File | Shows |
| --- | --- |
| `MarketListViewModel.swift`, `MarketDetailViewModel.swift` | One `@MainActor @Observable` class per screen, a nested `Input` enum handled by `send(_:)`, read-only observable state, navigation through injected callbacks |
| `PlatformServices.swift` | `AnalyticsClient` and the async `PaymentsClient`: platform services passed in through initializers, with in-memory doubles for tests and previews |
| `AsyncStreamAdapter.swift` | `AsyncStream.observing(bufferingPolicy:_:)` turns a callback API into a stream and unregisters when the stream ends or its consumer is cancelled |
| `MarketsAPI.swift` | A `URLSession` client behind the `canImport(FoundationNetworking)` import ladder |
| `Models.swift` | `Codable` models and one JSON configuration with ISO 8601 dates |

No file imports UIKit or SwiftUI,
so nothing here waits on an Apple UI framework;
whether it all compiles and passes on Android is what CI checks.
Hand the Kotlin side streams and plain callbacks rather than Combine publishers;
the bridge itself (swift-java or Skip) and the Compose UI are out of scope for this sample.

## Run the tests

```sh
swift test --package-path samples/SharedCore
```

The tests use XCTest,
because XCTest is what the Android emulator job runs.
None of them touch the network.
They check that observation tracking fires,
that the view models handle inputs and call their navigation callbacks,
that the stream adapter delivers values and unregisters on cancellation,
and that the Foundation pieces the core relies on work at runtime:
JSON with ISO 8601 dates,
a temporary-file round trip,
locale-aware `DateFormatter` output (which needs ICU data),
and building a `URLRequest`.

On Android the temporary directory comes from `TMPDIR`,
falling back to `/data/local/tmp/`
([swift-foundation](https://github.com/swiftlang/swift-foundation/blob/swift-6.4.0-RELEASE/Sources/FoundationEssentials/String/String+Path.swift)),
which suits the emulator's shell user that runs these tests.
An app should pass a directory such as `Context.getFilesDir()` in from Kotlin instead.

## On Android

`.github/workflows/android.yml` builds this package and its tests for Android
in every row of the compile matrix,
and its emulator job runs the same tests on an Android emulator
through `skiptools/swift-android-action`.
To build it yourself,
install the toolchain, the Swift SDK for Android and the NDK
as `references/versions.md` lists them, then run:

```sh
swift build --package-path samples/SharedCore --build-tests \
  --swift-sdk <sdk-id> --triple aarch64-unknown-linux-android28
```

`python3 scripts/toolchain_report.py` says what this machine is missing.

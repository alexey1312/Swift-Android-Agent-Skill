# Checks

Every automated rule in `android_scan.py`,
and the checks that need a toolchain, a device or a person.
The scanner never writes anything.
Matches are heuristics:
the agent reads the code before a finding becomes a recommendation.

## Automated

| Rule | Severity (by route) | Finds | Source | Skill |
| --- | --- | --- | --- | --- |
| `AND001` | high | `import UIKit`, `AppKit` or `WatchKit` in shared code that Android compiles; `import SwiftUI` outside a Skip UI module (one that depends on SkipFuseUI or SkipUI) | Swift Forums › Our Android App Is Written in Swift (2026-08-04); skip.dev › Porting Swift Packages to Android; skip.dev › FAQs | `swift-android-architecture` |
| `AND002` | high | An import of one of nearly 80 Apple-only frameworks, such as MapKit, StoreKit, CoreData, CryptoKit or HealthKit; `detail` names an Android-capable alternative where one exists, such as a Skip framework or swift-crypto | skip.dev › Porting Swift Packages to Android; skip.dev › FAQs; Swift Forums › Our Android App Is Written in Swift (2026-08-04) | `swift-android-architecture` |
| `AND003` | high where Swift is compiled natively (fuse-app, shared-core, bare-sdk); info in transpiled modules (lite) | `import Combine` | skip.dev › FAQs; Swift Forums › Our Android App Is Written in Swift (2026-08-04); skip.dev › SkipModel | `swift-android-architecture` |
| `AND004` | high where compiled natively; info in transpiled modules | `ObservableObject` conformance and `@Published` | Swift Forums › Our Android App Is Written in Swift (2026-08-04); skip.dev › SkipModel; skip.dev › App Development | `swift-android-architecture` |
| `AND005` | high, natively compiled code only | `URLSession`, `URLRequest`, `HTTPURLResponse` and the other networking types in a file without `FoundationNetworking`; a `canImport(FoundationNetworking)` guard counts, an `os(Linux)` guard does not | docs.swift.org › Android › Building for Android; skip.dev › Porting Swift Packages to Android | `swift-android-sdk` |
| `AND006` | medium, natively compiled code only | `import Darwin`; `import Glibc` or `Musl` in a file with no Android branch; `FILE` used as a type | docs.swift.org › Android › Porting Swift Packages to Android; skip.dev › Porting Swift Packages to Android | `swift-android-sdk` |
| `AND007` | low; info on bare-sdk | `print`, `debugPrint` and `NSLog` outside test and executable targets | skip.dev › Debugging › Logging; skip.dev › FAQs › How does logging work in Skip? | `swift-android-sdk` |
| `AND008` | high, natively compiled code only | `@objc`, `@objcMembers`, `#selector`, `#keyPath`, KVO `observe(_:options:)` and `addObserver(_:forKeyPath:)`, associated objects, `method_exchangeImplementations`, `import ObjectiveC`; subclassing `NSObject` alone is not flagged | GitHub › swiftlang/swift-corelibs-foundation README.md; GitHub › swiftlang/swift lib/Frontend/CompilerInvocation.cpp | `swift-android-sdk` |
| `AND009` | medium, Skip modules in native mode | A file that defines an `@Observable` type and imports none of SkipFuse, SkipFuseUI, SwiftUI or SkipSwiftUI | skip.dev › App Development › @Observables; GitHub › skiptools/skipstone Sources/SkipSyntax/Kotlin/KotlinMessage.swift; GitHub › skiptools/skipstone Sources/SkipSyntax/Kotlin/KotlinBridgeToKotlinVisitor.swift | `swift-android-architecture` |
| `AND010` | low, Skip modules in native mode | `#if !SKIP` or `#elseif !SKIP` whose branch Android compiles — native Swift on both platforms, not iOS-only | skip.dev › Cross-Platform Topics › #if os(Android) vs #if SKIP | `swift-android-architecture` |
| `AND011` | medium, bridged Skip modules | Public API typed `AnyPublisher`, `PassthroughSubject`, `CurrentValueSubject`, `Published<…>.Publisher` or `some`/`any Publisher` | Swift Forums › Our Android App Is Written in Swift (2026-08-04); skip.dev › Bridging Reference; skip.dev › SkipBridge | `swift-android-architecture` |
| `AND012` | medium, bridged Skip modules | Public API with a closure type of more than five parameters, a closure inside a collection type, or a closure that takes a closure | skip.dev › Bridging Reference; Swift Forums › Our Android App Is Written in Swift (2026-08-04) | `swift-android-architecture` |
| `AND020` | info | A `skip.yml` that does not set `mode`, or sets `automatic`; `detail` says which mode the scan assumed | skip.dev › Lite and Fuse Modes › Configuration; skip.dev › Internal Architecture; GitHub › skiptools/skipstone Sources/SkipBuild/Commands/SkipstoneCommand.swift | `swift-android-architecture` |

### Routes, shared code and guards

`--route` names how Swift reaches Android:
`fuse-app` (Skip Fuse, SwiftUI on both platforms through SkipFuseUI),
`shared-core` (the default:
Swift modules that Skip compiles natively
and exports as AARs to a native Kotlin and Compose app),
`lite` (Skip Lite, transpiled to Kotlin)
or `bare-sdk` (the Swift SDK for Android without Skip, with swift-java or JNI).
The route sets the compile mode of shared targets that are not Skip modules
(transpiled on `lite`, native otherwise),
the severity of `AND007`,
and whether `AND002` suggests Skip frameworks.

Shared code is every Skip module
(a target with `Skip/skip.yml` or the `skipstone` plugin)
plus the targets and paths named with `--shared`.
Xcode projects count as iOS-side unless named.
A Skip module compiles in the `mode` its `skip.yml` sets.
Without one,
it is native when SkipFuse or SkipFuseUI is in its dependency graph
and transpiled otherwise,
which is what skipstone does,
and `AND020` asks for the mode to be written down.
With nothing shared, the scan is a survey:
it rates each target as a sharing candidate
(Swift lines, blocker counts by rule, and a verdict of `clean`, `fixable` or `ios-only`)
and lists only `info` findings.

Every line is evaluated for an Android build of its module:
compiled, not compiled, or undecided.
A line Android does not compile is not reported;
an undecided one is reported with its condition in `guard`.
`os(Android)` holds and every other `os(...)` fails,
`os(Linux)` included:
an Android triple sets only `os(Android)`
(GitHub › swiftlang/swift lib/Basic/LangOptions.cpp).
`canImport` holds for Android, Bionic, Foundation and its sub-modules,
Dispatch, Observation and the target's own dependencies;
it fails for UIKit, AppKit, Darwin, ObjectiveC, Combine and the `AND002` modules,
and for SwiftUI except in a module that depends on SkipFuseUI.
`canImport(Glibc)`, `canImport(Musl)`, `targetEnvironment(simulator)`, `arch(...)`,
`SKIP_BRIDGE`, `ROBOLECTRIC` and custom flags stay undecided.
`SKIP` is false in natively compiled modules,
where that code is transpiled rather than compiled,
and true in transpiled ones;
`DEBUG` is false in transpiled modules:
Skip's FAQs note that `#if DEBUG` never holds
on the Android side of a Skip Lite app.

The scanner also reports the targets with their Skip configuration,
the `Package.resolved` pins (formats 1 to 3)
and an inventory of Android-relevant APIs.

### Known limits

- `Package.swift` is read with regexes.
  Target declarations, list literals,
  and list variables built with `=`, `+=`, `append` or `append(contentsOf:)`
  are followed;
  targets made by functions or loops are missed,
  and `sources:` and `exclude:` are ignored.
  A `skip.yml` still marks its folder as a Skip module.
- Product names stand in for module names in `canImport`,
  and only local targets are followed
  when looking for SkipFuse in a module's dependency graph.
- Xcode project membership is not read from `project.pbxproj`:
  Swift files outside every SwiftPM target count as iOS-side,
  grouped under the nearest `.xcodeproj`.
- `AND005` reports the first use per file.
  It accepts `import SkipFuse`, `SkipFuseUI` or `SkipAndroidBridge`,
  and `SwiftUI` in a Fuse UI module,
  because SkipAndroidBridge re-exports FoundationNetworking
  (GitHub › skiptools/skip-android-bridge
  Sources/SkipAndroidBridge/AndroidBridgeBootstrap.swift).
- `AND006` passes `import Glibc` under an undecided guard
  when the file also imports `Android` or `Bionic`.
  A ladder that leaves Android out entirely,
  such as one guarded by `os(Linux)`,
  surfaces only as the build errors it causes.
- `AND008` leaves out `NSClassFromString`:
  corelibs-foundation implements it for top-level Swift classes named `Module.Class`.
- `AND009` reports the first `@Observable` per file
  and, like skipstone, accepts a file that imports SwiftUI or SkipSwiftUI.
- `AND011` and `AND012` read the public declarations of auto-bridged modules
  (`bridging: true`, or a mapping with `auto` or `enabled` set),
  declarations marked `// SKIP @bridge`,
  and files with `// SKIP @bridgeMembers`;
  `// SKIP @nobridge` exempts a declaration.
  Closure types are recognised by position
  (after `:`, `->`, `=` or an attribute),
  not by type checking.
- In a transpiled module that depends on SkipAV,
  `import AVKit` and `import AVFoundation` are not reported:
  Skip Lite maps them onto SkipAV (skip.dev › SkipAV).
- A survey rates a target `ios-only`
  when at least half of its Swift files import a UI framework (`AND001`).

## Manual

| Check | How |
| --- | --- |
| Android compile of shared samples | `.github/workflows/android.yml` (CI) |
| Behavior on a device or emulator | `samples/SharedCore` tests in CI |
| Skip bridging, Compose recomposition, GC timing, APK size | Never measured by this repository (cited only) |

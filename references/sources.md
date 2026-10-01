# Sources

Cite the page, the repository file, or the forum post (with its number, author handle and date)
that a recommendation rests on;
`measured-behavior.md` for what this repository's CI measured;
`versions.md` for anything with a version or a size.
Everything was read on 2026-10-01 from raw sources at the revisions below.
Quotes are one sentence at most; everything else is paraphrased.

## Documentation

### skip.dev

CC BY-SA 4.0 — paraphrase, attribute, no copied tables or passages.
Read at `skiptools/skip.dev` commit `f0680d1c29f8acdc791dc88edbd0194b80c68be2` (2026-09-08);
module pages come from each module's README (MPL-2.0).

| Page | URL | Backs |
| --- | --- | --- |
| Lite and Fuse Modes | <https://skip.dev/docs/modes/> | native versus transpiled, the mode recommendation, `kotlincompat`, bridging configuration, size cost |
| Bridging Reference | <https://skip.dev/docs/bridging/> | what bridges: closures, protocols, streams, generics, `Int`, errors |
| Cross-Platform Topics | <https://skip.dev/docs/platformcustomization/> | `#if SKIP`, `#if !SKIP`, `#if os(Android)` per mode |
| App Development | <https://skip.dev/docs/app-development/> | `import SkipFuse` for `@Observable`; private views not bridged |
| Debugging | <https://skip.dev/docs/debugging/> | `print` not in Logcat; `OSLog.Logger`; demangling crashes |
| Testing | <https://skip.dev/docs/testing/> | `skip test`, `skip android test`, Robolectric, Swift Testing for native modules |
| Deployment | <https://skip.dev/docs/deployment/> | `skip export` output |
| Project Structure | <https://skip.dev/docs/project-types/> | separate iOS and Android apps, exporting libraries, transitive dependencies, migrating apps |
| Porting Swift Packages | <https://skip.dev/docs/porting/> | FoundationNetworking, `canImport` ladders, `FILE`, unsuitable frameworks, CI action |
| Dependencies | <https://skip.dev/docs/dependencies/> | wrapping Android libraries in transpiled modules |
| Skip CLI Reference | <https://skip.dev/docs/skip-cli/> | commands and flags, the CI command sequence |
| FAQ | <https://skip.dev/docs/faq/> | API levels, Combine in native mode, debugging, Gradle cache, official agent skills |
| Common Topics | <https://skip.dev/docs/development-topics/> | Kotlin package names |
| SkipModel | <https://skip.dev/docs/modules/skip-model/> | `ObservableObject` and publishers in transpiled modules |
| SkipFuse, SkipBridge | <https://skip.dev/docs/modules/skip-fuse/>, <https://skip.dev/docs/modules/skip-bridge/> | logging, Observation, bridged types |
| Blog: Sharing a Swift Model Layer (2024-12-19) | <https://skip.dev/blog/shared-swift-model/> | consuming exported libraries from Gradle |
| Blog: Skip Is Now Free and Open Source (2026-01-21) | <https://skip.dev/blog/skip-is-free/> | licensing |
| Blog: Official Android support in Swift 6.3 (2026-03-26) | <https://skip.dev/blog/swift-63-android-support/> | Skip on the official SDK |

### swift.org and docs.swift.org

The swift.org site is Apache-2.0 except its blog, which is CC BY 4.0.

| Source | URL | Backs |
| --- | --- | --- |
| Getting Started with the Swift SDK for Android (updated 2026-09-15, commit `460cb39`) | <https://www.swift.org/documentation/articles/swift-sdk-for-android-getting-started.html> | install and build commands, matching toolchain, NDK, `libc++_shared.so` |
| Announcing the Swift SDK for Android (2025-10-24) | <https://www.swift.org/blog/nightly-swift-sdk-for-android/> | history |
| Exploring the Swift SDK for Android (2025-12-18) | <https://www.swift.org/blog/exploring-the-swift-sdk-for-android/> | runtime bundled in apps, `@available(Android …)`, no single GUI solution |
| Swift 6.3 Released (2026-03-24) | <https://www.swift.org/blog/swift-6.3-released/> | first official SDK |
| Swift 6.4 Released (2026-09-15) | <https://www.swift.org/blog/swift-6.4-released/> | NDK 30, availability attributes, Swift Build, no post-install script |
| Install API | <https://www.swift.org/api/v1/install/releases.json> | releases and SDK checksums |
| docs.swift.org › Swift Android (source in swiftlang/swift-android-examples, Apache-2.0) | <https://docs.swift.org/latest/documentation/swiftandroid/> | FoundationNetworking statement, `canImport` ladder, `@_cdecl`, Gradle task, older NDK and selector |
| swift-java documentation (0.6.0) | <https://docs.swift.org/latest/documentation/swiftjavadocumentation/> | JNI mode, configuration, plugins, R8, desugaring, binary size |

### Android Developers

| Page | URL | Backs |
| --- | --- | --- |
| ViewModel Scoping APIs (updated 2026-04-30) | <https://developer.android.com/topic/libraries/architecture/viewmodel/viewmodel-apis> | view models scoped to a navigation back-stack entry |
| Navigation 3: scoping view models to an entry (updated 2026-09-22) | <https://developer.android.com/guide/navigation/navigation-3/save-state> | `rememberViewModelStoreNavEntryDecorator()` |

## Repositories

Linked, pinned and never copied unless the licence allows it and the notice comes along.

| Repository | Revision | Licence | Backs |
| --- | --- | --- | --- |
| [skiptools/skills](https://github.com/skiptools/skills/tree/0399f0a2046635e268b37f43f5c370b32b7557db/) | `0399f0a` (2026-09-29) | Apache-2.0 | `official-skip-skills.md` |
| [skiptools/skipstone](https://github.com/skiptools/skipstone) | `584e579` (2026-09-29) | AGPL-3.0 | the `import SkipFuse` warning text (`Sources/SkipSyntax/Kotlin/KotlinMessage.swift`); default `mode` behavior |
| [swiftlang/swift-java](https://github.com/swiftlang/swift-java/tree/0.6.0) | `0.6.0` | Apache-2.0 | `swift-java` facts |
| [swiftlang/swift-android-examples](https://github.com/swiftlang/swift-android-examples/tree/b5d34855e188b1042af07a56bfd8d5098cb5469d) | `b5d3485` (2026-09-09) | Apache-2.0 | packaging, runtime libraries, the `dlopen` failure |
| [swiftlang/github-workflows](https://github.com/swiftlang/github-workflows/blob/fa1e46cf0f07ffde2de131e9ed5bd66a488c289c/.github/workflows/swift_package_test.yml) | `fa1e46c` (2026-09-24) | Apache-2.0 | `ci.md` |
| [skiptools/swift-android-action](https://github.com/skiptools/swift-android-action/tree/2044b79660f201ccef8cbce62877e4ec5409f9c8) | `v2.9.5` = `2044b79` | none — `uses:` only | `ci.md` |
| [theleftbit/BSWInterfaceKit](https://github.com/theleftbit/BSWInterfaceKit/tree/b74047a91f44875ad43cca7b778fc5b98d03b309/Sources/BSWInterfaceKit/Skip) | `b74047a` (2026-05-05) | MIT, © 2018–2024 TheLeftBit SL | the Compose lifetime example |
| [cricut/FishyJoes](https://github.com/cricut/FishyJoes) | `main` (2026-09-29) | Apache-2.0 | another binding generator, from the thread |
| [swiftlang/swift-corelibs-foundation](https://github.com/swiftlang/swift-corelibs-foundation) | `main` | Apache-2.0 | `NSObject` without an Objective-C runtime |
| [SwiftPackageIndex-Server](https://github.com/SwiftPackageIndex/SwiftPackageIndex-Server) | `29259e4` | Apache-2.0 | Android build results and the platforms badge |

### Swift Package Index

Android builds have run for every indexed package since 2025-06-02, for Swift 6.1 and later.
A package's results are at `https://swiftpackageindex.com/<owner>/<repo>/builds`,
and the public badge endpoint `https://swiftpackageindex.com/api/packages/<owner>/<repo>/badge?type=platforms`
lists Android when its Android build succeeded.
The search accepts `platform:android`.

## Swift Forums

Posts are under the Swift licence (Apache-2.0 with the Runtime Library Exception)
unless marked "Not a Contribution" (<https://forums.swift.org/tos>).

| Thread | Opened | Posts cited |
| --- | --- | --- |
| [Our Android app is written in Swift](https://forums.swift.org/t/our-android-app-is-written-in-swift/88778) | 2026-08-04 | 1 (@poly-rob), 4 (@marcprux), 8 and 11 (@mstokercricut), 13 (@pcifani) |
| [Android API minimum for the Swift SDK for Android](https://forums.swift.org/t/android-api-minimum-for-the-swift-sdk-for-android/82874) | 2025-10-27 | 1, 5, 18, 35, 37, 38 |
| [Swift Debugging on Android - Current State](https://forums.swift.org/t/swift-debugging-on-android-current-state/84155) | 2026-01-15 | 1, 3, 6 (@gabriele) |
| [On the topic of Swift runtimes, C++ instability, and mismatched NDK versions](https://forums.swift.org/t/on-the-topic-of-swift-runtimes-c-instability-and-mismatched-ndk-versions/87469) | 2026-06-17 | 1 (@etcwilde), 6 (@Finagolfin), 7 (@marcprux), 8 (@keeshux) |
| [Android app size and lib_FoundationICU.so](https://forums.swift.org/t/android-app-size-and-lib-foundationicu-so/78399) | 2025-03-09 | 1 (@marcprux), 15 (@mstokercricut), 26 (@keeshux) |
| [Android package compatibility now showing on swiftpackageindex.com](https://forums.swift.org/t/android-package-compatibility-now-showing-on-swiftpackageindex-com/80256) | 2025-06-02 | 6 (@marcprux) |

## The Polymarket report

Swift Forums, "Our Android app is written in Swift", post 1 by @poly-rob, 2026-08-04 —
<https://forums.swift.org/t/our-android-app-is-written-in-swift/88778/1>.
Polymarket describes its Android app:
Kotlin, Compose and Navigation 3 on top of about 170,000 lines of Swift shared with iOS,
compiled by Skip and delivered to Gradle as exported libraries.
It is the origin of the shared-core pattern in the architecture skill:
the package split, platform protocols injected at startup,
`@Observable` view models with an input enum,
lifetimes rebuilt on the Compose side,
no Combine at the boundary,
and an Android CI gate on every pull request.

It is one team's experience report, and Polymarket says it sponsors Skip.
Skip's maintainer (@marcprux) replies in the thread and discloses his role (post 4);
@pcifani links code "very similar to what we do there" (post 13).
The post does not name Skip's mode; native mode is inferred from compiled Swift and exported libraries.

| Report | This repository | Why |
| --- | --- | --- |
| Point-Free's swift-dependencies injects platform implementations | initializer injection first; a DI library optional | fewer dependencies, easier tests (*inference*) |
| A helper creates a fresh view model per screen or presentation and tears its scope down | the same, plus an explicit `close()` called from the holder's `onCleared()` | clearing a scope only drops a reference, and "We still don't control when Android's garbage collector frees a Swift-backed object" (post 1) |
| A Kotlin class conforms to a Swift protocol | reported, to be verified with a build | skip.dev does not document it, and Skip's bridge tests do not exercise it |
| About 50 MB at download | a dated report in `versions.md` | measure the app in question |
| Combine adapted to async/await for Android, and back to publishers for older iOS views | no Combine across the boundary | Skip bridges Swift Concurrency, not publishers (post 1); Combine is unavailable to native modules (skip.dev › FAQ) |

## Background reading (not a citation source)

Useful context; do not cite these for a recommendation —
cite the documentation or the measurement they lead to.

- **Readdle, "Swift for Android: Our Experience and Tools"** (last updated 2018-06-01) —
  <https://readdle.com/blog/swift-for-android-our-experience-and-tools>.
  Spark's shared Swift logic under a native Android UI, with an early open-source toolchain.
- **flowkey, "Why we put an app in the Android Play Store using Swift"** (2016-07-07) —
  <https://medium.com/@ephemer/why-we-put-an-app-in-the-android-play-store-using-swift-96ac87c88dfc>.
  Swift audio code reused on Android through JNI.
- **Ignit Group, "Swift on android: A practical use case"** (2026-04-23) —
  <https://ignit.group/blog/swift-on-android-a-practical-use-case>.
  swift-java in JNI mode without Skip; a long list of bridge and Foundation-on-Bionic limits, some possibly version-specific.
- **Brightec, "Swift 6.3 and the Android SDK: Is it too late to the party?"** (2026-05-12) —
  <https://www.brightec.co.uk/blog/swift-6-3-and-the-android-sdk-is-it-too-late-to-the-party>.
  A Kotlin Multiplatform shop's view: logic only, weak debugging.
- **Ugo Arangino, "Swift for Android: A First Glance"** (2026-05-20) —
  <https://www.arangino.app/blog/swift-for-android-first-glance/>.
  A walk through the official examples.
- **Pierluigi Cifani, "Android Doesn't Deserve Swift—But We Did It Anyway"**, NSSpain (2025-10-08) —
  <https://youtu.be/EIGl6GOo210>.
  Porting an app's Swift core with Skip's native mode.
- **Mads Odgaard, "Expanding Swift/Java Interoperability"**, ServerSide.swift (2025-10-27) —
  <https://www.youtube.com/watch?v=tOH6V1IvTAc>.
  How swift-java's JNI mode came about.
- **Swift Forums, "Dev writeups of the Swift SDK for Android"** (2026-09-23) —
  <https://forums.swift.org/t/dev-writeups-of-the-swift-sdk-for-android/89711>.
  A curated list of write-ups.
- **keeshux/swift-cmake-toolchains** (MIT) —
  <https://github.com/keeshux/swift-cmake-toolchains>.
  Building Swift for Android from CMake with FoundationEssentials only.

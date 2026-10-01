# Versions, sizes and dates

Everything here goes stale.
Every row says when it was checked, where it came from, and how to check it again;
the skills point here instead of repeating numbers.
`scripts/versions_check.py` compares the pins below with the latest releases,
and the weekly `drift` job in `.github/workflows/android.yml` runs it.

## Pins

```json
{
  "checked": "2026-10-01",
  "swift-release": "6.4.0",
  "swift-android-sdk-checksum": "21fb555122a3d801ad943d48df7ebffdd8824de61c25c180bb792d3edaee0b43",
  "skip-release": "1.9.12",
  "swift-java-release": "0.6.0",
  "swift-android-action-release": "v2.9.5"
}
```

## Swift SDK for Android

| Fact | Value | As of | Source | Re-check |
| --- | --- | --- | --- | --- |
| First official release | Swift 6.3, released 2026-03-24 | 2026-10-01 | swift.org › Swift 6.3 Released | `curl -s https://www.swift.org/api/v1/install/releases.json` |
| Latest release with an Android SDK | Swift 6.4.0, tag `swift-6.4.0-RELEASE`, dated 2026-09-14 | 2026-10-01 | swift.org install API `releases.json` | `curl -s https://www.swift.org/api/v1/install/releases.json \| jq -r '.[-1].name'` |
| SDK download, 6.4.0 | `https://download.swift.org/swift-6.4.0-release/android-sdk/swift-6.4.0-RELEASE/swift-6.4.0-RELEASE_android.artifactbundle.tar.gz` | 2026-10-01 | swift.org › Getting Started with the Swift SDK for Android | the article's step 2 |
| SDK checksum, 6.4.0 | `21fb555122a3d801ad943d48df7ebffdd8824de61c25c180bb792d3edaee0b43` | 2026-10-01 | swift.org article; `releases.json` (`platform == "android-sdk"`) | `jq '.[] \| select(.name=="6.4.0") \| .platforms[] \| select(.platform=="android-sdk") \| .checksum'` |
| SDK bundle size, 6.4.0 | 340,301,830 bytes | 2026-10-01 | `curl -sI` on the download URL | same |
| Host toolchain | an open-source toolchain whose version matches the SDK exactly, not Xcode's; swiftly installs it | 2026-10-01 | swift.org article, step 1 | the article |
| NDK, per swift.org's article | LTS r30, found through `ANDROID_NDK_HOME` | 2026-09-15 | swift.org article (updated for 6.4 on 2026-09-15); swift.org › Swift 6.4 Released | the article's step 3 |
| NDK, per docs.swift.org | "r27d+ recommended" | 2026-08-16 | docs.swift.org › Swift Android › Getting Started | the page |
| Build command, swift.org (6.4) | `swift build --swift-sdk swift-6.4.0-RELEASE_android --triple aarch64-unknown-linux-android23 --static-swift-stdlib` | 2026-09-15 | swift.org article | the article |
| Build command, docs.swift.org and examples | `swift build --swift-sdk aarch64-unknown-linux-android28` (older selector) | 2026-08-16 | docs.swift.org › Getting Started; swift-android-examples | the pages |
| Post-install script | not needed with Swift Build per the 6.4 release post, yet the 6.4.0 bundle still ships `scripts/setup-android-sdk.sh`, which creates the `ndk-sysroot` the older selector points at | 2026-10-01 | swift.org › Swift 6.4 Released; bundle listing | `tar -tzf <bundle> \| grep setup-android-sdk` |
| API levels in the 6.4.0 bundle | triples for API 23 through 36, for `aarch64`, `x86_64` and `armv7` | 2026-10-01 | bundle `swift-android/swift-sdk.json` | `swift sdk configure --show-configuration` or the JSON |
| Lowest API level | 23 from the first 6.4 snapshots (6.3: 28); API 23 imports `FILE*` differently, which breaks packages such as swift-log | 2026-05-28 | Swift Forums › Android API minimum for the Swift SDK for Android (2025-10-27), posts 35 and 38 | the thread |
| Page size | the SDK's toolset links with `-z max-page-size=16384` (16 KB pages) | 2026-10-01 | bundle `swift-toolset.json` | the JSON |
| `libc++_shared.so` | not in the bundle; ship the NDK's copy with the app | 2026-10-01 | bundle listing; swift.org article (Hello World) | `tar -tzf <bundle> \| grep libc++` |

## Skip

| Fact | Value | As of | Source | Re-check |
| --- | --- | --- | --- | --- |
| Latest Skip release | 1.9.12, published 2026-09-29 | 2026-10-01 | GitHub › skiptools/skip releases | `gh api repos/skiptools/skip/releases/latest --jq .tag_name` |
| Free and open source | since Skip 1.7, 2026-01-21 (`skipstone` is AGPL-3.0; the libraries MPL-2.0; skip.dev CC BY-SA 4.0) | 2026-10-01 | skip.dev › blog › Skip Is Now Free and Open Source | the post |
| Native mode on the official SDK | since Skip 1.8 (2026-03) | 2026-10-01 | skip.dev › blog › Official Android support in Swift 6.3 (2026-03-26) | the post |
| Minimum Android API for Skip apps | 28 | 2026-09-08 | skip.dev › FAQ (commit `f0680d1`) | the FAQ |
| Target API | the FAQ says 34; SkipUnit's current configuration compiles against 36, so 34 looks stale | 2026-10-01 | skip.dev › FAQ; GitHub › skiptools/skip-unit `skip.yml` | both |
| Minimum iOS for Skip apps | 16 (examples use 16 or 17) | 2026-09-08 | skip.dev › FAQ | the FAQ |
| Native-mode size cost | about 60 MB added to the Android app | 2026-09-08 | skip.dev › Lite and Fuse Modes | the page |
| Gradle cache | Compose dependencies add about 1 GB | 2026-09-08 | skip.dev › FAQ | `du -skh ~/.gradle` |
| Development machine | macOS 15 or later with Xcode 16.4 or later; Linux and WSL only for frameworks, CI and `skip android` | 2026-09-08 | skip.dev › Getting Started; skip.dev › FAQ; skip.dev › Skip CLI Reference | the pages |
| Official agent skills | `skiptools/skills` at commit `0399f0a` | 2026-09-29 | GitHub › skiptools/skills | `official-skip-skills.md` › Re-checking |

## swift-java

| Fact | Value | As of | Source | Re-check |
| --- | --- | --- | --- | --- |
| Latest release | 0.6.0, published 2026-09-05 | 2026-10-01 | GitHub › swiftlang/swift-java releases | `gh api repos/swiftlang/swift-java/releases/latest --jq .tag_name` |
| API stability | "There is no guarantee of API stability until the project reaches a 1.0 release." | 2026-09-05 | swift-java README › Project Status | the README |
| JNI mode | works on Android; JDK 17+ to build | 2026-09-05 | swift-java README | the README |
| FFM mode | the default; needs JDK 25+; not for Android | 2026-09-05 | swift-java README; Features Overview | the docs |
| Full binary-size optimization | needs Swift 6.3 or later | 2026-09-05 | swift-java › Reducing Binary Size | the doc |
| Java support libraries | not on Maven Central; publish them locally (`publishToMavenLocal`) | 2026-09-05 | swift-java README | the README |

## Sizes (reported, not measured here)

| Fact | Value | As of | Source | Re-check |
| --- | --- | --- | --- | --- |
| Polymarket's Android app | Swift adds about 50 MB at download | 2026-08-04 | Swift Forums › Our Android app is written in Swift, post 1 | — |
| Runtime libraries, 6.0.3 community SDK, aarch64 | `lib_FoundationICU.so` 40 MB, `libswiftCore.so` 9.6 MB, `libFoundationEssentials.so` 8.8 MB, `libFoundation.so` 8.7 MB, `libFoundationInternationalization.so` 3.8 MB | 2025-03-09 | Swift Forums › Android app size and lib_FoundationICU.so, post 1 | — |
| Skip samples, release bundles | transpiled "Hello Skip" 8.44 MB, native "Hiya Skip" 70.4 MB | 2025-03-09 | same thread, post 1 | — |
| Static runtime, FoundationEssentials only | library about 18 MB; release APK 31 MB (12 MB compressed) after R8 | 2026-05-06 | same thread, post 26 | — |
| Runtime libraries in the 6.4.0 bundle, aarch64, uncompressed | the 16 libraries a dynamic build ships total 86,227,344 bytes; `lib_FoundationICU.so` alone 45,817,552 | 2026-10-01 | read from the 6.4.0 bundle's file listing | `tar -tvzf <bundle> 'swift-android/swift-resources/usr/lib/swift-aarch64/android/*'` |

## Debugging

| Fact | Value | As of | Source | Re-check |
| --- | --- | --- | --- | --- |
| LLDB | works "reasonably well, from the command line or with VS Code" with the Swift 6.3 fixes; the VS Code route is an experimental extension built from a fork | 2026-03-24 | Swift Forums › Swift Debugging on Android - Current State (2026-01-15), post 6 | the thread; the lldb-dap RFC on LLVM Discourse |
| Android Studio | no Swift breakpoints | 2026-08-04 | skip.dev › FAQ; Swift Forums › Our Android app is written in Swift, post 1 | the FAQ |

## CI runners

| Fact | Value | As of | Source | Re-check |
| --- | --- | --- | --- | --- |
| `ubuntu-latest` | Ubuntu 24.04; NDK 27.3 (default), 28.2, 29.0, no r30; Swift 6.4; JDK 17 default | 2026-09-20 | GitHub › actions/runner-images `Ubuntu2404-Readme.md` | the readme |
| `ubuntu-latest` switch | becomes Ubuntu 26.04 in November 2026 | 2026-09-20 | same readme | the readme |
| `macos-latest` | macOS 26 arm64, Xcode 26.6 default; cannot run the Android emulator | 2026-09-07 | GitHub › actions/runner-images `macos-26-arm64-Readme.md`; swift-android-action README | the readmes |
| `skiptools/swift-android-action` | `v2.9.5` = `v2` = `2044b79660f201ccef8cbce62877e4ec5409f9c8`, released 2026-06-01, before Swift 6.4 | 2026-10-01 | GitHub › skiptools/swift-android-action | `gh api repos/skiptools/swift-android-action/releases/latest --jq .tag_name` |
| `swiftlang/github-workflows` | `main` = `fa1e46cf0f07ffde2de131e9ed5bd66a488c289c`, defaults moved to Swift 6.4 on 2026-09-24 | 2026-10-01 | GitHub › swiftlang/github-workflows | `gh api repos/swiftlang/github-workflows/commits/main --jq .sha` |

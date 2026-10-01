# Shipping the runtime in an app

A Swift library in an Android app is a `.so` file that the app loads with `System.loadLibrary`.
Everything it links must be in the app too, for every ABI the app ships.
Sources: swift.org › Getting Started with the Swift SDK for Android,
docs.swift.org › Swift Android › Integration,
and the Gradle files of swiftlang/swift-android-examples (Apache-2.0),
described here in our own words.
Sizes and versions: `versions.md`.

## Static or dynamic

- **Static** (`--static-swift-stdlib`, or `-Xswiftc -static-stdlib` as the examples' Gradle script passes it):
  the Swift runtime and Foundation are linked into your library.
  Only your `.so` files and `libc++_shared.so` ship.
  This is what swift.org's article builds,
  what the examples' raw-JNI Gradle script does,
  and what one team measured as "the game changer" for size
  (Swift Forums › Android app size and lib_FoundationICU.so, post 26, 2026-05-06).
- **Dynamic:** your library loads the runtime's `.so` files at launch.
  The swift-java example ships sixteen of them —
  `swiftCore`, `swift_Concurrency`, `swift_StringProcessing`, `swift_RegexParser`, `swift_Builtin_float`,
  `swift_math`, `swiftAndroid`, `dispatch`, `BlocksRuntime`, `swiftSwiftOnoneSupport`, `swiftDispatch`,
  `Foundation`, `FoundationEssentials`, `FoundationInternationalization`, `_FoundationICU`, `swiftSynchronization`
  (each as `lib<name>.so`) —
  copied from the SDK's `swift-resources/usr/lib/swift-<arch>/android/`.
  Anything else your code imports must be added:
  `import Observation` needs `libswiftObservation.so`,
  networking needs `libFoundationNetworking.so`.
  A missing one fails at launch:
  `java.lang.UnsatisfiedLinkError: dlopen failed: library "libswiftObservation.so" not found`
  (swift-android-examples › hello-swift-java README).
- **Either way, ship `libc++_shared.so`** from the NDK — Android provides no C++ runtime to apps
  (Swift Forums › On the topic of Swift runtimes, C++ instability, and mismatched NDK versions, post 6).
  It lives in the NDK at `toolchains/llvm/prebuilt/<host>/sysroot/usr/lib/<arch>-linux-android/`.

## Where the files go

- `src/main/jniLibs/<abi>/` (or a generated directory added to `jniLibs`),
  one set per ABI the app declares in `abiFilters`:
  `arm64-v8a` from `aarch64`, `x86_64` from `x86_64`, `armeabi-v7a` from `armv7`.
- The examples' script builds `arm64-v8a` only for debug and all three ABIs for release.
- Keep native symbols when Skip's export is involved:
  Skip's shared-model post keeps `**/*.so` debug symbols to avoid a `dlopen` failure (skip.dev › blog › Sharing a Swift Model Layer).

## A Gradle task, written for this skill

```kotlin
// typecheck: none — Gradle Kotlin DSL; adjust the SDK id, triples and paths, then build it
val swiftPackageDir = rootProject.file("swift")
val swiftSdk = providers.environmentVariable("SWIFT_ANDROID_SDK").orElse("swift-6.4.0-RELEASE_android")
val ndkHome = providers.environmentVariable("ANDROID_NDK_HOME")
val apiLevel = 28
val abis = mapOf("arm64-v8a" to "aarch64", "x86_64" to "x86_64")

abis.forEach { (abi, arch) ->
    val triple = "$arch-unknown-linux-android$apiLevel"
    val build = tasks.register<Exec>("buildSwift_$abi") {
        workingDir = swiftPackageDir
        commandLine("swift", "build", "-c", "release",
            "--swift-sdk", swiftSdk.get(), "--triple", triple, "--static-swift-stdlib")
    }
    val copy = tasks.register<Copy>("copySwift_$abi") {
        dependsOn(build)
        from(swiftPackageDir.resolve(".build/$triple/release")) { include("*.so") }
        from(ndkHome.map { file(it).resolve("toolchains/llvm/prebuilt").listFiles()!!.first()
            .resolve("sysroot/usr/lib/$arch-linux-android/libc++_shared.so") })
        into(layout.buildDirectory.dir("swiftJniLibs/$abi"))
    }
    tasks.named("preBuild") { dependsOn(copy) }
}

android.sourceSets["main"].jniLibs.srcDir(layout.buildDirectory.dir("swiftJniLibs"))
```

- One build per ABI, each with its own triple; the API level matches the app's `minSdk`.
- The examples hook the copy into `merge<Variant>JniLibFolders`;
  `preBuild` is simpler and works for a single variant.
- The examples' `swift-android.gradle.kts` is the fuller reference: it finds swiftly,
  maps every ABI and handles debug and release variants.
  Read it; code copied from it keeps its Apache-2.0 notice.

## Verify

```bash
unzip -l app/build/outputs/apk/release/app-release.apk 'lib/*'
```

- Every ABI directory has your libraries, `libc++_shared.so`,
  and — for a dynamic build — every runtime library they link.
- Then launch on an emulator or a device; say which, or that neither was done.

## C++ runtime versions

The Swift runtime is built against one NDK's C++ runtime, and the app ships another's `libc++_shared.so`.
Runtime maintainers call a static runtime that works with mismatched NDKs unsafe in principle (post 1 of the thread above);
Skip's maintainer reports mixing SDKs built with NDK 27 or 28 and `libc++_shared.so` from NDK 28 to 30 without a C++ problem (post 7).
Use the NDK the SDK was built with when you can (`versions.md`).

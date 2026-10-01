# Installing the SDK and building

The Swift SDK for Android cross-compiles Swift on a macOS or Linux host
into libraries and executables for Android.
Three components are needed:
an open-source Swift toolchain, the Swift SDK for Android, and the Android NDK
(swift.org › Getting Started with the Swift SDK for Android).
The article is Apache-2.0; its commands are reproduced as published.
Values change with every release — `versions.md` has the current ones and their dates.

## Check first

```bash
python3 scripts/toolchain_report.py --format markdown
swift --version
swift sdk list
echo "$ANDROID_NDK_HOME"
```

Everything below changes the machine; propose it, then run it after approval.

## swift.org's commands (Swift 6.4.0, article updated 2026-09-15)

```bash
swiftly install latest
swiftly use latest
swift --version
swift sdk install https://download.swift.org/swift-6.4.0-release/android-sdk/swift-6.4.0-RELEASE/swift-6.4.0-RELEASE_android.artifactbundle.tar.gz --checksum 21fb555122a3d801ad943d48df7ebffdd8824de61c25c180bb792d3edaee0b43
swift sdk list
curl -fSL -o ndk.zip https://dl.google.com/android/repository/android-ndk-r30-$(uname -s).zip
unzip -qo ndk.zip
export ANDROID_NDK_HOME=$PWD/android-ndk-r30
swift build --swift-sdk swift-6.4.0-RELEASE_android --triple aarch64-unknown-linux-android23 --static-swift-stdlib
swift build --swift-sdk swift-6.4.0-RELEASE_android --triple x86_64-unknown-linux-android23 --static-swift-stdlib
```

- **The toolchain must match the SDK exactly.**
  "using a cross-compilation Swift SDK requires using an open-source toolchain and for the Swift SDK version to match exactly"
  (the article, step 1).
  The `swift` inside Xcode cannot use the SDK.
- **The checksum comes from swift.org** — the article, or the install API
  (`https://www.swift.org/api/v1/install/releases.json`, the `android-sdk` platform entry).
  Never type one from memory.
- **The NDK** provides headers, the linker and `libc++_shared.so`;
  the article asks for the LTS r30 release and finds it through `ANDROID_NDK_HOME`.
  Swift Build reads `ANDROID_NDK_ROOT` before `ANDROID_NDK_HOME`,
  so set both, or unset `ANDROID_NDK_ROOT`, when a machine already has another NDK
  (the swiftlang reusable workflow does exactly that).
- An executable built this way still needs `libc++_shared.so` from the NDK next to it on the device:

  ```bash
  adb push .build/aarch64-unknown-linux-android23/debug/hello /data/local/tmp
  adb push $ANDROID_NDK_HOME/toolchains/llvm/prebuilt/*/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so /data/local/tmp/
  adb shell /data/local/tmp/hello
  ```

## What the other sources still say

Until the 6.4 update the article, and still today docs.swift.org's Swift Android guide,
the official examples and swift-android-action, used an older recipe:

- NDK "r27d+ recommended" (docs.swift.org › Getting Started);
- after `swift sdk install`, running `scripts/setup-android-sdk.sh` from inside the installed bundle;
- selecting the SDK by triple: `swift build --swift-sdk aarch64-unknown-linux-android28 --static-swift-stdlib`.

The 6.4 release post says Swift Build "now supports Android in SwiftPM as well, removing the need for a post-install script".
The 6.4.0 bundle still ships the script,
and the per-triple SDK ids still point at the `ndk-sysroot` directory only the script creates —
so the older selector most likely still needs it (*inference*, `versions.md`).
Follow the article; when a guide disagrees, say which one you followed.
What this repository's CI measured about both forms, and about NDK releases, is in `measured-behavior.md` (M1, M5).

## Architectures and API levels

| Android ABI | Swift triple | Use |
| --- | --- | --- |
| `arm64-v8a` | `aarch64-unknown-linux-android<API>` | devices |
| `x86_64` | `x86_64-unknown-linux-android<API>` | most emulators |
| `armeabi-v7a` | `armv7-unknown-linux-android<API>` (docs.swift.org spells it `…-androideabi<API>`) | older 32-bit devices |

- The API level in the triple is the oldest Android version the code may run on.
  The 6.4.0 bundle carries triples for API 23 through 36; 6.3 started at 28 (`versions.md`).
- Below API 24, `FILE*` imports differently, which breaks packages that assume its type (swift-log among them);
  Foundation's `Process` needs `posix_spawn`, which Bionic has from API 28
  (Swift Forums › Android API minimum for the Swift SDK for Android, posts 18, 35, 38).
- Skip apps start at API 28 regardless (`versions.md`).

## Android API availability

Swift 6.3 added an `Android` platform for availability, so newer Android APIs can be gated as on Apple platforms
(swift.org › blog › Exploring the Swift SDK for Android; swift-java › Android):

```swift
// typecheck: shared
#if canImport(Android)
import Android
#endif

@available(Android 33, *)
public func usesAndroid13API() -> Int {
    33
}

public func featureLevel() -> Int {
    if #available(Android 33, *) {
        return usesAndroid13API()
    }
    return 0
}
```

The 6.4 SDK is built with NDK r30, which puts availability attributes on the NDK's own APIs too
(swift.org › Swift 6.4 Released).

## Build systems

SwiftPM 6.4 builds with Swift Build by default;
the official examples still pass `--build-system native` for their Gradle scripts' output paths.
The two word errors differently — a missing module is "no such module 'UIKit'" with the native build system
and "unable to resolve module dependency: 'UIKit'" with Swift Build —
so match on the module name, not the whole message.

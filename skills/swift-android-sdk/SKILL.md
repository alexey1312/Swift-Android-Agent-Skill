---
name: swift-android-sdk
description: >-
  Use this skill when Swift has to build and run on Android without Skip's app
  tooling, or when a Skip Fuse build fails below the Skip layer: installing the
  Swift SDK for Android with a matching open-source toolchain and the NDK,
  swift build with an Android triple and API level, linking the Swift runtime
  statically or shipping its .so files and libc++_shared.so, 'dlopen failed:
  library not found' crashes, FoundationNetworking and Android module imports,
  calling Swift from Kotlin or Java with swift-java jextract in JNI mode or raw
  @_cdecl functions, Gradle jniLibs per ABI, R8 keep rules, app size, LLDB
  debugging, symbolicating tombstones, and Android emulator tests in CI. Not
  for choosing a route or designing shared view models
  (swift-android-architecture), Skip project setup or skip.yml
  (skip-project-creation, skip-fuse), Skip's own test runners (skip-testing),
  or installing Android Studio and Google's SDK by themselves.
---

# Swift on Android: the SDK underneath

The Swift SDK for Android is a cross-compiler, not an app framework.
You pick a toolchain that matches it exactly,
choose how the Swift runtime is linked,
ship every library the app loads,
and own the boundary with Java and Kotlin.
Skip does all of this for the projects it creates;
this skill is for Swift without Skip,
and for failures underneath a Skip Fuse build.

- Install and build, with exact commands: `references/sdk-setup.md`
- Shipping the runtime in an app: `references/packaging.md`
- Swift to and from Java and Kotlin: `references/swift-java.md`
- Code that differs on Android: `references/portability.md`
- App size and debugging: `references/size-and-debugging.md`
- Skip bridging and swift-java side by side: `references/bridge-surface.md`
- CI recipes: `references/ci.md`
- Versions, URLs, checksums and sizes, dated: `references/versions.md`
- What CI measured: `references/measured-behavior.md`
- Skip's skills, and where they disagree with skip.dev: `references/official-skip-skills.md`
- Plan format: `references/recommendation-format.md`
- Citations: `references/sources.md`

## Contract

- **Phase 1 is read-only.**
  The toolchain report, the scan, reading build files and writing the plan change nothing.
- **No edits without approval of item IDs** (`references/recommendation-format.md`).
- **Installing is a change.**
  swiftly, `swift sdk install`, an NDK download or an emulator image changes the machine:
  propose the exact commands, ask, then run them.
- **Cite a source for every item.**
  Commands, URLs, checksums, NDK and API levels come from `references/versions.md`
  and `references/sdk-setup.md` with their dates, never from memory;
  where swift.org's article and the docs.swift.org guide disagree, say which you followed.
  Anything else is labelled *inference*.
- **Report verification honestly.**
  `toolchain_report.py` says what this machine can do.
  A host build is not an Android build;
  an Android build is not a run;
  a run on an emulator is not a run on a device.

## 1. Toolchain

- The SDK needs an open-source Swift toolchain whose version matches it exactly;
  the toolchain inside Xcode cannot use it (swift.org › Getting Started with the Swift SDK for Android).
  swiftly installs and switches open-source toolchains.
- Install the SDK with `swift sdk install <url> --checksum <sha256>`;
  the URL and checksum for the current release are in `references/versions.md`.
- The Android NDK provides the linker and system libraries;
  which NDK release the SDK expects, and how the build finds it,
  changed between releases (`references/sdk-setup.md`).
  Use the release the SDK was built with: with older NDKs, linking the static Swift runtime failed
  on an undefined C++ library symbol (*Measured* M5).
- Check first: `python3 scripts/toolchain_report.py` reports the host toolchain, installed SDKs,
  the NDK, Java and `adb`, and whether this machine can build or run anything for Android.

## 2. Build

- `swift build --swift-sdk <sdk> [--triple <arch>-unknown-linux-android<api>] --static-swift-stdlib`
  (`references/sdk-setup.md` has the exact forms the two official guides use).
- Build `aarch64` for devices and `x86_64` for most emulators;
  the API level in the triple is the minimum Android version the code may call into
  (`references/versions.md`).
- Gate newer Android APIs with `@available(Android <n>, *)` and `#available`
  where the SDK provides availability attributes (`references/portability.md`).

## 3. Ship the runtime

- A dynamically linked Swift library loads the Swift runtime libraries at launch:
  every one it links must be in the app,
  or Android fails with `dlopen failed: library "lib….so" not found`
  (`references/packaging.md`).
- Link the runtime statically where possible; ship `libc++_shared.so` from the NDK either way.
- Libraries go under `jniLibs/<abi>/`, one set per ABI the app declares.
- Verify by listing the built app's `lib/` folder, then by launching it;
  say which of the two was done.

## 4. Swift to and from Java and Kotlin

- **Kotlin calling Swift:** swift-java's `jextract` in JNI mode generates Java wrappers
  that Kotlin can call; its FFM mode needs a newer Java than Android has (`references/swift-java.md`).
  `async` functions come back as futures; closures and generics are limited.
- **Swift calling Java:** swift-java's wrappers and macros, or a handful of hand-written JNI calls.
- **Raw JNI** with `@_cdecl("Java_<package>_<Class>_<method>")`
  suits a few functions with simple types.
- swift-java is pre-1.0 with no API-stability promise: pin its version (`references/versions.md`).
- Keep the generated Java classes from R8 shrinking (`references/swift-java.md`).

## 5. Code that differs on Android

- Networking types need `import FoundationNetworking` behind `#if canImport(FoundationNetworking)`.
- C library imports need a `canImport` ladder that includes `Android`;
  `FILE` handles differ (`references/portability.md`).
- There is no Objective-C runtime: `@objc`, `#selector`, key-value observing and swizzling fail;
  subclassing `NSObject` alone does not.
- `print` output does not reach Android's log in Skip apps (skip.dev › Debugging);
  log through a logging API that writes to logcat (`references/portability.md`).
- `python3 scripts/android_scan.py <path> --route bare-sdk` flags these.

## 6. App size

- The ICU data and Foundation dominate a Swift app's size on Android;
  static linking with stripping, `FoundationEssentials` instead of `Foundation` where the code allows it,
  and size-oriented compiler flags are the levers (`references/size-and-debugging.md`).
- Size figures from other projects are reports with dates (`references/versions.md`);
  measure the app in question before and after.

## 7. Debugging

- LLDB debugs Swift on Android from the command line and from VS Code;
  Android Studio does not stop at Swift breakpoints (`references/size-and-debugging.md`).
- Swift frames in a tombstone or logcat crash are mangled;
  demangle them with `swift demangle` (`references/size-and-debugging.md`).

## 8. CI

- A Linux runner can build for Android and run tests on an emulator;
  `references/ci.md` has the official reusable workflow and a GitHub Action, pinned.
- This repository's own Android job is the reference that the measured facts come from
  (`references/measured-behavior.md`).

## 9. Underneath Skip

- When a Skip Fuse build fails because of the SDK, the NDK, a toolchain mismatch or a missing library,
  the fixes above apply;
  `skip.yml`, bridging options and Skip's commands belong to Skip's `skip-fuse` skill.

## Workflow

### Phase 1 — Recommend

1. **Preflight.**
   `python3 scripts/toolchain_report.py`; the project's own agent instructions
   (`AGENTS.md`, `CLAUDE.md`); `Package.swift`, the Gradle files, and any crash log.
2. **Scan** Swift sources with `--route bare-sdk` (or the project's route).
3. **Plan** with `references/recommendation-format.md`:
   toolchain and installs first, then build, then the runtime and packaging,
   then the Java boundary, then size, debugging and CI.
4. **Ask** which item IDs to apply, and separately for any install.

### Phase 2 — Apply and verify

1. Apply approved items only; change only what they name.
2. Build for the host, then for Android if `toolchain_report.py` says this machine can;
   where a sandbox blocks `swift build`, fall back to `swiftc -typecheck` and say so.
3. Check the packaged libraries; run on an emulator or a device only where one is available.
4. Update each item's status and hand back the report, with what was *not verified*.

## Guardrails

- Do not mix toolchain and SDK versions; check both before building.
- Do not invent download URLs or checksums; copy them from `references/versions.md` or swift.org.
- Do not ship a dynamically linked Swift library without the runtime libraries it links and `libc++_shared.so`.
- Do not claim a fix works on Android from a host build or a successful Gradle build alone.
- Do not run installers or downloads in Phase 1.
- Do not copy third-party code; link it pinned to a commit.

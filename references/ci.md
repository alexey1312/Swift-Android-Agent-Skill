# CI recipes

Two jobs keep shared Swift honest on Android:
a build for Android on every pull request,
and the shared tests running on an Android emulator.
Pins and dates: `versions.md` › CI runners.
This repository's own `.github/workflows/android.yml` runs both against `samples/SharedCore`
and records what it measured in `measured-behavior.md`.

## Where the emulator can run

- Linux runners can run the Android emulator; both recipes below add a udev rule for `/dev/kvm` first.
- macOS on Apple silicon cannot run it (no nested virtualization),
  so `macos-latest` can only build; tests need `ubuntu-latest` or an Intel macOS image
  (swift-android-action README).
- No GitHub-hosted image ships NDK r30, which swift.org's 6.4 article asks for.
  With the image's NDKs, libraries compiled but static executables failed to link (`measured-behavior.md` M5);
  download r30 in the job, as this repository's `compile` job does, and set both `ANDROID_NDK_HOME` and `ANDROID_NDK_ROOT`.

## A Swift package, without Skip

### skiptools/swift-android-action

```yaml
# typecheck: none — workflow YAML; the action has no licence, so it is referenced, never copied
jobs:
  android:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: skiptools/swift-android-action@2044b79660f201ccef8cbce62877e4ec5409f9c8 # v2.9.5
        with:
          swift-version: "6.4.0"     # quote versions; this pin built and tested on 2026-10-01 (M4)
          android-api-level: 28
          free-disk-space: true      # the emulator fails to install on a full disk
          package-path: .
```

- Builds the package for Android and runs its tests on an emulator with `adb`;
  `run-tests: false` only builds, which is much faster.
- It uses the runner's NDK unless `ndk-version` names another preinstalled one,
  and the older `--swift-sdk <arch>-unknown-linux-android<API>` selector.
- Outputs `swift-build`, `swift-sdk` and `swift-install` let later steps reuse the toolchain.

### swiftlang/github-workflows

The official reusable workflow `swift_package_test.yml` builds packages for Android
with `enable_android_sdk_build: true`
and runs tests on an emulator with `enable_android_sdk_checks: true`.
Its defaults test NDK r27d and r28c with `android28` triples,
and it has no input for a package in a subdirectory;
pass `--package-path` through `android_sdk_build_command`.
Pin it to a commit (`versions.md`).

## A Skip project

skip.dev's command sequence for an emulator test run (skip.dev › Skip CLI Reference › CI/CD usage):

```bash
brew install skip
skip android sdk install
skip android emulator create
skip android emulator launch --background --headless
skip android test
```

- `skip android emulator launch` returns only after the emulator reports that it booted;
  `--headless` is picked automatically when `CI` is set (same page).
- `skip test` runs the parity suite (host and Android side by side) and, for native modules,
  Swift Testing tests only (skip.dev › Testing).
- Skip's own framework repositories use the reusable workflow
  `skiptools/actions/.github/workflows/skip-framework.yml@v1`,
  which the documentation does not mention.

## Shared code consumed by a separate Android app

What Polymarket gates every pull request on (`sources.md` › The Polymarket report):

1. the shared test suite on an Android emulator;
2. the Android app built against freshly exported libraries (`skip export`).

Add a scan before both:

```bash
python3 scripts/android_scan.py . --route shared-core --format markdown --fail-on high
```

## Reporting

- Put the Swift version, the SDK id, the NDK and the runner image in the job summary;
  a green run means little without them.
- Keep the probe results as an artifact so the next change can be compared with them.

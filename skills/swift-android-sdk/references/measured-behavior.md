# Measured behavior

What this repository's Android CI (`.github/workflows/android.yml`) actually measured.
A skill or rule may say *Measured* only by naming a section here whose status is `measured`;
a test enforces it.
Each section records the run, the date, the Swift version, the SDK, the NDK and the runner,
so a later run can be compared with it.
Everything else in the skills is cited, not measured.

## Scope

- **Measured here:** whether code compiles for Android with a given SDK, NDK, architecture and API level,
  and what tests assert when they run on an Android emulator.
- **Not measured here:** Skip's bridging and `skip export`, Compose recomposition,
  garbage-collection timing, Android Studio, app size on a device, behavior on physical devices.
  Those claims stay cited (`sources.md`).
- A macOS or iOS typecheck proves nothing about Android and is never recorded here.

## M1 · Installing the SDK as swift.org's article says

- **Status:** pending — waiting for the first run of the `compile` job.
- **Question:** do the article's commands (swiftly, `swift sdk install` with the checksum, NDK r30) work on `ubuntu-latest`?
- **Probe:** the install steps of `android.yml` › `compile`.
- **Result:** —

## M2 · The skills' shared samples build for Android

- **Status:** pending.
- **Question:** does every `// typecheck: shared` block in the references compile for Android?
- **Probe:** `python3 scripts/typecheck_samples.py --android …` in `android.yml` › `compile`.
- **Result:** —

## M3 · What does and does not compile for Android

- **Status:** pending.
- **Question:** the outcomes behind scanner rules `AND001`, `AND003`, `AND005`, `AND006` and `AND008`.
- **Probe:** `scripts/probes/android/` with `scripts/android_probes.py`; expectations in `expectations.json`.
- **Result:** —

## M4 · The shared-core sample's tests on an emulator

- **Status:** pending.
- **Question:** do observation tracking, stream cancellation, JSON and ISO 8601 dates,
  FileManager, ICU formatting and `URLRequest` behave on Android as on the host?
- **Probe:** `samples/SharedCore` tests, `android.yml` › `emulator`.
- **Result:** —

## M5 · NDK and API level

- **Status:** pending.
- **Question:** does the 6.4 SDK need NDK r30, or does the runner's NDK work;
  does API 23 build where API 28 does?
- **Probe:** the `compile` matrix.
- **Result:** —

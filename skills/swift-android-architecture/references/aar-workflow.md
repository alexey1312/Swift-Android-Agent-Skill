# The export loop and CI

How shared Swift modules reach a separate Android app,
and how to keep that path from breaking.
Commands are from skip.dev (paraphrased, CC BY-SA 4.0) and the Polymarket report;
flags change between Skip releases — check `skip export --help` against `versions.md`.

## Exporting

- `skip export` builds the project and writes the binaries to an output folder:
  one `.aar` per target in the project plus an `.aar` for every dependency;
  app projects also get an `.apk` and an `.aab`
  (skip.dev › Deployment › Exporting Build Artifacts).
  For native modules the export compiles the Swift and embeds the `.so` libraries.
- skip.dev's separate-apps example exports a model package into the Android app's library folder,
  once per configuration:

  ```bash
  skip export --project travel-posters-model -d Android/lib/debug/ --debug
  skip export --project travel-posters-model -d Android/lib/release/ --release
  ```

  (skip.dev › Project Structure › Creating Separate iOS and Android Apps).
  The CLI reference spells the output flag `--dir`, and adds `--module <Name>` to export one module
  (skip.dev › Skip CLI Reference).
- Polymarket's loop: edit Swift, run `skip export` — it "recompiles only the modules that changed and drops fresh AARs into the Android project" —
  sync Gradle, build and run (report, post 1).
  The extra step is the main cost Android engineers feel;
  Android Studio cannot run it for them.

## Consuming the libraries in Gradle

- Treat the exported archives like any other dependency.
  skip.dev's shared-model post wires them in per configuration with file-tree dependencies
  over the debug and release folders
  (skip.dev › blog › Sharing a Swift Model Layer, 2024-12-19).
  A local Maven repository or a git submodule are the documented alternatives for automating the hand-off
  (skip.dev › Project Structure).
- **Declare the transitive Android dependencies yourself.**
  "You must ensure that all transitive dependencies are in your own app's `build.gradle.kts`."
  (skip.dev › Project Structure).
  A missing one fails at run time, when the exported code first calls into it.
- The same post adds Kotlin reflection, which Skip uses,
  keeps the native libraries' symbols (`keepDebugSymbols` for `**/*.so`) to avoid a `dlopen` failure,
  and makes one initialization call from the main activity before the model is used
  (`skip.foundation.ProcessInfo.launch(context = this)`).
  Check each against the Skip release you export with;
  the post predates the official Swift SDK for Android.
- Kotlin sees a module in a package derived from its name
  (`TravelPostersModel` becomes `travel.posters.model`);
  `package` in `skip.yml` overrides it (skip.dev › Common Topics).

## CI

- Gate every pull request that touches shared code on two things,
  as Polymarket does:
  the shared test suite passing on an Android emulator,
  and the Android app building against freshly exported libraries.
  "The fix isn't vigilance, it's CI" (report).
- Recipes, pinned and dated, are in `ci.md`:
  Skip's own command sequence for an emulator test run,
  and a GitHub Action that builds a package for Android and runs its tests on an emulator.
- Add `python3 scripts/android_scan.py <root> --route shared-core --fail-on high`
  as a fast first step: it catches an Apple-only import before the Android build does.
- Write the shared tests with Swift Testing if the modules are native Skip modules:
  `skip test` runs native test targets through Swift Testing only (skip.dev › Testing).

## Keeping debug builds debuggable

- Print statements never reach Logcat; use `OSLog.Logger`, which Skip forwards to it
  (skip.dev › Debugging).
- There are no Swift breakpoints in Android Studio;
  a native crash in Logcat shows mangled Swift names —
  demangle them with `xcrun swift-demangle` (skip.dev › Debugging).
  LLDB outside Android Studio: `versions.md` › Debugging.

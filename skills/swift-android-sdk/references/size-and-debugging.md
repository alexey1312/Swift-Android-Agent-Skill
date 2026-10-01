# App size and debugging

## Where the size comes from

- A Swift library on Android carries the Swift runtime and Foundation with it.
  The ICU data inside Foundation's internationalization support is the largest single part:
  40 MB of `lib_FoundationICU.so` in a 2025 listing,
  about 44 MiB in the 6.4.0 SDK's aarch64 libraries (`versions.md` › Sizes).
- Reported totals, all dated in `versions.md`:
  Skip's native mode adds about 60 MB (skip.dev);
  Polymarket's app grew by about 50 MB at download (2026-08-04);
  a static, FoundationEssentials-only library was about 18 MB, its R8-shrunk APK 12 MB compressed (2026-05-06).
  None of these was measured by this repository.

## Levers

1. **Link statically and strip.**
   `--static-swift-stdlib` links only what the code uses;
   "static linking plus stripping is the game changer"
   (Swift Forums › Android app size and lib_FoundationICU.so, @keeshux, post 26, 2026-05-06).
2. **Use FoundationEssentials instead of Foundation** where the code needs no locale-aware formatting;
   that drops the ICU data.
   Formatting dates, numbers and currencies for the user's locale needs FoundationInternationalization and ICU —
   check what the code formats before cutting it.
   A change to load the ICU data from a file instead was closed unmerged (2026-01-11), so there is no lighter ICU option today.
3. **Size flags for JNI libraries** (swift-java › Reducing Binary Size; Swift 6.3 or later):
   `-Osize`, full LTO (`--experimental-lto-mode=full`),
   `-Xfrontend -internalize-at-link`,
   and the linker version script that `JExtractSwiftPlugin` writes (`-Xlinker --version-script=…`),
   which keeps only the JNI entry points exported.
4. **Deliver per ABI.**
   An Android App Bundle lets Google Play send each device one ABI's libraries;
   skip.dev's FAQ notes that an `.apk` therefore overstates download size.

Measure before and after on the app in question:

```bash
unzip -lv app-release.apk 'lib/arm64-v8a/*'
```

## Debugging

- **LLDB works outside Android Studio.**
  With the Swift 6.3 fixes, "debugging Swift on Android now works reasonably well, from the command line or with VS Code"
  (Swift Forums › Swift Debugging on Android - Current State, @gabriele, post 6, 2026-03-24).
  It runs `lldb-server` from the NDK on the device, inside the app's sandbox;
  the VS Code route is an experimental lldb-dap extension built from a fork,
  configured with the NDK path and an `androidComponent` in `launch.json`,
  and the app installed with `-Pandroid.injected.testOnly=true` to avoid an `lldb-server` bug (same post).
- **Android Studio** does not stop at Swift breakpoints
  (skip.dev › FAQ; Polymarket report, 2026-08-04).
- **Logging** is the everyday tool: `portability.md` › Logging.
- **Crashes.**
  A native Swift crash in Logcat shows mangled Swift symbols, not a line-numbered stack trace;
  demangle them (skip.dev › Debugging):

  ```bash
  adb logcat
  echo '<mangled symbol>' | xcrun swift-demangle
  ```

  On Linux, `swift demangle` does the same.
- **Keep symbols** in the packaged `.so` files of debug builds,
  or neither LLDB nor the demangled names get far.

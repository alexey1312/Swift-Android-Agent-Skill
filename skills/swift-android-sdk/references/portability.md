# Code that differs on Android

Swift on Android is Swift on Linux with Bionic instead of glibc,
plus the Android NDK.
Most portable Swift builds unchanged;
these are the places where it does not.
`python3 scripts/android_scan.py <path> --route bare-sdk` finds most of them;
`measured-behavior.md` (M3) records which ones CI saw fail.

## Foundation is split

Off Apple platforms Foundation is several modules:
FoundationEssentials, FoundationInternationalization,
FoundationNetworking (`URLSession`, `URLCache`) and FoundationXML (`XMLParser`)
(skip.dev › Porting).
`import Foundation` does not bring in networking:

```swift
// typecheck: shared
import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public func makeRequest(to url: URL) -> URLRequest {
    var request = URLRequest(url: url)
    request.setValue("application/json", forHTTPHeaderField: "Accept")
    return request
}
```

"Foundation networking types require a separate import on non-Apple platforms" (docs.swift.org › Building for Android).
Without it, the error is about `URLSession` lacking `shared`, which hides the cause (skip.dev › Porting).
Depending on `FoundationEssentials` alone, where the code allows it, also leaves out the ICU data (`size-and-debugging.md`).

## The C library

```swift
// typecheck: shared
#if canImport(Darwin)
import Darwin
#elseif canImport(Android)
import Android
#elseif canImport(Glibc)
import Glibc
#elseif canImport(Musl)
import Musl
#endif

public func processID() -> Int32 {
    getpid()
}
```

- `import Android` is a superset of `Bionic`; prefer it (skip.dev › Porting).
- "In my experience, adding `#if canImport(Android) import Android` is the single most common way to get a package that was already building for Linux to build for Android."
  (Swift Forums › Android package compatibility now showing on swiftpackageindex.com, @marcprux, post 6, 2025-06-03).
- `FILE` does not exist on Android: `UnsafeMutablePointer<FILE>` becomes `OpaquePointer` there (skip.dev › Porting):

```swift
// typecheck: shared
#if canImport(Darwin)
import Darwin
#elseif canImport(Android)
import Android
#elseif canImport(Glibc)
import Glibc
#endif

#if os(Android)
public typealias CFilePointer = OpaquePointer
#else
public typealias CFilePointer = UnsafeMutablePointer<FILE>
#endif

public func writeLine(_ text: String, to stream: CFilePointer) {
    fputs(text + "\n", stream)
}
```

## Apple-only frameworks

UIKit, SwiftUI, MapKit, PassKit, HealthKit, StoreKit, CloudKit, Combine, CoreGraphics and the other `*Kit` frameworks
do not exist on Android (skip.dev › Porting; skip.dev › FAQ).
Wrap optional uses in `#if canImport(<Module>)`,
and move required ones behind a protocol implemented per platform.
For Combine, skip.dev points to OpenCombine.

## No Objective-C runtime

Objective-C interoperability exists only on Apple platforms
(the compiler enables it for Darwin targets only),
so `@objc`, `@objcMembers`, `#selector`, `import ObjectiveC`, key-value observing through `#keyPath`
or `addObserver(_:forKeyPath:)`, and method swizzling do not compile or do not work on Android
(scanner `AND008`; CI probe in `measured-behavior.md`, M3).
Subclassing `NSObject` by itself is fine,
and so is `NSClassFromString`:
swift-corelibs-foundation provides both on platforms without an Objective-C runtime.

## Android API levels

Gate newer Android APIs with `@available(Android <n>, *)` and `if #available(Android <n>, *)`
(Swift 6.3 and later; `sdk-setup.md`).
Below API 28 Foundation's `Process` is missing its `posix_spawn` underpinning,
and below API 24 `FILE*` imports differently (`versions.md`).

## Logging

- `print` writes to standard output, which Android does not show in Logcat
  (skip.dev › FAQ; skip.dev › Debugging).
- In Skip modules, `OSLog.Logger` is forwarded to Logcat.
- Without Skip, log through Android's logging library from the NDK,
  or a logging package with a Logcat backend;
  check what your SDK's `Android` module exposes before relying on it (*inference*).

## Threads

Nothing in the Swift or Skip documentation says how `@MainActor` or `DispatchQueue.main`
relate to Android's main (Looper) thread, or which thread a JNI call arrives on (`sources.md`).
Do not assume that Swift's main actor is Android's UI thread;
hand results to the UI through the Java/Kotlin side's own main-thread mechanism (*inference*).

# Swift and Java/Kotlin with swift-java

swift-java (Apache-2.0) generates the glue between Swift and Java in both directions:
`jextract` makes Java classes that call into Swift,
and `wrap-java` makes Swift types that call into Java.
Kotlin uses the generated Java classes like any others.
Facts below are from the swift-java README and documentation at release 0.6.0
(`sources.md`; current version in `versions.md`).
"There is no guarantee of API stability until the project reaches a 1.0 release." (README) — pin the version.

## Pick JNI mode

- `jextract` has two modes.
  FFM is the default and needs JDK 25+;
  JNI "works on older JVMs as well as on Android" (README).
  The documentation's advice: "Start with JNI mode unless you have a specific need only FFM mode can meet."
  (Features Overview).
- Building with JNI mode needs JDK 17+ on the build machine.

## Swift package

```swift
// swift-tools-version: 6.2
// typecheck: none — needs the swift-java package, which this repository does not build
import PackageDescription

let package = Package(
    name: "Compress",
    products: [
        .library(name: "Compress", type: .dynamic, targets: ["Compress"]),
    ],
    dependencies: [
        .package(url: "https://github.com/swiftlang/swift-java", exact: "0.6.0"),
    ],
    targets: [
        .target(
            name: "Compress",
            dependencies: [.product(name: "SwiftJava", package: "swift-java")],
            swiftSettings: [.swiftLanguageMode(.v5)],
            plugins: [.plugin(name: "JExtractSwiftPlugin", package: "swift-java")]
        ),
    ]
)
```

and next to the target's sources, `Sources/Compress/swift-java.config` (JSON 5):

```json
{
  "javaPackage": "com.example.compress",
  "mode": "jni"
}
```

- `JExtractSwiftPlugin` generates the Java wrappers and the Swift thunks at build time;
  `SwiftJavaPlugin` runs `wrap-java`; `JavaCompilerPlugin` compiles `.java` files kept next to the target
  (swift-java › SwiftPM Plugin).
- The documentation's sample manifest uses the Swift 5 language mode
  because some generated code is not clean in Swift 6 mode.
- Useful keys (swift-java › Configuration File):
  `asyncFuncMode: "legacyFuture"` for apps that support Android 23 and below, where `CompletableFuture` is missing;
  `enableJavaCallbacks: true` to implement Swift protocols in Java or Kotlin (JNI mode only; the build then needs `--disable-sandbox`);
  `minimumInputAccessLevelMode` to extract more than `public` declarations;
  `specialize` for generic types.

## What Kotlin gets

- Classes and structs become Java classes whose instances live in a `SwiftArena`;
  close the arena (or use the automatic one, if allowed) to release them.
- `async` functions return `CompletableFuture`; Kotlin can `await()` them with kotlinx-coroutines.
- Throwing functions throw Java exceptions; optionals become `Optional`/`OptionalLong`;
  `Int` becomes `long`, range-checked.
- Closures may be escaping or not, with `Void` or primitive parameters and results.
- Generics are limited: members that use type parameters are dropped unless specialised.
- The full table, side by side with Skip's bridge: `bridge-surface.md`.

## The Android app

- **Java support libraries.**
  swift-java's runtime libraries are "not yet published to Maven Central" (README):
  publish them to the local Maven repository (`./gradlew publishToMavenLocal`, which needs JDK 25)
  and add `mavenLocal()`, as the official example does.
- **Native libraries.**
  Build the package for each ABI and ship the libraries with the Swift runtime and `libc++_shared.so`
  (`packaging.md`).
  The official example copies the runtime `.so` files next to its own.
- **Generated Java sources.**
  Add the plugin's output directory (under `.build/plugins/outputs/…/JExtractSwiftPlugin/`) as a Java source directory;
  the exact path differs between the documentation and the example — find it after a build.
- **R8.**
  "Since swift-java uses JNI and reflection APIs, the R8 optimizer must be told to keep the wrapped types."
  (swift-java › Android).
  swift-java's own runtime ships consumer rules; add yours:

  ```text
  -keep class com.example.compress.** { *; }
  -keep interface com.example.compress.** { *; }
  ```

- **Core library desugaring.**
  If the app enables it, turn on the `AndroidCoreLibraryDesugaring` trait on the swift-java package dependency
  so SwiftJava finds the relocated `j$` classes (swift-java › Android).
- The official example to read is `hello-swift-java` in swiftlang/swift-android-examples:
  a Swift library exposed to a Compose app through JNI-mode bindings.

## Swift calling Java

- `wrap-java` (through `SwiftJavaPlugin`) generates Swift wrappers for Java classes listed in `swift-java.config`.
- Wrapping `android.jar` with `--android-api-version-file` puts `@available(Android N, *)` on the wrappers;
  that needs Swift 6.3 or later (swift-java › Android).

## Raw JNI

For a few functions with simple types, `@_cdecl` exports a symbol that Java can bind to a `native` method:

```swift
// typecheck: none — needs the JNI headers that the Android SDK provides
@_cdecl("Java_com_example_weather_WeatherCore_average")
public func average(_ env: UnsafeMutablePointer<JNIEnv?>, _ clazz: jclass) -> jdouble {
    42
}
```

- The function name is `Java_` plus the package, class and method, with dots as underscores.
- docs.swift.org's example and the official example differ in how they type the `JNIEnv` pointer;
  check the one your SDK's JNI module declares.
- Strings, arrays and objects need JNI calls on both sides; past a handful of functions, use swift-java.

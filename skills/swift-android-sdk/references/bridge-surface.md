# What crosses to Kotlin

Two bridges carry natively compiled Swift to Kotlin and Java:
Skip's, for native (Fuse) modules,
and swift-java's `jextract` in JNI mode, without Skip.
Design a shared API for the stricter of the two if both may consume it.
Skip's rules are paraphrased from skip.dev's Bridging Reference and the SkipBridge README
(skip.dev commit `f0680d1`, read 2026-10-01);
swift-java's from its `FeaturesJextract.md` and `SwiftJavaConfigFile.md` at release 0.6.0.
Versions: `versions.md`.

## Side by side

| Swift | Skip bridging (native module) | swift-java `jextract`, JNI mode |
| --- | --- | --- |
| Classes | yes, inheritance up to four levels | yes; instances live until their `SwiftArena` closes |
| Structs | yes; keep mutable structs away from hand-written Kotlin (value semantics hold only toward transpiled Swift) | yes, as wrapper classes |
| Enums with associated values | yes | a Java class with a factory per case and pattern-matching helpers |
| Protocols | yes, with property and function requirements; no constructor or static requirements | Java interfaces; returning `any P` / `some P` through a generated box |
| Swift protocol implemented on the Java/Kotlin side | not documented; Polymarket reports doing it (`sources.md`) — verify with a build | with `enableJavaCallbacks: true` (JNI mode only, needs the SwiftPM sandbox disabled) |
| `async` functions | Kotlin `suspend` functions | `CompletableFuture` by default (`legacyFuture` for Android 23 and below); Kotlin can `await()` it |
| `AsyncStream`, `AsyncThrowingStream` | Kotlin `Flow` — the Bridging Reference says in `kotlincompat` mode, the SkipBridge README says always | not listed |
| `AsyncSequence` | not stated | not listed |
| Combine publishers | not bridged; Polymarket adapted them to `async`/`AsyncStream` | not listed |
| Closures | up to five parameters; not as collection elements; not as parameters of other closures; async closures supported | escaping and non-escaping, with `Void` or primitive parameters and results |
| Throwing functions | Swift errors become Kotlin exceptions; bridged `Error` types extend `Exception`, so they cannot be subclasses | yes; the Java exception type is `Exception` |
| Generics | limited: generic types cannot be constructed from Kotlin; generic global functions are erased | work in progress; members using type parameters are dropped unless specialised |
| `Int` | 32-bit Kotlin `Int` on the JVM | Java `long`, range-checked |
| `Optional` | yes | parameters and return values |
| `Date`, `UUID`, `URL` | with `kotlincompat`: `java.util.Date`, `java.util.UUID`, `java.net.URI` | `Instant` wrapper, `java.util.UUID`, a URL wrapper |
| Arrays, dictionaries, sets | Skip's own Kotlin types, or `List`, `Map`, `Set` with `kotlincompat` | copied arrays; live `SwiftDictionaryMap` / `SwiftSet` wrappers |
| `Character`, `OptionSet`, `A & B` | not bridgeable | — |
| Actors | bridgeable, but not their non-private mutable properties | — |
| Identity | never rely on `===`: one object can get several wrappers | — |

## Rules for a shared API

- **Prefer `async` functions and streams to closures.**
  Polymarket found bridging Swift closures to Kotlin "far harder than we expected" (report).
  When a closure is unavoidable, keep it to a few simple parameters and out of collections.
- **No Combine in the public surface** (scanner `AND011`).
- **Value types in, value types out**, immutable where Kotlin reads them;
  classes for things with identity and a lifetime
  (the architecture skill's lifetime reference).
- **Watch `Int`** on the Skip side: 32-bit in Kotlin.
- **Keep generics internal.**
  Expose concrete types, or specialise them (`specialize` in swift-java's configuration).
- **Read the generated Kotlin or Java** before writing the other side;
  names, packages and nullability come from the generator, not from the Swift source.

## Skip options that change the surface

- `bridging: true` in `skip.yml` bridges all public API;
  `// SKIP @nobridge` opts a declaration out, `// SKIP @bridge` opts one in,
  `// SKIP @bridgeMembers` bridges a type's members at its own visibility or above
  (skip.dev › Lite and Fuse Modes › Bridging).
- `options: 'kotlincompat'` makes the generated Kotlin use standard Kotlin and Java types
  instead of Skip's mirrors — what hand-written Kotlin and Compose want
  (skip.dev › Lite and Fuse Modes › Kotlin Compatibility Option).
- The `skip.yml` details belong to Skip's `skip-fuse` skill.

## swift-java configuration for Android

- `mode: "jni"` in `swift-java.config` — the default is FFM, which Android cannot run.
- `javaPackage` names the generated package.
- `enableJavaCallbacks: true` lets Java implement Swift protocols (JNI mode only).
- `asyncFuncMode: "legacyFuture"` for apps that support Android 23 and below.
- Details and the Gradle side: the SDK skill's swift-java reference.

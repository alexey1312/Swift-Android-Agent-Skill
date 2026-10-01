#!/usr/bin/env python3
"""Read-only Swift-on-Android scanner for code shared between iOS and Android.

The scanner never modifies files. It reads `Package.swift` manifests, Skip's
`Skip/skip.yml` files and `Package.resolved` pins, decides which targets are
shared with Android (every Skip module plus the targets or paths named with
`--shared`), and reports the patterns that stop shared Swift from compiling or
behaving on Android: Apple-only frameworks, Combine and `ObservableObject`,
networking without `FoundationNetworking`, the Objective-C runtime, `print`,
and API that Skip cannot bridge to Kotlin. With nothing shared yet it runs as a
survey and rates every target as a sharing candidate instead.

Conditional compilation is evaluated per line for an Android build of the
module (`#if os(Android)`, `canImport(UIKit)`, `SKIP`, `&&`, `||`, `!`,
`#elseif`, `#else`, nesting): a line that Android never compiles is not
reported, and a line under a condition the scanner cannot decide is reported
with that condition in `guard`.

Every rule cites where it comes from: a skip.dev or docs.swift.org page, a
Swift Forums post with its date, or a file in a GitHub repository. Matches are
heuristics: read the surrounding code before recommending a change.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

VERSION = "1.0.0"

SEVERITIES = ["high", "medium", "low", "info"]
ROUTES = {
    "fuse-app": "Skip Fuse app: SwiftUI on both platforms through SkipFuseUI, Swift compiled natively",
    "shared-core": "Swift modules compiled natively by Skip and exported as AARs to a native Kotlin and Compose app",
    "lite": "Skip Lite: Swift transpiled to Kotlin",
    "bare-sdk": "Swift SDK for Android without Skip; Java interop through swift-java or JNI",
}
DEFAULT_ROUTE = "shared-core"

ARCHITECTURE = "swift-android-architecture"
SDK = "swift-android-sdk"

EXCLUDED_DIRS = {".git", ".gradle", ".idea", ".kotlin", ".derived-data", "build", "node_modules", "xcuserdata"}
DEPENDENCY_DIRS = {".build", ".swiftpm", "DerivedData", "Pods", "Carthage", "checkouts", "SourcePackages"}
MANIFEST_VARIANT = re.compile(r"^Package@swift-[\d.]+\.swift$")

# The official Swift SDK for Android first shipped with the 6.3 toolchain (skip.dev › FAQs),
# so `swift(>=X)` and `compiler(>=X)` hold on Android for any X up to this.
ANDROID_SWIFT_FLOOR = (6, 3)

S_POLYMARKET = "Swift Forums › Our Android App Is Written in Swift (2026-08-04)"
S_PORTING = "skip.dev › Porting Swift Packages to Android"
S_FAQ = "skip.dev › FAQs › What core iOS frameworks will work with Skip Fuse?"
S_SKIPMODEL = "skip.dev › SkipModel"
S_APPDEV = "skip.dev › App Development › @Observables"
S_DEBUGGING = "skip.dev › Debugging › Logging"
S_FAQ_LOGGING = "skip.dev › FAQs › How does logging work in Skip?"
S_ARCHITECTURE = "skip.dev › Internal Architecture"
S_SKIPBRIDGE = "skip.dev › SkipBridge"
S_PLATFORM = "skip.dev › Cross-Platform Topics › #if os(Android) vs #if SKIP"
S_BRIDGING = "skip.dev › Bridging Reference"
S_MODES = "skip.dev › Lite and Fuse Modes › Configuration"
D_BUILDING = "docs.swift.org › Android › Building for Android"
D_PORTING = "docs.swift.org › Android › Porting Swift Packages to Android"
G_CORELIBS = "GitHub › swiftlang/swift-corelibs-foundation README.md"
G_OBJC_INTEROP = "GitHub › swiftlang/swift lib/Frontend/CompilerInvocation.cpp (EnableObjCInterop defaults to Target.isOSDarwin())"
G_SKIPSTONE_WARNING = "GitHub › skiptools/skipstone Sources/SkipSyntax/Kotlin/KotlinMessage.swift"
G_SKIPSTONE_UI_IMPORTS = "GitHub › skiptools/skipstone Sources/SkipSyntax/Kotlin/KotlinBridgeToKotlinVisitor.swift"
G_SKIPSTONE_MODE = "GitHub › skiptools/skipstone Sources/SkipBuild/Commands/SkipstoneCommand.swift"
# Compile probes this repository ran for Android in CI (references/measured-behavior.md).
M_PROBES = "Measured: M3"


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    severity: str
    # shared: every shared file; native: shared files compiled natively for Android;
    # skip-native: files of Skip modules in native mode; bridged: public API of bridged
    # Skip modules; skip.yml: a Skip module's configuration.
    scope: str
    skill: str
    source: str
    fix: str
    by_route: dict[str, str] = field(default_factory=dict)
    # Severity in a transpiled module (Skip Lite), where SkipModel and friends stand in.
    transpiled: str | None = None


RULES: dict[str, Rule] = {
    rule.id: rule
    for rule in [
        Rule(
            id="AND001",
            title="UIKit, AppKit or SwiftUI imported into shared code",
            severity="high",
            scope="shared",
            skill=ARCHITECTURE,
            source=f"{S_POLYMARKET}; {S_PORTING}; {S_FAQ}; {M_PROBES}",
            fix=(
                "Android has no UIKit, AppKit or WatchKit, and SwiftUI exists there only in a Skip UI "
                "module (one that depends on SkipFuseUI or SkipUI). Move the view code to the iOS target "
                "or guard it with `#if canImport(UIKit)` or `#if !os(Android)`, and keep shared types free "
                "of UI frameworks. Polymarket keeps UIKit and SwiftUI code in its iOS package and gates "
                "changes to shared code on an Android build in CI."
            ),
        ),
        Rule(
            id="AND002",
            title="Apple-only framework imported into shared code",
            severity="high",
            scope="shared",
            skill=ARCHITECTURE,
            source=f"{S_PORTING}; {S_FAQ}; {S_POLYMARKET}",
            fix=(
                "This framework does not exist on Android. Put the capability behind a protocol in shared "
                "code and inject the platform implementation at startup, as Polymarket did for payments, "
                "analytics, storage, notifications and authentication; `detail` names an Android-capable "
                "alternative where one exists (Skip's `skip-frameworks` skill covers adding Skip modules). "
                "Wrap what stays iOS-only in `#if canImport(<Module>)`."
            ),
        ),
        Rule(
            id="AND003",
            title="Combine imported into shared code",
            severity="high",
            scope="shared",
            skill=ARCHITECTURE,
            source=f"{S_FAQ}; {S_POLYMARKET}; {S_SKIPMODEL}; {M_PROBES}",
            fix=(
                "Combine is not available to Swift compiled for Android (Skip Fuse or the bare SDK), so this "
                "import does not compile there. Move to Swift Concurrency (async functions, `AsyncStream`) "
                "and Observation, or guard the import and use OpenCombine, which Polymarket reports running "
                "on Android; Skip's bridge carries async API to Kotlin but not publishers. In a transpiled "
                "Skip Lite module SkipModel supports `ObservableObject`, `@Published` and part of "
                "`Publisher`, so the finding is informational there."
            ),
            transpiled="info",
        ),
        Rule(
            id="AND004",
            title="ObservableObject or @Published in shared code",
            severity="high",
            scope="shared",
            skill=ARCHITECTURE,
            source=f"{S_POLYMARKET}; {S_SKIPMODEL}; {S_APPDEV}",
            fix=(
                "Migrate the type to `@Observable` (Observation ships with the Swift SDK for Android), as "
                "Polymarket did screen by screen before sharing its ViewModels; Skip makes `@Observable` "
                "types drive Compose. `ObservableObject` and `@Published` come from Combine, which natively "
                "compiled Swift only gets through OpenCombine. Only Skip Lite's SkipModel transpiles them, "
                "so the finding is informational in a transpiled module."
            ),
            transpiled="info",
        ),
        Rule(
            id="AND005",
            title="Networking types used without FoundationNetworking",
            severity="high",
            scope="native",
            skill=SDK,
            source=f"{D_BUILDING}; {S_PORTING}; {M_PROBES}",
            fix=(
                "Outside Apple platforms `URLSession`, `URLRequest`, `HTTPURLResponse` and the other "
                "networking types live in `FoundationNetworking`, not `Foundation`. Add "
                "`#if canImport(FoundationNetworking)` / `import FoundationNetworking` / `#endif` to every "
                "file that uses them; an `#if os(Linux)` guard leaves Android out."
            ),
        ),
        Rule(
            id="AND006",
            title="C library imported without an Android branch",
            severity="medium",
            scope="native",
            skill=SDK,
            source=f"{D_PORTING}; {S_PORTING}; {M_PROBES}",
            fix=(
                "Android's C library module is `Android`, not `Darwin` or `Glibc`. Use a `canImport` ladder "
                "with an Android branch (`#if canImport(Darwin)` … `#elseif canImport(Android)` / "
                "`import Android` …), and on Android replace `UnsafeMutablePointer<FILE>` with "
                "`OpaquePointer`: `FILE` is not a type there."
            ),
        ),
        Rule(
            id="AND007",
            title="print output does not reach Android logging",
            severity="low",
            scope="shared",
            skill=SDK,
            source=f"{S_DEBUGGING}; {S_FAQ_LOGGING}",
            fix=(
                "Skip's documentation says `print` goes to standard output, which Android's log never shows. "
                "Log through `OSLog.Logger` instead (`import SkipFuse` in a native module, `import OSLog` in "
                "Skip Lite); Skip forwards it to Logcat. On the bare SDK route the citation is Skip's, so the "
                "finding is informational: check where the app's standard output goes before relying on it."
            ),
            by_route={"bare-sdk": "info"},
        ),
        Rule(
            id="AND008",
            title="Objective-C runtime feature in natively compiled code",
            severity="high",
            scope="native",
            skill=SDK,
            source=f"{G_CORELIBS}; {G_OBJC_INTEROP}; {M_PROBES}",
            fix=(
                "The Swift compiler enables Objective-C interop only for Darwin targets, and Foundation "
                "outside Apple platforms (swift-corelibs-foundation) is built for platforms with no "
                "Objective-C runtime: `@objc`, `#selector`, `#keyPath`, KVO and associated objects do not "
                "compile for Android. Use closures, protocols, Observation or async sequences. Subclassing "
                "`NSObject` alone is fine: corelibs-foundation provides it."
            ),
        ),
        Rule(
            id="AND009",
            title="@Observable in a Skip native module without import SkipFuse",
            severity="medium",
            scope="skip-native",
            skill=ARCHITECTURE,
            source=f"{S_APPDEV}; {G_SKIPSTONE_WARNING}; {G_SKIPSTONE_UI_IMPORTS}",
            fix=(
                "Add `import SkipFuse` (or `import SkipFuseUI`) to this file. Skip asks for it in every file "
                "that declares an `@Observable` type, because without it changes to the type never reach "
                "Compose; the build only warns. Like skipstone, the scanner accepts a file that imports "
                "SwiftUI instead. A Kotlin UI also needs the type bridged and a SkipModel dependency. Skip's "
                "`skip-fuse` skill covers the rest of the Fuse setup."
            ),
        ),
        Rule(
            id="AND010",
            title="#if !SKIP in a natively compiled Skip module",
            severity="low",
            scope="skip-native",
            skill=ARCHITECTURE,
            source=S_PLATFORM,
            fix=(
                "In a native (Fuse) module, code under `#if !SKIP` is built for Android as well as iOS; only "
                "transpiled modules leave it out of Android. For iOS-only code use `#if !os(Android)`, and keep "
                "`#if !SKIP` for Swift meant to run on both platforms."
            ),
        ),
        Rule(
            id="AND011",
            title="Combine publisher in bridged public API",
            severity="medium",
            scope="bridged",
            skill=ARCHITECTURE,
            source=f"{S_POLYMARKET}; {S_BRIDGING}; {S_SKIPBRIDGE}",
            fix=(
                "Skip's bridge projects async Swift into Kotlin but leaves Combine publishers out, so Kotlin "
                "never sees this member. Expose an async function or an `AsyncStream` next to it, as "
                "Polymarket reports doing; `AsyncStream` and `AsyncThrowingStream` arrive in Kotlin as a "
                "`Flow` (the Bridging Reference says in kotlincompat mode, the SkipBridge README says always). "
                "Mark the publisher `// SKIP @nobridge` or make it internal."
            ),
        ),
        Rule(
            id="AND012",
            title="Closure type that Skip cannot bridge",
            severity="medium",
            scope="bridged",
            skill=ARCHITECTURE,
            source=f"{S_BRIDGING}; {S_POLYMARKET}",
            fix=(
                "Skip's bridge carries a closure with at most five parameters, and none that sits in a "
                "collection or is handed to another closure. Pass one struct instead of many parameters, wrap "
                "stored callbacks in a bridged class or protocol, or mark the declaration `// SKIP @nobridge`."
            ),
        ),
        Rule(
            id="AND020",
            title="skip.yml does not set mode",
            severity="info",
            scope="skip.yml",
            skill=ARCHITECTURE,
            source=f"{S_MODES}; {S_ARCHITECTURE}; {G_SKIPSTONE_MODE}",
            fix=(
                "The default depends on where you read: Lite and Fuse Modes says transpiled, Internal "
                "Architecture says automatic, and skipstone builds a module without `mode` (or with "
                "`automatic`) natively only when SkipFuse is in its dependency graph and it is the module "
                "being built, transpiled otherwise. Set `mode: 'native'` or `mode: 'transpiled'` "
                "explicitly; `detail` says which mode the scanner assumed. Skip recommends native mode for "
                "most apps."
            ),
        ),
    ]
}

# Apple-only modules (AND002, and `canImport(...)` is false for them on Android) with the
# Android-capable alternative where one exists. ("skip", text) names a Skip framework, which
# only helps on Skip routes; ("any", text) applies on every route.
PROTOCOL_HINT = "no Android counterpart: keep it behind a protocol with a platform implementation"
APPLE_ONLY: dict[str, tuple[str, str]] = {
    "ARKit": ("any", ""),
    "AVFoundation": ("skip", "SkipAV"),
    "AVKit": ("skip", "SkipAV"),
    "Accelerate": ("any", ""),
    "Accounts": ("any", ""),
    "ActivityKit": ("any", ""),
    "AdServices": ("any", ""),
    "AdSupport": ("any", ""),
    "AppIntents": ("any", ""),
    "AppTrackingTransparency": ("any", ""),
    "AudioToolbox": ("any", ""),
    "AuthenticationServices": ("skip", "SkipAuthenticationServices (web authentication sessions)"),
    "BackgroundTasks": ("any", ""),
    "CallKit": ("any", ""),
    "CarPlay": ("any", ""),
    "CloudKit": ("any", ""),
    "Contacts": ("skip", "SkipContacts"),
    "ContactsUI": ("skip", "SkipContacts"),
    "CoreAudio": ("any", ""),
    "CoreBluetooth": ("skip", "SkipBluetooth"),
    "CoreData": ("skip", "SkipSQL"),
    "CoreGraphics": ("any", "drop the import: Foundation outside Apple platforms defines CGFloat, CGPoint, CGSize and CGRect"),
    "CoreHaptics": ("any", ""),
    "CoreImage": ("any", ""),
    "CoreLocation": ("skip", "SkipDevice (location services)"),
    "CoreML": ("any", ""),
    "CoreMotion": ("skip", "SkipDevice (sensors)"),
    "CoreNFC": ("skip", "SkipNFC"),
    "CoreSpotlight": ("any", ""),
    "CoreTelephony": ("any", ""),
    "CoreText": ("any", ""),
    "CryptoKit": ("any", "swift-crypto (`import Crypto`), which Polymarket runs on Android"),
    "DeviceCheck": ("any", ""),
    "EventKit": ("skip", "SkipCalendar"),
    "EventKitUI": ("skip", "SkipCalendar"),
    "GameController": ("any", ""),
    "GameKit": ("any", ""),
    "HealthKit": ("any", ""),
    "ImageIO": ("any", ""),
    "Intents": ("any", ""),
    "IntentsUI": ("any", ""),
    "JavaScriptCore": ("skip", "SkipScript"),
    "LinkPresentation": ("any", ""),
    "LocalAuthentication": ("any", ""),
    "MapKit": ("any", "Polymarket kept MapKit on the iOS side; SkipGMaps draws Google Maps on both platforms"),
    "MessageUI": ("any", ""),
    "Metal": ("any", ""),
    "MetalKit": ("any", ""),
    "MobileCoreServices": ("any", ""),
    "MultipeerConnectivity": ("any", ""),
    "NaturalLanguage": ("any", ""),
    "Network": ("any", ""),
    "NetworkExtension": ("any", ""),
    "PDFKit": ("any", ""),
    "PassKit": ("any", "Polymarket put Apple Pay behind a payment protocol that a Kotlin Google Pay client implements"),
    "Photos": ("skip", "SkipKit (media picker)"),
    "PhotosUI": ("skip", "SkipKit (media picker)"),
    "PushKit": ("any", ""),
    "QuartzCore": ("any", ""),
    "QuickLook": ("any", ""),
    "RealityKit": ("any", ""),
    "SafariServices": ("any", ""),
    "SceneKit": ("any", ""),
    "Security": ("skip", "SkipKeychain for keychain storage"),
    "Speech": ("skip", "SkipSpeech"),
    "SpriteKit": ("any", ""),
    "StoreKit": ("skip", "SkipMarketplace (StoreKit on iOS, Play Billing on Android)"),
    "StoreKitTest": ("any", ""),
    "SwiftData": ("skip", "SkipSQL"),
    "TipKit": ("any", ""),
    "UniformTypeIdentifiers": ("any", ""),
    "UserNotifications": ("skip", "SkipNotify"),
    "Vision": ("any", ""),
    "VisionKit": ("any", ""),
    "WatchConnectivity": ("any", ""),
    "WebKit": ("skip", "SkipWeb"),
    "WidgetKit": ("any", ""),
    "os": ("skip", "`Logger` from `import SkipFuse`"),
    "simd": ("any", ""),
}
# Skip Lite maps these Apple imports onto a Skip framework when the target depends on it
# (skip.dev › SkipAV: "The transpiler includes `import skip.av.*` … for any Swift source
# that imports the `AVKit` or `AVFoundation` frameworks").
LITE_MAPPED = {"AVKit": "SkipAV", "AVFoundation": "SkipAV"}
UI_FRAMEWORKS = {"UIKit", "AppKit", "WatchKit"}
SWIFTUI_MODULES = {"SwiftUI", "SwiftUICore"}
NOT_ON_ANDROID = set(APPLE_ONLY) | UI_FRAMEWORKS | {"Darwin", "ObjectiveC", "Combine"}
ON_ANDROID = {
    "Android", "Bionic", "Dispatch", "Foundation", "FoundationEssentials", "FoundationInternationalization",
    "FoundationNetworking", "FoundationXML", "Observation", "Swift", "Synchronization", "_Concurrency",
    "_StringProcessing", "RegexBuilder",
}
APPLE_OS = {"iOS", "macOS", "OSX", "tvOS", "watchOS", "visionOS", "xrOS", "macCatalyst"}
OTHER_OS = {"Linux", "Windows", "WASI", "FreeBSD", "OpenBSD", "Cygwin", "Haiku", "PS4", "none", "Fuchsia"}

IMPORT = re.compile(
    r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:(?:public|package|internal|fileprivate|private)\s+)?import\s+"
    r"(?:(?:typealias|struct|class|enum|protocol|let|var|func)\s+)?([A-Za-z_]\w*)"
)
OBSERVABLE_OBJECT = re.compile(r"[:,]\s*(?:Combine\s*\.\s*)?ObservableObject\b|@Published\b")
PRINT = re.compile(r"(?<![\w.])(?:print|debugPrint|NSLog)\s*\(|\bSwift\s*\.\s*(?:print|debugPrint)\s*\(")
PRINT_DECLARATION = re.compile(r"\bfunc\s+(?:print|debugPrint|NSLog)\b")
OBJC = re.compile(
    r"@objc(?:Members)?\b|#selector\s*\(|#keyPath\s*\(|\bmethod_exchangeImplementations\s*\("
    r"|\bobjc_(?:set|get)AssociatedObject\s*\(|\.\s*observe\s*\(\s*\\[^,]*,\s*options\s*:"
    r"|\baddObserver\s*\([^)]*forKeyPath\s*:"
)
FILE_TYPE = re.compile(r"<\s*FILE\s*>|:\s*FILE\b")
NETWORKING = re.compile(
    r"\b(?:URLSession\w*|URLRequest|HTTPURLResponse|URLResponse|URLCache|CachedURLResponse|URLProtocol"
    r"|URLCredential\w*|URLAuthenticationChallenge|HTTPCookie\w*)\b"
)
# Modules that make FoundationNetworking visible: SkipFuse and SkipFuseUI re-export SkipAndroidBridge,
# which `@_exported import`s FoundationNetworking (skiptools/skip-android-bridge AndroidBridgeBootstrap.swift).
NETWORKING_PROVIDERS = {"FoundationNetworking", "SkipFuse", "SkipFuseUI", "SkipAndroidBridge"}
OBSERVABLE_MACRO = re.compile(r"@Observable\b")
# skipstone skips its missing-import warning when a file imports SkipFuse or any of the UI modules
# (KotlinBridgeToKotlinVisitor.swift: `includesUI` is SwiftUI, SkipSwiftUI or SkipFuseUI).
OBSERVATION_IMPORTS = {"SkipFuse", "SkipFuseUI", "SwiftUI", "SkipSwiftUI"}
NOT_SKIP = re.compile(r"!\s*SKIP\b")
COMBINE_API = re.compile(
    r"\b(?:AnyPublisher|PassthroughSubject|CurrentValueSubject)\b|\bPublished\s*<[^>]*>\s*\.\s*Publisher\b"
    r"|\b(?:some|any)\s+Publisher\b"
)
DECLARATION = re.compile(
    r"^\s*(?:@\w+(?:\([^()]*\))?\s+)*((?:\w+(?:\(set\))?\s+)*?)(func|var|let|init|subscript|typealias)\b"
)
DIRECTIVE = re.compile(r"^\s*#\s*(if|elseif|else|endif)\b(.*)$")

INVENTORY_PATTERNS = {
    "@Observable": r"@Observable\b",
    "ObservableObject": r"\bObservableObject\b",
    "@Published": r"@Published\b",
    "import Combine": r"(?m)^\s*(?:@\w+\s+)*import\s+Combine\b",
    "AsyncStream": r"\bAsync(?:Throwing)?Stream\b",
    "URLSession": r"\bURLSession\b",
    "#if os(Android)": r"#\s*(?:if|elseif)\b[^\n]*\bos\s*\(\s*Android\s*\)",
    "#if SKIP": r"#\s*(?:if|elseif)\s+SKIP\b",
    "#if !SKIP": r"#\s*(?:if|elseif)\s+!\s*SKIP\b",
    "@_cdecl": r"@_cdecl\b",
    "swift-java": r"\bimport\s+(?:SwiftJava|SwiftJavaJNICore|JavaUtil|JavaNet|JavaIO|JavaLangReflect|JavaKit)\b|@Java(?:Class|Method|Interface|Implementation|Field)\b",
    "AnyDynamicObject": r"\bAnyDynamicObject\b",
}


@dataclass
class Finding:
    id: str
    rule: str
    title: str
    severity: str
    skill: str
    target: str
    file: str
    line: int
    snippet: str
    guard: str | None
    detail: str | None
    source: str
    fix: str


@dataclass
class SkipConfig:
    file: str | None
    mode: str  # "native" or "transpiled", after resolving a missing or automatic mode
    explicit: bool
    bridging: bool
    kotlincompat: bool
    basis: str = "skip.yml"


@dataclass
class Unit:
    """A SwiftPM target, the Swift files of an Xcode project, or loose files."""

    name: str
    kind: str
    path: Path
    package: str | None = None
    dependencies: list[str] = field(default_factory=list)
    # Dependencies without a platform condition that leaves Android out.
    android_dependencies: list[str] = field(default_factory=list)
    plugins: list[str] = field(default_factory=list)
    # `swiftSettings: [.define(...)]`: True, False (a platform condition without Android), None (by configuration).
    defines: dict[str, bool | None] = field(default_factory=dict)
    skip: SkipConfig | None = None
    files: list[Path] = field(default_factory=list)
    shared: bool = False
    label: str = ""

    @property
    def skip_module(self) -> bool:
        return self.skip is not None or "skipstone" in self.plugins

    @property
    def skip_ui(self) -> str | None:
        for product in ("SkipFuseUI", "SkipUI"):
            if product in self.dependencies:
                return product
        return None


@dataclass(frozen=True)
class Context:
    unit: str
    route: str
    native: bool
    skip: bool = False
    fuse_ui: bool = False
    lite_ui: bool = False
    bridged: bool = False
    test: bool = False
    executable: bool = False
    dependencies: frozenset[str] = frozenset()
    defines: tuple[tuple[str, bool | None], ...] = ()


# --- Source text ---------------------------------------------------------------------------


def strip_comments(text: str) -> str:
    """Blank out comments while keeping string literals and line numbers intact."""
    out: list[str] = []
    i, n = 0, len(text)
    depth = 0
    in_string = False
    multiline = False
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if depth:
            if ch == "*" and nxt == "/":
                depth -= 1
                out.append("  ")
                i += 2
            elif ch == "/" and nxt == "*":
                depth += 1
                out.append("  ")
                i += 2
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if in_string:
            if ch == "\\" and i + 1 < n:
                out.append(text[i : i + 2])
                i += 2
                continue
            if multiline and text.startswith('"""', i):
                in_string = multiline = False
                out.append('"""')
                i += 3
                continue
            if not multiline and ch in '"\n':
                in_string = False
            out.append(ch)
            i += 1
            continue
        if ch == "/" and nxt == "/":
            end = text.find("\n", i)
            end = n if end == -1 else end
            out.append(" " * (end - i))
            i = end
            continue
        if ch == "/" and nxt == "*":
            depth = 1
            out.append("  ")
            i += 2
            continue
        if text.startswith('"""', i):
            in_string = multiline = True
            out.append('"""')
            i += 3
            continue
        if ch == '"':
            in_string = True
        out.append(ch)
        i += 1
    return "".join(out)


def blank_strings(code: str) -> str:
    """Replace string literal contents with spaces; offsets and line numbers stay the same."""
    out = list(code)
    i, n = 0, len(code)
    while i < n:
        if code.startswith('"""', i):
            end = code.find('"""', i + 3)
            end = n if end == -1 else end
            for k in range(i + 3, end):
                if out[k] != "\n":
                    out[k] = " "
            i = end + 3
            continue
        if code[i] == '"':
            k = i + 1
            depth = 0
            while k < n and code[k] != "\n":
                if code[k] == "\\" and k + 1 < n:
                    if code[k + 1] == "(":
                        depth += 1
                    out[k] = out[k + 1] = " "
                    k += 2
                    continue
                if depth and code[k] == ")":
                    depth -= 1
                elif not depth and code[k] == '"':
                    break
                out[k] = " "
                k += 1
            i = k + 1
            continue
        i += 1
    return "".join(out)


def matching(code: str, open_index: int) -> int:
    """Index of the bracket closing the one at `open_index`, or -1."""
    pairs = {"(": ")", "{": "}", "[": "]"}
    opener = code[open_index]
    closer = pairs[opener]
    depth = 0
    for index in range(open_index, len(code)):
        ch = code[index]
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return index
    return -1


def split_top_level(text: str, blanked: str) -> list[str]:
    """Split at commas outside brackets; `blanked` has the same offsets with strings blanked."""
    parts: list[str] = []
    depth = 0
    start = 0
    for index, ch in enumerate(blanked):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


# --- Conditional compilation -------------------------------------------------------------------
# A tri-state per line: True (Android compiles it), False (it does not), None (cannot tell).


def t_not(value: bool | None) -> bool | None:
    return None if value is None else not value


def t_and(a: bool | None, b: bool | None) -> bool | None:
    if a is False or b is False:
        return False
    if a is True and b is True:
        return True
    return None


def t_or(a: bool | None, b: bool | None) -> bool | None:
    if a is True or b is True:
        return True
    if a is False and b is False:
        return False
    return None


@dataclass(frozen=True)
class Env:
    """What an Android build of one module looks like to `#if`."""

    native: bool
    fuse_ui: bool = False
    lite_ui: bool = False
    dependencies: frozenset[str] = frozenset()
    defines: tuple[tuple[str, bool | None], ...] = ()

    def flag(self, name: str) -> bool | None:
        if name == "true":
            return True
        if name == "false":
            return False
        if name == "SKIP":
            # SKIP code is transpiled to Kotlin: never native Swift, always part of a Lite build.
            return not self.native
        for defined, value in self.defines:
            if defined == name:
                return value
        if name == "DEBUG" and not self.native:
            return False  # skip.dev › FAQs: in Skip Lite `#if DEBUG` always resolves to false on Android
        return None  # SKIP_BRIDGE, ROBOLECTRIC, DEBUG in native code and other custom flags

    def can_import(self, module: str) -> bool | None:
        if module in ON_ANDROID:
            return True
        if module in SWIFTUI_MODULES:
            # SkipFuseUI vends a `SwiftUI` module on Android; Skip Lite's SkipUI is transpiled.
            return True if self.fuse_ui else (None if self.lite_ui else False)
        if module in NOT_ON_ANDROID:
            return False
        if module in self.dependencies:
            return True  # a product or target the module depends on for Android builds
        return None

    def call(self, name: str, argument: str) -> bool | None:
        value = argument.strip()
        if name == "os":
            if value == "Android":
                return True
            return False if value in APPLE_OS or value in OTHER_OS else None
        if name == "canImport":
            return self.can_import(value.split(",")[0].strip().split(".")[0])
        if name == "targetEnvironment":
            return False if value == "macCatalyst" else None
        if name == "_runtime":
            return {"_ObjC": False, "_Native": True}.get(value)
        if name == "_endian":
            return {"little": True, "big": False}.get(value)
        if name in ("swift", "compiler"):
            match = re.fullmatch(r"(>=|<)\s*(\d+)(?:\.(\d+))?(?:\.\d+)*", value)
            if not match:
                return None
            version = (int(match.group(2)), int(match.group(3) or 0))
            if version > ANDROID_SWIFT_FLOOR:
                return None
            return match.group(1) == ">="
        return None  # arch, _pointerBitWidth, hasFeature, hasAttribute …


class _Condition:
    """Recursive-descent evaluator for `#if` conditions."""

    def __init__(self, text: str, env: Env) -> None:
        self.text = text
        self.i = 0
        self.env = env

    def evaluate(self) -> bool | None:
        try:
            value = self.disjunction()
            self.space()
            return value if self.i == len(self.text) else None
        except ValueError:
            return None

    def space(self) -> None:
        while self.i < len(self.text) and self.text[self.i].isspace():
            self.i += 1

    def take(self, token: str) -> bool:
        self.space()
        if self.text.startswith(token, self.i):
            self.i += len(token)
            return True
        return False

    def disjunction(self) -> bool | None:
        value = self.conjunction()
        while self.take("||"):
            value = t_or(value, self.conjunction())
        return value

    def conjunction(self) -> bool | None:
        value = self.unary()
        while self.take("&&"):
            value = t_and(value, self.unary())
        return value

    def unary(self) -> bool | None:
        if self.take("!"):
            return t_not(self.unary())
        return self.primary()

    def primary(self) -> bool | None:
        if self.take("("):
            value = self.disjunction()
            if not self.take(")"):
                raise ValueError("unbalanced")
            return value
        self.space()
        match = re.compile(r"[A-Za-z_]\w*").match(self.text, self.i)
        if not match:
            raise ValueError("expected a name")
        self.i = match.end()
        name = match.group(0)
        self.space()
        if self.i < len(self.text) and self.text[self.i] == "(":
            depth = 0
            for index in range(self.i, len(self.text)):
                if self.text[index] == "(":
                    depth += 1
                elif self.text[index] == ")":
                    depth -= 1
                    if depth == 0:
                        argument = self.text[self.i + 1 : index]
                        self.i = index + 1
                        return self.env.call(name, argument)
            raise ValueError("unbalanced call")
        return self.env.flag(name)


def evaluate(condition: str, env: Env) -> bool | None:
    return _Condition(condition, env).evaluate()


@dataclass
class Directive:
    line: int
    kind: str
    condition: str
    state: bool | None  # whether Android compiles the branch this directive opens


def line_states(code: str, env: Env) -> tuple[list[bool | None], list[str | None], list[Directive]]:
    """Per line: does an Android build of the module compile it, and under which undecided guard."""
    states: list[bool | None] = []
    guards: list[str | None] = []
    directives: list[Directive] = []
    stack: list[dict] = []

    def region() -> tuple[bool | None, str | None]:
        state: bool | None = True
        parts: list[str] = []
        for frame in stack:
            state = t_and(state, frame["branch"])
            if frame["branch"] is None and frame["guard"]:
                parts.append(frame["guard"])
        return state, (" && ".join(parts) if state is None and parts else None)

    for number, line in enumerate(code.split("\n"), start=1):
        match = DIRECTIVE.match(line)
        if match:
            kind, condition = match.group(1), match.group(2).strip()
            if kind == "if":
                value = evaluate(condition, env)
                outer, _ = region()
                stack.append({"conditions": [(condition, value)], "branch": value, "guard": condition if value is None else None})
                directives.append(Directive(number, kind, condition, t_and(outer, value)))
            elif kind in ("elseif", "else") and stack:
                frame = stack.pop()
                outer, _ = region()
                conditions = frame["conditions"]
                branch: bool | None = True
                parts = []
                for text, value in conditions:
                    branch = t_and(branch, t_not(value))
                    if value is None:
                        parts.append(f"!({text})")
                if kind == "elseif":
                    value = evaluate(condition, env)
                    branch = t_and(branch, value)
                    if value is None:
                        parts.append(condition)
                    conditions = conditions + [(condition, value)]
                stack.append({"conditions": conditions, "branch": branch, "guard": " && ".join(parts) or None})
                directives.append(Directive(number, kind, condition, t_and(outer, branch)))
            elif kind == "endif" and stack:
                stack.pop()
            # A directive line holds no code of its own.
            states.append(False)
            guards.append(None)
            continue
        state, guard = region()
        states.append(state)
        guards.append(guard)
    return states, guards, directives


# --- Project structure --------------------------------------------------------------------------


@dataclass
class Walk:
    swift: list[Path] = field(default_factory=list)
    manifests: list[Path] = field(default_factory=list)
    skip_configs: list[Path] = field(default_factory=list)
    resolved: list[Path] = field(default_factory=list)
    xcode_projects: list[Path] = field(default_factory=list)


def walk_project(root: Path, include_dependencies: bool) -> Walk:
    excluded = set(EXCLUDED_DIRS)
    if not include_dependencies:
        excluded |= DEPENDENCY_DIRS
    found = Walk()
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(directory.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                name = entry.name
                if name in excluded:
                    continue
                if name.startswith(".") and not (include_dependencies and name in DEPENDENCY_DIRS):
                    continue
                if entry.suffix == ".xcodeproj":
                    found.xcode_projects.append(entry)
                    resolved = entry / "project.xcworkspace" / "xcshareddata" / "swiftpm" / "Package.resolved"
                    if resolved.is_file():
                        found.resolved.append(resolved)
                    continue
                if entry.suffix == ".xcworkspace":
                    resolved = entry / "xcshareddata" / "swiftpm" / "Package.resolved"
                    if resolved.is_file():
                        found.resolved.append(resolved)
                    continue
                stack.append(entry)
            elif entry.is_file():
                if entry.name == "Package.swift":
                    found.manifests.append(entry)
                elif entry.name == "Package.resolved":
                    found.resolved.append(entry)
                elif entry.name == "skip.yml" and directory.name == "Skip":
                    found.skip_configs.append(entry)
                elif entry.suffix == ".swift" and not MANIFEST_VARIANT.match(entry.name):
                    found.swift.append(entry)
    for name in ("swift", "manifests", "skip_configs", "resolved", "xcode_projects"):
        getattr(found, name).sort()
    return found


def string_literal(text: str | None) -> str | None:
    if text is None:
        return None
    match = re.fullmatch(r'\s*"([^"\\]*)"\s*', text)
    return match.group(1) if match else None


def named_strings(text: str, blanked: str) -> list[str]:
    """Names in a dependency or plugin list: `"A"`, `.product(name: "B", package: "b")`, `.target(name: "C")`."""
    names: list[str] = []
    for match in re.finditer(r'"([^"\\]*)"', text):
        before = blanked[: match.start()].rstrip()
        if before.endswith("name:") or before.endswith("[") or before.endswith(",") or before.endswith("(") or not before:
            names.append(match.group(1))
    return names


class _Manifest:
    """Regex reading of one Package.swift: target declarations and the lists they use."""

    def __init__(self, raw: str) -> None:
        self.code = strip_comments(raw)
        self.blanked = blank_strings(self.code)

    def platforms_of(self, element: str) -> str | None:
        """The platform list in an element's `condition:`, following one variable."""
        match = re.search(r"condition\s*:\s*(?:\.when\s*\(\s*platforms\s*:\s*\[([^\]]*)\]|([A-Za-z_]\w*))", element)
        if not match:
            return None
        if match.group(1) is not None:
            return match.group(1)
        definition = re.search(
            r"\b(?:let|var)\s+" + re.escape(match.group(2))
            + r"\b[^=\n]*=\s*(?:TargetDependencyCondition\s*)?\.when\s*\(\s*platforms\s*:\s*\[([^\]]*)\]",
            self.code,
        )
        return definition.group(1) if definition else None

    def element(self, text: str, blanked: str) -> tuple[str, bool] | None:
        names = named_strings(text, blanked)
        if not names:
            return None
        platforms = self.platforms_of(text)
        return names[0], platforms is None or bool(re.search(r"\.android\b", platforms))

    def entries(self, text: str, blanked: str, seen: set[str] | None = None) -> list[tuple[str, bool]]:
        """(name, used on Android) for a list expression: literals, and variables built from literals."""
        seen = set() if seen is None else seen
        result: list[tuple[str, bool]] = []
        outside = list(blanked)
        i = 0
        while i < len(blanked):
            if blanked[i] == "[":
                close = matching(blanked, i)
                if close == -1:
                    break
                inner, inner_blanked = text[i + 1 : close], blanked[i + 1 : close]
                offset = 0
                for part in split_top_level(inner, inner_blanked):
                    index = inner.find(part, offset)
                    offset = index + len(part)
                    entry = self.element(part, inner_blanked[index : index + len(part)])
                    if entry:
                        result.append(entry)
                for k in range(i, close + 1):
                    outside[k] = " "
                i = close + 1
                continue
            i += 1
        rest = "".join(outside)
        if re.fullmatch(r"[\w\s+.]*", rest):  # `deps`, `common + extra`, `base + [ ... ]`
            for name in re.findall(r"\b[A-Za-z_]\w*\b", rest):
                result.extend(self.variable(name, seen))
        return result

    def expression_end(self, start: int) -> int:
        depth = 0
        for i in range(start, len(self.blanked)):
            ch = self.blanked[i]
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                if depth == 0:
                    return i
                depth -= 1
            elif ch == "\n" and depth == 0 and not self.blanked[i + 1 :].lstrip(" \t").startswith(("+", ".")):
                return i
        return len(self.blanked)

    def variable(self, name: str, seen: set[str]) -> list[tuple[str, bool]]:
        """Entries a list variable collects through `=`, `+=`, `append(contentsOf:)` and `append(_:)`."""
        if name in seen:
            return []
        seen.add(name)
        escaped = re.escape(name)
        result: list[tuple[str, bool]] = []
        for pattern in (
            r"\b(?:let|var)\s+" + escaped + r"\b[^=\n]*=\s*",
            r"\b" + escaped + r"\s*\+=\s*",
            r"\b" + escaped + r"\s*\.\s*append\s*\(\s*contentsOf\s*:\s*",
        ):
            for match in re.finditer(pattern, self.blanked):
                end = self.expression_end(match.end())
                result.extend(self.entries(self.code[match.end() : end], self.blanked[match.end() : end], seen))
        for match in re.finditer(r"\b" + escaped + r"\s*\.\s*append\s*\((?!\s*contentsOf)", self.blanked):
            close = matching(self.blanked, match.end() - 1)
            if close != -1:
                entry = self.element(self.code[match.end() : close], self.blanked[match.end() : close])
                if entry:
                    result.append(entry)
        return result

    def texts(self, text: str, blanked: str, seen: set[str] | None = None) -> list[str]:
        """The expression itself plus the expressions that build each list variable it names."""
        seen = set() if seen is None else seen
        found = [text]
        rest = re.sub(r"\[[^\[\]]*\]", " ", blanked)
        if not re.fullmatch(r"[\w\s+.]*", rest):
            return found
        for name in re.findall(r"\b[A-Za-z_]\w*\b", rest):
            if name in seen:
                continue
            seen.add(name)
            escaped = re.escape(name)
            for pattern in (
                r"\b(?:let|var)\s+" + escaped + r"\b[^=\n]*=\s*",
                r"\b" + escaped + r"\s*\+=\s*",
                r"\b" + escaped + r"\s*\.\s*append\s*\(\s*(?:contentsOf\s*:\s*)?",
            ):
                for match in re.finditer(pattern, self.blanked):
                    end = self.expression_end(match.end())
                    found.extend(self.texts(self.code[match.end() : end], self.blanked[match.end() : end], seen))
        return found

    def defines(self, text: str, blanked: str) -> dict[str, bool | None]:
        """Compilation conditions from `.define("NAME")`, with `.when(platforms:)` read for Android."""
        result: dict[str, bool | None] = {}
        for source in self.texts(text, blanked):
            for match in re.finditer(r'\.define\s*\(\s*"(\w+)"\s*(?:,\s*\.when\s*\(([^()]*)\))?\s*\)', source):
                condition = match.group(2)
                platforms = re.search(r"platforms\s*:\s*\[([^\]]*)\]", condition or "")
                if platforms and not re.search(r"\.android\b", platforms.group(1)):
                    result[match.group(1)] = False
                elif condition and "configuration" in condition:
                    result[match.group(1)] = None
                else:
                    result[match.group(1)] = True
        return result

    def declarations(self) -> list[tuple[str, dict[str, tuple[str, str]]]]:
        """(kind, labelled arguments) for each target declaration."""
        found: list[tuple[str, dict[str, tuple[str, str]]]] = []
        spans: list[tuple[int, int]] = []
        pattern = r"\.\s*(target|executableTarget|testTarget|macro|plugin|systemLibrary|binaryTarget)\s*\("
        for match in re.finditer(pattern, self.blanked):
            if any(start <= match.start() < end for start, end in spans):
                continue  # `.target(name:)` or `.plugin(name:package:)` inside another target
            open_index = match.end() - 1
            close = matching(self.blanked, open_index)
            if close == -1:
                continue
            inner, inner_blanked = self.code[open_index + 1 : close], self.blanked[open_index + 1 : close]
            arguments: dict[str, tuple[str, str]] = {}
            offset = 0
            for part in split_top_level(inner, inner_blanked):
                index = inner.find(part, offset)
                offset = index + len(part)
                label = re.match(r"^(\w+)\s*:(?!:)\s*", part)
                if label:
                    body = part[label.end() :]
                    start = index + label.end()
                    arguments[label.group(1)] = (body, inner_blanked[start : start + len(body)])
            kind = match.group(1)
            if kind == "plugin" and "capability" not in arguments:
                continue  # a plugin usage such as `.plugin(name: "skipstone", package: "skip")`
            if "condition" in arguments or (kind == "target" and "package" in arguments):
                continue  # a target dependency, not a declaration
            spans.append((open_index, close))
            found.append((kind, arguments))
        return found


def parse_manifest(path: Path, root: Path) -> tuple[dict, list[Unit]]:
    raw = read_text(path) or ""
    manifest = _Manifest(raw)
    code, blanked = manifest.code, manifest.blanked
    tools = re.search(r"^\s*//\s*swift-tools-version\s*:\s*([\d.]+)", raw, re.M)
    platforms: list[str] = []
    platform_list = re.search(r"\bplatforms\s*:\s*\[", blanked)
    if platform_list:
        close = matching(blanked, platform_list.end() - 1)
        segment = code[platform_list.end() : close if close != -1 else len(code)]
        for match in re.finditer(r'\.(\w+)\s*\(\s*(?:\.v(\d+)(?:_(\d+))?|"([\d.]+)")', segment):
            version = match.group(4) or (match.group(2) + (f".{match.group(3)}" if match.group(3) else ""))
            platforms.append(f"{match.group(1)} {version}")
    package_rel = relative(path, root)
    units: list[Unit] = []
    declarations = manifest.declarations()
    counts: dict[str, int] = {}
    for _, arguments in declarations:
        name = string_literal(arguments.get("name", (None, ""))[0])
        if name:
            counts[name] = counts.get(name, 0) + 1
    for kind, arguments in declarations:
        name = string_literal(arguments.get("name", (None, ""))[0])
        if not name:
            continue
        if counts[name] > 1 and set(arguments) == {"name"}:
            continue  # `.target(name: "X")` in a dependency list kept in a variable
        explicit = string_literal(arguments.get("path", (None, ""))[0])
        directory = path.parent / explicit if explicit else default_target_dir(path.parent, kind, name)
        dependencies = manifest.entries(*arguments["dependencies"]) if "dependencies" in arguments else []
        plugins = [entry for entry, _ in manifest.entries(*arguments["plugins"])] if "plugins" in arguments else []
        names = list(dict.fromkeys(dependency for dependency, _ in dependencies))
        android = list(dict.fromkeys(dependency for dependency, on_android in dependencies if on_android))
        defines = manifest.defines(*arguments["swiftSettings"]) if "swiftSettings" in arguments else {}
        units.append(
            Unit(
                name=name,
                kind=kind,
                path=directory,
                package=package_rel,
                dependencies=names,
                android_dependencies=android,
                plugins=plugins,
                defines=defines,
            )
        )
    info = {
        "manifest": package_rel,
        "swift_tools_version": tools.group(1) if tools else None,
        "platforms": platforms,
        "targets": [unit.name for unit in units],
    }
    return info, units


def default_target_dir(package_dir: Path, kind: str, name: str) -> Path:
    if kind == "testTarget":
        candidates = ["Tests", "Sources", "Source", "src", "srcs"]
    elif kind == "plugin":
        candidates = ["Plugins"]
    else:
        candidates = ["Sources", "Source", "src", "srcs"]
    for candidate in candidates:
        if (package_dir / candidate / name).is_dir():
            return package_dir / candidate / name
    return package_dir / candidates[0] / name


def parse_skip_config(path: Path, root: Path) -> SkipConfig:
    """`mode`, `bridging` (true, or a mapping with `auto`/`enabled`) and `kotlincompat` from skip.yml."""
    mode: str | None = None
    bridging = False
    kotlincompat = False
    stack: list[tuple[int, str]] = []
    for raw in (read_text(path) or "").splitlines():
        line = re.sub(r"(?:^|\s)#.*$", "", raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        content = line.strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        keys = [key for _, key in stack]
        pair = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", content)
        if not pair:
            if keys[-1:] == ["options"] and "kotlincompat" in content:
                kotlincompat = True
            continue
        key, value = pair.group(1), pair.group(2).strip()
        scalar = value.strip("'\"").lower()
        path_keys = keys + [key]
        if path_keys == ["skip", "mode"]:
            mode = scalar
        elif path_keys == ["skip", "bridging"] and value:
            if value.startswith("{"):
                bridging = bool(re.search(r"\b(?:auto|enabled)\s*:\s*['\"]?(?:true|yes|on)\b", value, re.I))
                kotlincompat = kotlincompat or "kotlincompat" in value
            else:
                bridging = scalar in ("true", "yes", "on")
        elif path_keys in (["skip", "bridging", "auto"], ["skip", "bridging", "enabled"]):
            bridging = scalar in ("true", "yes", "on")
        elif path_keys == ["skip", "bridging", "options"] and "kotlincompat" in value:
            kotlincompat = True
        stack.append((indent, key))
    explicit = mode in ("native", "transpiled")
    return SkipConfig(
        file=relative(path, root),
        mode=mode if explicit else "transpiled",
        explicit=explicit,
        bridging=bridging,
        kotlincompat=kotlincompat,
        basis="skip.yml" if explicit else f"mode {mode or 'not set'}",
    )


def parse_resolved(path: Path, root: Path) -> list[dict]:
    """Pins from Package.resolved, format 1 (`object.pins`) or 2 and 3 (`pins`)."""
    try:
        data = json.loads(read_text(path) or "")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    pins = data.get("pins")
    if pins is None and isinstance(data.get("object"), dict):
        pins = data["object"].get("pins")
    entries: list[dict] = []
    for pin in pins or []:
        if not isinstance(pin, dict):
            continue
        location = pin.get("location") or pin.get("repositoryURL") or ""
        identity = pin.get("identity") or re.sub(r"\.git$", "", location.rstrip("/").rsplit("/", 1)[-1]).lower()
        if not identity and pin.get("package"):
            identity = str(pin["package"]).lower()
        state = pin.get("state") if isinstance(pin.get("state"), dict) else {}
        entries.append(
            {
                "identity": identity,
                "location": location,
                "version": state.get("version"),
                "revision": state.get("revision"),
                "branch": state.get("branch"),
                "resolved_in": relative(path, root),
                "format": data.get("version"),
            }
        )
    return entries


# --- Rules over one file --------------------------------------------------------------------------


def severity_of(rule: Rule, ctx: Context) -> str:
    if not ctx.native and rule.transpiled:
        return rule.transpiled
    return rule.by_route.get(ctx.route, rule.severity)


def make_finding(rule: Rule, ctx: Context, rel: str, number: int, original: list[str], guard: str | None, detail: str | None = None) -> Finding:
    snippet = original[number - 1] if 0 < number <= len(original) else ""
    return Finding(
        id=f"{rule.id}:{rel}:{number}",
        rule=rule.id,
        title=rule.title,
        severity=severity_of(rule, ctx),
        skill=rule.skill,
        target=ctx.unit,
        file=rel,
        line=number,
        snippet=snippet.strip()[:200],
        guard=guard,
        detail=detail,
        source=rule.source,
        fix=rule.fix,
    )


def apple_only_detail(module: str, route: str) -> str:
    kind, hint = APPLE_ONLY[module]
    if not hint or (kind == "skip" and route == "bare-sdk"):
        return f"{module}: {PROTOCOL_HINT}"
    if kind == "skip":
        return f"{module}: on Skip routes, {hint}"
    return f"{module}: {hint}"


@dataclass
class Declaration:
    line: int
    text: str
    annotated: bool
    nobridge: bool


def bridge_annotations(original: list[str], index: int) -> tuple[bool, bool]:
    """`// SKIP @bridge` / `// SKIP @nobridge` on the declaration line or the comment lines above it."""
    annotated = nobridge = False
    lines = [original[index]] if index < len(original) else []
    k = index - 1
    while k >= 0 and len(lines) < 5:
        text = original[k].strip()
        if text and not (text.startswith("//") or text.startswith("@")):
            break
        lines.append(text)
        k -= 1
    for text in lines:
        annotated = annotated or bool(re.search(r"SKIP\s+@bridge\b", text))
        nobridge = nobridge or bool(re.search(r"SKIP\s+@nobridge\b", text))
    return annotated, nobridge


def public_declarations(lines: list[str], states: list[bool | None], original: list[str]) -> list[Declaration]:
    declarations: list[Declaration] = []
    for i, line in enumerate(lines):
        if states[i] is False:
            continue
        head = DECLARATION.match(line)
        if not head or not re.search(r"\b(?:public|open)\b", head.group(1)):
            continue
        text = ""
        depth = 0
        j = i
        while j < len(lines) and j < i + 30:
            segment = lines[j]
            cut = None
            for k, ch in enumerate(segment):
                if ch in "([":
                    depth += 1
                elif ch in ")]":
                    depth -= 1
                elif ch == "{" and depth <= 0:
                    cut = k
                    break
            if cut is not None:
                text += " " + segment[:cut]
                break
            text += " " + segment
            j += 1
            if depth <= 0:
                following = lines[j].strip() if j < len(lines) else ""
                if not re.match(r"(?:->|(?:throws|rethrows|async|where)\b)", following):
                    break
        annotated, nobridge = bridge_annotations(original, i)
        declarations.append(Declaration(i + 1, text, annotated, nobridge))
    return declarations


TYPE_POSITION = re.compile(r"(?:[:,(\[<=?!]|->|@\w+(?:\([^()]*\))?|\b(?:some|any|inout|sending|borrowing|consuming))$")


def closure_problem(text: str) -> str | None:
    """Why Skip's bridge cannot carry a closure type in this declaration, or None."""
    if re.search(r"\[[^\[\]]*->[^\[\]]*\]", text) or re.search(r"\b(?:Array|ContiguousArray|Set|Dictionary)\s*<[^<>]*->", text):
        return "closure stored in a collection"
    for match in re.finditer(r"\(", text):
        start = match.start()
        end = matching(text, start)
        if end == -1:
            continue
        if not re.match(r"\s*(?:async\s*)?(?:(?:re)?throws(?:\s*\([^()]*\))?\s*)?->", text[end + 1 :]):
            continue
        if not TYPE_POSITION.search(text[:start].rstrip()):
            continue  # a declaration's own parameter clause, not a function type
        inner = text[start + 1 : end]
        parameters = [part for part in split_top_level(inner, inner) if part]
        if "->" in inner:
            return "closure that takes a closure"
        if len(parameters) > 5:
            return f"closure with {len(parameters)} parameters"
    return None


def scan_swift(rel: str, text: str, ctx: Context) -> list[Finding]:
    code = strip_comments(text)
    blanked = blank_strings(code)
    env = Env(native=ctx.native, fuse_ui=ctx.fuse_ui, lite_ui=ctx.lite_ui, dependencies=ctx.dependencies, defines=ctx.defines)
    states, guards, directives = line_states(blanked, env)
    lines = blanked.split("\n")
    original = text.split("\n")
    findings: list[Finding] = []

    def add(rule_id: str, number: int, detail: str | None = None) -> None:
        findings.append(make_finding(RULES[rule_id], ctx, rel, number, original, guards[number - 1], detail))

    imports: dict[str, int] = {}
    for number, line in enumerate(lines, start=1):
        if states[number - 1] is not False:
            match = IMPORT.match(line)
            if match:
                imports.setdefault(match.group(1), number)
    android_libc = "Android" in imports or "Bionic" in imports

    for number, line in enumerate(lines, start=1):
        state = states[number - 1]
        if state is False:
            continue
        match = IMPORT.match(line)
        if match:
            module = match.group(1)
            if module in UI_FRAMEWORKS or (module in SWIFTUI_MODULES and not (ctx.fuse_ui or ctx.lite_ui)):
                add("AND001", number, module)
            elif module == "Combine":
                add("AND003", number)
            elif module in APPLE_ONLY:
                if not (not ctx.native and LITE_MAPPED.get(module) in ctx.dependencies):
                    add("AND002", number, apple_only_detail(module, ctx.route))
            elif module == "Darwin" and ctx.native:
                add("AND006", number, "import Darwin")
            elif module in ("Glibc", "Musl") and ctx.native and not (state is None and android_libc):
                add("AND006", number, f"import {module}")
            elif module == "ObjectiveC" and ctx.native:
                add("AND008", number, "import ObjectiveC")
            continue
        if OBSERVABLE_OBJECT.search(line):
            add("AND004", number)
        if not (ctx.test or ctx.executable) and PRINT.search(line) and not PRINT_DECLARATION.search(line):
            add("AND007", number)
        if ctx.native:
            objc = OBJC.search(line)
            if objc:
                add("AND008", number, objc.group(0).strip())
            if FILE_TYPE.search(line):
                add("AND006", number, "FILE")

    if ctx.native and not (NETWORKING_PROVIDERS & set(imports) or (ctx.fuse_ui and "SwiftUI" in imports)):
        for number, line in enumerate(lines, start=1):
            if states[number - 1] is False or IMPORT.match(line):
                continue
            match = NETWORKING.search(line)
            if match:
                add("AND005", number, match.group(0))
                break

    if ctx.skip and ctx.native:
        if not (OBSERVATION_IMPORTS & set(imports)):
            for number, line in enumerate(lines, start=1):
                if states[number - 1] is not False and OBSERVABLE_MACRO.search(line):
                    add("AND009", number)
                    break
        for directive in directives:
            if directive.kind in ("if", "elseif") and NOT_SKIP.search(directive.condition) and directive.state is not False:
                add("AND010", directive.line)

    if ctx.skip:
        whole_file = ctx.bridged or bool(re.search(r"SKIP\s+@bridgeMembers\b", text))
        for declaration in public_declarations(lines, states, original):
            if declaration.nobridge or not (whole_file or declaration.annotated):
                continue
            publisher = COMBINE_API.search(declaration.text)
            if publisher:
                add("AND011", declaration.line, publisher.group(0))
            problem = closure_problem(declaration.text)
            if problem:
                add("AND012", declaration.line, problem)

    unique: dict[str, Finding] = {}
    for finding in findings:
        unique.setdefault(finding.id, finding)
    return list(unique.values())


# --- Whole project --------------------------------------------------------------------------------


def contains(directory: Path, path: Path) -> bool:
    return directory == path or directory in path.parents


def skip_fuse_in_graph(unit: Unit, by_package: dict[tuple[str | None, str], Unit]) -> bool:
    """SkipFuse (or SkipFuseUI, which depends on it) among the target's dependencies, through local targets."""
    seen = {id(unit)}
    stack = [unit]
    while stack:
        current = stack.pop()
        if {"SkipFuse", "SkipFuseUI"} & set(current.dependencies):
            return True
        for name in current.dependencies:
            other = by_package.get((current.package, name))
            if other is not None and id(other) not in seen:
                seen.add(id(other))
                stack.append(other)
    return False


def build_units(root: Path, found: Walk) -> tuple[list[dict], list[Unit], list[Unit]]:
    packages: list[dict] = []
    targets: list[Unit] = []
    for manifest in found.manifests:
        info, units = parse_manifest(manifest, root)
        packages.append(info)
        targets.extend(units)
    by_dir = {unit.path.resolve(): unit for unit in targets}
    for config in found.skip_configs:
        module_dir = config.parent.parent.resolve()
        unit = by_dir.get(module_dir)
        if unit is None:
            # A skip.yml makes a Skip module even when the manifest declares it in a way regexes miss.
            unit = Unit(name=module_dir.name, kind="target", path=module_dir)
            targets.append(unit)
            by_dir[module_dir] = unit
        unit.skip = parse_skip_config(config, root)
    by_package = {(unit.package, unit.name): unit for unit in targets}
    for unit in targets:
        if not unit.skip_module:
            continue
        if unit.skip is None:
            unit.skip = SkipConfig(file=None, mode="transpiled", explicit=False, bridging=False, kotlincompat=False, basis="no skip.yml")
        if not unit.skip.explicit:
            # skipstone: a missing or `automatic` mode is native only when SkipFuse is in the
            # module's dependency graph (it is always the primary module of its own build).
            fuse = skip_fuse_in_graph(unit, by_package)
            unit.skip.mode = "native" if fuse else "transpiled"
            unit.skip.basis += ", SkipFuse in dependencies" if fuse else ", no SkipFuse dependency"
    names: dict[str, int] = {}
    for unit in targets:
        names[unit.name] = names.get(unit.name, 0) + 1
    for unit in targets:
        if names[unit.name] > 1 and unit.package:
            unit.label = f"{unit.name} ({Path(unit.package).parent.as_posix()})"
        else:
            unit.label = unit.name
    groups = [
        Unit(name=project.name, kind="xcode", path=project.parent, label=relative(project, root))
        for project in found.xcode_projects
    ]
    return packages, targets, groups


def assign_files(root: Path, files: list[Path], targets: list[Unit], groups: list[Unit]) -> dict[Path, Unit]:
    owners: dict[Path, Unit] = {}
    ordered_targets = sorted(((unit, unit.path.resolve()) for unit in targets), key=lambda item: len(item[1].parts), reverse=True)
    ordered_groups = sorted(((unit, unit.path.resolve()) for unit in groups), key=lambda item: len(item[1].parts), reverse=True)
    loose: Unit | None = None
    for path in files:
        resolved = path.resolve()
        owner = next((unit for unit, directory in ordered_targets if contains(directory, resolved)), None)
        if owner is None:
            owner = next((unit for unit, directory in ordered_groups if contains(directory, resolved)), None)
        if owner is None:
            if loose is None:
                loose = Unit(name="(no target)", kind="loose", path=root, label="(no target)")
                groups.append(loose)
            owner = loose
        owner.files.append(path)
        owners[path] = owner
    return owners


def resolve_shared(root: Path, values: list[str], targets: list[Unit], groups: list[Unit], files: list[Path]) -> tuple[set[Path], list[str]]:
    """Mark the targets named with --shared; return extra shared files and warnings."""
    extra: set[Path] = set()
    warnings: list[str] = []
    resolved_files = [(path, path.resolve()) for path in files] if values else []
    for value in values:
        named = [unit for unit in targets + groups if value in (unit.name, unit.label)]
        if named:
            for unit in named:
                unit.shared = True
            continue
        candidate = Path(value)
        candidate = (candidate if candidate.is_absolute() else root / candidate).resolve()
        if not candidate.exists():
            warnings.append(f"--shared {value}: no target or path by that name")
            continue
        if candidate.suffix == ".xcodeproj":
            for unit in groups:
                if unit.kind == "xcode" and (unit.path / unit.name).resolve() == candidate:
                    unit.shared = True
            continue
        marked = False
        for unit in targets:
            if contains(candidate, unit.path.resolve()):
                unit.shared = marked = True
        for path, resolved in resolved_files:
            if contains(candidate, resolved):
                extra.add(path)
                marked = True
        if not marked:
            warnings.append(f"--shared {value}: no Swift files there")
    return extra, warnings


def context_for(unit: Unit, route: str, as_skip: bool = True) -> Context:
    skip = as_skip and unit.skip_module
    native = (unit.skip is not None and unit.skip.mode == "native") if skip else route != "lite"
    return Context(
        unit=unit.label or unit.name,
        route=route,
        native=native,
        skip=skip,
        fuse_ui="SkipFuseUI" in unit.android_dependencies,
        lite_ui="SkipUI" in unit.android_dependencies,
        bridged=bool(skip and unit.skip and unit.skip.bridging),
        test=unit.kind == "testTarget",
        executable=unit.kind == "executableTarget",
        dependencies=frozenset(unit.android_dependencies),
        defines=tuple(sorted(unit.defines.items())),
    )


def count_lines(text: str) -> int:
    return len(text.splitlines())


def verdict(files: int, ui_files: int, blockers: dict[str, int]) -> str:
    if files and ui_files * 2 >= files:
        return "ios-only"
    return "fixable" if blockers else "clean"


def scan(root: Path, route: str = DEFAULT_ROUTE, shared: list[str] | None = None, include_dependencies: bool = False) -> dict:
    if route not in ROUTES:
        raise ValueError(f"unknown route: {route}")
    root = root.resolve()
    found = walk_project(root, include_dependencies)
    packages, targets, groups = build_units(root, found)
    owners = assign_files(root, found.swift, targets, groups)
    extra, warnings = resolve_shared(root, shared or [], targets, groups, found.swift)
    for unit in targets:
        if unit.skip_module:
            unit.shared = True

    texts: dict[Path, str] = {}
    inventory_counts = {name: 0 for name in INVENTORY_PATTERNS}
    line_counts: dict[Path, int] = {}
    for path in found.swift:
        text = read_text(path)
        if text is None:
            continue
        texts[path] = text
        line_counts[path] = count_lines(text)
        blanked = blank_strings(strip_comments(text))
        for name, pattern in INVENTORY_PATTERNS.items():
            inventory_counts[name] += len(re.findall(pattern, blanked))

    shared_files = [path for path in texts if owners[path].shared or path in extra]
    survey = not shared_files and not any(unit.skip_module for unit in targets)
    findings: list[Finding] = []
    candidates: list[dict] = []

    if survey:
        for unit in targets + groups:
            if unit.kind in ("testTarget", "plugin", "macro", "systemLibrary", "binaryTarget"):
                continue
            unit_files = [path for path in unit.files if path in texts]
            if not unit_files:
                continue
            ctx = context_for(unit, route, as_skip=False)
            blockers: dict[str, int] = {}
            ui_files = 0
            for path in unit_files:
                file_findings = scan_swift(relative(path, root), texts[path], ctx)
                if any(f.rule == "AND001" for f in file_findings):
                    ui_files += 1
                for finding in file_findings:
                    if finding.severity == "info":
                        findings.append(finding)
                    else:
                        blockers[finding.rule] = blockers.get(finding.rule, 0) + 1
            candidates.append(
                {
                    "target": unit.label or unit.name,
                    "kind": unit.kind,
                    "path": relative(unit.path, root),
                    "swift_files": len(unit_files),
                    "swift_lines": sum(line_counts[path] for path in unit_files),
                    "blockers": dict(sorted(blockers.items())),
                    "verdict": verdict(len(unit_files), ui_files, blockers),
                }
            )
        order = {"clean": 0, "fixable": 1, "ios-only": 2}
        candidates.sort(key=lambda item: (order[item["verdict"]], item["target"]))
    else:
        for path in shared_files:
            unit = owners[path]
            ctx = context_for(unit, route, as_skip=True)
            findings.extend(scan_swift(relative(path, root), texts[path], ctx))
        for unit in targets:
            if unit.skip and unit.skip.file and not unit.skip.explicit:
                rule = RULES["AND020"]
                ctx = context_for(unit, route)
                config_lines = (read_text(root / unit.skip.file) or "").split("\n")
                number = next((i for i, line in enumerate(config_lines, start=1) if re.match(r"^skip\s*:", line)), 1)
                detail = f"scanned as {unit.skip.mode} ({unit.skip.basis})"
                findings.append(make_finding(rule, ctx, unit.skip.file, number, config_lines, None, detail))

    findings.sort(key=lambda f: (SEVERITIES.index(f.severity), f.rule, f.file, f.line))
    by_severity = {severity: 0 for severity in SEVERITIES}
    by_rule: dict[str, int] = {}
    by_skill: dict[str, int] = {}
    by_target: dict[str, int] = {}
    for finding in findings:
        by_severity[finding.severity] += 1
        by_rule[finding.rule] = by_rule.get(finding.rule, 0) + 1
        by_skill[finding.skill] = by_skill.get(finding.skill, 0) + 1
        by_target[finding.target] = by_target.get(finding.target, 0) + 1

    dependencies: dict[tuple, dict] = {}
    for resolved in found.resolved:
        for entry in parse_resolved(resolved, root):
            key = (entry["identity"], entry["version"], entry["revision"], entry["branch"])
            if key in dependencies:
                dependencies[key]["resolved_in"].append(entry["resolved_in"])
            else:
                dependencies[key] = {**entry, "resolved_in": [entry["resolved_in"]]}

    target_entries = []
    for unit in targets + groups:
        unit_files = [path for path in unit.files if path in texts]
        is_shared = unit.shared or any(path in extra for path in unit_files)
        ctx = context_for(unit, route)
        target_entries.append(
            {
                "name": unit.label or unit.name,
                "kind": unit.kind,
                "package": unit.package,
                "path": relative(unit.path, root),
                "skip": (
                    {
                        "config": unit.skip.file if unit.skip else None,
                        "mode": unit.skip.mode if unit.skip else "transpiled",
                        "mode_explicit": bool(unit.skip and unit.skip.explicit),
                        "mode_basis": unit.skip.basis if unit.skip else None,
                        "bridging": bool(unit.skip and unit.skip.bridging),
                        "kotlincompat": bool(unit.skip and unit.skip.kotlincompat),
                    }
                    if unit.skip_module
                    else None
                ),
                "skip_ui": unit.skip_ui,
                "skip_dependencies": sorted(name for name in unit.dependencies if name.startswith("Skip")),
                "shared": is_shared,
                "android": ("native" if ctx.native else "transpiled") if is_shared else None,
                "swift_files": len(unit_files),
                "swift_lines": sum(line_counts[path] for path in unit_files),
            }
        )

    shared_names = sorted({owners[path].label or owners[path].name for path in shared_files})
    return {
        "tool": "android_scan",
        "version": VERSION,
        "root": str(root),
        "read_only": True,
        "route": route,
        "mode": "survey" if survey else "shared",
        "source_files_scanned": len(texts),
        "dependencies_included": include_dependencies,
        "shared": shared_names,
        "skip_modules": sorted(unit.label for unit in targets if unit.skip_module),
        "warnings": warnings,
        "summary": {"by_severity": by_severity, "by_rule": by_rule, "by_skill": by_skill, "by_target": by_target},
        "findings": [asdict(finding) for finding in findings],
        "sharing_candidates": candidates,
        "inventory": {
            "packages": packages,
            "targets": target_entries,
            "xcode_projects": [relative(path, root) for path in found.xcode_projects],
            "dependencies": sorted(dependencies.values(), key=lambda entry: (entry["identity"], str(entry["version"]))),
            "apis": {name: count for name, count in inventory_counts.items() if count},
        },
    }


# --- Output ---------------------------------------------------------------------------------------


def render_markdown(report: dict, limit: int) -> str:
    survey = report["mode"] == "survey"
    skip_modules = ", ".join(report["skip_modules"]) or "none"
    lines = [
        "# Swift on Android scan",
        "",
        f"- Root: `{report['root']}`",
        f"- Route: `{report['route']}` ({ROUTES[report['route']]})",
        (
            "- Mode: survey — nothing is shared with Android yet, so targets are rated as sharing candidates"
            if survey
            else f"- Mode: shared code — {', '.join(report['shared'])}"
        ),
        f"- Swift files scanned: {report['source_files_scanned']}",
        f"- Skip modules: {skip_modules}",
        "- Read-only: nothing was modified. Matches are heuristics; read the code before acting.",
    ]
    for warning in report["warnings"]:
        lines.append(f"- Warning: {warning}")
    lines += ["", "## Summary", "", "| Severity | Count |", "| --- | ---: |"]
    for severity, count in report["summary"]["by_severity"].items():
        lines.append(f"| {severity} | {count} |")
    if survey:
        lines += ["", "## Sharing candidates", "", "| Target | Kind | Swift lines | Blockers | Verdict |", "| --- | --- | ---: | --- | --- |"]
        for candidate in report["sharing_candidates"]:
            blockers = ", ".join(f"{rule}×{count}" for rule, count in candidate["blockers"].items()) or "none"
            lines.append(
                f"| {candidate['target']} | {candidate['kind']} | {candidate['swift_lines']} | {blockers} | {candidate['verdict']} |"
            )
        if not report["sharing_candidates"]:
            lines.append("| (no Swift targets found) | | | | |")
    lines += ["", "## Findings", ""]
    findings = report["findings"]
    if not findings:
        lines.append("No findings." if not survey else "No informational findings; blockers are counted per candidate above.")
    for finding in findings[:limit]:
        extras = []
        if finding["detail"]:
            extras.append(finding["detail"])
        if finding["guard"]:
            extras.append(f"guard `{finding['guard']}`")
        extra = f" — {'; '.join(extras)}" if extras else ""
        lines.append(
            f"- **{finding['rule']} {finding['title']}** ({finding['severity']}, {finding['skill']}) "
            f"`{finding['file']}:{finding['line']}` in {finding['target']}{extra}  \n  `{finding['snippet']}`"
        )
    if len(findings) > limit:
        lines.append(f"- … {len(findings) - limit} more (use --format json for all)")
    inventory = report["inventory"]
    if inventory["targets"]:
        lines += ["", "## Targets", "", "| Target | Kind | Android | Skip mode | Bridging | Swift lines |", "| --- | --- | --- | --- | --- | ---: |"]
        for target in inventory["targets"]:
            skip = target["skip"]
            mode = (skip["mode"] + ("" if skip["mode_explicit"] else " (default)")) if skip else "—"
            bridging = ("yes" + (", kotlincompat" if skip["kotlincompat"] else "")) if skip and skip["bridging"] else "—"
            lines.append(
                f"| {target['name']} | {target['kind']} | {target['android'] or 'iOS only'} | {mode} | {bridging} | {target['swift_lines']} |"
            )
    if inventory["dependencies"]:
        lines += ["", "## Resolved dependencies", "", "| Package | Version |", "| --- | --- |"]
        for entry in inventory["dependencies"]:
            version = entry["version"] or entry["branch"] or (entry["revision"] or "")[:12] or "?"
            lines.append(f"| {entry['identity']} | {version} |")
    if inventory["apis"]:
        lines += ["", "## Inventory", "", "| API | Occurrences |", "| --- | ---: |"]
        for name, count in inventory["apis"].items():
            lines.append(f"| `{name}` | {count} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=".", help="Project or package root to scan")
    parser.add_argument("--route", choices=list(ROUTES), default=DEFAULT_ROUTE, help="How Swift reaches Android (default: shared-core)")
    parser.add_argument(
        "--shared",
        nargs="+",
        action="extend",
        default=[],
        metavar="NAME|PATH",
        help="Targets or paths shared with Android besides Skip modules (put the root before this option)",
    )
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--include-dependencies", action="store_true", help="Also scan .build, SwiftPM checkouts, Pods and Carthage")
    parser.add_argument("--limit", type=int, default=200, help="Maximum findings listed in markdown output")
    parser.add_argument("--fail-on", choices=SEVERITIES, help="Exit with status 2 when a finding at or above this severity exists")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    report = scan(root, route=args.route, shared=args.shared, include_dependencies=args.include_dependencies)
    if args.format == "json":
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown(report, args.limit))

    if args.fail_on:
        threshold = SEVERITIES.index(args.fail_on)
        if any(SEVERITIES.index(f["severity"]) <= threshold for f in report["findings"]):
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

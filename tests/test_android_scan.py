from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("android_scan", ROOT / "scripts" / "android_scan.py")
assert SPEC and SPEC.loader
android_scan = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = android_scan
SPEC.loader.exec_module(android_scan)

SOURCE_PART = (
    r"(?:skip\.dev › .+|docs\.swift\.org › .+|swift\.org › .+|Swift Forums › .+ \(\d{4}-\d{2}-\d{2}\)"
    r"|GitHub › [\w.-]+/[\w.-]+.*|Measured: M\d+)"
)
SOURCE = re.compile(rf"^{SOURCE_PART}(?:; {SOURCE_PART})*$")
SKILLS = {"swift-android-architecture", "swift-android-sdk"}

FUSE = '.product(name: "SkipFuse", package: "skip-fuse")'
FUSE_UI = '.product(name: "SkipFuseUI", package: "skip-fuse-ui")'
SKIP_UI = '.product(name: "SkipUI", package: "skip-ui")'
SKIP_AV = '.product(name: "SkipAV", package: "skip-av")'
SKIPSTONE = '.plugin(name: "skipstone", package: "skip")'

NATIVE = "skip:\n  mode: 'native'\n"
BRIDGED = "skip:\n  mode: 'native'\n  bridging: true\n"
LITE = "skip:\n  mode: 'transpiled'\n"


def manifest(*targets: str) -> str:
    body = ",\n".join(f"        {target}" for target in targets)
    return (
        "// swift-tools-version: 6.1\n"
        "import PackageDescription\n\n"
        "let package = Package(\n"
        '    name: "App",\n'
        "    platforms: [.iOS(.v17), .macOS(.v14)],\n"
        "    targets: [\n"
        f"{body}\n"
        "    ]\n"
        ")\n"
    )


def skip_target(name: str, *dependencies: str) -> str:
    return f'.target(name: "{name}", dependencies: [{", ".join(dependencies)}], plugins: [{SKIPSTONE}])'


class ScanTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)

    def tearDown(self) -> None:
        self._directory.cleanup()

    def write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")
        return path

    def scan(self, route: str = "shared-core", shared: list[str] | None = None, **options) -> dict:
        return android_scan.scan(self.root, route=route, shared=shared, **options)

    def plain(self, swift: str, route: str = "shared-core", kind: str = "target") -> list[dict]:
        """A plain SwiftPM target named with --shared."""
        self.write("Package.swift", manifest(f'.{kind}(name: "Core")'))
        directory = "Tests" if kind == "testTarget" else "Sources"
        self.write(f"{directory}/Core/Core.swift", swift)
        return self.scan(route=route, shared=["Core"])["findings"]

    def skip_module(self, swift: str, config: str | None = NATIVE, dependencies: tuple[str, ...] = (FUSE,), route: str = "fuse-app") -> list[dict]:
        """A Skip module named Model with the given skip.yml."""
        self.write("Package.swift", manifest(skip_target("Model", *dependencies)))
        if config is not None:
            self.write("Sources/Model/Skip/skip.yml", config)
        self.write("Sources/Model/Model.swift", swift)
        return self.scan(route=route)["findings"]

    @staticmethod
    def rules(findings: list[dict]) -> list[str]:
        return sorted(finding["rule"] for finding in findings)

    def only(self, findings: list[dict], rule: str) -> dict:
        matching = [finding for finding in findings if finding["rule"] == rule]
        self.assertEqual(len(matching), 1, findings)
        return matching[0]


class ImportRuleTests(ScanTestCase):
    def test_uikit_in_shared_code(self) -> None:
        finding = self.only(self.plain("import UIKit\n"), "AND001")
        self.assertEqual(finding["severity"], "high")
        self.assertEqual(finding["detail"], "UIKit")
        self.assertIsNone(finding["guard"])

    def test_swiftui_in_shared_code(self) -> None:
        self.assertEqual(self.rules(self.plain("import SwiftUI\n")), ["AND001"])

    def test_swiftui_in_a_fuse_ui_module(self) -> None:
        self.assertEqual(self.skip_module("import SwiftUI\n", dependencies=(FUSE_UI,)), [])

    def test_swiftui_in_a_lite_ui_module(self) -> None:
        self.assertEqual(self.skip_module("import SwiftUI\n", config=LITE, dependencies=(SKIP_UI,), route="lite"), [])

    def test_uikit_in_a_fuse_ui_module(self) -> None:
        self.assertEqual(self.rules(self.skip_module("import UIKit\n", dependencies=(FUSE_UI,))), ["AND001"])

    def test_guarded_uikit(self) -> None:
        self.assertEqual(self.plain("#if canImport(UIKit)\nimport UIKit\n#endif\n"), [])

    def test_apple_only_framework(self) -> None:
        finding = self.only(self.plain("import MapKit\n"), "AND002")
        self.assertEqual(finding["severity"], "high")
        self.assertIn("MapKit", finding["detail"])

    def test_apple_only_hint_names_a_skip_module_on_skip_routes(self) -> None:
        self.assertIn("SkipMarketplace", self.only(self.plain("import StoreKit\n"), "AND002")["detail"])

    def test_apple_only_hint_on_the_bare_sdk(self) -> None:
        detail = self.only(self.plain("import StoreKit\n", route="bare-sdk"), "AND002")["detail"]
        self.assertNotIn("SkipMarketplace", detail)
        self.assertIn("protocol", detail)

    def test_guarded_apple_only_framework(self) -> None:
        self.assertEqual(self.plain("#if canImport(StoreKit)\nimport StoreKit\n#endif\n"), [])

    def test_lite_maps_avkit_onto_skipav(self) -> None:
        self.assertEqual(self.skip_module("import AVKit\n", config=LITE, dependencies=(SKIP_AV,), route="lite"), [])
        self.assertEqual(self.rules(self.skip_module("import AVKit\n", config=LITE, dependencies=(), route="lite")), ["AND002"])

    def test_dependency_answers_can_import(self) -> None:
        swift = "#if canImport(SkipAV)\nimport SkipAV\n#else\nimport AVKit\n#endif\n"
        self.assertEqual(self.skip_module(swift, dependencies=(FUSE_UI, SKIP_AV)), [])


class CombineRuleTests(ScanTestCase):
    def test_combine_is_high_where_swift_is_compiled_natively(self) -> None:
        for route in ("shared-core", "bare-sdk", "fuse-app"):
            with self.subTest(route=route):
                self.assertEqual(self.only(self.plain("import Combine\n", route=route), "AND003")["severity"], "high")

    def test_combine_in_a_fuse_module_is_high(self) -> None:
        self.assertEqual(self.only(self.skip_module("import Combine\n"), "AND003")["severity"], "high")

    def test_combine_in_a_lite_module_is_info(self) -> None:
        finding = self.only(self.skip_module("import Combine\n", config=LITE, dependencies=(), route="lite"), "AND003")
        self.assertEqual(finding["severity"], "info")

    def test_guarded_combine(self) -> None:
        self.assertEqual(self.plain("#if canImport(Combine)\nimport Combine\n#endif\n"), [])

    def test_observable_object(self) -> None:
        swift = """
        #if canImport(Combine)
        import Combine
        #endif
        final class Settings: ObservableObject {
            @Published var name = ""
        }
        """
        findings = self.plain(swift)
        self.assertEqual(self.rules(findings), ["AND004", "AND004"])
        self.assertEqual({finding["severity"] for finding in findings}, {"high"})

    def test_observable_object_in_a_lite_module_is_info(self) -> None:
        swift = "import Combine\nfinal class Settings: ObservableObject {}\n"
        findings = self.skip_module(swift, config=LITE, dependencies=(), route="lite")
        self.assertEqual({finding["severity"] for finding in findings}, {"info"})
        self.assertEqual(self.rules(findings), ["AND003", "AND004"])

    def test_observable_macro_is_not_observable_object(self) -> None:
        self.assertEqual(self.plain("import Observation\n@Observable final class Settings { var name = \"\" }\n"), [])


class FoundationRuleTests(ScanTestCase):
    FETCH = """
    import Foundation
    {imports}
    func fetch(_ url: URL) async throws -> Data {{
        let (data, _) = try await URLSession.shared.data(from: url)
        return data
    }}
    """

    def fetch(self, imports: str = "") -> str:
        return self.FETCH.format(imports=imports)

    def test_networking_without_foundation_networking(self) -> None:
        finding = self.only(self.plain(self.fetch()), "AND005")
        self.assertEqual((finding["severity"], finding["detail"]), ("high", "URLSession"))

    def test_networking_with_foundation_networking(self) -> None:
        imports = "#if canImport(FoundationNetworking)\nimport FoundationNetworking\n#endif"
        self.assertEqual(self.plain(self.fetch(imports)), [])

    def test_linux_only_guard_leaves_android_out(self) -> None:
        imports = "#if os(Linux)\nimport FoundationNetworking\n#endif"
        self.assertEqual(self.rules(self.plain(self.fetch(imports))), ["AND005"])

    def test_skip_fuse_reexports_foundation_networking(self) -> None:
        self.assertEqual(self.skip_module(self.fetch("import SkipFuse")), [])

    def test_transpiled_networking_is_not_checked(self) -> None:
        self.assertEqual(self.skip_module(self.fetch(), config=LITE, dependencies=(), route="lite"), [])

    def test_darwin_import(self) -> None:
        self.assertEqual(self.only(self.plain("import Darwin\n"), "AND006")["severity"], "medium")

    def test_file_pointer(self) -> None:
        swift = "#if canImport(Android)\nimport Android\n#endif\nlet stream: UnsafeMutablePointer<FILE>? = nil\n"
        self.assertEqual(self.only(self.plain(swift), "AND006")["detail"], "FILE")

    def test_ladder_with_an_android_branch(self) -> None:
        swift = """
        #if canImport(Darwin)
        import Darwin
        #elseif canImport(Android)
        import Android
        #elseif canImport(Glibc)
        import Glibc
        #endif
        #if os(Android)
        typealias Descriptor = OpaquePointer
        #else
        typealias Descriptor = UnsafeMutablePointer<FILE>
        #endif
        """
        self.assertEqual(self.plain(swift), [])

    def test_ladder_without_an_android_branch(self) -> None:
        swift = "#if canImport(Darwin)\nimport Darwin\n#elseif canImport(Glibc)\nimport Glibc\n#endif\n"
        finding = self.only(self.plain(swift), "AND006")
        self.assertEqual(finding["detail"], "import Glibc")
        self.assertIn("canImport(Glibc)", finding["guard"])


class LoggingRuleTests(ScanTestCase):
    def test_print_in_shared_code(self) -> None:
        self.assertEqual(self.only(self.plain('func run() { print("started") }\n'), "AND007")["severity"], "low")

    def test_print_on_the_bare_sdk_is_info(self) -> None:
        finding = self.only(self.plain('func run() { debugPrint("started") }\n', route="bare-sdk"), "AND007")
        self.assertEqual(finding["severity"], "info")

    def test_print_in_tests_and_strings(self) -> None:
        self.assertEqual(self.plain('func testRun() { print("x") }\n', kind="testTarget"), [])
        self.assertEqual(self.plain('let help = "call print(value) to debug"\n'), [])
        self.assertEqual(self.plain("func run(logger: Logger) { logger.print(1) }\nstruct Logger { func print(_ value: Int) {} }\n"), [])


class ObjectiveCRuleTests(ScanTestCase):
    def test_objective_c_runtime_features(self) -> None:
        cases = {
            "@objc func tapped() {}": "@objc",
            "final class A: NSObject { @objc dynamic var name = \"\" }": "@objc",
            "let action = #selector(Target.run)": "#selector(",
            "let path = #keyPath(Target.name)": "#keyPath(",
            "func tag(_ o: AnyObject) { objc_setAssociatedObject(o, &key, 1, .OBJC_ASSOCIATION_RETAIN) }": "objc_setAssociatedObject(",
            "let token = player.observe(\\.status, options: [.new]) { _, _ in }": "observe",
        }
        for line, detail in cases.items():
            with self.subTest(line=line):
                finding = self.only(self.plain(f"import Foundation\n{line}\n"), "AND008")
                self.assertEqual(finding["severity"], "high")
                self.assertIn(detail.split("(")[0], finding["detail"])

    def test_nsobject_subclass_alone(self) -> None:
        self.assertEqual(self.plain("import Foundation\nfinal class Box: NSObject {}\n"), [])

    def test_objective_c_behind_runtime_check(self) -> None:
        swift = "import Foundation\n#if _runtime(_ObjC)\n@objc final class Box: NSObject {}\n#endif\n"
        self.assertEqual(self.plain(swift), [])

    def test_transpiled_module_is_not_checked(self) -> None:
        self.assertEqual(self.skip_module("@objc final class Box {}\n", config=LITE, dependencies=(), route="lite"), [])


class SkipRuleTests(ScanTestCase):
    MODEL = "import Foundation\n{imports}\n@Observable public final class Model {{\n    public var count = 0\n}}\n"

    def test_observable_without_skip_fuse(self) -> None:
        finding = self.only(self.skip_module(self.MODEL.format(imports="import Observation")), "AND009")
        self.assertEqual(finding["severity"], "medium")
        self.assertEqual(finding["skill"], "swift-android-architecture")

    def test_observable_with_skip_fuse(self) -> None:
        self.assertEqual(self.skip_module(self.MODEL.format(imports="import SkipFuse")), [])

    def test_observable_in_a_file_that_imports_swiftui(self) -> None:
        self.assertEqual(self.skip_module(self.MODEL.format(imports="import SwiftUI"), dependencies=(FUSE_UI,)), [])

    def test_observable_outside_fuse_modules(self) -> None:
        self.assertEqual(self.plain(self.MODEL.format(imports="import Observation")), [])
        self.assertEqual(self.skip_module(self.MODEL.format(imports=""), config=LITE, dependencies=(), route="lite"), [])

    def test_not_skip_in_a_native_module(self) -> None:
        finding = self.only(self.skip_module("#if !SKIP\nimport Foundation\n#endif\n"), "AND010")
        self.assertEqual((finding["severity"], finding["line"]), ("low", 1))

    def test_not_os_android_in_a_native_module(self) -> None:
        self.assertEqual(self.skip_module("#if !os(Android)\nimport Foundation\n#endif\n"), [])

    def test_not_skip_in_a_lite_module(self) -> None:
        self.assertEqual(self.skip_module("#if !SKIP\nimport UIKit\n#endif\n", config=LITE, dependencies=(), route="lite"), [])

    def test_publisher_in_bridged_api(self) -> None:
        swift = """
        #if canImport(Combine)
        import Combine
        #endif
        public final class PriceFeed {
            public let prices: AnyPublisher<Double, Never>
            init(prices: AnyPublisher<Double, Never>) { self.prices = prices }
        }
        """
        finding = self.only(self.skip_module(swift, config=BRIDGED), "AND011")
        self.assertEqual((finding["severity"], finding["detail"]), ("medium", "AnyPublisher"))

    def test_publisher_not_bridged(self) -> None:
        swift = "public final class PriceFeed {\n    public let prices: AnyPublisher<Double, Never>\n}\n"
        self.assertEqual(self.rules(self.skip_module(swift, config=NATIVE)), [])
        nobridge = "public final class PriceFeed {\n    // SKIP @nobridge\n    public let prices: AnyPublisher<Double, Never>\n}\n"
        self.assertEqual(self.rules(self.skip_module(nobridge, config=BRIDGED)), [])
        internal = "public final class PriceFeed {\n    let prices: AnyPublisher<Double, Never>\n}\n"
        self.assertEqual(self.rules(self.skip_module(internal, config=BRIDGED)), [])

    def test_bridge_annotation_without_auto_bridging(self) -> None:
        swift = "public final class PriceFeed {\n    // SKIP @bridge\n    public let prices: PassthroughSubject<Double, Never>\n}\n"
        self.assertEqual(self.rules(self.skip_module(swift, config=NATIVE)), ["AND011"])

    def test_closures_skip_cannot_bridge(self) -> None:
        cases = {
            "public func run(_ body: @escaping (Int, Int, Int, Int, Int, Int) -> Void) {}": "6 parameters",
            "public var handlers: [() -> Void] = []": "collection",
            "public var routes: [String: (Int) -> Void] = [:]": "collection",
            "public func run(_ body: @escaping (@escaping (Int) -> Void) -> Void) {}": "takes a closure",
            "public func make() -> (Int, Int, Int, Int, Int, Int) -> Int { { $0 + $1 + $2 + $3 + $4 + $5 } }": "6 parameters",
        }
        for declaration, detail in cases.items():
            with self.subTest(declaration=declaration):
                finding = self.only(self.skip_module(f"public final class Runner {{\n    {declaration}\n}}\n", config=BRIDGED), "AND012")
                self.assertIn(detail, finding["detail"])

    def test_closures_skip_can_bridge(self) -> None:
        swift = """
        public final class Runner {
            public func run(_ body: @escaping (Int, Int) -> Void) {}
            public func perform(_ action: (URL) -> Void) {}
            public func sum(a: Int, b: Int, c: Int, d: Int, e: Int, f: Int) -> Int { a + b + c + d + e + f }
            public func multiline(
                first: Int,
                second: @escaping (Int) async throws -> String
            ) -> Int { first }
            public var values: [Int] = []
        }
        """
        self.assertEqual(self.skip_module(swift, config=BRIDGED), [])

    def test_skip_yml_without_mode(self) -> None:
        finding = self.only(self.skip_module("import Foundation\n", config="skip:\n  bridging: true\n"), "AND020")
        self.assertEqual(finding["severity"], "info")
        self.assertEqual(finding["file"], "Sources/Model/Skip/skip.yml")
        self.assertIn("native", finding["detail"])

    def test_skip_yml_with_mode(self) -> None:
        self.assertEqual(self.skip_module("import Foundation\n", config=NATIVE), [])


class GuardTests(ScanTestCase):
    def test_platform_guards(self) -> None:
        excluded = [
            "#if os(iOS)\nimport UIKit\n#endif\n",
            "#if canImport(UIKit)\nimport UIKit\n#elseif canImport(AppKit)\nimport AppKit\n#endif\n",
            "#if os(Android)\nimport Foundation\n#else\nimport UIKit\n#endif\n",
            "#if os(iOS) || os(macOS)\nimport UIKit\n#endif\n",
            "#if os(iOS) && DEBUG\nimport UIKit\n#endif\n",
            "#if DEBUG\n#if os(iOS)\nimport UIKit\n#endif\n#endif\n",
            "#if os(iOS)\nimport UIKit\n#elseif os(Android)\nimport Foundation\n#else\nimport AppKit\n#endif\n",
            "#if !os(Android)\nimport UIKit\n#endif\n",
            "#if targetEnvironment(macCatalyst)\nimport UIKit\n#endif\n",
            "#if os(Linux)\nimport UIKit\n#endif\n",
        ]
        for swift in excluded:
            with self.subTest(swift=swift):
                self.assertEqual(self.plain(swift), [])

    def test_else_branch_compiles_on_android(self) -> None:
        swift = "#if canImport(UIKit)\nimport Foundation\n#else\nimport UIKit\n#endif\n"
        finding = self.only(self.plain(swift), "AND001")
        self.assertEqual(finding["line"], 4)
        self.assertIsNone(finding["guard"])

    def test_undecided_guards_are_attached(self) -> None:
        cases = {
            "#if DEBUG\nimport UIKit\n#endif\n": "DEBUG",
            "#if os(Android) && DEBUG\nimport UIKit\n#endif\n": "os(Android) && DEBUG",
            "#if os(iOS) || DEBUG\nimport UIKit\n#endif\n": "os(iOS) || DEBUG",
            "#if DEBUG\n#if canImport(Foundation)\nimport UIKit\n#endif\n#endif\n": "DEBUG",
            "#if FEATURE\nimport Foundation\n#else\nimport UIKit\n#endif\n": "!(FEATURE)",
            "#if !SKIP_BRIDGE\nimport UIKit\n#endif\n": "!SKIP_BRIDGE",
        }
        for swift, guard in cases.items():
            with self.subTest(swift=swift):
                self.assertEqual(self.only(self.plain(swift), "AND001")["guard"], guard)

    def test_not_skip_compiles_natively_in_fuse(self) -> None:
        findings = self.skip_module("#if !SKIP\nimport UIKit\n#endif\n")
        self.assertEqual(self.rules(findings), ["AND001", "AND010"])
        self.assertEqual(self.skip_module("#if !os(Android)\nimport UIKit\n#endif\n"), [])

    def test_skip_blocks_are_not_native(self) -> None:
        swift = "#if SKIP\nimport android.content.Context\nfunc log() { print(1) }\n#endif\n"
        self.assertEqual(self.skip_module(swift), [])

    def test_conditions(self) -> None:
        native = android_scan.Env(native=True)
        transpiled = android_scan.Env(native=False)
        cases = [
            ("os(Android)", native, True),
            ("os(Linux)", native, False),
            ("os(iOS) || os(visionOS)", native, False),
            ("canImport(Android)", native, True),
            ("canImport(FoundationNetworking)", native, True),
            ("canImport(Glibc)", native, None),
            ("canImport(Musl)", native, None),
            ("canImport(UIKit.UIGestureRecognizerSubclass)", native, False),
            ("canImport(SwiftUI)", native, False),
            ("canImport(SwiftUI)", android_scan.Env(native=True, fuse_ui=True), True),
            ("canImport(Combine)", native, False),
            ("canImport(SomethingElse)", native, None),
            ("targetEnvironment(simulator)", native, None),
            ("targetEnvironment(macCatalyst)", native, False),
            ("_runtime(_ObjC)", native, False),
            ("_runtime(_Native)", native, True),
            ("swift(>=5.9)", native, True),
            ("compiler(<6.0)", native, False),
            ("swift(>=99.0)", native, None),
            ("SKIP", native, False),
            ("!SKIP", native, True),
            ("SKIP", transpiled, True),
            ("!SKIP", transpiled, False),
            ("SKIP_BRIDGE", native, None),
            ("DEBUG", native, None),
            ("DEBUG", transpiled, False),
            ("!(os(iOS) || os(macOS)) && canImport(Foundation)", native, True),
            ("arch(arm64)", native, None),
            ("os(Android", native, None),
        ]
        for condition, env, expected in cases:
            with self.subTest(condition=condition, native=env.native):
                self.assertIs(android_scan.evaluate(condition, env), expected)

    def test_package_defines(self) -> None:
        settings = (
            '[.define("ANDROID_BUILD", .when(platforms: [.android])), .define("APPLE_BUILD", .when(platforms: [.iOS, .macOS])), '
            '.define("FEATURE"), .define("TRACE", .when(configuration: .debug))]'
        )
        self.write("Package.swift", manifest(f'.target(name: "Core", swiftSettings: {settings})'))
        self.write(
            "Sources/Core/Core.swift",
            "#if APPLE_BUILD\nimport UIKit\n#endif\n#if ANDROID_BUILD && FEATURE\nimport AppKit\n#endif\n#if TRACE\nimport WatchKit\n#endif\n",
        )
        findings = self.scan(shared=["Core"])["findings"]
        self.assertEqual([(finding["detail"], finding["guard"]) for finding in findings], [("AppKit", None), ("WatchKit", "TRACE")])

    def test_package_defines_through_a_variable(self) -> None:
        self.write(
            "Package.swift",
            """\
            // swift-tools-version: 6.1
            import PackageDescription

            var settings: [SwiftSetting] = []
            settings.append(.define("APPLE_BUILD", .when(platforms: [.iOS])))

            let package = Package(name: "Core", targets: [.target(name: "Core", swiftSettings: settings)])
            """,
        )
        self.write("Sources/Core/Core.swift", "#if APPLE_BUILD\nimport UIKit\n#endif\n")
        self.assertEqual(self.scan(shared=["Core"])["findings"], [])

    def test_comments_are_ignored(self) -> None:
        self.assertEqual(self.plain("// import UIKit\n/* import UIKit\n   print(1) */\n"), [])


class SkipConfigTests(ScanTestCase):
    def config(self, text: str) -> android_scan.SkipConfig:
        return android_scan.parse_skip_config(self.write("skip.yml", text), self.root)

    def targets(self) -> dict[str, dict]:
        return {target["name"]: target for target in self.scan()["inventory"]["targets"]}

    def test_modes(self) -> None:
        self.assertEqual((self.config(NATIVE).mode, self.config(NATIVE).explicit), ("native", True))
        self.assertEqual((self.config(LITE).mode, self.config(LITE).explicit), ("transpiled", True))
        self.assertFalse(self.config("skip:\n  mode: 'automatic'\n").explicit)
        self.assertFalse(self.config("# comments only\n#skip:\n#  mode: 'native'\n").explicit)

    def test_bridging_forms(self) -> None:
        self.assertTrue(self.config("skip:\n  bridging: true\n").bridging)
        self.assertFalse(self.config("skip:\n  bridging: false\n").bridging)
        long_form = self.config("skip:\n  mode: 'native'\n  bridging:\n    auto: true\n    options: 'kotlincompat'\n")
        self.assertEqual((long_form.bridging, long_form.kotlincompat), (True, True))
        legacy = self.config("# comment\nskip:\n  mode: 'native' # inline\n  bridging:\n    enabled: true\n    options:\n      - 'kotlincompat'\n")
        self.assertEqual((legacy.mode, legacy.bridging, legacy.kotlincompat), ("native", True, True))
        flow = self.config("skip:\n  bridging: { auto: true, options: 'kotlincompat' }\n")
        self.assertEqual((flow.bridging, flow.kotlincompat), (True, True))

    def test_missing_mode_follows_the_skip_fuse_dependency(self) -> None:
        self.write(
            "Package.swift",
            manifest(
                skip_target("Model", FUSE),
                skip_target("Logic"),
                skip_target("Screens", '"Model"'),
                f'.testTarget(name: "ModelTests", dependencies: ["Model"], plugins: [{SKIPSTONE}])',
            ),
        )
        for target in ("Model", "Logic", "Screens"):
            self.write(f"Sources/{target}/Skip/skip.yml", "# no mode\n")
            self.write(f"Sources/{target}/{target}.swift", "import Foundation\n")
        self.write("Tests/ModelTests/Skip/skip.yml", LITE)
        targets = self.targets()
        self.assertEqual(targets["Model"]["skip"]["mode"], "native")
        self.assertEqual(targets["Logic"]["skip"]["mode"], "transpiled")
        self.assertEqual(targets["Screens"]["skip"]["mode"], "native")
        self.assertFalse(targets["Model"]["skip"]["mode_explicit"])
        self.assertEqual(targets["ModelTests"]["skip"]["mode"], "transpiled")
        self.assertTrue(targets["ModelTests"]["skip"]["mode_explicit"])
        self.assertEqual(targets["Model"]["android"], "native")
        self.assertEqual(targets["Logic"]["android"], "transpiled")

    def test_skip_yml_makes_a_skip_module(self) -> None:
        self.write("Package.swift", manifest('.target(name: "Model")'))
        self.write("Sources/Model/Skip/skip.yml", BRIDGED)
        self.write("Sources/Model/Model.swift", "import Foundation\n")
        report = self.scan()
        self.assertEqual(report["skip_modules"], ["Model"])
        self.assertEqual(report["shared"], ["Model"])
        model = report["inventory"]["targets"][0]["skip"]
        self.assertEqual((model["mode"], model["bridging"], model["kotlincompat"]), ("native", True, False))


class PackageTests(ScanTestCase):
    def test_target_paths_and_manifest_details(self) -> None:
        self.write(
            "Package.swift",
            manifest(
                '.target(name: "Core", dependencies: [.target(name: "Base")], path: "Shared/Core")',
                '.target(name: "Base")',
                '.testTarget(name: "CoreTests", dependencies: ["Core"])',
            ),
        )
        self.write("Shared/Core/Core.swift", "import UIKit\n")
        self.write("Sources/Base/Base.swift", "import Foundation\n")
        self.write("Tests/CoreTests/CoreTests.swift", "import UIKit\n")
        report = self.scan(shared=["Core"])
        self.assertEqual(report["inventory"]["packages"][0]["swift_tools_version"], "6.1")
        self.assertEqual(report["inventory"]["packages"][0]["platforms"], ["iOS 17", "macOS 14"])
        targets = {target["name"]: target for target in report["inventory"]["targets"]}
        self.assertEqual(set(targets), {"Core", "Base", "CoreTests"})
        self.assertEqual(targets["Core"]["path"], "Shared/Core")
        self.assertEqual(targets["CoreTests"]["path"], "Tests/CoreTests")
        self.assertEqual([(f["file"], f["target"]) for f in report["findings"]], [("Shared/Core/Core.swift", "Core")])

    def test_shared_by_path(self) -> None:
        self.write("Package.swift", manifest('.target(name: "Core")'))
        self.write("Sources/Core/Core.swift", "import UIKit\n")
        self.assertEqual(self.rules(self.scan(shared=["Sources/Core"])["findings"]), ["AND001"])

    def test_dependencies_through_variables(self) -> None:
        self.write(
            "Package.swift",
            """\
            // swift-tools-version: 6.1
            import PackageDescription

            let apple = TargetDependencyCondition.when(platforms: [.iOS, .macOS])
            var dependencies: [Target.Dependency] = [
                .product(name: "Nuke", package: "Nuke", condition: apple),
                "Base",
            ]
            var plugins: [Target.PluginUsage] = []
            if ProcessInfo.processInfo.environment["SKIP_ENABLED"] != nil {
                dependencies.append(contentsOf: [
                    .product(name: "SkipFuseUI", package: "skip-fuse-ui"),
                ])
                plugins.append(.plugin(name: "skipstone", package: "skip"))
            }

            let package = Package(
                name: "Kit",
                targets: [
                    .target(name: "Base"),
                    .target(name: "Kit", dependencies: dependencies, plugins: plugins),
                ]
            )
            """,
        )
        self.write("Sources/Kit/Kit.swift", "import SwiftUI\n#if canImport(Nuke)\nimport UIKit\n#endif\n")
        report = self.scan(shared=["Kit"])
        targets = {target["name"]: target for target in report["inventory"]["targets"]}
        self.assertEqual(set(targets), {"Base", "Kit"})
        self.assertEqual(targets["Kit"]["skip_ui"], "SkipFuseUI")
        self.assertIsNotNone(targets["Kit"]["skip"])
        self.assertEqual(report["findings"][0]["guard"], "canImport(Nuke)")
        self.assertEqual(self.rules(report["findings"]), ["AND001"])

    def test_xcode_projects_are_ios_side(self) -> None:
        self.write("App.xcodeproj/project.pbxproj", "// !$*UTF8*$!\n")
        self.write("App/ContentView.swift", "import SwiftUI\nimport UIKit\n")
        self.write("Package.swift", manifest('.target(name: "Core")'))
        self.write("Sources/Core/Core.swift", "import Foundation\n")
        report = self.scan(shared=["Core"])
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["inventory"]["xcode_projects"], ["App.xcodeproj"])
        named = self.scan(shared=["App.xcodeproj"])
        self.assertEqual(self.rules(named["findings"]), ["AND001", "AND001"])
        self.assertEqual({finding["target"] for finding in named["findings"]}, {"App.xcodeproj"})

    def test_unknown_shared_name(self) -> None:
        self.write("Package.swift", manifest('.target(name: "Core")'))
        self.write("Sources/Core/Core.swift", "import Foundation\n")
        report = self.scan(shared=["Missing"])
        self.assertEqual(report["mode"], "survey")
        self.assertIn("Missing", report["warnings"][0])

    def test_dependency_directories_are_skipped(self) -> None:
        self.write("Package.swift", manifest('.target(name: "Core")'))
        self.write("Sources/Core/Core.swift", "import Foundation\n")
        for directory in (".build/checkouts/Vendor", "Pods/Vendor", "Carthage/Checkouts/Vendor", "DerivedData/App/SourcePackages/checkouts/Vendor"):
            self.write(f"{directory}/Package.swift", manifest(skip_target("Vendor", FUSE)))
            self.write(f"{directory}/Sources/Vendor/Skip/skip.yml", NATIVE)
            self.write(f"{directory}/Sources/Vendor/Vendor.swift", "import UIKit\n")
        self.assertEqual(self.scan(shared=["Core"])["findings"], [])
        included = self.scan(shared=["Core"], include_dependencies=True)
        self.assertEqual(self.rules(included["findings"]), ["AND001"] * 4)

    def test_package_resolved_formats(self) -> None:
        self.write("Package.swift", manifest('.target(name: "Core")'))
        self.write("Sources/Core/Core.swift", "import Foundation\n")
        self.write(
            "Package.resolved",
            json.dumps({"pins": [{"identity": "skip-fuse", "kind": "remoteSourceControl", "location": "https://github.com/skiptools/skip-fuse.git", "state": {"revision": "a" * 40, "version": "1.0.3"}}], "version": 2}),
        )
        self.write(
            "App.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved",
            json.dumps({"object": {"pins": [{"package": "OpenCombine", "repositoryURL": "https://github.com/OpenCombine/OpenCombine.git", "state": {"branch": None, "revision": "b" * 40, "version": "0.14.0"}}]}, "version": 1}),
        )
        self.write(
            "Other/Package.resolved",
            json.dumps({"originHash": "c" * 64, "pins": [{"identity": "swift-crypto", "kind": "remoteSourceControl", "location": "https://github.com/apple/swift-crypto.git", "state": {"revision": "d" * 40, "branch": "main"}}], "version": 3}),
        )
        report = self.scan(shared=["Core"])
        dependencies = {entry["identity"]: entry for entry in report["inventory"]["dependencies"]}
        self.assertEqual(set(dependencies), {"skip-fuse", "opencombine", "swift-crypto"})
        self.assertEqual(dependencies["skip-fuse"]["version"], "1.0.3")
        self.assertEqual(dependencies["opencombine"]["format"], 1)
        self.assertEqual(dependencies["swift-crypto"]["branch"], "main")
        self.assertEqual(dependencies["opencombine"]["resolved_in"], ["App.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved"])
        self.assertEqual(report["findings"], [])


class SurveyTests(ScanTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write(
            "Package.swift",
            manifest('.target(name: "Domain")', '.target(name: "Networking")', '.target(name: "Screens")', '.testTarget(name: "DomainTests")'),
        )
        self.write("Sources/Domain/Domain.swift", "import Foundation\nstruct Item: Codable { let id: Int }\n")
        self.write("Sources/Networking/Client.swift", "import Foundation\nfunc load() async throws { _ = try await URLSession.shared.data(from: URL(string: \"https://example.com\")!) }\n")
        self.write("Sources/Networking/Stream.swift", "import Combine\n")
        self.write("Sources/Networking/Other.swift", "import Foundation\n")
        self.write("Sources/Screens/Screen.swift", "import SwiftUI\nstruct Screen: View { var body: some View { Text(\"Hi\") } }\n")
        self.write("Tests/DomainTests/DomainTests.swift", "import XCTest\n")

    def test_survey_rates_candidates(self) -> None:
        report = self.scan()
        self.assertEqual(report["mode"], "survey")
        self.assertEqual(report["findings"], [])
        candidates = {item["target"]: item for item in report["sharing_candidates"]}
        self.assertEqual(set(candidates), {"Domain", "Networking", "Screens"})
        self.assertEqual(candidates["Domain"]["verdict"], "clean")
        self.assertEqual(candidates["Networking"]["verdict"], "fixable")
        self.assertEqual(candidates["Networking"]["blockers"], {"AND003": 1, "AND005": 1})
        self.assertEqual(candidates["Networking"]["swift_files"], 3)
        self.assertEqual(candidates["Networking"]["swift_lines"], 4)
        self.assertEqual(candidates["Screens"]["verdict"], "ios-only")

    def test_survey_lists_only_info_findings(self) -> None:
        report = self.scan(route="lite")
        self.assertEqual({finding["severity"] for finding in report["findings"]}, {"info"})
        self.assertEqual(self.rules(report["findings"]), ["AND003"])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(android_scan.main([str(self.root), "--fail-on", "high"]), 0)

    def test_survey_markdown(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            android_scan.main([str(self.root), "--format", "markdown"])
        text = output.getvalue()
        self.assertIn("## Sharing candidates", text)
        self.assertIn("| Networking | target | 4 | AND003×1, AND005×1 | fixable |", text)


class OutputTests(ScanTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write("Package.swift", manifest(skip_target("Model", FUSE), '.target(name: "Core")'))
        self.write("Sources/Model/Skip/skip.yml", NATIVE)
        self.write("Sources/Model/Model.swift", "import UIKit\nfunc run() { print(1) }\n")
        self.write("Sources/Core/Core.swift", "import Foundation\n")

    def run_main(self, *arguments: str) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            status = android_scan.main([str(self.root), *arguments])
        return status, output.getvalue()

    def test_json_shape(self) -> None:
        status, text = self.run_main("--format", "json")
        self.assertEqual(status, 0)
        report = json.loads(text)
        for key in ("tool", "version", "root", "read_only", "route", "mode", "source_files_scanned", "shared", "skip_modules", "warnings", "summary", "findings", "sharing_candidates", "inventory"):
            self.assertIn(key, report)
        self.assertEqual((report["tool"], report["version"], report["read_only"]), ("android_scan", android_scan.VERSION, True))
        self.assertEqual((report["route"], report["mode"]), ("shared-core", "shared"))
        self.assertEqual(set(report["summary"]), {"by_severity", "by_rule", "by_skill", "by_target"})
        self.assertEqual(report["summary"]["by_rule"], {"AND001": 1, "AND007": 1})
        self.assertEqual(report["summary"]["by_skill"], {"swift-android-architecture": 1, "swift-android-sdk": 1})
        self.assertEqual(report["summary"]["by_target"], {"Model": 2})
        self.assertEqual(set(report["inventory"]), {"packages", "targets", "xcode_projects", "dependencies", "apis"})
        finding = report["findings"][0]
        self.assertEqual(
            set(finding),
            {"id", "rule", "title", "severity", "skill", "target", "file", "line", "snippet", "guard", "detail", "source", "fix"},
        )
        self.assertEqual(finding["id"], "AND001:Sources/Model/Model.swift:1")
        self.assertEqual(report["findings"][1]["severity"], "low")

    def test_markdown(self) -> None:
        status, text = self.run_main("--format", "markdown", "--route", "fuse-app")
        self.assertEqual(status, 0)
        self.assertTrue(text.startswith("# Swift on Android scan\n"))
        self.assertIn("- Route: `fuse-app`", text)
        self.assertIn("**AND001 UIKit, AppKit or SwiftUI imported into shared code** (high, swift-android-architecture)", text)
        self.assertIn("`Sources/Model/Model.swift:1` in Model", text)
        self.assertIn("| Model | target | native | native | — | 2 |", text)
        _, limited = self.run_main("--format", "markdown", "--limit", "1")
        self.assertIn("… 1 more", limited)

    def test_fail_on(self) -> None:
        self.assertEqual(self.run_main("--fail-on", "high")[0], 2)
        self.assertEqual(self.run_main("--fail-on", "low")[0], 2)
        self.write("Sources/Model/Model.swift", "func run() { print(1) }\n")
        self.assertEqual(self.run_main("--fail-on", "medium")[0], 0)
        self.assertEqual(self.run_main("--fail-on", "low")[0], 2)

    def test_shared_option_takes_several_names(self) -> None:
        self.write("Sources/Core/Core.swift", "import UIKit\n")
        _, text = self.run_main("--shared", "Core", "Model")
        self.assertEqual(json.loads(text)["shared"], ["Core", "Model"])

    def test_scan_does_not_modify_files(self) -> None:
        self.write("Package.resolved", json.dumps({"pins": [], "version": 3}))
        self.write("App.xcodeproj/project.pbxproj", "// !$*UTF8*$!\n")

        def snapshot() -> dict[str, tuple[str, int]]:
            state = {}
            for path in sorted(self.root.rglob("*")):
                stat = path.lstat()
                digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "dir"
                state[str(path.relative_to(self.root))] = (digest, stat.st_mtime_ns)
            return state

        before = snapshot()
        for arguments in (("--format", "json"), ("--format", "markdown"), ("--route", "lite", "--include-dependencies"), ("--shared", "Core", "--fail-on", "info")):
            self.run_main(*arguments)
        self.assertEqual(snapshot(), before)


class RuleMetadataTests(unittest.TestCase):
    def test_every_rule_cites_a_source(self) -> None:
        for rule in android_scan.RULES.values():
            with self.subTest(rule.id):
                self.assertRegex(rule.source, SOURCE)

    def test_measured_sources_name_measured_sections(self) -> None:
        measured = (ROOT / "references" / "measured-behavior.md").read_text(encoding="utf-8")
        status = {
            match.group(1): re.search(r"Status:\**\s*measured", match.group(0)) is not None
            for match in re.finditer(r"^## (M\d+)\b.*?(?=^## |\Z)", measured, re.S | re.M)
        }
        for rule in android_scan.RULES.values():
            for section in re.findall(r"Measured: (M\d+)", rule.source):
                with self.subTest(rule=rule.id, section=section):
                    self.assertTrue(status.get(section), f"{section} is not marked measured")

    def test_every_rule_names_a_skill_and_valid_severities(self) -> None:
        for rule in android_scan.RULES.values():
            with self.subTest(rule.id):
                self.assertIn(rule.skill, SKILLS)
                self.assertIn(rule.severity, android_scan.SEVERITIES)
                self.assertTrue(set(rule.by_route) <= set(android_scan.ROUTES))
                self.assertTrue(set(rule.by_route.values()) <= set(android_scan.SEVERITIES))
                self.assertIn(rule.transpiled, [None, *android_scan.SEVERITIES])
                self.assertIn(rule.scope, {"shared", "native", "skip-native", "bridged", "skip.yml"})
                self.assertTrue(rule.title and rule.fix)

    def test_every_rule_is_in_the_automated_table_once(self) -> None:
        checks = (ROOT / "CHECKS.md").read_text(encoding="utf-8")
        section = re.search(r"^## Automated\n(.*?)(?=^## )", checks, re.S | re.M)
        self.assertIsNotNone(section, "CHECKS.md needs an ## Automated section")
        first_cells = re.findall(r"^\|\s*`?(AND\d{3})`?\s*\|", section.group(1), re.M)
        for rule_id in android_scan.RULES:
            with self.subTest(rule_id):
                self.assertEqual(first_cells.count(rule_id), 1)
        self.assertEqual(sorted(set(first_cells)), sorted(android_scan.RULES))

    def test_version_is_semantic(self) -> None:
        self.assertRegex(android_scan.VERSION, r"^\d+\.\d+\.\d+$")


def shared_blocks() -> list[tuple[str, str]]:
    """(label, code) for each ```swift block tagged `// typecheck: shared` in the references."""
    root_references = sorted((ROOT / "references").glob("*.md"))
    names = {path.name for path in root_references}
    documents = list(root_references)
    for skill in sorted((ROOT / "skills").glob("*")):
        documents.extend(path for path in sorted((skill / "references").glob("*.md")) if path.name not in names)
    blocks: list[tuple[str, str]] = []
    for document in documents:
        text = document.read_text(encoding="utf-8")
        previous: str | None = None
        for match in re.finditer(r"^```swift\n(.*?)^```", text, re.S | re.M):
            first, _, body = match.group(1).partition("\n")
            tag = re.fullmatch(r"// typecheck: shared(, continues the block above)?\s*", first)
            if not tag:
                previous = None
                continue
            if tag.group(1) and previous is not None:
                body = previous + "\n" + body
            line = text.count("\n", 0, match.start()) + 1
            blocks.append((f"{document.relative_to(ROOT).as_posix()}:{line}", body))
            previous = body
    return blocks


class OwnAdviceTests(ScanTestCase):
    """The skills' own shared samples must scan clean on the shared-core route."""

    def test_shared_samples_have_no_findings_above_info(self) -> None:
        blocks = shared_blocks()
        if not blocks:
            return  # no tagged references yet
        names = [f"Sample{index:03d}" for index in range(1, len(blocks) + 1)]
        self.write("Package.swift", manifest(*(f'.target(name: "{name}")' for name in names)))
        labels = {}
        for name, (label, code) in zip(names, blocks):
            self.write(f"Sources/{name}/{name}.swift", code)
            labels[name] = label
        report = self.scan(route="shared-core", shared=names)
        problems = [
            f"{labels[finding['target']]}: {finding['rule']} {finding['title']} — {finding['snippet']}"
            for finding in report["findings"]
            if finding["severity"] != "info"
        ]
        self.assertEqual(problems, [])

    def test_the_shared_core_sample_scans_clean(self) -> None:
        # samples/SharedCore is the starter the skills point at; it must follow their own rules.
        report = android_scan.scan(ROOT / "samples" / "SharedCore", route="shared-core", shared=["SharedCore"])
        self.assertEqual(
            [f"{finding['rule']} {finding['file']}:{finding['line']}" for finding in report["findings"]],
            [],
        )


if __name__ == "__main__":
    unittest.main()

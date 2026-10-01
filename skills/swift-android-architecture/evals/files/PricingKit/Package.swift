// swift-tools-version: 6.1
import PackageDescription

let package = Package(
    name: "pricing-kit",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "PricingKit", type: .dynamic, targets: ["PricingKit"]),
    ],
    dependencies: [
        .package(url: "https://source.skip.tools/skip.git", from: "1.6.0"),
        .package(url: "https://source.skip.tools/skip-fuse.git", from: "1.0.0"),
    ],
    targets: [
        .target(
            name: "PricingKit",
            dependencies: [.product(name: "SkipFuse", package: "skip-fuse")],
            plugins: [.plugin(name: "skipstone", package: "skip")]
        ),
    ]
)

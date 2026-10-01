// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "uikit-import",
    platforms: [.macOS(.v14), .iOS(.v17)],
    targets: [
        .target(name: "UIKitImport"),
    ]
)

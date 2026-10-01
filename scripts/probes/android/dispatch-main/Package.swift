// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "dispatch-main",
    platforms: [.macOS(.v14), .iOS(.v17)],
    targets: [
        .target(name: "DispatchMain"),
    ]
)

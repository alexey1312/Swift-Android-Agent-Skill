// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "combine-import",
    platforms: [.macOS(.v14), .iOS(.v17)],
    targets: [
        .target(name: "CombineImport"),
    ]
)

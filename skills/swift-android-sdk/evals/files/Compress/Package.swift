// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Compress",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "Compress", targets: ["Compress"]),
    ],
    targets: [
        .target(name: "Compress"),
    ]
)

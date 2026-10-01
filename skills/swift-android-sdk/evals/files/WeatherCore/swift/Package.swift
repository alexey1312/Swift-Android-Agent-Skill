// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "WeatherCore",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "WeatherCore", type: .dynamic, targets: ["WeatherCore"]),
    ],
    targets: [
        .target(name: "WeatherCore"),
    ]
)

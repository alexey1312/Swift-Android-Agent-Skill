// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Notes",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "Notes", targets: ["Notes"]),
    ],
    targets: [
        // Meant to be shared with the Android app, whose UI is Kotlin and Jetpack Compose.
        .target(name: "NotesShared"),
        .target(name: "Notes", dependencies: ["NotesShared"]),
    ]
)

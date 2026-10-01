// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "TripNotes",
    platforms: [.iOS(.v17)],
    products: [
        .library(name: "TripNotesUI", targets: ["TripNotesUI"]),
    ],
    targets: [
        .target(name: "TripNotesKit"),
        .target(name: "TripNotesUI", dependencies: ["TripNotesKit"]),
        .testTarget(name: "TripNotesKitTests", dependencies: ["TripNotesKit"]),
    ]
)

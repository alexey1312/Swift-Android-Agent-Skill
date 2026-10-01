// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "urlsession-with-ladder",
    platforms: [.macOS(.v14), .iOS(.v17)],
    targets: [
        .target(name: "URLSessionWithLadder"),
    ]
)

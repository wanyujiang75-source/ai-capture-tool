// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "AICaptureNative",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "AI抓包工具", targets: ["AICaptureNativeApp"])
    ],
    targets: [
        .executableTarget(
            name: "AICaptureNativeApp",
            path: "Sources/AICaptureNativeApp"
        )
    ]
)

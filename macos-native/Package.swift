// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "AICaptureNative",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "抓包工具", targets: ["AICaptureNativeApp"])
    ],
    dependencies: [
        .package(url: "https://github.com/sparkle-project/Sparkle", exact: "2.10.1")
    ],
    targets: [
        .executableTarget(
            name: "AICaptureNativeApp",
            dependencies: [.product(name: "Sparkle", package: "Sparkle")],
            path: "Sources/AICaptureNativeApp",
            linkerSettings: [.unsafeFlags(["-Xlinker", "-rpath", "-Xlinker", "@executable_path/../Frameworks"])]
        ),
        .testTarget(
            name: "AICaptureNativeAppTests",
            dependencies: ["AICaptureNativeApp"],
            path: "Tests/AICaptureNativeAppTests"
        )
    ]
)

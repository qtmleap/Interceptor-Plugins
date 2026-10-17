// swift-tools-version: 6.0
import PackageDescription

// Drives the pinned app libraries (.tools/interceptor, fetched by tools/bootstrap.sh) through their public API only.
let package = Package(
    name: "Verifier",
    platforms: [.macOS(.v14)],
    dependencies: [.package(path: "../../.tools/interceptor/Packages/InterceptorAutomation")],
    targets: [
        .executableTarget(
            name: "interceptor-samples-check",
            dependencies: [
                .product(name: "AutomationCore", package: "InterceptorAutomation"),
                .product(name: "AutomationRuntime", package: "InterceptorAutomation"),
                .product(name: "AutomationRepository", package: "InterceptorAutomation"),
            ]
        )
    ],
    swiftLanguageModes: [.v5]
)

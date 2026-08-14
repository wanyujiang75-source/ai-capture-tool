import Darwin
import AppKit
import Foundation
import Testing
@testable import AICaptureNativeApp

@MainActor
struct RuntimeManagerTests {
    @Test
    func shutdownStopsOnlyTheOwnedBackend() throws {
        let temporaryDirectory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let projectRoot = temporaryDirectory.appendingPathComponent("backend", isDirectory: true)
        let scriptsDirectory = projectRoot.appendingPathComponent("scripts", isDirectory: true)
        let runtimeDirectory = temporaryDirectory.appendingPathComponent("runtime", isDirectory: true)
        try FileManager.default.createDirectory(at: scriptsDirectory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temporaryDirectory) }

        let launcher = scriptsDirectory.appendingPathComponent("start_console.sh")
        try """
        #!/bin/bash
        trap 'exit 0' TERM INT
        while true; do sleep 1; done
        """.write(to: launcher, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes(
            [.posixPermissions: 0o755],
            ofItemAtPath: launcher.path
        )

        let manager = RuntimeManager(
            backendURL: URL(string: "http://127.0.0.1:65530")!,
            runtimeDirectory: runtimeDirectory,
            projectRootOverride: projectRoot
        )
        try manager.startBackend()
        let pidURL = runtimeDirectory.appendingPathComponent("native-backend.pid")
        let pid = try #require(Int32(String(contentsOf: pidURL, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)))
        #expect(kill(pid, 0) == 0)

        manager.shutdown()

        #expect(!FileManager.default.fileExists(atPath: pidURL.path))
        #expect(kill(pid, 0) != 0)
    }

    @Test
    func shutdownDoesNotStopAnUnownedProcess() throws {
        let external = Process()
        external.executableURL = URL(fileURLWithPath: "/bin/sleep")
        external.arguments = ["30"]
        try external.run()
        defer {
            if external.isRunning {
                external.terminate()
                external.waitUntilExit()
            }
        }

        let manager = RuntimeManager(
            backendURL: URL(string: "http://127.0.0.1:65529")!,
            runtimeDirectory: FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString, isDirectory: true)
        )
        manager.shutdown()

        #expect(external.isRunning)
    }

    @Test
    func backendDoesNotWritePythonBytecodeIntoTheSignedAppBundle() {
        let temporaryDirectory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let projectRoot = temporaryDirectory.appendingPathComponent("backend", isDirectory: true)
        let runtimeDirectory = temporaryDirectory.appendingPathComponent("runtime", isDirectory: true)

        let manager = RuntimeManager(
            backendURL: URL(string: "http://127.0.0.1:65528")!,
            runtimeDirectory: runtimeDirectory,
            projectRootOverride: projectRoot
        )
        let environment = manager.backendEnvironment(projectRoot: projectRoot)

        #expect(environment["PYTHONDONTWRITEBYTECODE"] == "1")
        #expect(environment["PYTHONPYCACHEPREFIX"] == runtimeDirectory.appendingPathComponent("python-cache", isDirectory: true).path)
    }

    @Test
    func backendEnvironmentDropsInheritedDeviceConfigOverride() {
        let temporaryDirectory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let projectRoot = temporaryDirectory.appendingPathComponent("backend", isDirectory: true)
        let runtimeDirectory = temporaryDirectory.appendingPathComponent("runtime", isDirectory: true)
        let manager = RuntimeManager(
            backendURL: URL(string: "http://127.0.0.1:65527")!,
            runtimeDirectory: runtimeDirectory,
            projectRootOverride: projectRoot
        )

        let environment = manager.backendEnvironment(
            projectRoot: projectRoot,
            inheriting: [
                "CAPTURE_DEVICES_CONFIG": "/tmp/deleted-test-devices.json",
                "CAPTURE_RUNTIME_DIR": "/tmp/deleted-test-runtime",
                "PATH": "/usr/bin:/bin",
            ]
        )

        #expect(environment["CAPTURE_DEVICES_CONFIG"] == nil)
        #expect(environment["CAPTURE_RUNTIME_DIR"] == runtimeDirectory.path)
    }

    @Test
    func nativeRuntimeDirectoryIgnoresBackendRuntimeOverride() {
        let runtimeDirectory = RuntimeManager.defaultRuntimeDirectory(
            inheriting: ["CAPTURE_RUNTIME_DIR": "/tmp/deleted-test-runtime"]
        )

        #expect(runtimeDirectory.path.hasSuffix("/Library/Application Support/AI抓包工具/runtime-native"))
        #expect(runtimeDirectory.path != "/tmp/deleted-test-runtime")
    }

    @Test
    func appDelegateReopensAnExistingHiddenWindow() {
        let application = NSApplication.shared
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 600, height: 400),
            styleMask: [.titled, .closable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.identifier = NSUserInterfaceItemIdentifier("ai-capture-main-window")
        window.orderOut(nil)
        defer {
            window.close()
        }

        let delegate = AppDelegate()
        let handled = delegate.applicationShouldHandleReopen(application, hasVisibleWindows: false)

        #expect(handled)
        #expect(window.isVisible)
    }
}

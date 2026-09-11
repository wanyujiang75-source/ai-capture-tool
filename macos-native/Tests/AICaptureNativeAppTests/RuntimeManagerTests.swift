import Darwin
import AppKit
import Foundation
import Testing
@testable import AICaptureNativeApp

private final class RuntimeStatusURLProtocol: URLProtocol, @unchecked Sendable {
    nonisolated(unsafe) static var responseBodies: [Data] = []
    nonisolated(unsafe) static var receivedRequests: [URLRequest] = []
    nonisolated(unsafe) static var stallRequests = false

    static func reset(buildIDs: [String?], activeSession: Bool = false, stallRequests: Bool = false) {
        receivedRequests = []
        self.stallRequests = stallRequests
        responseBodies = buildIDs.map { buildID in
            let buildIDField = buildID.map { "\"build_id\": \"\($0)\"" } ?? ""
            let activeSessionField = activeSession ? "{\"id\": 42}" : "null"
            return Data(
                """
                {"desktop": {"enabled": true, \(buildIDField)}, "active_session": \(activeSessionField)}
                """.utf8
            )
        }
    }

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        Self.receivedRequests.append(request)
        if Self.stallRequests {
            return
        }
        let response = HTTPURLResponse(
            url: request.url!,
            statusCode: 200,
            httpVersion: nil,
            headerFields: ["Content-Type": "application/json"]
        )!
        let body = Self.responseBodies.isEmpty
            ? Data("{\"desktop\": {\"enabled\": true}}".utf8)
            : Self.responseBodies.removeFirst()
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: body)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

@MainActor
@Suite(.serialized)
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
    func shutdownRequestsCaptureCleanupForTheOwnedBackend() throws {
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
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: launcher.path)

        RuntimeStatusURLProtocol.reset(buildIDs: [])
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [RuntimeStatusURLProtocol.self]
        let manager = RuntimeManager(
            backendURL: URL(string: "http://127.0.0.1:65521")!,
            runtimeDirectory: runtimeDirectory,
            projectRootOverride: projectRoot,
            sessionConfiguration: configuration
        )
        try manager.startBackend()

        manager.shutdown()

        #expect(RuntimeStatusURLProtocol.receivedRequests.contains { request in
            request.httpMethod == "POST"
                && request.url?.path == "/api/desktop/stop-captures"
        })
    }

    @Test
    func shutdownCleanupTimeoutDoesNotPreventOwnedBackendTermination() throws {
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
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: launcher.path)

        RuntimeStatusURLProtocol.reset(buildIDs: [], stallRequests: true)
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [RuntimeStatusURLProtocol.self]
        let manager = RuntimeManager(
            backendURL: URL(string: "http://127.0.0.1:65520")!,
            runtimeDirectory: runtimeDirectory,
            projectRootOverride: projectRoot,
            sessionConfiguration: configuration,
            shutdownCleanupTimeout: 0.05
        )
        try manager.startBackend()
        let pid = try #require(Int32(
            String(
                contentsOf: runtimeDirectory.appendingPathComponent("native-backend.pid"),
                encoding: .utf8
            ).trimmingCharacters(in: .whitespacesAndNewlines)
        ))
        let startedAt = Date()

        manager.shutdown()

        #expect(Date().timeIntervalSince(startedAt) < 1)
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

        RuntimeStatusURLProtocol.reset(buildIDs: [])
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [RuntimeStatusURLProtocol.self]
        let manager = RuntimeManager(
            backendURL: URL(string: "http://127.0.0.1:65529")!,
            runtimeDirectory: FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString, isDirectory: true),
            sessionConfiguration: configuration
        )
        manager.shutdown()

        #expect(external.isRunning)
        #expect(RuntimeStatusURLProtocol.receivedRequests.isEmpty)
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
    func backendEnvironmentIncludesExpectedBuildIdentity() {
        let temporaryDirectory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let projectRoot = temporaryDirectory.appendingPathComponent("backend", isDirectory: true)
        let runtimeDirectory = temporaryDirectory.appendingPathComponent("runtime", isDirectory: true)
        let manager = RuntimeManager(
            backendURL: URL(string: "http://127.0.0.1:65526")!,
            runtimeDirectory: runtimeDirectory,
            projectRootOverride: projectRoot,
            buildID: "new-build"
        )

        let environment = manager.backendEnvironment(projectRoot: projectRoot, inheriting: [:])

        #expect(environment["TRACEDECK_DESKTOP_BUILD_ID"] == "new-build")
    }

    @Test
    func checkStatusReplacesARecordedBackendOnlyWhenOwnershipIsVerified() async throws {
        let temporaryDirectory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let projectRoot = temporaryDirectory.appendingPathComponent("backend", isDirectory: true)
        let scriptsDirectory = projectRoot.appendingPathComponent("scripts", isDirectory: true)
        let runtimeDirectory = temporaryDirectory.appendingPathComponent("runtime", isDirectory: true)
        try FileManager.default.createDirectory(at: scriptsDirectory, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: runtimeDirectory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temporaryDirectory) }

        let launcher = scriptsDirectory.appendingPathComponent("start_console.sh")
        try """
        #!/bin/bash
        trap 'exit 0' TERM INT
        while true; do sleep 1; done
        """.write(to: launcher, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: launcher.path)

        let staleProcess = Process()
        staleProcess.executableURL = URL(fileURLWithPath: "/bin/sleep")
        staleProcess.arguments = ["30"]
        try staleProcess.run()
        defer {
            if staleProcess.isRunning {
                staleProcess.terminate()
                staleProcess.waitUntilExit()
            }
        }
        try "\(staleProcess.processIdentifier)\n".write(
            to: runtimeDirectory.appendingPathComponent("native-backend.pid"),
            atomically: true,
            encoding: .utf8
        )

        RuntimeStatusURLProtocol.reset(buildIDs: ["old-build", "new-build"])
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [RuntimeStatusURLProtocol.self]
        let manager = RuntimeManager(
            backendURL: URL(string: "http://127.0.0.1:65525")!,
            runtimeDirectory: runtimeDirectory,
            projectRootOverride: projectRoot,
            buildID: "new-build",
            sessionConfiguration: configuration,
            processOwnershipVerifier: { $0 == staleProcess.processIdentifier }
        )
        defer { manager.shutdown() }

        let status = await manager.checkStatus()

        #expect(status == .ready("http://127.0.0.1:65525"))
        #expect(!staleProcess.isRunning)
    }

    @Test
    func checkStatusDoesNotStopAnUnverifiedProcessForAMismatchedBackend() async throws {
        let temporaryDirectory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let runtimeDirectory = temporaryDirectory.appendingPathComponent("runtime", isDirectory: true)
        try FileManager.default.createDirectory(at: runtimeDirectory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temporaryDirectory) }

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
        try "\(external.processIdentifier)\n".write(
            to: runtimeDirectory.appendingPathComponent("native-backend.pid"),
            atomically: true,
            encoding: .utf8
        )

        RuntimeStatusURLProtocol.reset(buildIDs: ["old-build"])
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [RuntimeStatusURLProtocol.self]
        let manager = RuntimeManager(
            backendURL: URL(string: "http://127.0.0.1:65524")!,
            runtimeDirectory: runtimeDirectory,
            buildID: "new-build",
            sessionConfiguration: configuration,
            processOwnershipVerifier: { _ in false }
        )

        let status = await manager.checkStatus()

        guard case let .failed(message) = status else {
            Issue.record("expected a safe port-conflict failure, got \(status)")
            return
        }
        #expect(message.contains("其他程序"))
        #expect(external.isRunning)
    }

    @Test
    func matchingRecordedBackendIsAdoptedAndStoppedOnShutdown() async throws {
        let temporaryDirectory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let runtimeDirectory = temporaryDirectory.appendingPathComponent("runtime", isDirectory: true)
        try FileManager.default.createDirectory(at: runtimeDirectory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temporaryDirectory) }

        let orphan = Process()
        orphan.executableURL = URL(fileURLWithPath: "/bin/sleep")
        orphan.arguments = ["30"]
        try orphan.run()
        defer {
            if orphan.isRunning {
                orphan.terminate()
                orphan.waitUntilExit()
            }
        }
        try "\(orphan.processIdentifier)\n".write(
            to: runtimeDirectory.appendingPathComponent("native-backend.pid"),
            atomically: true,
            encoding: .utf8
        )

        RuntimeStatusURLProtocol.reset(buildIDs: ["current-build"])
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [RuntimeStatusURLProtocol.self]
        let manager = RuntimeManager(
            backendURL: URL(string: "http://127.0.0.1:65523")!,
            runtimeDirectory: runtimeDirectory,
            buildID: "current-build",
            sessionConfiguration: configuration,
            processOwnershipVerifier: { $0 == orphan.processIdentifier }
        )

        #expect(await manager.checkStatus() == .ready("http://127.0.0.1:65523"))
        manager.shutdown()

        #expect(!orphan.isRunning)
        #expect(!FileManager.default.fileExists(
            atPath: runtimeDirectory.appendingPathComponent("native-backend.pid").path
        ))
    }

    @Test
    func mismatchedBackendWithActiveCaptureIsNotReplaced() async throws {
        let temporaryDirectory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let runtimeDirectory = temporaryDirectory.appendingPathComponent("runtime", isDirectory: true)
        try FileManager.default.createDirectory(at: runtimeDirectory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temporaryDirectory) }

        let activeBackend = Process()
        activeBackend.executableURL = URL(fileURLWithPath: "/bin/sleep")
        activeBackend.arguments = ["30"]
        try activeBackend.run()
        defer {
            if activeBackend.isRunning {
                activeBackend.terminate()
                activeBackend.waitUntilExit()
            }
        }
        try "\(activeBackend.processIdentifier)\n".write(
            to: runtimeDirectory.appendingPathComponent("native-backend.pid"),
            atomically: true,
            encoding: .utf8
        )

        RuntimeStatusURLProtocol.reset(buildIDs: ["old-build"], activeSession: true)
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [RuntimeStatusURLProtocol.self]
        let manager = RuntimeManager(
            backendURL: URL(string: "http://127.0.0.1:65522")!,
            runtimeDirectory: runtimeDirectory,
            buildID: "new-build",
            sessionConfiguration: configuration,
            processOwnershipVerifier: { $0 == activeBackend.processIdentifier }
        )

        let status = await manager.checkStatus()

        guard case let .failed(message) = status else {
            Issue.record("expected active capture protection, got \(status)")
            return
        }
        #expect(message.contains("正在抓包"))
        #expect(activeBackend.isRunning)
    }

    @Test
    func managedBackendExecutableMustBelongToTheCaptureAppRuntime() {
        #expect(RuntimeManager.isManagedBackendExecutable(
            path: "/Applications/抓包工具.app/Contents/Resources/runtime/bin/python3"
        ))
        #expect(RuntimeManager.isManagedBackendExecutable(
            path: "/Applications/AI抓包工具.app/Contents/Resources/runtime/python/bin/python3.12"
        ))
        #expect(!RuntimeManager.isManagedBackendExecutable(path: "/usr/bin/python3"))
        #expect(!RuntimeManager.isManagedBackendExecutable(
            path: "/Applications/其他工具.app/Contents/Resources/runtime/bin/python3"
        ))
    }

    @Test
    func takeoverRequiresAnOrphanedCaptureAppBackend() {
        let managedPath = "/Applications/抓包工具.app/Contents/Resources/runtime/bin/python3"

        #expect(RuntimeManager.canTakeOverBackend(executablePath: managedPath, parentProcessID: 1))
        #expect(!RuntimeManager.canTakeOverBackend(executablePath: managedPath, parentProcessID: 9123))
        #expect(!RuntimeManager.canTakeOverBackend(
            executablePath: "/usr/bin/python3",
            parentProcessID: 1
        ))
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

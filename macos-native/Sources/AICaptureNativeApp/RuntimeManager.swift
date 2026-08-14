import Darwin
import Foundation

@MainActor
final class RuntimeManager {
    static let shared = RuntimeManager()

    let backendURL: URL
    let runtimeDirectory: URL
    private let projectRootOverride: URL?
    private var backendProcess: Process?

    init(
        backendURL: URL = URL(string: "http://127.0.0.1:7001")!,
        runtimeDirectory: URL = RuntimeManager.defaultRuntimeDirectory(),
        projectRootOverride: URL? = nil
    ) {
        self.backendURL = backendURL
        self.runtimeDirectory = runtimeDirectory
        self.projectRootOverride = projectRootOverride
    }

    func checkStatus() async -> AppState.RuntimeStatus {
        do {
            try FileManager.default.createDirectory(
                at: runtimeDirectory,
                withIntermediateDirectories: true
            )
        } catch {
            return .failed("无法创建本机运行目录：\(error.localizedDescription)")
        }

        if let status = await probeBackendStatus() {
            return status
        }

        do {
            try startBackend()
        } catch {
            return .failed("无法启动本机抓包后端：\(error.localizedDescription)")
        }

        let deadline = Date().addingTimeInterval(30)
        while Date() < deadline {
            if let status = await probeBackendStatus() {
                return status
            }
            try? await Task.sleep(nanoseconds: 1_000_000_000)
        }

        return .failed("本机抓包后端启动超时，请查看日志：\(backendLogURL.path)")
    }

    private func probeBackendStatus() async -> AppState.RuntimeStatus? {
        var request = URLRequest(url: backendURL.appendingPathComponent("api/status"))
        request.timeoutInterval = 3

        let configuration = URLSessionConfiguration.ephemeral
        configuration.connectionProxyDictionary = [:]
        let session = URLSession(configuration: configuration)
        defer {
            session.invalidateAndCancel()
        }

        do {
            let (_, response) = try await session.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                return .failed("本机抓包后端响应无效")
            }
            guard httpResponse.statusCode == 200 else {
                return .failed("本机抓包后端返回 HTTP \(httpResponse.statusCode)")
            }
            return .ready(backendURL.absoluteString)
        } catch {
            return nil
        }
    }

    func startBackend() throws {
        if let backendProcess, backendProcess.isRunning {
            return
        }
        guard let projectRoot = findProjectRoot() else {
            throw RuntimeError("未找到项目运行目录，缺少 scripts/start_console.sh")
        }
        try FileManager.default.createDirectory(
            at: runtimeDirectory,
            withIntermediateDirectories: true
        )
        let script = projectRoot.appendingPathComponent("scripts/start_console.sh")
        let logURL = backendLogURL
        FileManager.default.createFile(atPath: logURL.path, contents: nil)
        let logHandle = try FileHandle(forWritingTo: logURL)
        defer { try? logHandle.close() }
        try logHandle.seekToEnd()

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = [script.path]
        process.currentDirectoryURL = projectRoot
        process.environment = backendEnvironment(projectRoot: projectRoot)
        process.standardOutput = logHandle
        process.standardError = logHandle
        try process.run()
        do {
            try "\(process.processIdentifier)\n".write(
                to: backendPIDURL,
                atomically: true,
                encoding: .utf8
            )
        } catch {
            process.terminate()
            process.waitUntilExit()
            throw error
        }
        backendProcess = process
    }

    func backendEnvironment(
        projectRoot: URL,
        inheriting inheritedEnvironment: [String: String] = ProcessInfo.processInfo.environment
    ) -> [String: String] {
        var environment = inheritedEnvironment
        environment.removeValue(forKey: "CAPTURE_DEVICES_CONFIG")
        environment["TRACEDECK_DESKTOP"] = "1"
        environment["CAPTURE_RUNTIME_DIR"] = runtimeDirectory.path
        environment["CONSOLE_HOST"] = backendURL.host ?? "127.0.0.1"
        environment["CONSOLE_PORT"] = backendURL.port.map(String.init) ?? "7001"
        environment["PYTHONPATH"] = projectRoot.path
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONPYCACHEPREFIX"] = runtimeDirectory
            .appendingPathComponent("python-cache", isDirectory: true).path
        if let embeddedRuntime = embeddedRuntimeDirectory() {
            let runtimeBin = embeddedRuntime.appendingPathComponent("bin", isDirectory: true)
            let runtimePython = runtimeBin.appendingPathComponent("python3")
            environment["CONSOLE_PYTHON"] = runtimePython.path
            environment["CONSOLE_SKIP_INSTALL"] = "1"
            environment["CONSOLE_USE_EMBEDDED_RUNTIME"] = "1"
            environment["TRACEDECK_RUNTIME_BIN"] = runtimeBin.path
            environment["FRIDA_PYTHON_BIN"] = runtimePython.path
            environment["MITMWEB_BIN"] = runtimeBin.appendingPathComponent("mitmweb").path
            environment["PYTHONNOUSERSITE"] = "1"
            environment["PATH"] = runtimeBin.path + ":" + (environment["PATH"] ?? "/usr/bin:/bin")
        } else {
            environment["CONSOLE_VENV_DIR"] = runtimeDirectory
                .appendingPathComponent("venv-console", isDirectory: true).path
        }
        return environment
    }

    func shutdown() {
        guard let process = backendProcess else {
            return
        }
        let processIdentifier = process.processIdentifier
        if process.isRunning {
            process.terminate()
            let deadline = Date().addingTimeInterval(5)
            while process.isRunning && Date() < deadline {
                usleep(100_000)
            }
            if process.isRunning {
                kill(processIdentifier, SIGKILL)
            }
            process.waitUntilExit()
        }
        removePIDRecord(ifOwnedBy: processIdentifier)
        backendProcess = nil
    }

    private var backendLogURL: URL {
        runtimeDirectory.appendingPathComponent("native-backend.log")
    }

    private var backendPIDURL: URL {
        runtimeDirectory.appendingPathComponent("native-backend.pid")
    }

    private func removePIDRecord(ifOwnedBy processIdentifier: Int32) {
        guard let contents = try? String(contentsOf: backendPIDURL, encoding: .utf8),
              Int32(contents.trimmingCharacters(in: .whitespacesAndNewlines)) == processIdentifier else {
            return
        }
        try? FileManager.default.removeItem(at: backendPIDURL)
    }

    private func embeddedRuntimeDirectory() -> URL? {
        guard let resourceURL = Bundle.main.resourceURL else {
            return nil
        }
        let runtime = resourceURL.appendingPathComponent("runtime", isDirectory: true)
        let python = runtime.appendingPathComponent("bin/python3")
        let mitmweb = runtime.appendingPathComponent("bin/mitmweb")
        guard FileManager.default.isExecutableFile(atPath: python.path),
              FileManager.default.isExecutableFile(atPath: mitmweb.path) else {
            return nil
        }
        return runtime
    }

    private func findProjectRoot() -> URL? {
        if let projectRootOverride,
           FileManager.default.fileExists(
               atPath: projectRootOverride.appendingPathComponent("scripts/start_console.sh").path
           ) {
            return projectRootOverride
        }
        var candidates: [URL] = []
        if let resourceURL = Bundle.main.resourceURL {
            candidates.append(resourceURL.appendingPathComponent("backend", isDirectory: true))
            candidates.append(resourceURL)
        }
        candidates.append(Bundle.main.bundleURL)
        candidates.append(URL(fileURLWithPath: FileManager.default.currentDirectoryPath))
        candidates.append(runtimeDirectory)

        for candidate in candidates {
            var current = candidate
            for _ in 0..<8 {
                if FileManager.default.fileExists(atPath: current.appendingPathComponent("scripts/start_console.sh").path) {
                    return current
                }
                let parent = current.deletingLastPathComponent()
                if parent.path == current.path {
                    break
                }
                current = parent
            }
        }
        return nil
    }

    private struct RuntimeError: LocalizedError {
        let message: String

        init(_ message: String) {
            self.message = message
        }

        var errorDescription: String? {
            message
        }
    }

    static func defaultRuntimeDirectory(
        inheriting environment: [String: String] = ProcessInfo.processInfo.environment
    ) -> URL {
        if let configuredRuntime = environment["AI_CAPTURE_NATIVE_RUNTIME_DIR"],
           !configuredRuntime.isEmpty {
            return URL(fileURLWithPath: configuredRuntime, isDirectory: true)
        }
        let applicationSupport = FileManager.default.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first ?? FileManager.default.homeDirectoryForCurrentUser

        return applicationSupport
            .appendingPathComponent("AI抓包工具", isDirectory: true)
            .appendingPathComponent("runtime-native", isDirectory: true)
    }
}

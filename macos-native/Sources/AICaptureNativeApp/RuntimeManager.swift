import Darwin
import Foundation

@MainActor
final class RuntimeManager {
    static let shared = RuntimeManager()

    let backendURL: URL
    let runtimeDirectory: URL
    private let projectRootOverride: URL?
    private let buildID: String
    private let sessionConfiguration: URLSessionConfiguration
    private let processOwnershipVerifier: (Int32) -> Bool
    private let shutdownCleanupTimeout: TimeInterval
    private var backendProcess: Process?
    private var adoptedBackendPID: Int32?

    init(
        backendURL: URL = URL(string: "http://127.0.0.1:7001")!,
        runtimeDirectory: URL = RuntimeManager.defaultRuntimeDirectory(),
        projectRootOverride: URL? = nil,
        buildID: String = RuntimeManager.defaultBuildID(),
        sessionConfiguration: URLSessionConfiguration = RuntimeManager.defaultSessionConfiguration(),
        processOwnershipVerifier: @escaping (Int32) -> Bool = RuntimeManager.isManagedBackendProcess,
        shutdownCleanupTimeout: TimeInterval = 4
    ) {
        self.backendURL = backendURL
        self.runtimeDirectory = runtimeDirectory
        self.projectRootOverride = projectRootOverride
        self.buildID = buildID
        self.sessionConfiguration = sessionConfiguration
        self.processOwnershipVerifier = processOwnershipVerifier
        self.shutdownCleanupTimeout = shutdownCleanupTimeout
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

        switch await probeBackendStatus() {
        case let .ready(status):
            return status
        case .unavailable:
            break
        case let .incompatible(activeCapture):
            if activeCapture {
                return .failed("旧版抓包工具正在抓包，请先在旧版中停止抓包后重新检查。")
            }
            do {
                try stopRecordedBackendForUpgrade()
            } catch {
                return .failed(error.localizedDescription)
            }
        case let .failed(message):
            return .failed(message)
        }

        do {
            try startBackend()
        } catch {
            return .failed("无法启动本机抓包后端：\(error.localizedDescription)")
        }

        let deadline = Date().addingTimeInterval(30)
        while Date() < deadline {
            switch await probeBackendStatus() {
            case let .ready(status):
                return status
            case .unavailable:
                break
            case .incompatible:
                return .failed("本机抓包后端版本校验失败，请重新安装抓包工具。")
            case let .failed(message):
                return .failed(message)
            }
            try? await Task.sleep(nanoseconds: 1_000_000_000)
        }

        return .failed("本机抓包后端启动超时，请查看日志：\(backendLogURL.path)")
    }

    private func probeBackendStatus() async -> BackendProbeResult {
        var request = URLRequest(url: backendURL.appendingPathComponent("api/status"))
        request.timeoutInterval = 3

        let configuration = sessionConfiguration.copy() as? URLSessionConfiguration
            ?? RuntimeManager.defaultSessionConfiguration()
        configuration.connectionProxyDictionary = [:]
        let session = URLSession(configuration: configuration)
        defer {
            session.invalidateAndCancel()
        }

        do {
            let (data, response) = try await session.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                return .failed("本机抓包后端响应无效。")
            }
            guard httpResponse.statusCode == 200 else {
                return .failed("本机抓包后端暂时不可用，请重新检查。")
            }
            guard let status = try? JSONDecoder().decode(BackendStatus.self, from: data) else {
                return .incompatible(activeCapture: false)
            }
            guard status.desktop?.enabled == true,
                  status.desktop?.buildID == buildID else {
                return .incompatible(activeCapture: status.activeSession != nil)
            }
            if backendProcess == nil {
                adoptedBackendPID = recordedManagedBackendPID()
            }
            return .ready(.ready(backendURL.absoluteString))
        } catch {
            return .unavailable
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
        environment["TRACEDECK_DESKTOP_BUILD_ID"] = buildID
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

    private func stopRecordedBackendForUpgrade() throws {
        guard let processIdentifier = recordedManagedBackendPID() else {
            throw RuntimeError(
                "抓包端口 \(backendURL.port ?? 7001) 正被其他程序使用。工具不会自动结束该程序，请关闭占用程序后重新检查。"
            )
        }

        try stopRecordedBackend(processIdentifier)
    }

    private func stopRecordedBackend(_ processIdentifier: Int32) throws {
        guard recordedManagedBackendPID() == processIdentifier else {
            throw RuntimeError("旧版抓包后端的进程身份已变化，工具不会自动结束该进程。")
        }

        if backendProcess?.processIdentifier == processIdentifier {
            shutdown()
            return
        }

        guard kill(processIdentifier, SIGTERM) == 0 else {
            throw RuntimeError("旧版抓包后端无法停止，请退出抓包工具后重试。")
        }
        var deadline = Date().addingTimeInterval(5)
        while kill(processIdentifier, 0) == 0 && Date() < deadline {
            usleep(100_000)
        }
        if kill(processIdentifier, 0) == 0 {
            guard kill(processIdentifier, SIGKILL) == 0 else {
                throw RuntimeError("旧版抓包后端无法停止，请重新启动 Mac 后重试。")
            }
            deadline = Date().addingTimeInterval(2)
            while kill(processIdentifier, 0) == 0 && Date() < deadline {
                usleep(100_000)
            }
        }
        guard kill(processIdentifier, 0) != 0 else {
            throw RuntimeError("旧版抓包后端仍在运行，请重新启动 Mac 后重试。")
        }
        removePIDRecord(ifOwnedBy: processIdentifier)
    }

    private func recordedManagedBackendPID() -> Int32? {
        guard let contents = try? String(contentsOf: backendPIDURL, encoding: .utf8),
              let processIdentifier = Int32(contents.trimmingCharacters(in: .whitespacesAndNewlines)),
              processIdentifier > 1,
              kill(processIdentifier, 0) == 0,
              processOwnershipVerifier(processIdentifier) else {
            return nil
        }
        return processIdentifier
    }

    func shutdown() {
        let ownsRunningBackend = backendProcess?.isRunning == true || adoptedBackendPID != nil
        if ownsRunningBackend {
            requestCaptureCleanup()
        }

        guard let process = backendProcess else {
            if let adoptedBackendPID {
                try? stopRecordedBackend(adoptedBackendPID)
                self.adoptedBackendPID = nil
            }
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
        adoptedBackendPID = nil
    }

    private func requestCaptureCleanup() {
        var request = URLRequest(
            url: backendURL.appendingPathComponent("api/desktop/stop-captures")
        )
        request.httpMethod = "POST"
        request.timeoutInterval = shutdownCleanupTimeout

        let configuration = sessionConfiguration.copy() as? URLSessionConfiguration
            ?? RuntimeManager.defaultSessionConfiguration()
        configuration.connectionProxyDictionary = [:]
        let session = URLSession(configuration: configuration)
        let completed = DispatchSemaphore(value: 0)
        let task = session.dataTask(with: request) { _, _, _ in
            completed.signal()
        }
        task.resume()
        if completed.wait(timeout: .now() + shutdownCleanupTimeout) == .timedOut {
            task.cancel()
        }
        session.invalidateAndCancel()
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

    nonisolated static func isManagedBackendExecutable(path: String) -> Bool {
        let normalizedPath = URL(fileURLWithPath: path).standardizedFileURL.path
        return normalizedPath.contains("/抓包工具.app/Contents/Resources/runtime/")
            || normalizedPath.contains("/AI抓包工具.app/Contents/Resources/runtime/")
    }

    nonisolated static func canTakeOverBackend(
        executablePath: String,
        parentProcessID: UInt32
    ) -> Bool {
        parentProcessID == 1 && isManagedBackendExecutable(path: executablePath)
    }

    nonisolated private static func isManagedBackendProcess(_ processIdentifier: Int32) -> Bool {
        var buffer = [CChar](repeating: 0, count: 4_096)
        let length = proc_pidpath(processIdentifier, &buffer, UInt32(buffer.count))
        guard length > 0 else {
            return false
        }
        let pathBytes = buffer.prefix(while: { $0 != 0 }).map { UInt8(bitPattern: $0) }
        var processInfo = proc_bsdinfo()
        let processInfoSize = Int32(MemoryLayout<proc_bsdinfo>.size)
        guard proc_pidinfo(
            processIdentifier,
            PROC_PIDTBSDINFO,
            0,
            &processInfo,
            processInfoSize
        ) == processInfoSize else {
            return false
        }
        return canTakeOverBackend(
            executablePath: String(decoding: pathBytes, as: UTF8.self),
            parentProcessID: processInfo.pbi_ppid
        )
    }

    nonisolated private static func defaultBuildID() -> String {
        if let buildIDURL = Bundle.main.url(forResource: "backend-build-id", withExtension: "txt"),
           let buildID = try? String(contentsOf: buildIDURL, encoding: .utf8)
            .trimmingCharacters(in: .whitespacesAndNewlines),
           !buildID.isEmpty {
            return buildID
        }
        return "development"
    }

    nonisolated private static func defaultSessionConfiguration() -> URLSessionConfiguration {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.connectionProxyDictionary = [:]
        return configuration
    }

    private enum BackendProbeResult {
        case ready(AppState.RuntimeStatus)
        case unavailable
        case incompatible(activeCapture: Bool)
        case failed(String)
    }

    private struct BackendStatus: Decodable {
        let desktop: DesktopRuntime?
        let activeSession: ActiveSession?

        struct ActiveSession: Decodable {}

        enum CodingKeys: String, CodingKey {
            case desktop
            case activeSession = "active_session"
        }

        struct DesktopRuntime: Decodable {
            let enabled: Bool
            let buildID: String?

            enum CodingKeys: String, CodingKey {
                case enabled
                case buildID = "build_id"
            }
        }
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

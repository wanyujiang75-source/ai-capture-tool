import Foundation

enum LogcatMinimumLevel: String, CaseIterable, Identifiable, Sendable {
    case verbose = "V"
    case debug = "D"
    case info = "I"
    case warning = "W"
    case error = "E"
    case fatal = "F"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .verbose:
            AppCopy.Log.allLevels
        case .debug:
            "Debug 及以上"
        case .info:
            "Info 及以上"
        case .warning:
            "Warning 及以上"
        case .error:
            "Error 及以上"
        case .fatal:
            "Fatal"
        }
    }

    fileprivate var rank: Int {
        switch self {
        case .verbose:
            0
        case .debug:
            1
        case .info:
            2
        case .warning:
            3
        case .error:
            4
        case .fatal:
            5
        }
    }
}

@MainActor
final class LogcatController: ObservableObject {
    typealias Sleep = @Sendable (Duration) async throws -> Void

    @Published private(set) var entries: [LogcatEntry] = []
    @Published var source: LogcatSource = .app
    @Published private(set) var state = "stopped"
    @Published var searchText = ""
    @Published var minimumLevel: LogcatMinimumLevel = .verbose
    @Published private(set) var isPaused = false
    @Published var autoScroll = true
    @Published private(set) var truncated = false
    @Published private(set) var message = AppCopy.Log.deviceOffline
    @Published private(set) var lastIssue: UserFacingIssue?

    private struct StreamKey: Equatable {
        let deviceID: String
        let source: LogcatSource
        let packageName: String
        let deviceKind: AndroidDeviceKind
    }

    private let api: any LogcatAPI
    private let sleep: Sleep
    private let maximumEntryCount = 5_000
    private var pollingTask: Task<Void, Never>?
    private var currentStream: StreamKey?
    private var cursor: Int64 = 0
    private var pendingEntries: [LogcatEntry] = []
    private var streamRevision: UInt64 = 0

    init(
        api: any LogcatAPI = APIClient(),
        sleep: @escaping Sleep = { duration in
            try await Task.sleep(for: duration)
        }
    ) {
        self.api = api
        self.sleep = sleep
    }

    deinit {
        pollingTask?.cancel()
    }

    var presentedEntries: [LogcatEntry] {
        LogcatPresentation.coalesced(entries)
    }

    var filteredEntries: [LogcatEntry] {
        let query = searchText.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return presentedEntries.filter { entry in
            guard Self.rank(for: entry.level) >= minimumLevel.rank else {
                return false
            }
            guard !query.isEmpty else {
                return true
            }
            return [
                entry.timestamp,
                entry.level,
                entry.tag,
                entry.message,
                entry.raw,
                entry.pid.map(String.init) ?? "",
                entry.tid.map(String.init) ?? ""
            ].contains { $0.lowercased().contains(query) }
        }
    }

    var isPolling: Bool {
        pollingTask != nil
    }

    var pollDelay: Duration {
        isPaused ? .seconds(5) : .milliseconds(750)
    }

    func configure(
        deviceID: String?,
        packageName: String?,
        deviceKind: AndroidDeviceKind = .emulator
    ) async {
        guard let deviceID, !deviceID.isEmpty else {
            await stopCurrentStream()
            state = "offline"
            message = AppCopy.Log.deviceOffline
            lastIssue = nil
            return
        }

        let selectedPackage = source == .app ? (packageName ?? "") : ""
        guard source != .app || !selectedPackage.isEmpty else {
            await stopCurrentStream()
            state = "waiting_app"
            message = AppCopy.Log.waitingForApp
            lastIssue = nil
            return
        }

        let requestedStream = StreamKey(
            deviceID: deviceID,
            source: source,
            packageName: selectedPackage,
            deviceKind: deviceKind
        )
        if currentStream == requestedStream, isPolling {
            return
        }

        await stopCurrentStream()
        resetForNewStream()

        do {
            let response = try await api.startLogcat(
                deviceID: deviceID,
                source: source,
                packageName: selectedPackage
            )
            currentStream = requestedStream
            apply(response, buffering: false)
            if await pollOnce() {
                startPolling()
            }
        } catch {
            currentStream = nil
            state = "error"
            lastIssue = issue(from: error)
            message = connectionMessage(for: lastIssue)
        }
    }

    @discardableResult
    func pollOnce() async -> Bool {
        guard let currentStream else {
            return false
        }
        let requestedRevision = streamRevision
        do {
            let response = try await api.pollLogcat(
                deviceID: currentStream.deviceID,
                after: cursor,
                limit: 500
            )
            guard streamRevision == requestedRevision,
                  self.currentStream == currentStream else {
                return false
            }
            apply(response, buffering: isPaused)
            if response.state == "error" {
                cancelPolling()
                let disconnectedMessage = currentStream.deviceKind == .physical
                    ? AppCopy.Log.physicalOffline
                    : AppCopy.Log.disconnected
                lastIssue = UserFacingIssue(
                    code: currentStream.deviceKind == .physical
                        ? "physical_device_offline"
                        : "log_connection_failed",
                    title: "日志连接中断",
                    message: disconnectedMessage,
                    recoveryAction: currentStream.deviceKind == .physical
                        ? "请检查 USB 或无线调试连接，然后刷新设备。"
                        : nil
                )
                message = disconnectedMessage
                return false
            }
            if response.state == "stopped" {
                cancelPolling()
                return false
            }
            return true
        } catch {
            guard streamRevision == requestedRevision,
                  self.currentStream == currentStream else {
                return false
            }
            cancelPolling()
            state = "error"
            lastIssue = issue(from: error)
            message = connectionMessage(for: lastIssue)
            return false
        }
    }

    func pause() {
        isPaused = true
        message = "日志显示已暂停，后台每 5 秒继续同步。"
    }

    func resume() {
        isPaused = false
        appendVisible(pendingEntries)
        pendingEntries.removeAll(keepingCapacity: true)
        message = stateMessage(for: state)
    }

    func clear() async {
        guard let currentStream else {
            entries = []
            pendingEntries = []
            return
        }
        let shouldResumePolling = isPolling
        streamRevision &+= 1
        let clearRevision = streamRevision
        cancelPolling()
        do {
            let response = try await api.clearLogcat(deviceID: currentStream.deviceID)
            guard streamRevision == clearRevision,
                  self.currentStream == currentStream else {
                return
            }
            entries = []
            pendingEntries = []
            cursor = response.nextCursor
            truncated = false
            state = response.state
            message = "日志已清空，新的日志仍会实时显示。"
            if shouldResumePolling {
                startPolling()
            }
        } catch {
            guard streamRevision == clearRevision,
                  self.currentStream == currentStream else {
                return
            }
            state = "error"
            lastIssue = issue(from: error)
            message = connectionMessage(for: lastIssue)
            if shouldResumePolling {
                startPolling()
            }
        }
    }

    func stop() async {
        streamRevision &+= 1
        cancelPolling()
        guard let stream = currentStream else {
            state = "stopped"
            message = "日志读取已停止。"
            return
        }
        currentStream = nil
        do {
            let response = try await api.stopLogcat(deviceID: stream.deviceID)
            cursor = response.nextCursor
            state = response.state
            message = "日志读取已停止。"
        } catch {
            state = "error"
            lastIssue = issue(from: error)
            message = AppCopy.Log.disconnected
        }
    }

    func reportConnectionFailure(_ error: Error) async {
        await stopCurrentStream()
        state = "error"
        lastIssue = issue(from: error)
        message = connectionMessage(for: lastIssue)
    }

    func reportDeviceOffline(kind: AndroidDeviceKind) async {
        await stopCurrentStream()
        state = "offline"
        lastIssue = nil
        message = kind == .physical ? AppCopy.Log.physicalOffline : AppCopy.Log.deviceOffline
    }

    func reportDeviceLocked() async {
        await stopCurrentStream()
        state = "device_locked"
        lastIssue = nil
        message = AppCopy.Log.deviceLocked
    }

    func cancelPolling() {
        pollingTask?.cancel()
        pollingTask = nil
    }

    private func startPolling() {
        cancelPolling()
        pollingTask = Task { [weak self] in
            await self?.runPollingLoop()
        }
    }

    private func runPollingLoop() async {
        while !Task.isCancelled {
            do {
                try await sleep(pollDelay)
            } catch {
                break
            }
            guard !Task.isCancelled else {
                break
            }
            if !(await pollOnce()) {
                break
            }
        }
    }

    private func stopCurrentStream() async {
        streamRevision &+= 1
        cancelPolling()
        guard let stream = currentStream else {
            return
        }
        currentStream = nil
        _ = try? await api.stopLogcat(deviceID: stream.deviceID)
    }

    private func resetForNewStream() {
        entries = []
        pendingEntries = []
        cursor = 0
        truncated = false
        state = "starting"
        lastIssue = nil
        message = "正在连接日志…"
    }

    private func apply(_ response: LogcatActionResponse, buffering: Bool) {
        cursor = max(cursor, response.nextCursor)
        truncated = response.truncated
        state = response.state
        if buffering {
            appendPending(response.entries)
        } else {
            appendVisible(response.entries)
        }
        if !isPaused {
            message = stateMessage(for: response.state)
        }
    }

    private func appendVisible(_ newEntries: [LogcatEntry]) {
        entries = merged(entries, with: newEntries, limit: maximumEntryCount)
    }

    private func appendPending(_ newEntries: [LogcatEntry]) {
        let available = max(0, maximumEntryCount - entries.count)
        pendingEntries = merged(pendingEntries, with: newEntries, limit: available)
    }

    private func merged(
        _ existing: [LogcatEntry],
        with additions: [LogcatEntry],
        limit: Int
    ) -> [LogcatEntry] {
        guard limit > 0 else {
            return []
        }
        var byCursor = Dictionary(uniqueKeysWithValues: existing.map { ($0.cursor, $0) })
        for entry in additions {
            byCursor[entry.cursor] = entry
        }
        return Array(byCursor.values.sorted { $0.cursor < $1.cursor }.suffix(limit))
    }

    private func stateMessage(for state: String) -> String {
        switch state {
        case "streaming":
            "日志已连接，正在实时读取。"
        case "waiting_app":
            AppCopy.Log.waitingForApp
        case "starting":
            "正在连接日志…"
        case "stopped":
            "日志读取已停止。"
        case "error":
            AppCopy.Log.disconnected
        default:
            "日志状态：\(state)"
        }
    }

    private func issue(from error: Error) -> UserFacingIssue {
        if let apiError = error as? APIClientError {
            return apiError.userFacingIssue
        }
        return UserFacingIssue(
            code: "log_connection_failed",
            title: "日志连接中断",
            message: AppCopy.Log.disconnected,
            technicalDetail: error.localizedDescription
        )
    }

    private func connectionMessage(for issue: UserFacingIssue?) -> String {
        switch issue?.code {
        case "physical_device_unauthorized", "physical_device_offline":
            issue?.message ?? AppCopy.Log.disconnected
        default:
            AppCopy.Log.disconnected
        }
    }

    private static func rank(for level: String) -> Int {
        switch level.uppercased() {
        case "V":
            0
        case "D":
            1
        case "I":
            2
        case "W":
            3
        case "E":
            4
        case "F":
            5
        default:
            0
        }
    }
}

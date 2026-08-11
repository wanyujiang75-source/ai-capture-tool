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
            "Verbose 及以上"
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
    @Published private(set) var message = "请选择在线设备和应用。"

    private struct StreamKey: Equatable {
        let deviceID: String
        let source: LogcatSource
        let packageName: String
    }

    private let api: any LogcatAPI
    private let sleep: Sleep
    private let maximumEntryCount = 5_000
    private var pollingTask: Task<Void, Never>?
    private var currentStream: StreamKey?
    private var cursor: Int64 = 0
    private var pendingEntries: [LogcatEntry] = []

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

    var filteredEntries: [LogcatEntry] {
        let query = searchText.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return entries.filter { entry in
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

    func configure(deviceID: String?, packageName: String?) async {
        guard let deviceID, !deviceID.isEmpty else {
            cancelPolling()
            state = "offline"
            message = "请选择一台在线模拟器。"
            return
        }

        let selectedPackage = source == .app ? (packageName ?? "") : ""
        guard source != .app || !selectedPackage.isEmpty else {
            cancelPolling()
            state = "waiting_app"
            message = "请选择要读取日志的应用。"
            return
        }

        let requestedStream = StreamKey(
            deviceID: deviceID,
            source: source,
            packageName: selectedPackage
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
            await pollOnce()
            startPolling()
        } catch {
            currentStream = nil
            state = "error"
            message = error.localizedDescription
        }
    }

    func pollOnce() async {
        guard let currentStream else {
            return
        }
        do {
            let response = try await api.pollLogcat(
                deviceID: currentStream.deviceID,
                after: cursor,
                limit: 500
            )
            apply(response, buffering: isPaused)
        } catch {
            state = "error"
            message = error.localizedDescription
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
        do {
            let response = try await api.clearLogcat(deviceID: currentStream.deviceID)
            entries = []
            pendingEntries = []
            cursor = response.nextCursor
            truncated = false
            state = response.state
            message = "日志已清空，新的日志仍会实时显示。"
        } catch {
            state = "error"
            message = error.localizedDescription
        }
    }

    func stop() async {
        cancelPolling()
        guard let stream = currentStream else {
            state = "stopped"
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
            message = error.localizedDescription
        }
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
            await pollOnce()
        }
    }

    private func stopCurrentStream() async {
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
        message = "正在连接 Android Logcat..."
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
            "应用尚未运行；打开目标应用后会自动连接。"
        case "starting":
            "正在连接 Android Logcat..."
        case "stopped":
            "日志读取已停止。"
        case "error":
            "日志读取异常，请检查设备连接。"
        default:
            "日志状态：\(state)"
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

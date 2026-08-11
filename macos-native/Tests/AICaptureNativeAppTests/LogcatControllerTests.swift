import Foundation
import Testing
@testable import AICaptureNativeApp

private actor FakeLogcatAPI: LogcatAPI {
    enum Call: Equatable, Sendable {
        case start(deviceID: String, source: LogcatSource, packageName: String)
        case poll(deviceID: String, after: Int64, limit: Int)
        case clear(deviceID: String)
        case stop(deviceID: String)
    }

    private(set) var calls: [Call] = []
    private var startResponses: [LogcatActionResponse] = []
    private var pollResponses: [LogcatPollResponse] = []
    private var clearResponses: [LogcatActionResponse] = []
    private var stopResponses: [LogcatActionResponse] = []

    func enqueueStart(_ response: LogcatActionResponse) {
        startResponses.append(response)
    }

    func enqueuePoll(_ response: LogcatPollResponse) {
        pollResponses.append(response)
    }

    func enqueueClear(_ response: LogcatActionResponse) {
        clearResponses.append(response)
    }

    func enqueueStop(_ response: LogcatActionResponse) {
        stopResponses.append(response)
    }

    func startLogcat(
        deviceID: String,
        source: LogcatSource,
        packageName: String
    ) async throws -> LogcatActionResponse {
        calls.append(.start(deviceID: deviceID, source: source, packageName: packageName))
        return startResponses.isEmpty
            ? makeLogcatResponse(source: source, packageName: packageName)
            : startResponses.removeFirst()
    }

    func pollLogcat(deviceID: String, after: Int64, limit: Int) async throws -> LogcatPollResponse {
        calls.append(.poll(deviceID: deviceID, after: after, limit: limit))
        return pollResponses.isEmpty
            ? makeLogcatResponse(nextCursor: after)
            : pollResponses.removeFirst()
    }

    func clearLogcat(deviceID: String) async throws -> LogcatActionResponse {
        calls.append(.clear(deviceID: deviceID))
        return clearResponses.isEmpty
            ? makeLogcatResponse()
            : clearResponses.removeFirst()
    }

    func stopLogcat(deviceID: String) async throws -> LogcatActionResponse {
        calls.append(.stop(deviceID: deviceID))
        return stopResponses.isEmpty
            ? makeLogcatResponse(state: "stopped")
            : stopResponses.removeFirst()
    }
}

@Suite(.serialized)
@MainActor
struct LogcatControllerTests {
    @Test
    func configureStartsAppLogsAndImmediatelyPolls() async throws {
        let fake = FakeLogcatAPI()
        await fake.enqueueStart(makeLogcatResponse(source: .app, packageName: "com.example.app"))
        await fake.enqueuePoll(makeLogcatResponse(nextCursor: 1, entries: [entry(cursor: 1)]))
        let controller = makeController(api: fake)

        await controller.configure(deviceID: "device-1", packageName: "com.example.app")

        #expect(await fake.calls == [
            .start(deviceID: "device-1", source: .app, packageName: "com.example.app"),
            .poll(deviceID: "device-1", after: 0, limit: 500)
        ])
        #expect(controller.entries == [entry(cursor: 1)])
        #expect(controller.isPolling)
        controller.cancelPolling()
    }

    @Test
    func changingSourceStopsPreviousStreamBeforeStartingNext() async {
        let fake = FakeLogcatAPI()
        let controller = makeController(api: fake)
        await controller.configure(deviceID: "device-1", packageName: "com.example.app")

        controller.source = .system
        await controller.configure(deviceID: "device-1", packageName: "com.example.app")

        #expect(await fake.calls == [
            .start(deviceID: "device-1", source: .app, packageName: "com.example.app"),
            .poll(deviceID: "device-1", after: 0, limit: 500),
            .stop(deviceID: "device-1"),
            .start(deviceID: "device-1", source: .system, packageName: ""),
            .poll(deviceID: "device-1", after: 0, limit: 500)
        ])
        controller.cancelPolling()
    }

    @Test
    func pauseBuffersHeartbeatEntriesUntilResume() async {
        let fake = FakeLogcatAPI()
        let controller = makeController(api: fake)
        await controller.configure(deviceID: "device-1", packageName: "com.example.app")
        controller.pause()
        await fake.enqueuePoll(makeLogcatResponse(nextCursor: 2, entries: [entry(cursor: 2)]))

        await controller.pollOnce()

        #expect(controller.entries.isEmpty)
        #expect(controller.pollDelay == .seconds(5))
        controller.resume()
        #expect(controller.entries == [entry(cursor: 2)])
        #expect(controller.pollDelay == .milliseconds(750))
        controller.cancelPolling()
    }

    @Test
    func clearRemovesEntriesAndUsesReturnedCursorForNextPoll() async {
        let fake = FakeLogcatAPI()
        await fake.enqueuePoll(makeLogcatResponse(nextCursor: 4, entries: [entry(cursor: 4)]))
        let controller = makeController(api: fake)
        await controller.configure(deviceID: "device-1", packageName: "com.example.app")
        await fake.enqueueClear(makeLogcatResponse(nextCursor: 9))

        await controller.clear()
        await controller.pollOnce()

        #expect(controller.entries.isEmpty)
        #expect(await fake.calls.suffix(2) == [
            .clear(deviceID: "device-1"),
            .poll(deviceID: "device-1", after: 9, limit: 500)
        ])
        controller.cancelPolling()
    }

    @Test
    func minimumLevelAndSearchFilterVisibleEntries() async {
        let fake = FakeLogcatAPI()
        await fake.enqueuePoll(
            makeLogcatResponse(
                nextCursor: 3,
                entries: [
                    entry(cursor: 1, level: "I", tag: "Flutter", message: "ordinary line"),
                    entry(cursor: 2, level: "W", tag: "Network", message: "needle timeout"),
                    entry(cursor: 3, level: "E", tag: "Database", message: "other failure")
                ]
            )
        )
        let controller = makeController(api: fake)
        await controller.configure(deviceID: "device-1", packageName: "com.example.app")

        controller.minimumLevel = .warning
        controller.searchText = "needle"

        #expect(controller.filteredEntries == [
            entry(cursor: 2, level: "W", tag: "Network", message: "needle timeout")
        ])
        controller.cancelPolling()
    }

    @Test
    func stopCancelsPollingAndStopsBackendStream() async {
        let fake = FakeLogcatAPI()
        let controller = makeController(api: fake)
        await controller.configure(deviceID: "device-1", packageName: "com.example.app")

        await controller.stop()

        #expect(!controller.isPolling)
        #expect(controller.state == "stopped")
        #expect(await fake.calls.last == .stop(deviceID: "device-1"))
    }

    private func makeController(api: FakeLogcatAPI) -> LogcatController {
        LogcatController(
            api: api,
            sleep: { _ in
                try await Task.sleep(for: .seconds(60))
            }
        )
    }
}

private func entry(
    cursor: Int64,
    level: String = "I",
    tag: String = "Flutter",
    message: String = "line"
) -> LogcatEntry {
    LogcatEntry(
        cursor: cursor,
        timestamp: "08-11 14:22:03.456",
        pid: 1234,
        tid: 1235,
        level: level,
        tag: tag,
        message: message,
        raw: ""
    )
}

private func makeLogcatResponse(
    source: LogcatSource = .app,
    state: String = "streaming",
    packageName: String = "com.example.app",
    nextCursor: Int64 = 0,
    truncated: Bool = false,
    entries: [LogcatEntry] = []
) -> LogcatActionResponse {
    let entryJSON = entries.map { entry in
        """
        {
          "cursor": \(entry.cursor),
          "timestamp": \(jsonString(entry.timestamp)),
          "pid": \(entry.pid.map(String.init) ?? "null"),
          "tid": \(entry.tid.map(String.init) ?? "null"),
          "level": \(jsonString(entry.level)),
          "tag": \(jsonString(entry.tag)),
          "message": \(jsonString(entry.message)),
          "raw": \(jsonString(entry.raw))
        }
        """
    }.joined(separator: ",")
    let data = Data(
        """
        {
          "device_id": "device-1",
          "source": "\(source.rawValue)",
          "state": "\(state)",
          "package_name": "\(packageName)",
          "next_cursor": \(nextCursor),
          "truncated": \(truncated),
          "entries": [\(entryJSON)]
        }
        """.utf8
    )
    return try! JSONDecoder().decode(LogcatActionResponse.self, from: data)
}

private func jsonString(_ value: String) -> String {
    let data = try! JSONEncoder().encode(value)
    return String(decoding: data, as: UTF8.self)
}

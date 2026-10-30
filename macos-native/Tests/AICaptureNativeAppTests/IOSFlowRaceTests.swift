import Foundation
import Testing
@testable import AICaptureNativeApp

private actor PagedFlowRaceAPI: FlowAPI {
    var continuation: CheckedContinuation<FlowPage, any Error>?
    var waiter: CheckedContinuation<Void, Never>?
    func getCaptureSources() async throws -> [CaptureSource] {
        [CaptureSource(id: 12, platform: "ios", status: "running", appName: "Test", mode: "ios-http-proxy")]
    }
    func getFlows(sessionID: Int) async throws -> [FlowSummary] { [] }
    func getFlowPage(sessionID: Int, cursor: Int) async throws -> FlowPage {
        if cursor == 0 {
            return FlowPage(flows: [try flow("before-clear")], total: 3, cursor: 1, nextCursor: 1)
        }
        if cursor == 1 {
            return try await withCheckedThrowingContinuation {
                continuation = $0
                waiter?.resume(); waiter = nil
            }
        }
        return FlowPage(flows: [try flow("before-clear", status: "200")], total: 3, cursor: 3, nextCursor: nil)
    }
    func getFlowDetail(sessionID: Int, flowID: String) async throws -> FlowDetail { throw APIClientError.invalidResponse }
    func getFlowCurl(sessionID: Int, flowID: String) async throws -> String { "" }
    func waitForSecondPage() async {
        if continuation != nil { return }
        await withCheckedContinuation { waiter = $0 }
    }
    func completePage() throws {
        continuation?.resume(returning: FlowPage(flows: [try flow("new")], total: 3, cursor: 2, nextCursor: nil))
        continuation = nil
    }
    private func flow(_ id: String, status: String = "NO_RESPONSE") throws -> FlowSummary {
        try JSONDecoder().decode(FlowSummary.self, from: Data("{\"id\":\"\(id)\",\"status\":\"\(status)\"}".utf8))
    }
}

@MainActor
struct IOSFlowRaceTests {
    @Test func clearBoundaryRejectsUnfetchedOldRequestsButKeepsNewOnes() throws {
        let boundary = Date(timeIntervalSince1970: 1_700_000_000)
        func flow(_ stamp: String) throws -> FlowSummary {
            try JSONDecoder().decode(FlowSummary.self, from: Data("{\"id\":\"same-id\",\"time\":\"\(stamp)\"}".utf8))
        }
        #expect(IOSFlowBoundary.predates(try flow("2023-11-14T22:13:19.999999+00:00"), boundary: boundary))
        #expect(!IOSFlowBoundary.predates(try flow("2023-11-14T22:13:20.100000+00:00"), boundary: boundary))
        #expect(IOSFlowBoundary.predates(try flow("2023-11-14T22:13:19Z"), boundary: boundary))
        let fractionalBoundary = Date(timeIntervalSince1970: 1_700_000_000.123500)
        #expect(!IOSFlowBoundary.predates(try flow("2023-11-14T22:13:20.123900+00:00"), boundary: fractionalBoundary))
        #expect(IOSFlowBoundary.predates(try flow("2023-11-14T22:13:20.123100Z"), boundary: fractionalBoundary))
        #expect(!IOSFlowBoundary.predates(try flow("2023-11-15T06:13:20.123900+08:00"), boundary: fractionalBoundary))
    }

    @Test func clearSuppressesFetchedButUncommittedBatchAndItsLaterResponse() async throws {
        let api = PagedFlowRaceAPI()
        let state = AppState(flowAPI: api)
        await state.refreshFlowSources()
        state.selectFlowSource(12)
        let poll = Task { await state.refreshFlows() }
        await api.waitForSecondPage()
        state.clearCurrentFlows()
        try await api.completePage()
        await poll.value
        #expect(state.visibleFlows.map(\.id) == ["new"])
        await state.refreshFlows()
        #expect(state.visibleFlows.map(\.id) == ["new"])
    }

    @Test func switchingSourceRejectsWholePendingBatchAndDoesNotAdvanceNewCursor() async throws {
        let api = PagedFlowRaceAPI()
        let state = AppState(flowAPI: api)
        state.activeSessionID = 4
        await state.refreshFlowSources()
        state.selectFlowSource(12)
        let poll = Task { await state.refreshFlows() }
        await api.waitForSecondPage()
        state.selectFlowSource(nil)
        try await api.completePage()
        await poll.value
        #expect(state.flowSessionID == 4)
        #expect(state.flows.isEmpty)
    }
}

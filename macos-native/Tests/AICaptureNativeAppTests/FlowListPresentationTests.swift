import Foundation
import Testing
@testable import AICaptureNativeApp

private actor FlowAPISpy: FlowAPI {
    private var flows: [FlowSummary]

    init(flows: [FlowSummary]) {
        self.flows = flows
    }

    func getFlows(sessionID: Int) async throws -> [FlowSummary] {
        flows
    }

    func getFlowDetail(sessionID: Int, flowID: String) async throws -> FlowDetail {
        throw FlowAPISpyError.unexpectedDetailRequest
    }

    func getFlowCurl(sessionID: Int, flowID: String) async throws -> String {
        throw FlowAPISpyError.unexpectedCurlRequest
    }

    func setFlows(_ flows: [FlowSummary]) {
        self.flows = flows
    }
}

private enum FlowAPISpyError: Error {
    case unexpectedDetailRequest
    case unexpectedCurlRequest
}

private actor DelayedFlowAPI: FlowAPI {
    private var flowContinuation: CheckedContinuation<[FlowSummary], any Error>?
    private var flowStartWaiter: CheckedContinuation<Void, Never>?
    private var detailContinuation: CheckedContinuation<FlowDetail, any Error>?
    private var detailStartWaiter: CheckedContinuation<Void, Never>?

    func getFlows(sessionID: Int) async throws -> [FlowSummary] {
        try await withCheckedThrowingContinuation { continuation in
            flowContinuation = continuation
            flowStartWaiter?.resume()
            flowStartWaiter = nil
        }
    }

    func getFlowDetail(sessionID: Int, flowID: String) async throws -> FlowDetail {
        try await withCheckedThrowingContinuation { continuation in
            detailContinuation = continuation
            detailStartWaiter?.resume()
            detailStartWaiter = nil
        }
    }

    func getFlowCurl(sessionID: Int, flowID: String) async throws -> String {
        "curl https://api.example.test/delayed"
    }

    func waitForFlowRequest() async {
        guard flowContinuation == nil else {
            return
        }
        await withCheckedContinuation { continuation in
            flowStartWaiter = continuation
        }
    }

    func waitForDetailRequest() async {
        guard detailContinuation == nil else {
            return
        }
        await withCheckedContinuation { continuation in
            detailStartWaiter = continuation
        }
    }

    func completeFlowRequest(with flows: [FlowSummary]) {
        flowContinuation?.resume(returning: flows)
        flowContinuation = nil
    }

    func completeDetailRequest(with detail: FlowDetail) {
        detailContinuation?.resume(returning: detail)
        detailContinuation = nil
    }
}

@MainActor
struct FlowListPresentationTests {
    @Test
    func searchMatchesEndpointAndRequestMetadataCaseInsensitively() throws {
        let flows = try makeFlows()

        #expect(FlowListPresentation.filtered(flows, query: "PROFILE?USER=42").map(\.id) == ["flow-1"])
        #expect(FlowListPresentation.filtered(flows, query: "api.example.test").map(\.id) == ["flow-1"])
        #expect(FlowListPresentation.filtered(flows, query: "POST").map(\.id) == ["flow-2"])
        #expect(FlowListPresentation.filtered(flows, query: "404").map(\.id) == ["flow-2"])
        #expect(FlowListPresentation.filtered(flows, query: "  ").map(\.id) == flows.map(\.id))
    }

    @Test
    func endpointPrefersCompleteURLAndFallsBackToPath() throws {
        let flows = try makeFlows()

        #expect(FlowListPresentation.endpoint(for: flows[0]) == "https://api.example.test/rest/v1/profile?user=42")
        #expect(FlowListPresentation.endpoint(for: flows[1]) == "auth.example.test/v1/session")
    }

    @Test
    func refreshingFlowsClearsDetailsThatNoLongerExist() async throws {
        let oldFlows = try makeFlows()
        let state = AppState(flowAPI: FlowAPISpy(flows: []))
        state.activeSessionID = 22
        state.flows = oldFlows
        state.selectedFlowID = oldFlows[0].id
        state.selectedFlowDetail = try makeFlowDetail(id: oldFlows[0].id)
        state.selectedFlowCurl = "curl https://api.example.test/rest/v1/profile"

        await state.refreshFlows()

        #expect(state.flows.isEmpty)
        #expect(state.selectedFlowID == nil)
        #expect(state.selectedFlowDetail == nil)
        #expect(state.selectedFlowCurl.isEmpty)
        #expect(state.flowDetailLoadState == .idle)
    }

    @Test
    func loadingAnotherFlowNeverLeavesThePreviousDetailBehind() async throws {
        let flows = try makeFlows()
        let state = AppState(flowAPI: FlowAPISpy(flows: flows))
        state.activeSessionID = 22
        state.selectedFlowID = flows[0].id
        state.selectedFlowDetail = try makeFlowDetail(id: flows[0].id)
        state.selectedFlowCurl = "curl https://api.example.test/rest/v1/profile"

        await state.loadFlowDetail(flows[1])

        #expect(state.selectedFlowID == flows[1].id)
        #expect(state.selectedFlowDetail == nil)
        #expect(state.selectedFlowCurl.isEmpty)
        guard case .failed = state.flowDetailLoadState else {
            Issue.record("详情请求失败时应展示失败状态")
            return
        }
    }

    @Test
    func clearingCurrentFlowsKeepsPollingAndShowsOnlyNewFlows() async throws {
        let currentFlows = try makeFlows()
        let api = FlowAPISpy(flows: currentFlows)
        let state = AppState(flowAPI: api)
        state.activeSessionID = 22
        state.flows = currentFlows
        state.selectedFlowID = currentFlows[0].id
        state.selectedFlowDetail = try makeFlowDetail(id: currentFlows[0].id)
        state.selectedFlowCurl = "curl https://api.example.test/rest/v1/profile"

        state.clearCurrentFlows()

        #expect(state.visibleFlows.isEmpty)
        #expect(state.selectedFlowID == nil)
        #expect(state.selectedFlowDetail == nil)
        #expect(state.selectedFlowCurl.isEmpty)

        let newFlow = try makeFlow(id: "flow-3", path: "/v1/new-request")
        await api.setFlows(currentFlows + [newFlow])
        await state.refreshFlows()

        #expect(state.visibleFlows.map(\.id) == ["flow-3"])
        #expect(state.activeSessionID == 22)
    }

    @Test
    func staleFlowRefreshCannotOverwriteAnotherSession() async throws {
        let oldFlows = try makeFlows()
        let api = DelayedFlowAPI()
        let state = AppState(flowAPI: api)
        state.activeSessionID = 22

        let refreshTask = Task {
            await state.refreshFlows()
        }
        await api.waitForFlowRequest()
        state.activeSessionID = 23
        state.flows = []
        await api.completeFlowRequest(with: oldFlows)
        await refreshTask.value

        #expect(state.activeSessionID == 23)
        #expect(state.flows.isEmpty)
    }

    @Test
    func clearingWhileDetailLoadsCannotRestoreClearedDetail() async throws {
        let flow = try makeFlow(id: "flow-delayed", path: "/v1/delayed")
        let detail = try makeFlowDetail(id: flow.id)
        let api = DelayedFlowAPI()
        let state = AppState(flowAPI: api)
        state.activeSessionID = 22
        state.flows = [flow]

        let detailTask = Task {
            await state.loadFlowDetail(flow)
        }
        await api.waitForDetailRequest()
        state.clearCurrentFlows()
        await api.completeDetailRequest(with: detail)
        await detailTask.value

        #expect(state.selectedFlowID == nil)
        #expect(state.selectedFlowDetail == nil)
        #expect(state.selectedFlowCurl.isEmpty)
        #expect(state.flowDetailLoadState == .idle)
    }

    @Test
    func stoppingCaptureResetsClearedFlowBaseline() throws {
        let flows = try makeFlows()
        let state = AppState(flowAPI: FlowAPISpy(flows: flows))
        state.activeSessionID = 22
        state.flows = flows
        state.clearCurrentFlows()

        #expect(state.hasClearedFlows)

        state.didStopCapture()

        #expect(state.activeSessionID == nil)
        #expect(state.flows.isEmpty)
        #expect(state.clearedFlowIDs.isEmpty)
        #expect(state.flowLoadState == .idle)
        #expect(state.flowDetailLoadState == .idle)
    }

    private func makeFlows() throws -> [FlowSummary] {
        try JSONDecoder().decode(
            [FlowSummary].self,
            from: Data(
                """
                [
                  {
                    "id": "flow-1",
                    "method": "GET",
                    "status": "200",
                    "host": "api.example.test",
                    "path": "/rest/v1/profile?user=42",
                    "url": "https://api.example.test/rest/v1/profile?user=42"
                  },
                  {
                    "id": "flow-2",
                    "method": "POST",
                    "status": "404",
                    "host": "auth.example.test",
                    "path": "/v1/session"
                  }
                ]
                """.utf8
            )
        )
    }

    private func makeFlowDetail(id: String) throws -> FlowDetail {
        try JSONDecoder().decode(
            FlowDetail.self,
            from: Data(
                """
                {
                  "id": "\(id)",
                  "method": "GET",
                  "status": "200",
                  "url": "https://api.example.test/rest/v1/profile"
                }
                """.utf8
            )
        )
    }

    private func makeFlow(id: String, path: String) throws -> FlowSummary {
        try JSONDecoder().decode(
            FlowSummary.self,
            from: Data(
                """
                {
                  "id": "\(id)",
                  "method": "GET",
                  "status": "200",
                  "host": "api.example.test",
                  "path": "\(path)",
                  "url": "https://api.example.test\(path)"
                }
                """.utf8
            )
        )
    }
}

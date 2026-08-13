import Foundation
import Testing
@testable import AICaptureNativeApp

private actor FlowAPISpy: FlowAPI {
    let flows: [FlowSummary]

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
}

private enum FlowAPISpyError: Error {
    case unexpectedDetailRequest
    case unexpectedCurlRequest
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
}

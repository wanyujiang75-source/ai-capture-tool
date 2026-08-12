import Foundation
import Testing
@testable import AICaptureNativeApp

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
}

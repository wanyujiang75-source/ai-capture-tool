import Foundation
import Testing
@testable import AICaptureNativeApp

@MainActor
struct BreakpointLiveTests {
    @Test(.enabled(if: ProcessInfo.processInfo.environment["BP3_TEST_RUNTIME"] != nil))
    func nativeControllerThroughHTTPIPCProxyAndArchive() async throws {
        let root = URL(fileURLWithPath: ProcessInfo.processInfo.environment["BP3_TEST_RUNTIME"]!)
        struct Info: Decodable { let port: Int; let originUrl: String }
        let info = try BreakpointWire.decode(Info.self, from: Data(contentsOf: root.appendingPathComponent("fixture-info.json")))
        let base = URL(string: "http://127.0.0.1:\(info.port)")!
        let api = APIClient(baseURL: base)
        let c = BreakpointController(api: BreakpointHTTPClient(baseURL: base, directory: root), flowAPI: api)
        await c.poll()
        #expect(c.canControl)
        var rule = try BreakpointRuleSpec.seed(url: info.originUrl, method: "POST")
        rule.stage = "both"; rule.timeoutSeconds = 60
        await c.saveRule(rule, id: "swift-live", enable: true)
        #expect(c.status?.enabled == true)
        let configuration = URLSessionConfiguration.ephemeral
        configuration.connectionProxyDictionary = [:]
        let session = URLSession(configuration: configuration)
        defer { session.invalidateAndCancel() }
        var trigger = URLRequest(url: base.appendingPathComponent("__trigger")); trigger.httpMethod = "POST"
        _ = try await session.data(for: trigger)
        func paused(_ stage: String) async throws -> BreakpointPending {
            for _ in 0..<50 {
                await c.poll()
                if let item = c.pending.first(where: { $0.stage == stage && $0.state == "paused" }) { return item }
                try await Task.sleep(for: .milliseconds(100))
            }
            throw BreakpointFailure("missing_pending")
        }
        let request = try await paused("request")
        await c.select(request.id)
        #expect(c.canEdit)
        c.draft?.body = "{\"native_request\":true}"
        await c.resolve("apply")
        #expect(c.issue == nil)
        let response = try await paused("response")
        await c.select(response.id)
        c.draft?.status = "201"
        c.draft?.body = "{\"native_response\":true}"
        await c.resolve("apply")
        #expect(c.issue == nil)
        for _ in 0..<50 {
            await c.poll()
            if c.pending.isEmpty { break }
            try await Task.sleep(for: .milliseconds(100))
        }
        let detail = try await api.getFlowDetail(sessionID: 1, flowID: request.flowId)
        #expect(detail.requestText == "{\"native_request\":true}")
        #expect(detail.responseText == "{\"native_response\":true}")
        #expect(detail.status == "201")
        #expect(detail.breakpoints?["request"]?.original.bodyText == "{\"original\":1}")
        #expect(detail.breakpoints?["response"]?.effective.bodyText == "{\"native_response\":true}")
        let (data, _) = try await session.data(from: base.appendingPathComponent("__results"))
        let evidence = String(decoding: data, as: UTF8.self)
        #expect(evidence.contains("native_request") && evidence.contains("native_response"))
        await c.releaseAll()
        #expect(c.status?.enabled == false && c.pending.isEmpty)
    }
}

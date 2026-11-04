import Foundation
import Testing
@testable import AICaptureNativeApp

private actor BPFixture: BreakpointAPI, FlowAPI {
    var enabled = false
    var fail = false
    var requests: [String] = []
    var decisions: [Data] = []
    var ruleBodies: [Data] = []
    var rows = true
    var paused = true
    var delay = false
    var continuation: CheckedContinuation<Void, Never>?
    var inFlight = 1
    var sourceCalls = 0
    var holdStatus = false
    var statusWait: CheckedContinuation<Void, Never>?
    let target = BreakpointTarget(captureId: "1", deviceId: "test-device", epoch: "test-epoch")
    func setFail(_ value: Bool) { fail = value }
    func end() { rows = false; inFlight = 0 }
    func delayStatus() { holdStatus = true }
    func waitForStatus() async { while statusWait == nil { await Task.yield() } }
    func finishStatus() { statusWait?.resume(); statusWait = nil }
    func collectingOnly() { rows = false; inFlight = 1 }
    func delayDetail() { delay = true }
    func waitForDetail() async { while continuation == nil { await Task.yield() } }
    func finishDetail() { continuation?.resume(); continuation = nil }
    func context(captureID: Int) async throws -> BreakpointTarget { target }
    func call(_ target: BreakpointTarget, path: String, method: String, body: Data?) async throws -> Data {
        requests.append(path)
        if fail { throw BreakpointFailure("private-secret-not-for-ui") }
        if path == "/disable" || path == "/release-all" { enabled = false; return Data("{}".utf8) }
        if path == "/enable" { enabled = true; return Data("{}".utf8) }
        if path == "/heartbeat" { return Data("{}".utf8) }
        if path.contains("/resolve") { decisions.append(body!); paused = false; return Data("{}".utf8) }
        if path.hasPrefix("/rules/") { ruleBodies.append(body!); return Data("{}".utf8) }
        if path == "" {
            if holdStatus { holdStatus = false; await withCheckedContinuation { statusWait = $0 } }
            return Data("""
            {"capture_id":"1","device_id":"test-device","epoch":"test-epoch","enabled":\(enabled),"stopped":false,
            "in_flight":\(inFlight),"pending_count":\(rows ? 1 : 0),"rules":[],"transport_attached":true}
            """.utf8)
        }
        if path == "/pending" {
            return Data("{\"data\":[\(rows ? "{\"id\":\"p\",\"flow_id\":\"f\",\"stage\":\"request\",\"state\":\"\(paused ? "paused" : "applying")\",\"revision\":1,\"matched_rule\":\"r\",\"remaining_seconds\":30}" : "")],\"next_cursor\":null}".utf8)
        }
        if delay { delay = false; await withCheckedContinuation { continuation = $0 } }
        return Data("""
        {"id":"p","stage":"request","revision":1,"state":"paused","original":{"url":"https://example.test/",
        "method":"POST","headers":[["content-type","application/json"]],"body_base64":"e30=","status":null,"editable_body":true}}
        """.utf8)
    }
    func getCaptureSources() async throws -> [CaptureSource] {
        sourceCalls += 1
        return [.init(id: 1, platform: "ios", status: "running", appName: "Fixture", mode: "ios-http-proxy")]
    }
    func getFlows(sessionID: Int) async throws -> [FlowSummary] { [] }
    func getFlowDetail(sessionID: Int, flowID: String) async throws -> FlowDetail { fatalError("not used") }
    func getFlowCurl(sessionID: Int, flowID: String) async throws -> String { "" }
}

@MainActor
struct BreakpointControllerTests {
    @Test func newlyEnabledCannotRebindBeforeStatusReturns() async {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await api.end(); await c.poll(); await api.delayStatus()
        let polling = Task { await c.poll() }
        await api.waitForStatus(); await c.setEnabled(true)
        let before = await api.requests.filter { $0 == "/disable" }.count
        await c.bind(2)
        #expect(await api.requests.filter { $0 == "/disable" }.count == before)
        await api.finishStatus(); await polling.value
    }
    @Test func saveAndEnableAlsoEnablesDisabledTemplate() async throws {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await c.poll()
        var rule = try BreakpointRuleSpec.seed(url: "https://example.test/", method: "GET")
        rule.enabled = false
        await c.saveRule(rule, enable: true)
        struct Payload: Decodable { let rule: BreakpointRuleSpec }
        let actual = try BreakpointWire.decode(Payload.self, from: await api.ruleBodies[0])
        #expect(actual.rule.enabled)
    }
    @Test func bindDoesNotEnableAndHeartbeatDoesNotDependOnSheet() async {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await c.poll()
        #expect(c.canControl && c.status?.enabled == false)
        #expect(await api.requests.first == "/disable")
        await c.setEnabled(true)
        c.showsPanel = false
        await c.refreshLease(); await c.poll()
        #expect(await api.requests.contains("/heartbeat"))
        #expect(c.pending.count == 1)
        await c.bind(2)
        #expect(c.target?.captureId == "1")
    }
    @Test func originalNeverSubmitsDraftAndAcceptedIsNotDelivered() async {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await c.poll(); await c.select("p")
        c.draft?.body = "secret invalid JSON"
        await c.resolve("original")
        let payload = try? JSONSerialization.jsonObject(with: await api.decisions[0]) as? [String: Any]
        #expect(payload?["patch"] == nil)
        #expect(payload?["action"] as? String == "original")
        #expect((payload?["operation_id"] as? String)?.hasPrefix("p.") == true)
        #expect(c.draft == nil && !c.canEdit)
        #expect(c.selectedID == nil && c.message == BreakpointCopy.accepted)
    }
    @Test func failedDetailClearsSelectionForRetry() async {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await c.poll(); await api.setFail(true); await c.select("p")
        #expect(c.selectedID == nil && !c.loadingDetail)
        await api.setFail(false); await c.select("p")
        #expect(c.canEdit)
    }
    @Test func invalidPatchKeepsDraftWithoutSendingAndTimeoutClearsIt() async {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await c.poll(); await c.select("p")
        c.draft?.body = "{bad"
        await c.resolve("apply")
        #expect(await api.decisions.isEmpty)
        #expect(c.draft?.body == "{bad" && c.canEdit)
        await api.end(); await c.poll()
        #expect(c.draft == nil && c.detail == nil && !c.canEdit)
    }
    @Test func lateDetailCannotResurrectEndedItem() async {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await c.poll(); await api.delayDetail()
        let request = Task { await c.select("p") }
        await api.waitForDetail(); await api.end(); await c.poll(); await api.finishDetail(); await request.value
        #expect(c.detail == nil && c.draft == nil && !c.canEdit)
    }
    @Test func loadingDetailIsNotReportedAsEnded() async {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await c.poll(); await api.delayDetail()
        let load = Task { await c.select("p") }
        await api.waitForDetail(); await c.poll()
        #expect(c.loadingDetail && c.message == nil)
        await api.finishDetail(); await load.value
    }
    @Test func abortDoesNotClaimForwarding() async {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await c.poll(); await c.select("p"); await c.resolve("abort")
        #expect(c.message?.contains("终止") == true && c.message?.contains("转发") == false)
    }
    @Test func failuresDoNotLeakBackendErrorsOrClaimEnableSuccess() async {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await c.poll(); await api.setFail(true); await c.setEnabled(true)
        #expect(c.status?.enabled == false)
        #expect(!c.healthy && c.issue == BreakpointCopy.disconnected)
        #expect(c.issue?.contains("private-secret") == false)
    }
    @Test func transientFailureRecoversLeaseRenewal() async {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await c.poll(); await c.setEnabled(true)
        await api.setFail(true); await c.poll()
        let before = await api.requests.filter { $0 == "/heartbeat" }.count
        await api.setFail(false); await c.refreshLease(); await c.poll()
        #expect(await api.requests.filter { $0 == "/heartbeat" }.count > before)
        #expect(c.healthy && c.status?.enabled == true)
    }
    @Test func endedSelectionLoadingDoesNotSurviveMutation() async {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await c.poll(); await api.delayDetail()
        let load = Task { await c.select("p") }
        await api.waitForDetail(); await c.setEnabled(true); await api.finishDetail(); await load.value
        #expect(!c.loadingDetail && c.detail == nil)
    }
    @Test func cannotRebindWhileCollectingWithoutVisiblePending() async {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await c.poll(); await api.collectingOnly(); await c.poll()
        let before = await api.requests.filter { $0 == "/disable" }.count
        await c.bind(2)
        #expect(await api.requests.filter { $0 == "/disable" }.count == before)
    }
    @Test func boundPollingNeverWaitsForDiscovery() async {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await c.poll(); let calls = await api.sourceCalls
        try? await Task.sleep(for: .milliseconds(2100))
        await c.poll()
        #expect(await api.sourceCalls == calls)
    }
    @Test func heartbeatContinuesWhileStatusReadIsSuspended() async {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await c.poll(); await c.setEnabled(true); await api.delayStatus()
        let poll = Task { await c.poll() }
        await api.waitForStatus()
        await c.refreshLease(); await c.refreshLease()
        #expect(await api.requests.filter { $0 == "/heartbeat" }.count == 2)
        await api.finishStatus(); await poll.value
        #expect(c.healthy)
    }
    @Test(arguments: [false, true]) func lateDetailCannotResurrectAfterConnectionFailure(heartbeat: Bool) async {
        let api = BPFixture(); let c = BreakpointController(api: api, flowAPI: api)
        await c.poll(); await c.setEnabled(true); await api.delayDetail()
        let load = Task { await c.select("p") }
        await api.waitForDetail(); await api.setFail(true)
        if heartbeat { await c.refreshLease() } else { await c.poll() }
        await api.finishDetail(); await load.value
        #expect(c.selectedID == nil && c.detail == nil && c.draft == nil && !c.loadingDetail)
    }
}

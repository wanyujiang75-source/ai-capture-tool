import Foundation
import Testing
@testable import AICaptureNativeApp

struct FlowTrafficFilterTests {
    @Test(arguments: [
        #"{"url":"https://cdn.example.test/avatar.PNG?v=3"}"#,
        #"{"url":"https://images.example.test/photo-123?w=1080","response_content_type":"IMAGE/JPEG; charset=binary"}"#,
        #"{"path":"/assets/main.js?revision=4"}"#,
        #"{"path":"/font.woff2"}"#,
        #"{"path":"/home","response_content_type":"text/html"}"#,
        #"{"path":"/movie","response_content_type":"video/mp4"}"#,
        #"{"url":"https://app-measurement.com/a","method":"POST","request_content_type":"application/json"}"#,
        #"{"url":"https://region1.google-analytics.com/g/collect","method":"POST"}"#,
        #"{"url":"https://reports.crashlytics.com/report","method":"POST"}"#,
        #"{"url":"https://captive.apple.com/hotspot-detect.html"}"#,
        #"{"url":"https://connectivitycheck.gstatic.com/generate_204"}"#,
        #"{"url":"https://capture-check.invalid/validation"}"#,
        #"{"path":"/v1/users","method":"OPTIONS"}"#,
        #"{"path":"/tunnel","method":"CONNECT"}"#
    ])
    func hidesKnownNonInterfaceTraffic(json: String) throws {
        let flow = try makeFlow(json)
        #expect(FlowListPresentation.filtered([flow], query: "", scope: .interfaces).isEmpty)
        #expect(FlowListPresentation.filtered([flow], query: "", scope: .all).map(\.id) == [flow.id])
    }

    @Test(arguments: [
        #"{"path":"/v1/users","status":"500","response_content_type":"text/html"}"#,
        #"{"path":"/getProfile","status":"NO_RESPONSE"}"#,
        #"{"path":"/events","response_content_type":"text/event-stream"}"#,
        #"{"path":"/rpc","response_content_type":"application/grpc+proto"}"#,
        #"{"path":"/config.json"}"#,
        #"{"path":"/unknown"}"#,
        #"{"path":"/download?file=avatar.png"}"#,
        #"{"path":"/avatar.png","method":"POST","request_content_type":"multipart/form-data"}"#,
        #"{"path":"/avatar.png","has_response_json":true}"#,
        #"{"path":"/avatar.png","response_content_type":"application/problem+json"}"#,
        #"{"path":"/image","request_content_type":"application/json","response_content_type":"image/png"}"#,
        #"{"path":"/image","method":"POST","response_content_type":"image/png"}"#,
        #"{"url":"https://oauth2.googleapis.com/token","method":"POST","kind":"noise"}"#,
        #"{"url":"https://api.example.test/connectivity/adjust","kind":"noise"}"#,
        #"{"url":"https://google-analytics.com.example.test/profile"}"#,
        #"{"url":"https://notgoogle-analytics.com/profile"}"#,
        #"{"url":"https://example.test/?next=google-analytics.com/collect"}"#,
        #"{}"#
    ])
    func preservesBusinessFailuresAndUnknownTraffic(json: String) throws {
        let flow = try makeFlow(json)
        #expect(FlowListPresentation.filtered([flow], query: "", scope: .interfaces).map(\.id) == [flow.id])
    }

    @Test
    func filteringCombinesWithSearchAndRestoresOriginalOrder() throws {
        let api = try makeFlow(#"{"path":"/v1/users","method":"POST","status":"401"}"#, id: "api")
        let image = try makeFlow(#"{"path":"/users.png"}"#, id: "image")
        let pending = try makeFlow(#"{"path":"/other","status":"NO_RESPONSE"}"#, id: "pending")
        let flows = [api, image, pending]
        #expect(FlowListPresentation.filtered(flows, query: "USERS", scope: .interfaces).map(\.id) == ["api"])
        #expect(FlowListPresentation.filtered(flows, query: "401", scope: .interfaces).map(\.id) == ["api"])
        #expect(FlowListPresentation.filtered(flows, query: "", scope: .interfaces).map(\.id) == ["api", "pending"])
        #expect(FlowListPresentation.filtered(flows, query: "", scope: .all).map(\.id) == flows.map(\.id))
    }

    private func makeFlow(_ json: String, id: String = "example") throws -> FlowSummary {
        var fields = try JSONSerialization.jsonObject(with: Data(json.utf8)) as! [String: Any]
        fields["id"] = id
        if fields["method"] == nil { fields["method"] = "GET" }
        return try JSONDecoder().decode(FlowSummary.self, from: JSONSerialization.data(withJSONObject: fields))
    }
}

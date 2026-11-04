import AppKit
import Foundation
import Testing
@testable import AICaptureNativeApp

private final class BPControlProtocol: URLProtocol, @unchecked Sendable {
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        let path = request.url!.lastPathComponent
        let code = path == "redirect" ? 302 : path == "failure" ? 503 : 200
        let headers = path == "declared" ? ["Content-Length": "1048577"] :
            path == "redirect" ? ["Location": "https://must-not-be-contacted.invalid/"] : [:]
        client?.urlProtocol(self, didReceive: HTTPURLResponse(url: request.url!, statusCode: code,
            httpVersion: "HTTP/1.1", headerFields: headers)!, cacheStoragePolicy: .notAllowed)
        let bytes: Data
        if path == "chunked" { bytes = Data(repeating: 65, count: 1_048_577) }
        else {
            bytes = try! JSONSerialization.data(withJSONObject: [
                "authorization": request.value(forHTTPHeaderField: "Authorization") ?? "",
                "device": request.value(forHTTPHeaderField: "X-Device-ID") ?? "",
                "epoch": request.value(forHTTPHeaderField: "X-Breakpoint-Epoch") ?? "",
                "url": request.url!.absoluteString,
            ])
        }
        client?.urlProtocol(self, didLoad: bytes)
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

struct BreakpointSafetyTests {
    @Test func controlFramesAreAuthenticatedBoundedAndLocalOnly() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let secret = String(repeating: "test-", count: 10)
        let file = root.appendingPathComponent("breakpoint-desktop.json")
        try JSONSerialization.data(withJSONObject: ["token": secret]).write(to: file)
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: file.path)
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [BPControlProtocol.self]
        let api = BreakpointHTTPClient(baseURL: URL(string: "http://127.0.0.1:1/")!, directory: root, configuration: configuration)
        let target = BreakpointTarget(captureId: "1", deviceId: "device", epoch: "epoch")
        let response = try await api.call(target, path: "/echo")
        let result = try #require(JSONSerialization.jsonObject(with: response) as? [String: String])
        #expect(result["authorization"] == "Bearer " + secret)
        #expect(result["device"] == "device" && result["epoch"] == "epoch")
        #expect(result["url"] == "http://127.0.0.1:1/api/captures/1/breakpoints/echo")
        for path in ["/declared", "/chunked"] {
            await #expect(throws: BreakpointFailure("frame_too_large")) { try await api.call(target, path: path) }
        }
        await #expect(throws: BreakpointFailure("unavailable")) { try await api.call(target, path: "/redirect") }
        await #expect(throws: BreakpointFailure("disconnected")) { try await api.call(target, path: "/failure") }
        let remote = BreakpointHTTPClient(baseURL: URL(string: "http://example.invalid/")!, directory: root, configuration: configuration)
        await #expect(throws: BreakpointFailure("unavailable")) { try await remote.call(target, path: "/echo") }
    }

    @Test @MainActor func editorRejectsOversizedPasteBeforeReplacingText() {
        var limited = false
        let editor = BreakpointTextEditor(text: .constant(""), label: "test", onLimit: { limited = true })
        let delegate = editor.makeCoordinator()
        let text = NSTextView()
        text.string = String(repeating: "a", count: 262_140)
        #expect(!delegate.textView(text, shouldChangeTextIn: NSRange(location: 0, length: 0), replacementString: "多行内容"))
        #expect(limited && text.string.utf8.count == 262_140)
        #expect(delegate.textView(text, shouldChangeTextIn: NSRange(location: 0, length: text.string.count), replacementString: "first\nsecond"))
    }
}

import Foundation
import Testing
@testable import AICaptureNativeApp

@Suite struct BreakpointTests {
    @Test func ruleSeedDropsCredentialsQueryAndFragment() throws {
        let spec = try BreakpointRuleSpec.seed(url: "https://user:secret@Example.test:8443/v1/test?a=token#part", method: "POST")
        #expect(spec.host == "example.test")
        #expect(spec.port == 8443)
        #expect(spec.path == "/v1/test")
        #expect(spec.once && spec.timeoutSeconds == 30)
        #expect(throws: (any Error).self) { try BreakpointRuleSpec.seed(url: "file:///tmp/secret", method: "GET") }
    }
    @Test func engineNullablePortNormalizesToSchemeDefault() throws {
        let data = Data("{\"id\":\"r\",\"revision\":1,\"consumed\":false,\"scheme\":\"https\",\"host\":\"example.test\",\"port\":null,\"path\":\"/\",\"method\":\"GET\",\"stage\":\"request\",\"once\":true,\"enabled\":true,\"timeout_seconds\":30,\"path_match\":\"exact\"}".utf8)
        #expect(try BreakpointWire.decode(BreakpointRule.self, from: data).spec.port == 443)
    }

    private func message(_ body: String = "{\"a\":1}") -> BreakpointMessage {
        BreakpointMessage(url: "https://example.test/v1?a=1&a=2", method: "POST",
                          headers: [["Content-Type", "application/json"], ["X-A", "one"], ["X-A", "two"],
                                    ["Authorization", "secret"], ["Content-Length", "7"]],
                          bodyBase64: Data(body.utf8).base64EncodedString(), status: nil, editableBody: true)
    }

    @Test func unchangedDraftProducesEmptyPatchAndKeepsRepeatedHeaders() throws {
        let original = message()
        let draft = BreakpointDraft(original: original)
        #expect(try draft.patch(stage: "request", original: original) == BreakpointPatch())
        #expect(draft.headers == original.headers)
    }

    @Test func patchValidatesOriginBodyAndManagedHeaders() throws {
        let original = message()
        var draft = BreakpointDraft(original: original)
        draft.url = "https://other.test/v1"
        #expect(throws: (any Error).self) { try draft.patch(stage: "request", original: original) }
        draft.url = original.url
        draft.body = "{bad"
        #expect(throws: (any Error).self) { try draft.patch(stage: "request", original: original) }
        draft.body = String(repeating: "中", count: 100_000)
        #expect(throws: (any Error).self) { try draft.patch(stage: "request", original: original) }
        draft.body = "{\"a\":2}"
        draft.headers[4][1] = "9"
        #expect(throws: (any Error).self) { try draft.patch(stage: "request", original: original) }
        draft.headers = original.headers
        #expect(try draft.patch(stage: "request", original: original).bodyText == "{\"a\":2}")
    }

    @Test func responseDoesNotSendRequestFields() throws {
        var original = message()
        original.status = 200
        var draft = BreakpointDraft(original: original)
        draft.status = "204"
        #expect(throws: (any Error).self) { try draft.patch(stage: "response", original: original) }
        draft.body = ""
        let patch = try draft.patch(stage: "response", original: original)
        #expect(patch.status == 204 && patch.url == nil && patch.method == nil && patch.bodyText == "")
    }

    @Test func credentialsRejectLinksAndWorldReadableFiles() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let file = directory.appendingPathComponent("breakpoint-desktop.json")
        try Data("{\"token\":\"\(String(repeating: "a", count: 40))\"}".utf8).write(to: file)
        try FileManager.default.setAttributes([.posixPermissions: 0o644], ofItemAtPath: file.path)
        #expect(throws: (any Error).self) { try BreakpointCredentials.read(directory: directory) }
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: file.path)
        #expect(try BreakpointCredentials.read(directory: directory).count == 40)
        let other = directory.appendingPathComponent("other")
        try FileManager.default.moveItem(at: file, to: other)
        try FileManager.default.createSymbolicLink(at: file, withDestinationURL: other)
        #expect(throws: (any Error).self) { try BreakpointCredentials.read(directory: directory) }
    }

    @Test func templatesPersistWithoutQueryOrSecretsAndDoNotEnableCapture() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let library = BreakpointRuleLibrary(directory: root)
        let rule = try BreakpointRuleSpec.seed(url: "https://user:secret@example.test/path?q=secret", method: "POST")
        try library.save(rule)
        #expect(try library.load() == [rule])
        let stored = try String(contentsOf: root.appendingPathComponent("breakpoint-rules.json"), encoding: .utf8)
        #expect(!stored.contains("secret") && !stored.contains("epoch") && !stored.contains("body"))
        var unsafe = rule; unsafe.path = "/path?secret=token"
        #expect(throws: (any Error).self) { try library.save(unsafe) }
        #expect(try library.load() == [rule])
    }
}

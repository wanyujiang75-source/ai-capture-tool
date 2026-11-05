import Foundation
import Testing
@testable import AICaptureNativeApp

struct FlowDetailPresentationTests {
    @Test func formatsCapturedJSONTextWithoutChangingValues() throws {
        let raw = #"{"user":{"id":9007199254740993,"name":"测试"},"items":[{"ok":true},null],"id":1,"id":2}"#
        let detail = try makeDetail(["response_text": raw, "response_body_kind": "json"])
        #expect(FlowListPresentation.responseBodyText(detail) == """
        {
          "user": {
            "id": 9007199254740993,
            "name": "测试"
          },
          "items": [
            {
              "ok": true
            },
            null
          ],
          "id": 1,
          "id": 2
        }
        """)
    }

    @Test func structuredJSONEscapesStringsAndPreservesIntegerIDs() throws {
        let data = Data(#"{"id":"f","request_json":{"id":9007199254740993,"max":18446744073709551615,"value":{"a\"b":"line\n\"quoted\""}}}"#.utf8)
        let detail = try JSONDecoder().decode(FlowDetail.self, from: data)
        let text = FlowListPresentation.requestBodyText(detail)
        #expect(text.contains("9007199254740993"))
        #expect(text.contains("18446744073709551615"))
        #expect(text.contains(#"    "a\"b": "line\n\"quoted\""#))
        #expect(throws: Never.self) { try JSONSerialization.jsonObject(with: Data(text.utf8)) }
    }

    @Test func partialJSONAndPlainTextRemainUnmodified() throws {
        for raw in ["{\"incomplete\":", "  first line\n\nsecond line  ", "\n\t"] {
            let detail = try makeDetail(["response_text": raw])
            #expect(FlowListPresentation.responseBodyText(detail) == raw)
        }
    }

    @Test func requestDocumentIncludesRepeatedParametersHeadersAndBody() throws {
        let detail = try makeDetail([
            "url": "https://example.test/items?tag=one&tag=two&empty=&flag&q=a+b%26c&name=%E6%B5%8B%E8%AF%95",
            "request_text": #"{"count":2}"#,
            "meta_json": ["summary": ["request_headers": [["X-Tag", "one"], ["X-Tag", "two"], ["X-Line", "a\nb"]]]],
        ])
        let shown = FlowDetailPresentation.request(detail).text
        #expect(shown == """
        查询参数
        tag: one
        tag: two
        empty:\u{20}
        flag
        q: a+b&c
        name: 测试

        请求头 · Headers
        X-Tag: one
        X-Tag: two
        X-Line: a\\nb

        请求正文 · Body
        {
          "count": 2
        }
        """)
    }

    @Test func formFieldsRespectEncodingDuplicatesAndEmptyValues() throws {
        let detail = try makeDetail([
            "request_text": "tag=one&tag=two&name=a+b%2Bc&data=a%3Db%26c&empty=&bad=%zz",
            "request_body": ["content_type": "application/x-www-form-urlencoded; charset=UTF-8", "size_bytes": 70],
        ])
        #expect(FlowListPresentation.requestBodyText(detail) == "tag: one\ntag: two\nname: a b+c\ndata: a=b&c\nempty: \nbad: %zz")
    }

    @Test func responseDocumentRetainsRepeatedCookiesAndStatus() throws {
        let detail = try makeDetail([
            "response_text": #"{"ok":true}"#,
            "meta_json": ["summary": ["response_headers": [["Set-Cookie", "a=1"], ["Set-Cookie", "b=2"]]]],
        ])
        #expect(FlowDetailPresentation.response(detail).text == """
        响应状态：200

        响应头 · Headers
        Set-Cookie: a=1
        Set-Cookie: b=2

        响应正文 · Body
        {
          "ok": true
        }
        """)
    }

    @Test func distinguishesEmptyMissingBinaryAndPendingData() throws {
        let empty = try makeDetail([:])
        #expect(FlowListPresentation.requestBodyText(empty) == AppCopy.Flow.noRequestBody)
        #expect(FlowDetailPresentation.response(empty).text.contains(AppCopy.Flow.noHeaders))
        #expect(FlowListPresentation.responseBodyText(empty) == AppCopy.Flow.responseWithoutBody(statusCode: "200"))
        let pending = try JSONDecoder().decode(FlowDetail.self, from: Data(#"{"id":"f","status":"NO_RESPONSE"}"#.utf8))
        #expect(FlowListPresentation.responseBodyText(pending) == AppCopy.Flow.responsePending)
        let binary = try makeDetail(["response_body": ["kind": "binary", "size_bytes": 42, "path": "/tmp/body.bin"]])
        let shown = FlowListPresentation.responseBody(binary)
        #expect(shown == FlowBodyPresentation(text: AppCopy.Flow.binaryBody, isTruncated: false, sizeBytes: 42,
                                             fullFileURL: URL(fileURLWithPath: "/tmp/body.bin"), notice: AppCopy.Flow.binaryBody))
        let missing = try makeDetail(["response_body": ["size_bytes": 10]])
        #expect(FlowListPresentation.responseBodyText(missing) == AppCopy.Flow.unavailableBody)
    }

    @Test func formatterPreservesLiteralTokensAndHandlesEmptyContainers() throws {
        let raw = #"{"s":"[{},]: \"x\" \\ \n \u0041","a":[],"b":{},"decimal":1.2300e-08,"n":-0}"#
        let text = try #require(FlowJSONFormatter.formatted(raw))
        #expect(text.contains(#""s": "[{},]: \"x\" \\ \n \u0041""#))
        #expect(text.contains(#""decimal": 1.2300e-08"#))
        #expect(text.contains(#""n": -0"#))
        #expect(text.contains(#""a": []"#))
        #expect(text.contains(#""b": {}"#))
        for scalar in ["null", "false", "3", #""string""#] {
            #expect(FlowJSONFormatter.formatted(scalar) == scalar)
        }
        for invalid in ["", "{", "{]", "[1,]", "{\"x\": tru e}", "1 2", #""unterminated"#] {
            #expect(FlowJSONFormatter.formatted(invalid) == nil)
        }
    }

    @Test func limitsFormattingExpansionDepthLinesAndInput() throws {
        let deep = String(repeating: "[", count: 65) + "0" + String(repeating: "]", count: 65)
        let rows = "[" + Array(repeating: "0", count: 8_001).joined(separator: ",") + "]"
        let expanded = String(repeating: "[", count: 63) + "[" + Array(repeating: "0", count: 5_000).joined(separator: ",") + "]" + String(repeating: "]", count: 63)
        let huge = "{\"text\":\"" + String(repeating: "x", count: FlowJSONFormatter.inputLimit) + "\"}"
        for raw in [deep, rows, expanded, huge] {
            #expect(FlowJSONFormatter.formatted(raw) == nil)
        }
        let shown = FlowListPresentation.responseBody(try makeDetail(["response_text": huge]))
        #expect(shown.isTruncated)
        #expect(shown.text.utf8.count <= FlowJSONFormatter.inputLimit)
        #expect(shown.text == String(huge.prefix(FlowJSONFormatter.inputLimit)))
    }

    @Test func truncatedJSONIsNotMadeToLookComplete() throws {
        let raw = #"{"preview":true}"#
        let detail = try makeDetail(["response_text": raw,
                                     "response_body": ["kind": "json", "size_bytes": 76, "truncated": true]])
        let shown = FlowDetailPresentation.response(detail)
        #expect(shown.isTruncated)
        #expect(shown.text.hasSuffix(raw))
        #expect(!AppCopy.Flow.largeBodyPreview(sizeBytes: 76).contains("256"))
    }

    @Test func metadataIsBoundedAndRawTextTakesPrecedence() throws {
        let detail = try makeDetail([
            "response_text": #"{"exact":1.2300}"#, "response_json": ["exact": 1.23],
            "meta_json": ["summary": ["response_headers": [["X-Large", String(repeating: "x", count: 40_000)]]]],
        ])
        let shown = FlowDetailPresentation.response(detail)
        #expect(shown.text.contains("1.2300"))
        #expect(shown.text.contains(AppCopy.Flow.metadataPreview))
        #expect(shown.text.contains("X-Large: xxx"))
        #expect(shown.text.utf8.count < FlowDetailPresentation.metadataLimit + 1_024)
    }

    @Test func legacyBinaryKindsAreNotReportedAsEmpty() throws {
        let detail = try makeDetail(["request_body_kind": "binary", "response_body_kind": "binary"])
        #expect(FlowListPresentation.requestBodyText(detail) == AppCopy.Flow.binaryBody)
        #expect(FlowListPresentation.responseBodyText(detail) == AppCopy.Flow.binaryBody)
    }

    @Test func explicitJSONNullIsDifferentFromAnAbsentBody() throws {
        let json = try makeDetail(["request_body_kind": "json", "request_json": NSNull(),
                                   "response_body_kind": "json", "response_json": NSNull()])
        #expect(FlowListPresentation.requestBodyText(json) == "null")
        #expect(FlowListPresentation.responseBodyText(json) == "null")
        let absent = try makeDetail(["request_body_kind": "empty", "request_json": NSNull()])
        #expect(FlowListPresentation.requestBodyText(absent) == AppCopy.Flow.noRequestBody)
    }

    @Test func oversizedQueryShowsBoundedPrefixAndTruncation() throws {
        let detail = try makeDetail(["url": "https://example.test/?" + String(repeating: "k=v&", count: 100_000)])
        let text = FlowDetailPresentation.request(detail).text
        #expect(text.hasPrefix("查询参数\nk: v\nk: v"))
        #expect(text.contains(AppCopy.Flow.metadataPreview))
        #expect(text.utf8.count < FlowDetailPresentation.metadataLimit + 1_024)
        let fragmentOnly = try makeDetail(["url": "https://example.test/#anchor?not=query"])
        #expect(!FlowDetailPresentation.request(fragmentOnly).text.contains(AppCopy.Flow.queryParameters))
    }

    private func makeDetail(_ fields: [String: Any]) throws -> FlowDetail {
        var json = fields
        json["id"] = "flow-test"
        json["status"] = "200"
        return try JSONDecoder().decode(FlowDetail.self, from: JSONSerialization.data(withJSONObject: json))
    }
}

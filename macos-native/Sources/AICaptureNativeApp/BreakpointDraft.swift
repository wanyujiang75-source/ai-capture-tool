import Foundation

struct BreakpointDraft: Equatable {
    static let methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
    static let managedHeaders: Set<String> = ["host", "content-length", "transfer-encoding", "content-encoding",
        "connection", "trailer", "te", "upgrade", "proxy-authorization", "proxy-authenticate"]
    static let sensitiveHeaders: Set<String> = ["authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization"]
    var url: String
    var method: String
    var status: String
    var headers: [[String]]
    var body: String

    init(original: BreakpointMessage) {
        url = original.url
        method = original.method
        status = original.status.map(String.init) ?? "200"
        headers = original.headers
        body = original.text ?? ""
    }

    func patch(stage: String, original: BreakpointMessage) throws -> BreakpointPatch {
        var result = BreakpointPatch()
        if stage == "request" {
            let before = try BreakpointRuleSpec.seed(url: original.url, method: original.method)
            let after = try BreakpointRuleSpec.seed(url: url, method: method)
            guard before.scheme == after.scheme, before.host == after.host, before.port == after.port,
                  let parts = URLComponents(string: url), parts.user == nil, parts.password == nil,
                  parts.fragment == nil, url.utf8.count <= 8192 else { throw BreakpointFailure("origin_change") }
            if url != original.url { result.url = url }
            if method != original.method { result.method = method }
        } else {
            guard let value = Int(status), (200...599).contains(value) else { throw BreakpointFailure("invalid_status") }
            if value != original.status { result.status = value }
        }
        guard headers.count <= 200, headers.allSatisfy({ $0.count == 2 }),
              headers.reduce(0, { $0 + $1.joined().utf8.count + 4 }) <= 65536 else { throw BreakpointFailure("invalid_headers") }
        for pair in headers {
            guard !pair[0].isEmpty, pair[0].utf8.allSatisfy({ byte in
                (33...126).contains(byte) && !Array("()<>@,;:\\\"/[]?={} \t".utf8).contains(byte)
            }), !pair[1].contains("\r"), !pair[1].contains("\n"), !pair[1].contains("\0") else {
                throw BreakpointFailure("invalid_headers")
            }
        }
        let managed: ([[String]]) -> [[String]] = { $0.filter { Self.managedHeaders.contains($0[0].lowercased()) } }
        guard managed(headers) == managed(original.headers) else { throw BreakpointFailure("managed_headers") }
        if headers != original.headers { result.headers = headers }
        if body != (original.text ?? "") {
            guard original.editableBody, original.text != nil, body.utf8.count <= 262144 else { throw BreakpointFailure("body_limit") }
            let mime = headers.first { $0[0].lowercased() == "content-type" }?[1].lowercased() ?? ""
            if !body.isEmpty && (mime.contains("/json") || mime.contains("+json")) {
                guard (try? JSONSerialization.jsonObject(with: Data(body.utf8), options: .fragmentsAllowed)) != nil else {
                    throw BreakpointFailure("invalid_json")
                }
            }
            result.bodyText = body
        }
        if stage == "response", (original.method == "HEAD" || [204, 304].contains(Int(status) ?? 0)), !body.isEmpty {
            throw BreakpointFailure("no_body_status")
        }
        return result
    }

    mutating func formatJSON() throws {
        guard body.utf8.count <= 262144 else { throw BreakpointFailure("body_limit") }
        let object = try JSONSerialization.jsonObject(with: Data(body.utf8), options: .fragmentsAllowed)
        let data = try JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .fragmentsAllowed, .withoutEscapingSlashes])
        guard data.count <= 262144 else { throw BreakpointFailure("body_limit") }
        body = String(decoding: data, as: UTF8.self)
    }
}

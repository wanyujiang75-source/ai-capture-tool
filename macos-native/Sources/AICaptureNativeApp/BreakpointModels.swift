import Foundation

struct BreakpointTarget: Codable, Equatable, Sendable {
    let captureId: String
    let deviceId: String
    let epoch: String
}

struct BreakpointRuleSpec: Codable, Equatable, Sendable {
    var scheme: String
    var host: String
    var port: Int
    var path: String
    var pathMatch = "exact"
    var method: String
    var stage = "request"
    var once = true
    var enabled = true
    var timeoutSeconds = 30

    init(scheme: String, host: String, port: Int, path: String, method: String) {
        self.scheme = scheme; self.host = host; self.port = port; self.path = path; self.method = method
    }
    enum CodingKeys: String, CodingKey { case scheme, host, port, path, pathMatch, method, stage, once, enabled, timeoutSeconds }
    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        scheme = try values.decode(String.self, forKey: .scheme)
        host = try values.decode(String.self, forKey: .host)
        port = try values.decodeIfPresent(Int.self, forKey: .port) ?? (scheme == "https" ? 443 : 80)
        path = try values.decode(String.self, forKey: .path)
        method = try values.decode(String.self, forKey: .method)
        pathMatch = try values.decode(String.self, forKey: .pathMatch)
        stage = try values.decode(String.self, forKey: .stage)
        once = try values.decode(Bool.self, forKey: .once)
        enabled = try values.decode(Bool.self, forKey: .enabled)
        timeoutSeconds = try values.decode(Int.self, forKey: .timeoutSeconds)
    }

    static func seed(url: String, method: String) throws -> Self {
        guard let parts = URLComponents(string: url), let scheme = parts.scheme?.lowercased(),
              ["http", "https"].contains(scheme), let host = parts.host, !host.isEmpty,
              BreakpointDraft.methods.contains(method) else { throw BreakpointFailure("invalid_rule") }
        return Self(scheme: scheme, host: host.lowercased(), port: parts.port ?? (scheme == "https" ? 443 : 80),
                    path: parts.percentEncodedPath.isEmpty ? "/" : parts.percentEncodedPath, method: method)
    }

    var endpoint: String { "\(scheme)://\(host):\(port)\(path)" }
}

struct BreakpointRule: Decodable, Identifiable, Sendable {
    let id: String
    let revision: Int
    let consumed: Bool
    let spec: BreakpointRuleSpec
    enum CodingKeys: String, CodingKey { case id, revision, consumed }
    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        id = try values.decode(String.self, forKey: .id)
        revision = try values.decode(Int.self, forKey: .revision)
        consumed = try values.decode(Bool.self, forKey: .consumed)
        spec = try BreakpointRuleSpec(from: decoder)
    }
}

struct BreakpointStatus: Decodable, Sendable {
    let epoch: String
    let captureId: String
    let deviceId: String
    let enabled: Bool
    let stopped: Bool
    let inFlight: Int
    let pendingCount: Int
    let rules: [BreakpointRule]
    let transportAttached: Bool
}

struct BreakpointPending: Decodable, Identifiable, Sendable {
    let id: String
    let flowId: String
    let stage: String
    let state: String
    let revision: Int
    let matchedRule: String
    let remainingSeconds: Double
}

struct BreakpointPage: Decodable, Sendable {
    let data: [BreakpointPending]
    let nextCursor: Int?
}

struct BreakpointDetail: Decodable, Sendable {
    let id: String
    let stage: String
    let revision: Int
    let state: String
    let original: BreakpointMessage
}

struct BreakpointMessage: Codable, Equatable, Sendable {
    var url: String
    var method: String
    var headers: [[String]]
    var bodyBase64: String
    var status: Int?
    var editableBody: Bool
    var text: String? { Data(base64Encoded: bodyBase64).flatMap { String(data: $0, encoding: .utf8) } }
}

struct BreakpointPatch: Encodable, Equatable, Sendable {
    var url: String?
    var method: String?
    var status: Int?
    var headers: [[String]]?
    var bodyText: String?
}

enum BreakpointWire {
    static func encode<T: Encodable>(_ value: T) throws -> Data {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return try encoder.encode(value)
    }
    static func decode<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(type, from: data)
    }
}

struct BreakpointFailure: Error, Equatable {
    let code: String
    init(_ code: String) { self.code = code }
}

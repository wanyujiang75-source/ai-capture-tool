import Foundation

struct APIClient {
    let baseURL: URL

    private let session: URLSession
    private let decoder = JSONDecoder()

    init(baseURL: URL = URL(string: "http://127.0.0.1:7001")!) {
        self.baseURL = baseURL

        let configuration = URLSessionConfiguration.ephemeral
        configuration.connectionProxyDictionary = [:]
        configuration.timeoutIntervalForRequest = 25
        configuration.timeoutIntervalForResource = 30
        self.session = URLSession(configuration: configuration)
    }

    func getDevices() async throws -> [CaptureDevice] {
        let response: DevicesResponse = try await get("api/devices")
        return response.devices
    }

    func getApps() async throws -> [CaptureApp] {
        let response: AppsResponse = try await get("api/apps")
        return response.apps
    }

    func prepareFrida(deviceId: String) async throws -> BasicActionResponse {
        try await post("api/devices/\(deviceId)/prepare-frida")
    }

    func launchApp(appId: Int, deviceId: String) async throws -> BasicActionResponse {
        try await post(
            "api/apps/\(appId)/launch",
            queryItems: [URLQueryItem(name: "device_id", value: deviceId)]
        )
    }

    func startCapture(appId: Int, deviceId: String, mode: String?) async throws -> CaptureStartResponse {
        try await post(
            "api/captures/start",
            body: CaptureStartPayload(appId: appId, deviceId: deviceId, mode: mode)
        )
    }

    func stopCapture(deviceId: String) async throws -> CaptureStopResponse {
        try await post(
            "api/captures/stop",
            queryItems: [URLQueryItem(name: "device_id", value: deviceId)]
        )
    }

    private func get<Response: Decodable>(_ path: String) async throws -> Response {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "GET"

        return try await send(request)
    }

    private func post<Response: Decodable>(
        _ path: String,
        queryItems: [URLQueryItem] = []
    ) async throws -> Response {
        var request = URLRequest(url: url(path: path, queryItems: queryItems))
        request.httpMethod = "POST"
        return try await send(request)
    }

    private func post<Response: Decodable, Body: Encodable>(
        _ path: String,
        queryItems: [URLQueryItem] = [],
        body: Body
    ) async throws -> Response {
        var request = URLRequest(url: url(path: path, queryItems: queryItems))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        return try await send(request)
    }

    private func send<Response: Decodable>(_ request: URLRequest) async throws -> Response {
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIClientError.invalidResponse
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw APIClientError.httpStatus(httpResponse.statusCode, body)
        }

        do {
            return try decoder.decode(Response.self, from: data)
        } catch {
            throw APIClientError.decoding(error.localizedDescription)
        }
    }

    private func url(path: String, queryItems: [URLQueryItem]) -> URL {
        let endpoint = baseURL.appendingPathComponent(path)
        guard !queryItems.isEmpty else {
            return endpoint
        }
        var components = URLComponents(url: endpoint, resolvingAgainstBaseURL: false)!
        components.queryItems = queryItems
        return components.url ?? endpoint
    }
}

enum APIClientError: LocalizedError {
    case invalidResponse
    case httpStatus(Int, String)
    case decoding(String)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            "后端响应无效"
        case .httpStatus(let statusCode, let body):
            body.isEmpty ? "后端返回 HTTP \(statusCode)" : "后端返回 HTTP \(statusCode)：\(body)"
        case .decoding(let message):
            "数据解析失败：\(message)"
        }
    }
}

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

    private func get<Response: Decodable>(_ path: String) async throws -> Response {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "GET"

        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIClientError.invalidResponse
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            throw APIClientError.httpStatus(httpResponse.statusCode)
        }

        do {
            return try decoder.decode(Response.self, from: data)
        } catch {
            throw APIClientError.decoding(error.localizedDescription)
        }
    }
}

enum APIClientError: LocalizedError {
    case invalidResponse
    case httpStatus(Int)
    case decoding(String)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            "后端响应无效"
        case .httpStatus(let statusCode):
            "后端返回 HTTP \(statusCode)"
        case .decoding(let message):
            "数据解析失败：\(message)"
        }
    }
}

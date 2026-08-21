import Foundation

protocol LogcatAPI: Sendable {
    func startLogcat(
        deviceID: String,
        source: LogcatSource,
        packageName: String
    ) async throws -> LogcatActionResponse
    func pollLogcat(deviceID: String, after: Int64, limit: Int) async throws -> LogcatPollResponse
    func clearLogcat(deviceID: String) async throws -> LogcatActionResponse
    func stopLogcat(deviceID: String) async throws -> LogcatActionResponse
}

protocol ForegroundTargetAPI: Sendable {
    func getForegroundApp(deviceID: String) async throws -> ForegroundAppState
    func resolveForegroundTarget(deviceID: String) async throws -> ForegroundTargetResponse
    func getAppReadiness(appID: Int, deviceID: String) async throws -> ForegroundReadinessResponse
}

protocol LocalPackageInstallAPI: Sendable {
    func installLocalAPK(
        fileURL: URL,
        deviceID: String,
        environment: String
    ) async throws -> CaptureApp?
}

protocol FlowAPI: Sendable {
    func getFlows(sessionID: Int) async throws -> [FlowSummary]
    func getFlowDetail(sessionID: Int, flowID: String) async throws -> FlowDetail
    func getFlowCurl(sessionID: Int, flowID: String) async throws -> String
}

protocol CaptureWorkflowAPI: Sendable {
    func getDevices() async throws -> [CaptureDevice]
    func startDevice(deviceId: String, visible: Bool) async throws -> BasicActionResponse
    func prepareSystem(deviceId: String, visible: Bool) async throws -> SystemPrepareResponse
    func startCapture(appId: Int, deviceId: String, mode: String?) async throws -> CaptureStartResponse
    func stopCapture(deviceId: String) async throws -> CaptureStopResponse
}

struct APIClient: LogcatAPI, ForegroundTargetAPI, LocalPackageInstallAPI, FlowAPI, CaptureWorkflowAPI, @unchecked Sendable {
    let baseURL: URL

    private let session: URLSession
    private let decoder = JSONDecoder()

    init(
        baseURL: URL = URL(string: "http://127.0.0.1:7001")!,
        sessionConfiguration: URLSessionConfiguration? = nil
    ) {
        self.baseURL = baseURL

        let configuration = sessionConfiguration ?? URLSessionConfiguration.ephemeral
        configuration.connectionProxyDictionary = [:]
        configuration.timeoutIntervalForRequest = 240
        configuration.timeoutIntervalForResource = 1_200
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

    func getJenkinsPackages() async throws -> [JenkinsPackage] {
        let response: JenkinsPackagesResponse = try await get("api/package-sources/jenkins/packages")
        return response.packages
    }

    func getForegroundApp(deviceID: String) async throws -> ForegroundAppState {
        try await get("api/devices/\(deviceID)/foreground-app")
    }

    func resolveForegroundTarget(deviceID: String) async throws -> ForegroundTargetResponse {
        try await post("api/devices/\(deviceID)/foreground-target/resolve")
    }

    func getAppReadiness(appID: Int, deviceID: String) async throws -> ForegroundReadinessResponse {
        try await get(
            "api/apps/\(appID)/readiness",
            queryItems: [URLQueryItem(name: "device_id", value: deviceID)]
        )
    }

    func startDevice(deviceId: String, visible: Bool = false) async throws -> BasicActionResponse {
        try await post(
            "api/devices/\(deviceId)/start",
            queryItems: [URLQueryItem(name: "visible", value: visible ? "true" : "false")],
            timeoutInterval: 900
        )
    }

    func installJenkinsPackage(
        _ package: JenkinsPackage,
        deviceId: String,
        environment: String
    ) async throws -> JenkinsInstallResponse {
        try await post(
            "api/package-sources/jenkins/install",
            timeoutInterval: 900,
            body: JenkinsInstallPayload(
                deviceId: deviceId,
                jobName: package.jobName,
                buildNumber: package.buildNumber,
                artifactRelativePath: package.artifactRelativePath,
                environment: environment
            )
        )
    }

    func installLocalAPK(
        fileURL: URL,
        deviceID: String,
        environment: String
    ) async throws -> CaptureApp? {
        var request = URLRequest(
            url: url(
                path: "api/apps/install",
                queryItems: [
                    URLQueryItem(name: "filename", value: fileURL.lastPathComponent),
                    URLQueryItem(name: "environment", value: environment),
                    URLQueryItem(name: "device_id", value: deviceID)
                ]
            )
        )
        request.httpMethod = "POST"
        request.timeoutInterval = 900
        request.setValue("application/vnd.android.package-archive", forHTTPHeaderField: "Content-Type")

        let (data, response) = try await session.upload(for: request, fromFile: fileURL)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIClientError.invalidResponse
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw APIClientError.httpStatus(httpResponse.statusCode, body)
        }
        do {
            return try decoder.decode(JenkinsInstallResponse.self, from: data).app
        } catch {
            throw APIClientError.decoding(error.localizedDescription)
        }
    }

    func prepareFrida(deviceId: String) async throws -> BasicActionResponse {
        try await post("api/devices/\(deviceId)/prepare-frida")
    }

    func prepareSystem(deviceId: String, visible: Bool = false) async throws -> SystemPrepareResponse {
        try await post(
            "api/system/prepare",
            queryItems: [
                URLQueryItem(name: "device_id", value: deviceId),
                URLQueryItem(name: "visible", value: visible ? "true" : "false")
            ]
        )
    }

    func getGooglePlayImageStatus() async throws -> GooglePlayImageStatus {
        let response: GooglePlayImageResponse = try await get("api/system/google-play-image")
        return response.googlePlayImage
    }

    func installGooglePlayImage() async throws -> GooglePlayImageStatus {
        let response: GooglePlayImageResponse = try await post("api/system/install-google-play-image")
        return response.googlePlayImage
    }

    func ensureGooglePlayAvd(deviceId: String) async throws -> EnsureGooglePlayAvdResponse {
        try await post("api/devices/\(deviceId)/ensure-google-play-avd")
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

    func startLogcat(
        deviceID: String,
        source: LogcatSource,
        packageName: String
    ) async throws -> LogcatActionResponse {
        try await post(
            "api/devices/\(deviceID)/logcat/start",
            body: LogcatStartPayload(source: source, packageName: packageName)
        )
    }

    func pollLogcat(deviceID: String, after: Int64, limit: Int) async throws -> LogcatPollResponse {
        try await get(
            "api/devices/\(deviceID)/logcat",
            queryItems: [
                URLQueryItem(name: "after", value: String(after)),
                URLQueryItem(name: "limit", value: String(limit))
            ],
            timeoutInterval: 10
        )
    }

    func clearLogcat(deviceID: String) async throws -> LogcatActionResponse {
        try await post("api/devices/\(deviceID)/logcat/clear")
    }

    func stopLogcat(deviceID: String) async throws -> LogcatActionResponse {
        try await post("api/devices/\(deviceID)/logcat/stop")
    }

    func getFlows(sessionID: Int) async throws -> [FlowSummary] {
        let response: FlowsResponse = try await get("api/captures/\(sessionID)/flows")
        return response.flows
    }

    func getFlowDetail(sessionID: Int, flowID: String) async throws -> FlowDetail {
        try await get("api/captures/\(sessionID)/flows/\(flowID)")
    }

    func getFlowCurl(sessionID: Int, flowID: String) async throws -> String {
        var request = URLRequest(url: baseURL.appendingPathComponent("api/captures/\(sessionID)/flows/\(flowID)/curl"))
        request.httpMethod = "GET"

        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIClientError.invalidResponse
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw APIClientError.httpStatus(httpResponse.statusCode, body)
        }
        return String(data: data, encoding: .utf8) ?? ""
    }

    private func get<Response: Decodable>(
        _ path: String,
        queryItems: [URLQueryItem] = [],
        timeoutInterval: TimeInterval? = nil
    ) async throws -> Response {
        var request = URLRequest(url: url(path: path, queryItems: queryItems))
        request.httpMethod = "GET"
        if let timeoutInterval {
            request.timeoutInterval = timeoutInterval
        }

        return try await send(request)
    }

    private func post<Response: Decodable>(
        _ path: String,
        queryItems: [URLQueryItem] = [],
        timeoutInterval: TimeInterval? = nil
    ) async throws -> Response {
        var request = URLRequest(url: url(path: path, queryItems: queryItems))
        request.httpMethod = "POST"
        if let timeoutInterval {
            request.timeoutInterval = timeoutInterval
        }
        return try await send(request)
    }

    private func post<Response: Decodable, Body: Encodable>(
        _ path: String,
        queryItems: [URLQueryItem] = [],
        timeoutInterval: TimeInterval? = nil,
        body: Body
    ) async throws -> Response {
        var request = URLRequest(url: url(path: path, queryItems: queryItems))
        request.httpMethod = "POST"
        if let timeoutInterval {
            request.timeoutInterval = timeoutInterval
        }
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
        userFacingIssue.message
    }

    var userFacingIssue: UserFacingIssue {
        switch self {
        case .invalidResponse:
            return UserFacingIssue(
                code: "invalid_response",
                title: "本机服务响应异常",
                message: "请重新检查本机服务后重试。"
            )
        case let .decoding(message):
            return UserFacingIssue(
                code: "response_decoding_failed",
                title: "数据读取失败",
                message: "返回的数据无法读取，请刷新后重试。",
                technicalDetail: message
            )
        case let .httpStatus(statusCode, body):
            return Self.issue(statusCode: statusCode, body: body)
        }
    }

    private static func issue(statusCode: Int, body: String) -> UserFacingIssue {
        let detail = detailDictionary(from: body)
        let detailText = detailString(from: body)
        let code = detail?["code"] as? String ?? "http_status_\(statusCode)"
        let title = detail?["title"] as? String ?? defaultTitle(statusCode: statusCode)
        let message = detail?["user_message"] as? String ?? defaultMessage(statusCode: statusCode)
        let recoveryAction = detail?["recovery_action"] as? String
            ?? detail?["fix"] as? String
        let technicalDetail = detail?["technical_detail"] as? String
            ?? detail?["message"] as? String
            ?? detailText
            ?? (body.isEmpty ? nil : body)
        return UserFacingIssue(
            code: code,
            title: title,
            message: message,
            recoveryAction: recoveryAction,
            technicalDetail: technicalDetail
        )
    }

    private static func detailDictionary(from body: String) -> [String: Any]? {
        guard let data = body.data(using: .utf8),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return nil
        }
        return object["detail"] as? [String: Any] ?? object
    }

    private static func detailString(from body: String) -> String? {
        guard let data = body.data(using: .utf8),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return nil
        }
        return object["detail"] as? String
    }

    private static func defaultTitle(statusCode: Int) -> String {
        switch statusCode {
        case 404:
            "内容不可用"
        case 409:
            "当前操作暂时无法完成"
        case 500...599:
            "本机服务暂时不可用"
        default:
            "操作未完成"
        }
    }

    private static func defaultMessage(statusCode: Int) -> String {
        switch statusCode {
        case 404:
            "请求的内容不存在或已失效，请刷新后重试。"
        case 409:
            "当前操作与正在进行的任务冲突，请结束当前任务后重试。"
        case 500...599:
            "请打开运行检查，确认本机服务正常后重试。"
        default:
            "请稍后重试；如果问题持续，请打开运行检查。"
        }
    }
}

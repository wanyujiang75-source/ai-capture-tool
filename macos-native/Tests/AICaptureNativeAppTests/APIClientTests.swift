import Foundation
import Testing
@testable import AICaptureNativeApp

private final class CapturingURLProtocol: URLProtocol, @unchecked Sendable {
    nonisolated(unsafe) static var observedTimeout: TimeInterval?
    nonisolated(unsafe) static var observedRequests: [URLRequest] = []
    nonisolated(unsafe) static var responseData = Data("{}".utf8)

    static func reset(responseData: Data = Data("{}".utf8)) {
        observedTimeout = nil
        observedRequests = []
        Self.responseData = responseData
    }

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        Self.observedTimeout = request.timeoutInterval
        var capturedRequest = request
        if capturedRequest.httpBody == nil, let bodyStream = request.httpBodyStream {
            capturedRequest.httpBody = Self.readBody(from: bodyStream)
        }
        Self.observedRequests.append(capturedRequest)
        let response = HTTPURLResponse(
            url: request.url!,
            statusCode: 200,
            httpVersion: nil,
            headerFields: ["Content-Type": "application/json"]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Self.responseData)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}

    private static func readBody(from stream: InputStream) -> Data {
        stream.open()
        defer { stream.close() }
        var data = Data()
        var buffer = [UInt8](repeating: 0, count: 4_096)
        while stream.hasBytesAvailable {
            let count = stream.read(&buffer, maxLength: buffer.count)
            guard count > 0 else {
                break
            }
            data.append(buffer, count: count)
        }
        return data
    }
}

@Suite(.serialized)
struct APIClientTests {
    @Test
    func jenkinsInstallAllowsLongArtifactDownloads() async throws {
        CapturingURLProtocol.reset()
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [CapturingURLProtocol.self]
        let client = APIClient(
            baseURL: URL(string: "http://127.0.0.1:7001")!,
            sessionConfiguration: configuration
        )
        let package = try JSONDecoder().decode(
            JenkinsPackage.self,
            from: Data(
                """
                {
                  "id": "glp-1-tracker-158",
                  "job_name": "glp-1-tracker",
                  "build_number": 158,
                  "artifact_file_name": "glp-1-tracker_158.apk",
                  "artifact_relative_path": "glp-1-tracker_158.apk",
                  "environment": "test"
                }
                """.utf8
            )
        )

        _ = try await client.installJenkinsPackage(package, deviceId: "device-1", environment: "test")

        #expect(CapturingURLProtocol.observedTimeout == 900)
    }

    @Test
    func startsAppLogcatWithPackagePayload() async throws {
        CapturingURLProtocol.reset(responseData: logcatResponseData())
        let client = makeClient()

        let response = try await client.startLogcat(
            deviceID: "device-1",
            source: .app,
            packageName: "com.example.app"
        )

        let request = try #require(CapturingURLProtocol.observedRequests.last)
        #expect(request.httpMethod == "POST")
        #expect(request.url?.path == "/api/devices/device-1/logcat/start")
        let body = try JSONDecoder().decode(
            ObservedLogcatStartBody.self,
            from: try #require(request.httpBody)
        )
        #expect(body == ObservedLogcatStartBody(source: "app", packageName: "com.example.app"))
        #expect(response.deviceID == "device-1")
        #expect(response.source == .app)
    }

    @Test
    func pollsIncrementallyWithTenSecondTimeoutAndDecodesCompleteEntry() async throws {
        CapturingURLProtocol.reset(responseData: logcatResponseData())
        let client = makeClient()

        let response = try await client.pollLogcat(deviceID: "device-1", after: 41, limit: 500)

        let request = try #require(CapturingURLProtocol.observedRequests.last)
        let requestURL = try #require(request.url)
        let components = try #require(URLComponents(url: requestURL, resolvingAgainstBaseURL: false))
        #expect(request.httpMethod == "GET")
        #expect(components.path == "/api/devices/device-1/logcat")
        #expect(Set(components.queryItems ?? []) == Set([
            URLQueryItem(name: "after", value: "41"),
            URLQueryItem(name: "limit", value: "500")
        ]))
        #expect(request.timeoutInterval == 10)
        #expect(response.entries == [
            LogcatEntry(
                cursor: 42,
                timestamp: "08-11 14:22:03.456",
                pid: 1234,
                tid: 1235,
                level: "W",
                tag: "Flutter",
                message: "frame took 20ms",
                raw: ""
            )
        ])
        #expect(response.nextCursor == 42)
        #expect(response.truncated == false)
    }

    @Test
    func clearsAndStopsDeviceLogcatUsingDedicatedEndpoints() async throws {
        CapturingURLProtocol.reset(responseData: logcatResponseData())
        let client = makeClient()

        _ = try await client.clearLogcat(deviceID: "device-1")
        _ = try await client.stopLogcat(deviceID: "device-1")

        #expect(CapturingURLProtocol.observedRequests.map(\.httpMethod) == ["POST", "POST"])
        #expect(CapturingURLProtocol.observedRequests.compactMap { $0.url?.path } == [
            "/api/devices/device-1/logcat/clear",
            "/api/devices/device-1/logcat/stop"
        ])
    }

    private func makeClient() -> APIClient {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [CapturingURLProtocol.self]
        return APIClient(
            baseURL: URL(string: "http://127.0.0.1:7001")!,
            sessionConfiguration: configuration
        )
    }

    private func logcatResponseData() -> Data {
        Data(
            """
            {
              "device_id": "device-1",
              "source": "app",
              "state": "streaming",
              "package_name": "com.example.app",
              "next_cursor": 42,
              "truncated": false,
              "entries": [
                {
                  "cursor": 42,
                  "timestamp": "08-11 14:22:03.456",
                  "pid": 1234,
                  "tid": 1235,
                  "level": "W",
                  "tag": "Flutter",
                  "message": "frame took 20ms",
                  "raw": ""
                }
              ]
            }
            """.utf8
        )
    }
}

private struct ObservedLogcatStartBody: Decodable, Equatable {
    let source: String
    let packageName: String

    private enum CodingKeys: String, CodingKey {
        case source
        case packageName = "package_name"
    }
}

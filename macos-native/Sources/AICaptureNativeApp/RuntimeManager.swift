import Foundation

struct RuntimeManager: Sendable {
    let backendURL: URL
    let runtimeDirectory: URL

    init(
        backendURL: URL = URL(string: "http://127.0.0.1:7001")!,
        runtimeDirectory: URL = RuntimeManager.defaultRuntimeDirectory()
    ) {
        self.backendURL = backendURL
        self.runtimeDirectory = runtimeDirectory
    }

    func checkStatus() async -> AppState.RuntimeStatus {
        do {
            try FileManager.default.createDirectory(
                at: runtimeDirectory,
                withIntermediateDirectories: true
            )
        } catch {
            return .failed("无法创建本机运行目录：\(error.localizedDescription)")
        }

        var request = URLRequest(url: backendURL.appendingPathComponent("api/status"))
        request.timeoutInterval = 3

        let configuration = URLSessionConfiguration.ephemeral
        configuration.connectionProxyDictionary = [:]
        let session = URLSession(configuration: configuration)
        defer {
            session.invalidateAndCancel()
        }

        do {
            let (_, response) = try await session.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                return .failed("本机抓包后端响应无效")
            }
            guard httpResponse.statusCode == 200 else {
                return .failed("本机抓包后端返回 HTTP \(httpResponse.statusCode)")
            }
            return .ready(backendURL.absoluteString)
        } catch {
            return .failed("未检测到本机抓包后端")
        }
    }

    private static func defaultRuntimeDirectory() -> URL {
        let applicationSupport = FileManager.default.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first ?? FileManager.default.homeDirectoryForCurrentUser

        return applicationSupport
            .appendingPathComponent("AI抓包工具", isDirectory: true)
            .appendingPathComponent("runtime-native", isDirectory: true)
    }
}

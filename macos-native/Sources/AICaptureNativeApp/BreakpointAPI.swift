import Darwin
import Foundation

enum BreakpointCredentials {
    static func read(directory: URL) throws -> String {
        let fd = open(directory.appendingPathComponent("breakpoint-desktop.json").path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)
        guard fd >= 0 else { throw BreakpointFailure("credentials") }
        defer { close(fd) }
        var info = stat()
        guard fstat(fd, &info) == 0, info.st_mode & S_IFMT == S_IFREG, info.st_uid == getuid(),
              info.st_mode & 0o077 == 0, info.st_size > 0, info.st_size <= 4096 else { throw BreakpointFailure("credentials") }
        let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: false)
        struct Credential: Decodable { let token: String }
        guard let data = try handle.read(upToCount: 4097), data.count <= 4096,
              let token = try? JSONDecoder().decode(Credential.self, from: data).token,
              (32...256).contains(token.utf8.count), !token.contains("\r"), !token.contains("\n") else {
            throw BreakpointFailure("credentials")
        }
        return token
    }
}

protocol BreakpointAPI: Sendable {
    func context(captureID: Int) async throws -> BreakpointTarget
    func call(_ target: BreakpointTarget, path: String, method: String, body: Data?) async throws -> Data
}

final class BreakpointHTTPClient: NSObject, BreakpointAPI, URLSessionTaskDelegate, @unchecked Sendable {
    private let baseURL: URL
    private let directory: URL
    private let configuration: URLSessionConfiguration
    init(baseURL: URL, directory: URL, configuration: URLSessionConfiguration = .ephemeral) {
        self.baseURL = baseURL
        self.directory = directory
        self.configuration = configuration
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }

    func context(captureID: Int) async throws -> BreakpointTarget {
        let data = try await send(captureID: String(captureID), target: nil, path: "/context", method: "GET", body: nil)
        let target = try BreakpointWire.decode(BreakpointTarget.self, from: data)
        guard target.captureId == String(captureID) else { throw BreakpointFailure("target_conflict") }
        return target
    }

    func call(_ target: BreakpointTarget, path: String, method: String = "GET", body: Data? = nil) async throws -> Data {
        try await send(captureID: target.captureId, target: target, path: path, method: method, body: body)
    }

    private func send(captureID: String, target: BreakpointTarget?, path: String, method: String, body: Data?) async throws -> Data {
        guard baseURL.scheme == "http", ["localhost", "127.0.0.1", "[::1]", "::1"].contains(baseURL.host ?? ""),
              baseURL.user == nil, baseURL.password == nil,
              captureID.allSatisfy(\.isNumber), !captureID.isEmpty,
              (body?.count ?? 0) <= 1_048_576 else { throw BreakpointFailure("unavailable") }
        let endpoint = baseURL.appendingPathComponent("api/captures/\(captureID)/breakpoints\(path)")
        var request = URLRequest(url: endpoint, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 3)
        request.httpMethod = method
        request.httpBody = body
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(try BreakpointCredentials.read(directory: directory))", forHTTPHeaderField: "Authorization")
        if let target {
            request.setValue(target.deviceId, forHTTPHeaderField: "X-Device-ID")
            request.setValue(target.epoch, forHTTPHeaderField: "X-Breakpoint-Epoch")
        }
        let config = configuration.copy() as! URLSessionConfiguration
        config.connectionProxyDictionary = [:]
        config.urlCache = nil
        config.httpCookieStorage = nil
        config.timeoutIntervalForResource = 4
        let session = URLSession(configuration: config, delegate: self, delegateQueue: nil)
        defer { session.invalidateAndCancel() }
        let (bytes, response) = try await session.bytes(for: request)
        guard response.expectedContentLength <= 1_048_576 else { throw BreakpointFailure("frame_too_large") }
        var data = Data()
        for try await byte in bytes {
            guard data.count < 1_048_576 else { throw BreakpointFailure("frame_too_large") }
            data.append(byte)
        }
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            struct Failure: Decodable { let code: String }
            let fallback = ((response as? HTTPURLResponse)?.statusCode ?? 0) >= 500 ? "disconnected" : "unavailable"
            let code = (try? JSONDecoder().decode(Failure.self, from: data).code) ?? fallback
            throw BreakpointFailure(code)
        }
        return data
    }
}

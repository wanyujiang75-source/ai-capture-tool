import CoreServices
import CryptoKit
import Foundation

enum DesktopReleaseDownload {
    enum Event: Sendable {
        case progress(Double?)
        case verifying
    }

    enum Failure: LocalizedError, Equatable {
        case missingChecksum, invalidChecksum, checksumMismatch, saveFailed

        var errorDescription: String? {
            switch self {
            case .missingChecksum: "这个版本没有校验文件，请查看 GitHub 发布页。"
            case .invalidChecksum: "校验文件格式有误，请查看 GitHub 发布页。"
            case .checksumMismatch: "ZIP 校验失败，请重试下载。"
            case .saveFailed: "无法保存 ZIP 到「下载」文件夹，请检查权限和可用空间。"
            }
        }
    }

    struct Checksum {
        let digest: String

        init(_ data: Data, filename: String) throws {
            let fields = String(decoding: data, as: UTF8.self).split(whereSeparator: \.isWhitespace)
            guard fields.count == 2, fields[1] == filename,
                  fields[0].utf8.count == 64,
                  fields[0].utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) })
            else { throw Failure.invalidChecksum }
            digest = String(fields[0])
        }
    }

    @concurrent
    static func download(_ release: DesktopRelease, onEvent: @escaping @Sendable (Event) -> Void) async throws -> URL {
        guard let checksumURL = release.checksumURL else { throw Failure.missingChecksum }
        let (data, checksumResponse) = try await URLSession.shared.data(from: checksumURL)
        try validate(checksumResponse)
        let checksum = try Checksum(data, filename: release.downloadURL.lastPathComponent)

        let files = FileManager.default
        let workingDirectory = files.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try files.createDirectory(at: workingDirectory, withIntermediateDirectories: false)
        defer { try? files.removeItem(at: workingDirectory) }
        let temporaryFile = workingDirectory.appendingPathComponent("archive")
        let response = try await downloadArchive(from: release.downloadURL, to: temporaryFile, onEvent: onEvent)
        try validate(response)
        try Task.checkCancellation()
        onEvent(.verifying)
        do {
            let folder = try FileManager.default.url(
                for: .downloadsDirectory, in: .userDomainMask, appropriateFor: nil, create: true
            )
            return try saveVerifiedArchive(at: temporaryFile, in: folder, checksum: checksum, release: release)
        } catch let failure as Failure {
            throw failure
        } catch is CancellationError {
            throw CancellationError()
        } catch {
            throw Failure.saveFailed
        }
    }

    static func saveVerifiedArchive(at archive: URL, in folder: URL, checksum: Checksum, release: DesktopRelease) throws -> URL {
        let handle = try FileHandle(forReadingFrom: archive)
        defer { try? handle.close() }
        var hash = SHA256()
        while let chunk = try handle.read(upToCount: 1_048_576), !chunk.isEmpty {
            try Task.checkCancellation()
            hash.update(data: chunk)
        }
        let digest = hash.finalize().map { String(format: "%02x", $0) }.joined()
        guard digest == checksum.digest else { throw Failure.checksumMismatch }
        try Task.checkCancellation()

        let files = FileManager.default
        let staging = folder.appendingPathComponent(".ai-capture-\(UUID().uuidString)", isDirectory: true)
        try files.createDirectory(at: staging, withIntermediateDirectories: false)
        defer { try? files.removeItem(at: staging) }
        let filename = release.downloadURL.lastPathComponent
        var stagedArchive = staging.appendingPathComponent(filename)
        try files.moveItem(at: archive, to: stagedArchive)
        var values = URLResourceValues()
        values.quarantineProperties = [
            kLSQuarantineTypeKey as String: kLSQuarantineTypeOtherDownload as String,
            kLSQuarantineDataURLKey as String: release.downloadURL,
            kLSQuarantineOriginURLKey as String: DesktopReleaseCatalog.releasesPage,
        ]
        try stagedArchive.setResourceValues(values)

        let stem = (filename as NSString).deletingPathExtension
        var copy = 1
        while true {
            try Task.checkCancellation()
            let name = copy == 1 ? filename : "\(stem) (\(copy)).zip"
            let destination = folder.appendingPathComponent(name)
            do {
                try files.moveItem(at: stagedArchive, to: destination)
                return destination
            } catch CocoaError.fileWriteFileExists {
                copy += 1
            }
        }
    }

    private static func validate(_ response: URLResponse) throws {
        guard let http = response as? HTTPURLResponse, http.statusCode == 200,
              http.url?.scheme == "https" else { throw URLError(.badServerResponse) }
    }

    static func downloadArchive(
        from url: URL, to destination: URL, onEvent: @escaping @Sendable (Event) -> Void
    ) async throws -> URLResponse {
        let (results, completion) = AsyncThrowingStream<URLResponse, any Error>.makeStream()
        let task = URLSession.shared.downloadTask(with: url) { temporaryFile, response, error in
            do {
                if let error { throw error }
                guard let temporaryFile, let response else { throw URLError(.badServerResponse) }
                // URLSession removes its file as soon as this callback returns.
                try FileManager.default.moveItem(at: temporaryFile, to: destination)
                completion.yield(response)
                completion.finish()
            } catch {
                completion.finish(throwing: error)
            }
        }
        task.resume()
        let progress = Task {
            while !Task.isCancelled {
                let expected = task.countOfBytesExpectedToReceive
                let fraction = expected > 0 ? min(Double(task.countOfBytesReceived) / Double(expected), 1) : nil
                onEvent(.progress(fraction))
                try await Task.sleep(for: .milliseconds(100))
            }
        }
        defer {
            progress.cancel()
            task.cancel()
        }
        var iterator = results.makeAsyncIterator()
        guard let response = try await iterator.next() else { throw CancellationError() }
        return response
    }
}

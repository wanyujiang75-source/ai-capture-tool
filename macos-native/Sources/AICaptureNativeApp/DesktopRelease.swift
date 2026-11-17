import Foundation

struct DesktopRelease: Equatable, Sendable {
    let title: String
    let notes: String
    let publishedAt: Date
    let isPreview: Bool
    let downloadURL: URL
    let checksumURL: URL?
}

struct DesktopReleaseCatalog: Sendable {
    private static let repository = "wanyujiang75-source/ai-capture-tool"
    static let releasesPage = URL(string: "https://github.com/\(repository)/releases")!
    private static let api = "https://api.github.com/repos/\(repository)/releases"

    private let load: @Sendable (URLRequest) async throws -> (Data, URLResponse)

    init(load: @escaping @Sendable (URLRequest) async throws -> (Data, URLResponse) = {
        try await URLSession.shared.data(for: $0)
    }) {
        self.load = load
    }

    func latest(includePreview: Bool) async throws -> DesktopRelease? {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let (stableData, stableResponse) = try await request(URL(string: Self.api + "/latest")!)
        if Self.rateLimited(stableResponse) { return try await latestFromFeed(includePreview: includePreview) }
        switch stableResponse.statusCode {
        case 200:
            let stable = try decoder.decode(GitHubRelease.self, from: stableData)
            if !stable.prerelease, let release = stable.desktopRelease { return release }
        case 404:
            break
        default:
            throw URLError(.badServerResponse)
        }

        guard includePreview else { return nil }
        let (previewData, previewResponse) = try await request(URL(string: Self.api + "?per_page=30")!)
        if Self.rateLimited(previewResponse) { return try await latestFromFeed(includePreview: includePreview) }
        guard previewResponse.statusCode == 200 else { throw URLError(.badServerResponse) }
        return try decoder.decode([GitHubRelease].self, from: previewData)
            .filter(\.prerelease)
            .compactMap(\.desktopRelease)
            .max { $0.publishedAt < $1.publishedAt }
    }

    private func latestFromFeed(includePreview: Bool) async throws -> DesktopRelease? {
        async let current = head(Self.releasesPage.appendingPathComponent("latest"))
        async let feed = request(URL(string: Self.releasesPage.absoluteString + ".atom")!, accept: "application/atom+xml")
        let (stable, (data, response)) = try await (current, feed)
        guard [200, 404].contains(stable.statusCode), response.statusCode == 200
        else { throw URLError(.badServerResponse) }

        let entries = try DesktopReleaseFeed.parse(data)
        if stable.statusCode == 200,
           let entry = entries.first(where: { !$0.asset.isPreview && $0.asset.releasePage == stable.url }),
           let release = try await downloadableRelease(entry) {
            return release
        }
        guard includePreview else { return nil }
        for entry in entries.filter({ $0.asset.isPreview }).sorted(by: { $0.publishedAt > $1.publishedAt }) {
            if let release = try await downloadableRelease(entry) { return release }
        }
        return nil
    }

    private func downloadableRelease(_ entry: DesktopReleaseFeed.Entry) async throws -> DesktopRelease? {
        let zip = try await head(entry.asset.zip)
        if zip.statusCode == 404 { return nil }
        guard zip.statusCode == 200 else { throw URLError(.badServerResponse) }
        let checksum = try? await head(entry.asset.checksum)
        return DesktopRelease(
            title: entry.title,
            notes: entry.notes,
            publishedAt: entry.publishedAt,
            isPreview: entry.asset.isPreview,
            downloadURL: entry.asset.zip,
            checksumURL: checksum?.statusCode == 200 ? entry.asset.checksum : nil
        )
    }

    private static func rateLimited(_ response: HTTPURLResponse) -> Bool {
        response.statusCode == 429
            || (response.statusCode == 403 && response.value(forHTTPHeaderField: "x-ratelimit-remaining") == "0")
    }

    private func head(_ url: URL) async throws -> HTTPURLResponse {
        try await request(url, method: "HEAD", accept: "*/*").1
    }

    private func request(
        _ url: URL, method: String = "GET", accept: String = "application/vnd.github+json"
    ) async throws -> (Data, HTTPURLResponse) {
        var request = URLRequest(url: url, timeoutInterval: 12)
        request.httpMethod = method
        request.setValue(accept, forHTTPHeaderField: "Accept")
        let (data, response) = try await load(request)
        guard let response = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        return (data, response)
    }
}

private struct GitHubRelease: Decodable {
    struct Asset: Decodable {
        let name: String
        let downloadURL: String

        enum CodingKeys: String, CodingKey {
            case name
            case downloadURL = "browser_download_url"
        }
    }

    let tag: String
    let name: String?
    let body: String?
    let publishedAt: Date?
    let prerelease: Bool
    let draft: Bool
    let assets: [Asset]

    enum CodingKeys: String, CodingKey {
        case name, body, prerelease, draft, assets
        case tag = "tag_name", publishedAt = "published_at"
    }

    var desktopRelease: DesktopRelease? {
        guard !draft, let publishedAt else { return nil }
        guard let asset = DesktopReleaseAsset(tag: tag, isPreview: prerelease),
              hasAsset(asset.zip) else { return nil }
        let trimmedTitle = name?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return DesktopRelease(
            title: trimmedTitle.isEmpty ? tag : trimmedTitle,
            notes: String((body ?? "").prefix(12_000)).trimmingCharacters(in: .whitespacesAndNewlines),
            publishedAt: publishedAt,
            isPreview: prerelease,
            downloadURL: asset.zip,
            checksumURL: hasAsset(asset.checksum) ? asset.checksum : nil
        )
    }

    private func hasAsset(_ url: URL) -> Bool {
        assets.contains { $0.name == url.lastPathComponent && $0.downloadURL == url.absoluteString }
    }
}

struct DesktopReleaseAsset {
    let isPreview: Bool
    let releasePage: URL
    let zip: URL
    let checksum: URL

    init?(tag: String, isPreview: Bool) {
        let zipName: String
        if isPreview {
            let prefix = "desktop-preview-"
            guard tag.hasPrefix(prefix) else { return nil }
            let version = tag.dropFirst(prefix.count)
            guard version.range(of: #"^[0-9]{8}-[0-9a-f]{7,40}$"#, options: .regularExpression) != nil else {
                return nil
            }
            zipName = "AI-Capture-Desktop-\(version)-development-arm64.zip"
        } else {
            guard tag.range(of: #"^v[0-9]+\.[0-9]+\.[0-9]+$"#, options: .regularExpression) != nil else {
                return nil
            }
            zipName = "AI-Capture-Desktop-\(tag.dropFirst())-arm64.zip"
        }

        self.isPreview = isPreview
        let releases = DesktopReleaseCatalog.releasesPage
        releasePage = releases.appendingPathComponent("tag").appendingPathComponent(tag)
        let download = releases.appendingPathComponent("download").appendingPathComponent(tag)
        zip = download.appendingPathComponent(zipName)
        checksum = download.appendingPathComponent(zipName + ".sha256")
    }
}

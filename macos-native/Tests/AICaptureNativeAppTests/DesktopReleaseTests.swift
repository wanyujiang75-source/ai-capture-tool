import Foundation
import Testing
@testable import AICaptureNativeApp

struct DesktopReleaseTests {
    @Test func stableReleaseProvidesNotesAndOnlyMatchingDesktopAssets() async throws {
        let tag = "v0.2.3"
        let title = "0.2.3 连接修复"
        let notes = "## 更新内容\n- 修复连接重试"
        let zip = "AI-Capture-Desktop-0.2.3-arm64.zip"
        let response = release(tag, title: title, notes: notes, assets: [
            asset(tag, "AI-Capture-Update-0.2.3-arm64.zip"),
            asset(tag, zip), asset(tag, zip + ".sha256")
        ])
        let catalog = try catalog(latest: response)
        let update = try #require(await catalog.latest(includePreview: true))

        #expect(update.title == title)
        #expect(update.notes == notes)
        #expect(update.downloadURL.lastPathComponent == zip)
        #expect(update.checksumURL?.lastPathComponent == zip + ".sha256")
        #expect(!update.isPreview)
    }

    @Test func previewsUsePublishTimeAndSkipDraftsAndExternalDownloads() async throws {
        let old = preview("20261116-aaaaaaa", published: "2026-11-16T06:10:26Z")
        let newest = preview("20261116-bbbbbbb", published: "2026-11-16T08:47:14Z")
        let external = preview("20261116-ccccccc", published: "2026-11-16T10:00:00Z", externalURL: true)
        let draft = preview("20261116-ddddddd", published: "2026-11-16T11:00:00Z", draft: true)
        let catalog = try catalog(previews: [old, external, newest, draft])

        let update = try #require(await catalog.latest(includePreview: true))
        #expect(update.isPreview)
        #expect(update.downloadURL.lastPathComponent == "AI-Capture-Desktop-20261116-bbbbbbb-development-arm64.zip")
        #expect(update.checksumURL == nil)
        #expect(try await catalog.latest(includePreview: false) == nil)
    }

    @Test func missingDesktopPackageDoesNotOfferTheUpdaterArchive() async throws {
        let tag = "v0.2.3"
        let catalog = try catalog(latest: release(tag, assets: [asset(tag, "AI-Capture-Update-0.2.3-arm64.zip")]))
        #expect(try await catalog.latest(includePreview: true) == nil)
    }

    @Test func githubFailureIsReportedSeparatelyFromMissingRelease() async throws {
        let catalog = try catalog(latestStatus: 403)
        await #expect(throws: URLError.self) {
            try await catalog.latest(includePreview: true)
        }
    }

    @Test func rateLimitedGitHubUsesPublicFeedAndChecksArchiveAvailability() async throws {
        let tag = "desktop-preview-20261116-bbbbbbb"
        let releasePage = DesktopReleaseCatalog.releasesPage
        let releaseURL = releasePage.appendingPathComponent("tag").appendingPathComponent(tag)
        let feed = """
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <link rel="alternate" href="\(releaseURL.absoluteString)"/>
            <title>发布说明</title>
            <updated>2026-11-16T08:47:14Z</updated>
            <content type="html">&lt;ul&gt;&lt;li&gt;修复连接&lt;/li&gt;&lt;/ul&gt;</content>
          </entry>
        </feed>
        """
        let catalog = DesktopReleaseCatalog { request in
            let url = try #require(request.url)
            let response: (Int, URL, [String: String]?, Data)
            if url.host == "api.github.com" {
                response = (403, url, ["x-ratelimit-remaining": "0"], Data())
            } else if url.lastPathComponent == "releases.atom" {
                response = (200, url, nil, Data(feed.utf8))
            } else {
                #expect(request.httpMethod == "HEAD")
                #expect(request.value(forHTTPHeaderField: "Accept") == "*/*")
                let missingChecksum = url.lastPathComponent.hasSuffix(".sha256")
                response = (missingChecksum ? 404 : 200, url.lastPathComponent == "latest" ? releasePage : url, nil, Data())
            }
            return (response.3, HTTPURLResponse(
                url: response.1, statusCode: response.0, httpVersion: nil, headerFields: response.2
            )!)
        }

        let update = try #require(await catalog.latest(includePreview: true))
        #expect(update.title == "发布说明")
        #expect(update.notes == "• 修复连接")
        #expect(update.downloadURL.lastPathComponent == "AI-Capture-Desktop-20261116-bbbbbbb-development-arm64.zip")
        #expect(update.checksumURL == nil)
    }

    private func catalog(
        latest: [String: Any]? = nil, latestStatus: Int? = nil, previews: [[String: Any]] = []
    ) throws -> DesktopReleaseCatalog {
        let latestData = try JSONSerialization.data(withJSONObject: latest ?? [:])
        let latestCode = latestStatus ?? (latest == nil ? 404 : 200)
        let previewsData = try JSONSerialization.data(withJSONObject: previews)
        return DesktopReleaseCatalog { request in
            let url = try #require(request.url)
            #expect(url.host == "api.github.com")
            if url.lastPathComponent == "latest" {
                return (latestData, HTTPURLResponse(url: url, statusCode: latestCode, httpVersion: nil, headerFields: nil)!)
            }
            #expect(url.lastPathComponent == "releases")
            return (previewsData, HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil, headerFields: nil)!)
        }
    }

    private func asset(_ tag: String, _ name: String, externalURL: Bool = false) -> [String: Any] {
        let base = externalURL ? "https://example.com" : "https://github.com/wanyujiang75-source/ai-capture-tool/releases/download"
        return ["name": name, "browser_download_url": "\(base)/\(tag)/\(name)"]
    }

    private func preview(_ version: String, published: String, externalURL: Bool = false, draft: Bool = false) -> [String: Any] {
        let tag = "desktop-preview-\(version)"
        return release(tag, date: published, prerelease: true, draft: draft, assets: [
            asset(tag, "AI-Capture-Desktop-\(version)-development-arm64.zip", externalURL: externalURL)
        ])
    }

    private func release(
        _ tag: String, title: String = "", notes: String = "", date: String = "2026-11-16T10:00:00Z",
        prerelease: Bool = false, draft: Bool = false, assets: [[String: Any]]
    ) -> [String: Any] {
        ["tag_name": tag, "name": title, "body": notes, "published_at": date,
         "prerelease": prerelease, "draft": draft, "assets": assets]
    }
}

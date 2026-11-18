import Foundation
import Testing
@testable import AICaptureNativeApp

struct DesktopVersionTests {
    @Test func onlyHigherVersionsOfferDownloads() {
        let installed = InstalledDesktopVersion(version: "1.0.0", buildID: "aaaaaaa11111")
        #expect(installed.availability(for: preview(title: "抓包工具桌面预览版 v1.0.0")) == .current)
        #expect(installed.availability(for: preview(title: "抓包工具桌面预览版 v0.9.9")) == .current)
        #expect(installed.availability(for: preview(title: "抓包工具桌面预览版 v1.0.1")) == .newer)
        #expect(installed.availability(for: preview(title: "抓包工具桌面预览版 v1.2.0")) == .newer)
    }

    @Test func stableTagsCompareNumericComponents() {
        let installed = InstalledDesktopVersion(version: "1.9.9", buildID: nil)
        let stable = release(tag: "v1.10.0", title: "正式版更新说明", isPreview: false)
        #expect(installed.availability(for: stable) == .newer)
    }

    @Test func legacyReleasesCanConfirmMatchingBuildWithoutInferringAnUpgrade() {
        let legacy = preview(title: "抓包工具 Desktop Preview · 更新入口")
        let legacyInstall = InstalledDesktopVersion(version: "0.1.0", buildID: "bbbbbbb67890")
        let otherLegacyInstall = InstalledDesktopVersion(version: "0.1.0", buildID: "ccccccc67890")
        let installed = InstalledDesktopVersion(version: "1.0.0", buildID: "aaaaaaa11111")
        #expect(legacyInstall.availability(for: legacy) == .current)
        #expect(otherLegacyInstall.availability(for: legacy) == .unknown)
        #expect(installed.availability(for: legacy) == .current)
        #expect(legacyInstall.availability(for: preview(title: "抓包工具桌面预览版 v1.0.0")) == .newer)
    }

    @Test func versionRequiresThreeCanonicalNumericComponents() {
        #expect(DesktopVersion("1.0.0")?.description == "1.0.0")
        #expect(DesktopVersion("1.0") == nil)
        #expect(DesktopVersion("01.0.0") == nil)
        #expect(DesktopVersion("1.0.0.1") == nil)
        #expect(DesktopVersion("1.2.beta") == nil)
    }

    private func preview(title: String) -> DesktopRelease {
        release(tag: "desktop-preview-20261118-bbbbbbb", title: title, isPreview: true)
    }

    private func release(tag: String, title: String, isPreview: Bool) -> DesktopRelease {
        let asset = DesktopReleaseAsset(tag: tag, isPreview: isPreview)!
        return DesktopRelease(title: title, notes: "", publishedAt: .distantPast, isPreview: isPreview,
                              downloadURL: asset.zip, checksumURL: asset.checksum)
    }
}

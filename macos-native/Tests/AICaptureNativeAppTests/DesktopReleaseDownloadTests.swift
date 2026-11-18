import Foundation
import Testing
@testable import AICaptureNativeApp

struct DesktopReleaseDownloadTests {
    @Test func verifiedArchiveIsSavedWithoutOverwritingAnExistingCopy() throws {
        let fixture = try Fixture()
        defer { fixture.remove() }
        let existing = fixture.folder.appendingPathComponent(fixture.release.downloadURL.lastPathComponent)
        try Data("previous download".utf8).write(to: existing)

        let saved = try fixture.save()

        #expect(saved.deletingLastPathComponent().path == fixture.folder.path)
        #expect(saved.lastPathComponent == "AI-Capture-Desktop-1.0.1-arm64 (2).zip")
        #expect(try Data(contentsOf: saved) == fixture.archiveData)
        #expect(try Data(contentsOf: existing) == Data("previous download".utf8))
    }

    @Test func aMismatchedArchiveIsNeverSaved() throws {
        let fixture = try Fixture()
        defer { fixture.remove() }
        try Data("damaged archive".utf8).write(to: fixture.temporaryFile)

        #expect(throws: DesktopReleaseDownload.Failure.checksumMismatch) {
            try fixture.save()
        }
        #expect(try FileManager.default.contentsOfDirectory(atPath: fixture.folder.path).isEmpty)
    }

    @Test func checksumMustNameTheRequestedArchive() throws {
        let fixture = try Fixture()
        defer { fixture.remove() }
        let wrongName = Data(fixture.checksum.replacingOccurrences(of: "1.0.1", with: "1.0.2").utf8)

        #expect(throws: DesktopReleaseDownload.Failure.invalidChecksum) {
            try DesktopReleaseDownload.Checksum(wrongName, filename: fixture.release.downloadURL.lastPathComponent)
        }
    }

    private struct Fixture {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        let archiveData = Data("abc".utf8)
        let release: DesktopRelease
        var folder: URL { root.appendingPathComponent("Downloads", isDirectory: true) }
        var temporaryFile: URL { root.appendingPathComponent("temporary") }
        var checksum: String {
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad  \(release.downloadURL.lastPathComponent)\n"
        }

        init() throws {
            let asset = try #require(DesktopReleaseAsset(tag: "v1.0.1", isPreview: false))
            release = DesktopRelease(
                title: "1.0.1", notes: "", publishedAt: .distantPast, isPreview: false,
                downloadURL: asset.zip, checksumURL: asset.checksum
            )
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            try archiveData.write(to: temporaryFile)
        }

        func save() throws -> URL {
            let parsed = try DesktopReleaseDownload.Checksum(Data(checksum.utf8), filename: release.downloadURL.lastPathComponent)
            return try DesktopReleaseDownload.saveVerifiedArchive(
                at: temporaryFile, in: folder, checksum: parsed, release: release
            )
        }

        func remove() {
            try? FileManager.default.removeItem(at: root)
        }
    }
}

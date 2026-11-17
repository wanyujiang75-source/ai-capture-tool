import Foundation
import Testing
@testable import AICaptureNativeApp

@MainActor
struct DesktopUpdateTests {
    @Test func updateDefersDuringCaptureOrPendingLocalWork() async throws {
        let directory = try makeRuntime()
        defer { try? FileManager.default.removeItem(at: directory) }
        let busy = await DesktopUpdateSafety.blocker(runtime: directory, pendingWork: { true }) {
            Issue.record("Updating must wait for pending local work")
            return false
        }
        #expect(busy == .captureBusy)
        let recording = await DesktopUpdateSafety.blocker(runtime: directory, pendingWork: { false }) { true }
        #expect(recording == .captureBusy)
    }

    @Test func updateDefersUntilEachPhoneHasRecovered() async throws {
        let directory = try makeRuntime()
        defer { try? FileManager.default.removeItem(at: directory) }
        for relativePath in ["android-physical/recovery.json", "android-physical/pending-recovery/device.json",
                             "ios-setup/cleanup-required"] {
            let path = directory.appendingPathComponent(relativePath)
            try FileManager.default.createDirectory(at: path.deletingLastPathComponent(), withIntermediateDirectories: true)
            try Data().write(to: path)
            let blocker = await DesktopUpdateSafety.blocker(runtime: directory, pendingWork: { false }) { false }
            #expect(blocker == .phoneNeedsRecovery)
            try FileManager.default.removeItem(at: path)
        }
    }

    @Test func updateRequiresRecentVerifiedBackendState() async throws {
        let directory = try makeRuntime()
        defer { try? FileManager.default.removeItem(at: directory) }
        let unavailable = await DesktopUpdateSafety.blocker(runtime: directory, pendingWork: { false }) {
            throw URLError(.cannotConnectToHost)
        }
        #expect(unavailable == .backendUnavailable)
        let ready = await DesktopUpdateSafety.blocker(runtime: directory, pendingWork: { false }) { false }
        #expect(ready == nil)
        var pending = false
        let raced = await DesktopUpdateSafety.blocker(runtime: directory, pendingWork: { pending }) {
            pending = true
            return false
        }
        #expect(raced == .captureBusy)
    }

    @Test func updateStatusBelongsToSameDesktopBuildAndRuntime() throws {
        let runtime = try makeRuntime()
        defer { try? FileManager.default.removeItem(at: runtime) }
        let data = try JSONSerialization.data(withJSONObject: [
            "capture_active": false,
            "desktop": ["enabled": true, "build_id": "build-a", "runtime_dir": runtime.path],
        ])
        let status = try JSONDecoder().decode(DesktopUpdateBackendStatus.self, from: data)
        #expect(status.matches(buildID: "build-a", runtime: runtime))
        #expect(!status.matches(buildID: "build-b", runtime: runtime))
        #expect(!status.matches(buildID: "build-a", runtime: runtime.appendingPathComponent("another-runtime")))
    }

    private func makeRuntime() throws -> URL {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        return directory
    }
}

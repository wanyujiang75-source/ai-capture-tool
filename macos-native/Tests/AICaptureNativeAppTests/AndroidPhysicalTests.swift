import Foundation
import Testing
@testable import AICaptureNativeApp

@MainActor
struct AndroidPhysicalTests {
    @Test func returningFromFlowsKeepsPhysicalSelectionAndController() {
        let state = AppState()
        state.selectedAndroidCaptureTarget = .physical
        state.androidPhysicalController.consent = true
        state.androidPhysicalController.serial = "test-phone"
        let controller = state.androidPhysicalController
        state.selectedSection = .flows
        state.selectedSection = .capture
        #expect(state.selectedAndroidCaptureTarget == .physical)
        #expect(state.androidPhysicalController === controller)
        #expect(state.androidPhysicalController.consent)
        #expect(state.androidPhysicalController.serial == "test-phone")
    }
    @Test func recoveryBlocksNewCapture() {
        let status = AndroidPhysicalStatus(phase: .recoveryRequired)
        #expect(!status.canStart)
        #expect(status.action == .recover)
        #expect(status.title == "原网络尚未恢复")
    }
    @Test func permissionWaitAllowsCancellationNotSecondStart() {
        let status = AndroidPhysicalStatus(phase: .waitingVPN)
        #expect(!status.canStart)
        #expect(status.action == .stop)
        #expect(status.title == "等待手机授权")
    }
    @Test func unknownPhaseDoesNotEnableCapture() throws {
        let data = Data("{\"phase\":\"future_state\"}".utf8)
        let status = try JSONDecoder().decode(AndroidPhysicalStatus.self, from: data)
        #expect(!status.canStart)
    }
    @Test func physicalArchiveHasOwnLabelAndIncrementalPagination() {
        let source = CaptureSource(id: 1, platform: "android", status: "running", appName: "PokeHub", mode: "android-physical-wireguard")
        #expect(source.platformLabel == "Android 真机")
        #expect(!source.isIOS)
        #expect(source.usesRevisionArchive)
    }

    @Test func pollingDetectsReplacementWithoutRelabelingOldTask() async throws {
        let api = PhysicalSwitchAPI()
        await api.set(status: AndroidPhysicalStatus(phase: .recoveryRequired, serial: "old"), devices: [newPhone])
        let controller = AndroidPhysicalController(api: api)
        controller.serial = "old"
        await controller.refresh()
        #expect(controller.devices.map(\.serial) == ["new"])
        #expect(controller.serial == "old")
        #expect(!controller.canPerform)
    }

    @Test func terminationResetsConsentAndDiscoversNewDeviceWithoutStartingCapture() async throws {
        let api = PhysicalSwitchAPI()
        let controller = AndroidPhysicalController(api: api)
        controller.serial = "old"
        controller.consent = true
        await api.set(status: AndroidPhysicalStatus(phase: .recoveryRequired, serial: "old"), devices: [newPhone])
        await controller.refresh()
        await controller.terminate()
        #expect(!controller.consent)
        #expect(controller.status.phase == .terminating)
        #expect(!controller.canPerform)
        await api.set(status: AndroidPhysicalStatus(phase: .idle), devices: [newPhone])
        await controller.refresh()
        #expect(controller.serial == "new")
        #expect(await api.actions == ["terminate"])
        #expect(await api.starts == 0)
    }

    @Test func pendingRecoveryBlocksOnlyItsOwnPhoneAndSurvivesQuitCheck() async throws {
        let api = PhysicalSwitchAPI()
        let data = Data(#"{"phase":"idle","pending_recoveries":[{"serial":"old","name":"Old phone"}]}"#.utf8)
        await api.set(status: try JSONDecoder().decode(AndroidPhysicalStatus.self, from: data), devices: [oldPhone, newPhone])
        let controller = AndroidPhysicalController(api: api)
        controller.serial = "old"
        controller.consent = true
        await controller.refresh()
        #expect(!controller.canPerform)
        #expect(controller.canRecover("old"))
        controller.serial = "new"
        #expect(controller.canPerform)
        #expect(!controller.canRecover("new"))
        await controller.recover("old")
        #expect(await api.actions == ["recover:old"])
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let pending = root.appendingPathComponent("android-physical/pending-recovery")
        try FileManager.default.createDirectory(at: pending, withIntermediateDirectories: true)
        try data.write(to: pending.appendingPathComponent("record.json"))
        #expect(AndroidPhysicalQuitSafety.requiresWarning(runtimeDirectory: root))
    }

    @Test func stalePollCannotOverwriteTermination() async throws {
        let api = PhysicalSwitchAPI()
        let controller = AndroidPhysicalController(api: api)
        await api.set(status: AndroidPhysicalStatus(phase: .capturing, serial: "old"), devices: [oldPhone])
        await controller.refresh()
        await api.pauseNextRead()
        let poll = Task { await controller.refresh() }
        while !(await api.readIsWaiting) { await Task.yield() }
        await controller.terminate()
        await api.resumeRead()
        await poll.value
        #expect(controller.status.phase == .terminating)
    }

    private var oldPhone: AndroidPhysicalDevice { AndroidPhysicalDevice(serial: "old", model: "Old phone", status: "device") }
    private var newPhone: AndroidPhysicalDevice { AndroidPhysicalDevice(serial: "new", model: "New phone", status: "device") }
}

private actor PhysicalSwitchAPI: AndroidPhysicalAPI {
    var value = AndroidPhysicalStatus(phase: .idle)
    var devices: [AndroidPhysicalDevice] = []
    var actions: [String] = []
    var starts = 0
    var paused = false
    var continuation: CheckedContinuation<Void, Never>?
    var readIsWaiting: Bool { continuation != nil }
    func set(status: AndroidPhysicalStatus, devices: [AndroidPhysicalDevice]) { value = status; self.devices = devices }
    func pauseNextRead() { paused = true }
    func resumeRead() { continuation?.resume(); continuation = nil }
    func readAndroidPhysical() async throws -> AndroidPhysicalStatus {
        let snapshot = value
        if paused { paused = false; await withCheckedContinuation { continuation = $0 } }
        return snapshot
    }
    func discoverAndroidPhysical() async throws -> [AndroidPhysicalDevice] { devices }
    func startAndroidPhysical(serial: String, consent: Bool) async throws -> AndroidPhysicalStatus { starts += 1; return value }
    func actAndroidPhysical(_ action: String) async throws -> AndroidPhysicalStatus {
        actions.append(action)
        return AndroidPhysicalStatus(phase: .terminating)
    }
    func recoverAndroidPhysical(serial: String) async throws -> AndroidPhysicalStatus {
        actions.append("recover:" + serial)
        return AndroidPhysicalStatus(phase: .stopping, serial: serial)
    }
}

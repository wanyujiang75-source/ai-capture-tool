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
}

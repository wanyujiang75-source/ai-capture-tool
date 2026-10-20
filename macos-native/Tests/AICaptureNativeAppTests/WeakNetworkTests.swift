import Foundation
import Testing
@testable import AICaptureNativeApp

private actor NetworkAPI: WeakNetworkAPI {
    var applied: [(String, WeakNetworkProfile)] = []
    var restored: [String] = []
    var failure = false
    var delayed: CheckedContinuation<WeakNetworkStatus, Never>?
    var delayNext = false
    var state = WeakNetworkStatus.normal

    func fail() { failure = true }
    func holdNext() { delayNext = true }
    func setState(_ state: WeakNetworkStatus) { self.state = state }
    func readWeakNetwork(deviceID: String) async throws -> WeakNetworkStatus { state }
    func applyWeakNetwork(deviceID: String, profile: WeakNetworkProfile) async throws -> WeakNetworkStatus {
        applied.append((deviceID, profile))
        if failure { throw APIClientError.httpStatus(500, "raw failure") }
        if delayNext {
            return await withCheckedContinuation { delayed = $0 }
        }
        state = .init(enabled: true, pendingRestore: false, available: true, profile: profile,
                      message: "弱网已开启", technicalDetail: "")
        return state
    }
    func restoreWeakNetwork(deviceID: String) async throws -> WeakNetworkStatus {
        restored.append(deviceID)
        if failure { throw APIClientError.httpStatus(500, "raw failure") }
        state = .normal
        return state
    }
    func waitForRequest() async { while delayed == nil { await Task.yield() } }
    func finish() { delayed?.resume(returning: .normal); delayed = nil }
}

@MainActor
struct WeakNetworkTests {
    @Test func startsUnlimitedWithoutMutatingDevice() async {
        let api = NetworkAPI()
        let controller = WeakNetworkController(api: api)
        await controller.selectDevice("one")
        #expect(controller.preset == "unlimited")
        #expect(controller.profile == nil)
        #expect(controller.status == .normal)
        #expect(await api.applied.isEmpty)
        #expect(await api.restored.isEmpty)
    }

    @Test func unlimitedRestoresInsteadOfApplyingALargeBandwidth() async {
        let api = NetworkAPI()
        let controller = WeakNetworkController(api: api)
        await controller.selectDevice("one")
        controller.choosePreset("2g")
        await controller.apply()
        controller.choosePreset("unlimited")
        await controller.apply()
        #expect(await api.applied.count == 1)
        #expect(await api.restored == ["one"])
        #expect(controller.status == .normal)
        #expect(controller.preset == "unlimited")
    }

    @Test func appliesEveryCellularPresetAndRestoresSelection() async {
        let api = NetworkAPI()
        let controller = WeakNetworkController(api: api)
        await controller.selectDevice("one")
        let profiles: [(String, WeakNetworkProfile)] = [
            ("2g", .init(uploadKbps: 128, downloadKbps: 256, latencyMs: 600)),
            ("3g", .init(uploadKbps: 512, downloadKbps: 2048, latencyMs: 150)),
            ("4g", .init(uploadKbps: 5000, downloadKbps: 10000, latencyMs: 50)),
        ]
        for (preset, profile) in profiles {
            controller.choosePreset(preset)
            await controller.apply()
            #expect(await api.applied.last?.1 == profile)
            #expect(controller.status?.profile == profile)
            #expect(controller.status?.enabled == true)
        }
        await controller.restore()
        #expect(controller.status == .normal)
        #expect(await api.restored == ["one"])
        #expect(controller.preset == "unlimited")
    }

    @Test func refreshReflectsActivePresetWithoutOverwritingPendingSelection() async {
        let api = NetworkAPI()
        let profile = WeakNetworkProfile(uploadKbps: 128, downloadKbps: 256, latencyMs: 600)
        await api.setState(.init(enabled: true, pendingRestore: false, available: true,
                                 profile: profile, message: "enabled", technicalDetail: ""))
        let controller = WeakNetworkController(api: api)
        await controller.selectDevice("one")
        #expect(controller.preset == "2g")
        controller.choosePreset("4g")
        await controller.refresh()
        #expect(controller.preset == "4g")
        #expect(controller.status?.profile == profile)
        #expect(await api.applied.isEmpty)
    }

    @Test func failedRestoreDoesNotClaimUnlimited() async {
        let api = NetworkAPI()
        let controller = WeakNetworkController(api: api)
        await controller.selectDevice("one")
        controller.choosePreset("2g")
        await controller.apply()
        await api.fail()
        await controller.restore()
        #expect(controller.preset == "2g")
        #expect(controller.status == nil)
        #expect(controller.issue == AppCopy.WeakNetwork.connectionFailed)
    }

    @Test func connectionErrorDoesNotExposeRawResponse() async {
        let api = NetworkAPI()
        await api.fail()
        let controller = WeakNetworkController(api: api)
        await controller.selectDevice("one")
        controller.choosePreset("3g")
        await controller.apply()
        #expect(controller.issue == AppCopy.WeakNetwork.connectionFailed)
        #expect(!controller.busy)
    }

    @Test func switchingDeviceRejectsPreviousInFlightResult() async {
        let api = NetworkAPI()
        await api.holdNext()
        let controller = WeakNetworkController(api: api)
        await controller.selectDevice("one")
        controller.choosePreset("4g")
        let task = Task { await controller.apply() }
        await api.waitForRequest()
        await controller.selectDevice("two")
        await api.finish()
        await task.value
        #expect(controller.deviceID == "two")
        #expect(controller.status == .normal)
        #expect(controller.preset == "unlimited")
        #expect(!controller.busy)
    }
}

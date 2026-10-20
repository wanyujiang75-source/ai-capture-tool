import Foundation
import Testing
@testable import AICaptureNativeApp

private actor NetworkAPI: WeakNetworkAPI {
    var applied: [(String, WeakNetworkProfile)] = []
    var restored: [String] = []
    var failure = false
    var delayed: CheckedContinuation<WeakNetworkStatus, Never>?
    var delayNext = false

    func fail() { failure = true }
    func holdNext() { delayNext = true }
    func readWeakNetwork(deviceID: String) async throws -> WeakNetworkStatus { .normal }
    func applyWeakNetwork(deviceID: String, profile: WeakNetworkProfile) async throws -> WeakNetworkStatus {
        applied.append((deviceID, profile))
        if failure { throw APIClientError.httpStatus(500, "raw failure") }
        if delayNext {
            return await withCheckedContinuation { delayed = $0 }
        }
        return .init(enabled: true, pendingRestore: false, available: true, profile: profile,
                     message: "弱网已开启", technicalDetail: "")
    }
    func restoreWeakNetwork(deviceID: String) async throws -> WeakNetworkStatus {
        restored.append(deviceID)
        return .normal
    }
    func waitForRequest() async { while delayed == nil { await Task.yield() } }
    func finish() { delayed?.resume(returning: .normal); delayed = nil }
}

@MainActor
struct WeakNetworkTests {
    @Test func unchangedFieldWritesPreservePreset() {
        let controller = WeakNetworkController(api: NetworkAPI())
        for preset in ["light", "severe"] {
            controller.choosePreset(preset)
            controller.editValue(controller.upload, at: \.upload)
            controller.editValue(controller.download, at: \.download)
            controller.editValue(controller.latency, at: \.latency)
            #expect(controller.preset == preset)
        }
        controller.editValue("1024", at: \.download)
        #expect(controller.preset == "custom")
        #expect(controller.download == "1024")
    }

    @Test func normalPresetRestoresInsteadOfApplyingPreviousInputs() async {
        let api = NetworkAPI()
        let controller = WeakNetworkController(api: api)
        await controller.selectDevice("one")
        controller.choosePreset("severe")
        await controller.apply()
        controller.choosePreset("normal")
        await controller.apply()
        #expect(await api.applied.count == 1)
        #expect(await api.restored == ["one"])
        #expect(controller.status == .normal)
    }

    @Test func appliesCustomSettingsAndRestores() async {
        let api = NetworkAPI()
        let controller = WeakNetworkController(api: api)
        await controller.selectDevice("one")
        controller.upload = "128"
        controller.download = "256"
        controller.latency = "600"
        await controller.apply()
        #expect(controller.status?.enabled == true)
        #expect(await api.applied.first?.1 == WeakNetworkProfile(uploadKbps: 128, downloadKbps: 256, latencyMs: 600))
        await controller.restore()
        #expect(controller.status == .normal)
        #expect(await api.restored == ["one"])
    }

    @Test func invalidInputNeverReachesDevice() async {
        let api = NetworkAPI()
        let controller = WeakNetworkController(api: api)
        await controller.selectDevice("one")
        controller.upload = "0"
        await controller.apply()
        #expect(await api.applied.isEmpty)
        #expect(controller.issue == AppCopy.WeakNetwork.invalidInput)
    }

    @Test func connectionErrorDoesNotExposeRawResponse() async {
        let api = NetworkAPI()
        await api.fail()
        let controller = WeakNetworkController(api: api)
        await controller.selectDevice("one")
        await controller.apply()
        #expect(controller.issue == AppCopy.WeakNetwork.connectionFailed)
        #expect(!controller.busy)
    }

    @Test func switchingDeviceRejectsPreviousInFlightResult() async {
        let api = NetworkAPI()
        await api.holdNext()
        let controller = WeakNetworkController(api: api)
        await controller.selectDevice("one")
        let task = Task { await controller.apply() }
        await api.waitForRequest()
        await controller.selectDevice("two")
        await api.finish()
        await task.value
        #expect(controller.deviceID == "two")
        #expect(controller.status == .normal)
        #expect(!controller.busy)
    }
}

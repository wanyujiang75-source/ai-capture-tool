import Foundation
import Testing
@testable import AICaptureNativeApp

private actor NodeAPI: IOSShadowrocketAPI {
    var info = IOSShadowrocketInfo(host: "192.168.1.2", port: 9000, username: "ios", password: "fake-only",
        importURL: "shadowrocket://add/http://fake?remarks=Capture-Mac",
        profilePath: "/tmp/ios-setup/session-test/shadowrocket/iPhone.mobileconfig",
        devices: [IOSNodeDevice(id: "one", name: "First")])
    var failing = false
    var manual = false
    var sends: [String] = []
    var pending: CheckedContinuation<IOSShadowrocketInfo, any Error>?
    var holdsRead = false
    func readShadowrocket() async throws -> IOSShadowrocketInfo {
        if failing { throw APIClientError.httpStatus(500, "raw password token") }
        if holdsRead { return try await withCheckedThrowingContinuation { pending = $0 } }
        return info
    }
    func importShadowrocket(deviceID: String) async throws -> IOSNodeDelivery {
        sends.append(deviceID)
        if failing { throw APIClientError.httpStatus(500, "raw password token") }
        return IOSNodeDelivery(state: manual ? .manualRequired : .confirmationRequired)
    }
    func setFailure() { failing = true }
    func setManual() { manual = true }
    func setMultiple() { info.devices.append(IOSNodeDevice(id: "two", name: "Second")) }
    func hold() { holdsRead = true }
    func complete() { pending?.resume(returning: info); pending = nil }
    var hasPending: Bool { pending != nil }
}

@MainActor
struct IOSShadowrocketTests {
    @Test func oneDeviceIsPreselectedButDiscoveryDoesNotImportOrConnect() async {
        let api = NodeAPI()
        let controller = IOSShadowrocketController(api: api)
        await controller.load()
        #expect(controller.selectedDeviceID == "one")
        #expect(await api.sends == [])
        await controller.send()
        #expect(await api.sends == ["one"])
        #expect(controller.delivery == .confirmationRequired)
        #expect(!controller.sending)
    }

    @Test func multipleDevicesRequireAnExplicitChoice() async {
        let api = NodeAPI()
        await api.setMultiple()
        let controller = IOSShadowrocketController(api: api)
        await controller.load()
        #expect(controller.selectedDeviceID == nil)
        await controller.send()
        #expect(await api.sends == [])
        controller.selectedDeviceID = "two"
        await controller.send()
        #expect(await api.sends == ["two"])
    }

    @Test func failedRefreshClearsCredentialsAndImportFailureOffersManualFallback() async {
        let api = NodeAPI()
        let controller = IOSShadowrocketController(api: api)
        await controller.load()
        await api.setManual()
        await controller.send()
        #expect(controller.delivery == .manualRequired)
        #expect(controller.info != nil)
        await api.setFailure()
        await controller.send()
        #expect(controller.delivery == nil)
        #expect(controller.info == nil)
        await controller.load()
        #expect(controller.info == nil)
        #expect(controller.issue == AppCopy.IOSSetup.nodeLoadFailed)
        #expect(controller.issue?.contains("raw password") == false)
    }

    @Test func staleReadCannotRestoreSecretsAfterConnectionEnds() async {
        let api = NodeAPI()
        await api.hold()
        let controller = IOSShadowrocketController(api: api)
        let task = Task { await controller.load() }
        while !(await api.hasPending) { await Task.yield() }
        #expect(controller.loading)
        #expect(controller.info == nil)
        #expect(!controller.sending)
        controller.clear()
        await api.complete()
        await task.value
        #expect(controller.info == nil)
        #expect(!controller.loading)
    }

    @Test func shareAndImportValuesCannotPointToArbitraryFilesOrApps() throws {
        let raw = #"{"host":"192.168.1.2","port":9000,"username":"ios","password":"fake","import_url":"shadowrocket://connect","profile_path":"/tmp/secret.txt","devices":[]}"#
        let info = try JSONDecoder().decode(IOSShadowrocketInfo.self, from: Data(raw.utf8))
        #expect(info.profileURL == nil)
        #expect(info.safeImportURL == nil)
    }
}

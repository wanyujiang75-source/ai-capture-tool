import Foundation
import Testing
@testable import AICaptureNativeApp

private actor SetupAPI: IOSSetupAPI {
    var value = IOSSetupStatus(phase: .waitingPhone)
    var failure = false
    var prepares = 0
    func readIOSSetup() async throws -> IOSSetupStatus { value }
    func prepareIOSSetup(ssid: String) async throws -> IOSSetupStatus {
        prepares += 1
        if failure { throw APIClientError.httpStatus(500, "Frida HTTP 409 raw token") }
        return value
    }
    func stopIOSSetup() async throws -> IOSSetupStatus { IOSSetupStatus(phase: .stopped) }
    func fail() { failure = true }
    func set(_ status: IOSSetupStatus) { value = status }
}

@MainActor
struct IOSSetupTests {
    @Test func stoppedSessionDoesNotOverwriteEditedNetworkName() {
        let status = IOSSetupStatus(phase: .stopped, ssid: "Old Wi-Fi")
        #expect(status.configuredSSID == nil)
        #expect(IOSSetupStatus(phase: .waitingPhone, ssid: "Active").configuredSSID == "Active")
    }

    @Test func successfulPreparationStillRequiresPhoneAction() async {
        let controller = IOSSetupController(api: SetupAPI())
        await controller.prepare(ssid: "Office")
        #expect(controller.status.phase == .waitingPhone)
        #expect(!controller.status.hasCapturedTraffic)
        #expect(controller.status.requiresPhoneSetup)
    }

    @Test func httpsReadyIsNotApplicationCapture() async {
        let api = SetupAPI()
        await api.set(IOSSetupStatus(phase: .ready))
        let controller = IOSSetupController(api: api)
        await controller.refresh()
        #expect(!controller.status.hasCapturedTraffic)
        #expect(!controller.status.requiresPhoneSetup)
        await api.set(IOSSetupStatus(phase: .capturing, flowCount: 1))
        await controller.refresh()
        #expect(controller.status.hasCapturedTraffic)
    }

    @Test func stopRequiresExplicitPhoneCleanupAndPreservesActiveStateWithoutIt() async {
        let controller = IOSSetupController(api: SetupAPI())
        await controller.prepare(ssid: "Office")
        await controller.stop(phoneConfigurationRemoved: false)
        #expect(controller.status.phase == .waitingPhone)
        await controller.stop(phoneConfigurationRemoved: true)
        #expect(controller.status.phase == .stopped)
        #expect(controller.profileURL == nil)
    }

    @Test func invalidSSIDNeverStartsAndRawErrorsAreNotShown() async {
        let api = SetupAPI()
        let controller = IOSSetupController(api: api)
        await controller.prepare(ssid: "")
        #expect(await api.prepares == 0)
        await api.fail()
        await controller.prepare(ssid: "Office")
        #expect(controller.issue == AppCopy.IOSSetup.failed)
        #expect(!controller.busy)
    }

    @Test func profileSharingOnlyAcceptsExpectedLocalConfigurationFile() async {
        let api = SetupAPI()
        let controller = IOSSetupController(api: api)
        await api.set(IOSSetupStatus(phase: .waitingPhone, profilePath: "/tmp/secret.txt"))
        await controller.refresh()
        #expect(controller.profileURL == nil)
        await api.set(IOSSetupStatus(phase: .waitingPhone, profilePath: "/tmp/ios-setup/session-test/iPhone.mobileconfig"))
        await controller.refresh()
        #expect(controller.profileURL?.lastPathComponent == "iPhone.mobileconfig")
    }
}

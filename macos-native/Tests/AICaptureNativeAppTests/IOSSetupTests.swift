import Foundation
import Testing
@testable import AICaptureNativeApp

private actor SetupAPI: IOSSetupAPI {
    var value = IOSSetupStatus(phase: .waitingPhone)
    var failure = false
    var errorBody = "Frida HTTP 409 raw token"
    var prepares = 0
    func readIOSSetup() async throws -> IOSSetupStatus { value }
    func prepareIOSSetup(ssid: String) async throws -> IOSSetupStatus {
        prepares += 1
        if failure { throw APIClientError.httpStatus(500, errorBody) }
        return value
    }
    func stopIOSSetup() async throws -> IOSSetupStatus { IOSSetupStatus(phase: .stopped) }
    func fail() { failure = true }
    func failWithCode(_ code: String) {
        failure = true
        errorBody = "{\"detail\":{\"code\":\"\(code)\",\"user_message\":\"raw private error\"}}"
    }
    func set(_ status: IOSSetupStatus) { value = status }
}

@MainActor
struct IOSSetupTests {
    @Test func resumedIdentityAllowsReconnectWithoutClaimingPhoneReady() async throws {
        let json = Data(#"{"phase":"failed","flow_count":0,"flows":[],"can_resume":true,"identity_reused":true,"ssid":"Office"}"#.utf8)
        let saved = try JSONDecoder().decode(IOSSetupStatus.self, from: json)
        #expect(saved.canPrepare)
        #expect(saved.ssid == "Office")
        #expect(saved.configuredSSID == nil)
        #expect(!saved.isConnected)
        #expect(!saved.isRecording)
        #expect(AppCopy.IOSCapture.presentation(saved).0 == "iPhone 连接已暂停")
        let api = SetupAPI()
        await api.set(saved)
        let controller = IOSSetupController(api: api)
        await controller.refresh()
        await api.set(IOSSetupStatus(phase: .waitingPhone, identityReused: true))
        await controller.prepare(ssid: "Office")
        #expect(await api.prepares == 1)
        #expect(!controller.status.isConnected)
        #expect(AppCopy.IOSCapture.presentation(controller.status).0 == "等待手机重新验证")
    }

    @Test func legacyCleanupAndChangedRouteAreNotMisrepresentedAsReusableConnection() throws {
        let legacy = IOSSetupStatus(phase: .failed)
        #expect(!legacy.canPrepare)
        #expect(AppCopy.IOSCapture.presentation(legacy).0 == "测试代理已中断")
        let changed = try JSONDecoder().decode(IOSSetupStatus.self, from: Data(#"{"phase":"waiting_phone","flow_count":0,"flows":[],"identity_reused":true,"route_changed":true}"#.utf8))
        #expect(AppCopy.IOSCapture.presentation(changed).0 == "请更新手机抓包地址")
        #expect(!changed.isConnected)
    }

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

    @Test func keychainFailureExplainsRecoveryAndSurvivesStatusPoll() async {
        let api = SetupAPI()
        await api.failWithCode("ios_pairing_storage")
        let controller = IOSSetupController(api: api)
        await controller.prepare(ssid: "Office")
        #expect(controller.issue?.contains("钥匙串") == true)
        #expect(controller.issue?.contains("raw private") == false)
        let failure = controller.issue
        await controller.refresh()
        #expect(controller.issue == failure)
    }
}

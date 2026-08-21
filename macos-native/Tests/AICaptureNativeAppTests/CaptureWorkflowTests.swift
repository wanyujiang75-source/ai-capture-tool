import Foundation
import Testing
@testable import AICaptureNativeApp

private actor CaptureWorkflowAPISpy: CaptureWorkflowAPI {
    private var deviceResponses: [[CaptureDevice]]
    private let captureResponse: CaptureStartResponse
    private let startCaptureErrorBody: String?
    private let stopSucceeds: Bool
    private(set) var startDeviceCalls = 0
    private(set) var prepareCalls = 0
    private(set) var startCaptureCalls = 0
    private(set) var stopCaptureCalls = 0

    init(
        deviceResponses: [[CaptureDevice]],
        captureResponse: CaptureStartResponse,
        startCaptureErrorBody: String? = nil,
        stopSucceeds: Bool = true
    ) {
        self.deviceResponses = deviceResponses
        self.captureResponse = captureResponse
        self.startCaptureErrorBody = startCaptureErrorBody
        self.stopSucceeds = stopSucceeds
    }

    func getDevices() async throws -> [CaptureDevice] {
        if deviceResponses.count > 1 {
            return deviceResponses.removeFirst()
        }
        return deviceResponses[0]
    }

    func startDevice(deviceId: String, visible: Bool) async throws -> BasicActionResponse {
        startDeviceCalls += 1
        return try decode(BasicActionResponse.self, #"{"ok":true}"#)
    }

    func prepareSystem(deviceId: String, visible: Bool) async throws -> SystemPrepareResponse {
        prepareCalls += 1
        return try decode(
            SystemPrepareResponse.self,
            #"{"prepare":{"ok":true,"device_id":"device-1","steps":[]}}"#
        )
    }

    func startCapture(appId: Int, deviceId: String, mode: String?) async throws -> CaptureStartResponse {
        startCaptureCalls += 1
        if let startCaptureErrorBody {
            throw APIClientError.httpStatus(409, startCaptureErrorBody)
        }
        return captureResponse
    }

    func stopCapture(deviceId: String) async throws -> CaptureStopResponse {
        stopCaptureCalls += 1
        return try decode(
            CaptureStopResponse.self,
            stopSucceeds ? #"{"ok":true}"# : #"{"ok":false,"stderr":"proxy cleanup failed"}"#
        )
    }

    func callCounts() -> (startDevice: Int, prepare: Int, startCapture: Int, stopCapture: Int) {
        (startDeviceCalls, prepareCalls, startCaptureCalls, stopCaptureCalls)
    }
}

private actor CaptureForegroundAPISpy: ForegroundTargetAPI {
    private var foregroundResponses: [ForegroundAppState]
    private let target: ForegroundTargetResponse
    private let readinessFlowCount: Int

    init(
        foregroundResponses: [ForegroundAppState],
        target: ForegroundTargetResponse,
        readinessFlowCount: Int = 0
    ) {
        self.foregroundResponses = foregroundResponses
        self.target = target
        self.readinessFlowCount = readinessFlowCount
    }

    func getForegroundApp(deviceID: String) async throws -> ForegroundAppState {
        if foregroundResponses.count > 1 {
            return foregroundResponses.removeFirst()
        }
        return foregroundResponses[0]
    }

    func resolveForegroundTarget(deviceID: String) async throws -> ForegroundTargetResponse {
        target
    }

    func getAppReadiness(appID: Int, deviceID: String) async throws -> ForegroundReadinessResponse {
        try decode(
            ForegroundReadinessResponse.self,
            """
            {"readiness":{"state":"warning","flow_count":\(readinessFlowCount)}}
            """
        )
    }
}

@Suite(.serialized)
@MainActor
struct CaptureWorkflowTests {
    @Test
    func defaultsToFourUserFacingSectionsAndCapturePage() {
        let state = AppState()

        #expect(state.selectedSection == .capture)
        #expect(SidebarSection.allCases.map(\.rawValue) == ["抓包", "安装应用", "接口", "日志"])
    }

    @Test
    func hidesDeviceSelectorForOneDeviceAndShowsItForMultipleDevices() throws {
        let state = AppState()
        state.devices = [try device(adbOnline: true, bootCompleted: true, unlocked: true)]
        #expect(!state.showsDeviceSelector)

        state.devices.append(
            try device(id: "device-2", adbOnline: true, bootCompleted: true, unlocked: true)
        )
        #expect(state.showsDeviceSelector)
    }

    @Test
    func oneClickStartsOfflineDeviceWaitsForAppAndBeginsCapture() async throws {
        let offline = try device(adbOnline: false, bootCompleted: false, unlocked: false)
        let booting = try device(adbOnline: true, bootCompleted: false, unlocked: false)
        let locked = try device(adbOnline: true, bootCompleted: true, unlocked: false)
        let ready = try device(adbOnline: true, bootCompleted: true, unlocked: true)
        let target = try foregroundTarget(packageName: "com.example.music", name: "Melody")
        let captureAPI = CaptureWorkflowAPISpy(
            deviceResponses: [[offline], [booting], [locked], [ready], [ready]],
            captureResponse: try captureResponse(packageName: "com.example.music")
        )
        let foregroundAPI = CaptureForegroundAPISpy(
            foregroundResponses: [
                try foreground(state: "waiting_app"),
                try foreground(state: "ready", packageName: "com.example.music"),
            ],
            target: target
        )
        let state = AppState(
            foregroundAPI: foregroundAPI,
            captureWorkflowAPI: captureAPI,
            workflowPollInterval: .milliseconds(1)
        )

        await state.startCaptureWorkflow()

        #expect(state.captureWorkflowState == .capturing(name: "Melody", flowCount: 0))
        #expect(state.activeSessionID == 91)
        let calls = await captureAPI.callCounts()
        #expect(calls.startDevice == 1)
        #expect(calls.prepare == 1)
        #expect(calls.startCapture == 1)
    }

    @Test
    func startDeviceActionPollsUntilAndroidIsReady() async throws {
        let offline = try device(adbOnline: false, bootCompleted: false, unlocked: false)
        let booting = try device(adbOnline: true, bootCompleted: false, unlocked: false)
        let locked = try device(adbOnline: true, bootCompleted: true, unlocked: false)
        let ready = try device(adbOnline: true, bootCompleted: true, unlocked: true)
        let captureAPI = CaptureWorkflowAPISpy(
            deviceResponses: [[offline], [booting], [locked], [ready]],
            captureResponse: try captureResponse(packageName: "com.example.music")
        )
        let state = AppState(
            captureWorkflowAPI: captureAPI,
            workflowPollInterval: .milliseconds(1)
        )
        state.devices = [offline]
        state.selectedDeviceID = "device-1"

        await state.startSelectedDevice()

        #expect(state.captureWorkflowState == .ready)
        #expect(state.selectedDevice?.emulator?.adbOnline == true)
        #expect(state.selectedDevice?.emulator?.bootCompleted == true)
        #expect(state.selectedDevice?.emulator?.unlocked == true)
        let calls = await captureAPI.callCounts()
        #expect(calls.startDevice == 1)
    }

    @Test
    func activeCaptureForAnotherForegroundAppBecomesRecoverableConflict() async throws {
        let activeDevice = try device(
            adbOnline: true,
            bootCompleted: true,
            unlocked: true,
            activePackage: "com.example.running"
        )
        let captureAPI = CaptureWorkflowAPISpy(
            deviceResponses: [[activeDevice]],
            captureResponse: try captureResponse(packageName: "com.example.front")
        )
        let foregroundAPI = CaptureForegroundAPISpy(
            foregroundResponses: [try foreground(state: "ready", packageName: "com.example.front")],
            target: try foregroundTarget(packageName: "com.example.front", name: "Front App")
        )
        let state = AppState(
            foregroundAPI: foregroundAPI,
            captureWorkflowAPI: captureAPI,
            workflowPollInterval: .milliseconds(1)
        )

        await state.startCaptureWorkflow()

        #expect(state.captureWorkflowState == .conflict(currentApp: "com.example.running"))
        let calls = await captureAPI.callCounts()
        #expect(calls.prepare == 0)
        #expect(calls.startCapture == 0)
    }

    @Test
    func matchingActiveCaptureIsRecoveredWithoutStartingAnotherTask() async throws {
        let activeDevice = try device(
            adbOnline: true,
            bootCompleted: true,
            unlocked: true,
            activePackage: "com.example.music"
        )
        let captureAPI = CaptureWorkflowAPISpy(
            deviceResponses: [[activeDevice]],
            captureResponse: try captureResponse(packageName: "com.example.music")
        )
        let foregroundAPI = CaptureForegroundAPISpy(
            foregroundResponses: [try foreground(state: "ready", packageName: "com.example.music")],
            target: try foregroundTarget(packageName: "com.example.music", name: "Melody")
        )
        let state = AppState(
            foregroundAPI: foregroundAPI,
            captureWorkflowAPI: captureAPI,
            workflowPollInterval: .milliseconds(1)
        )

        await state.startCaptureWorkflow()

        #expect(state.captureWorkflowState == .restored(name: "Melody"))
        #expect(state.activeSessionID == 77)
        let calls = await captureAPI.callCounts()
        #expect(calls.prepare == 0)
        #expect(calls.startCapture == 0)
    }

    @Test
    func capturePageUpdatesCapturedInterfaceCountWithoutOpeningFlowsPage() async throws {
        let foreground = try foreground(state: "ready", packageName: "com.example.music")
        let foregroundAPI = CaptureForegroundAPISpy(
            foregroundResponses: [foreground, foreground],
            target: try foregroundTarget(packageName: "com.example.music", name: "Melody"),
            readinessFlowCount: 3
        )
        let state = AppState(foregroundAPI: foregroundAPI)
        state.selectedDeviceID = "device-1"
        state.activeSessionID = 91
        state.captureWorkflowState = .capturing(name: "Melody", flowCount: 0)

        await state.refreshForegroundTarget()
        await state.refreshForegroundTarget()

        #expect(state.captureWorkflowState == .capturing(name: "Melody", flowCount: 3))
    }

    @Test
    func failedStopKeepsRunningCaptureStateForRetry() async throws {
        let ready = try device(adbOnline: true, bootCompleted: true, unlocked: true)
        let captureAPI = CaptureWorkflowAPISpy(
            deviceResponses: [[ready]],
            captureResponse: try captureResponse(packageName: "com.example.music"),
            stopSucceeds: false
        )
        let state = AppState(captureWorkflowAPI: captureAPI)
        state.devices = [ready]
        state.selectedDeviceID = "device-1"
        state.activeSessionID = 91
        state.captureWorkflowState = .capturing(name: "Melody", flowCount: 3)

        await state.stopSelectedCapture()

        #expect(state.activeSessionID == 91)
        #expect(state.captureWorkflowState == .capturing(name: "Melody", flowCount: 3))
        let calls = await captureAPI.callCounts()
        #expect(calls.stopCapture == 1)
    }

    @Test
    func structuredCaptureConflictRecoversSessionStartedDuringRequest() async throws {
        let ready = try device(adbOnline: true, bootCompleted: true, unlocked: true)
        let active = try device(
            adbOnline: true,
            bootCompleted: true,
            unlocked: true,
            activePackage: "com.example.music"
        )
        let captureAPI = CaptureWorkflowAPISpy(
            deviceResponses: [[ready], [ready], [active]],
            captureResponse: try captureResponse(packageName: "com.example.music"),
            startCaptureErrorBody: #"{"detail":{"code":"capture_active","title":"其他应用正在抓包","user_message":"当前模拟器正在抓包，请停止后重试。","recovery_action":"停止抓包","technical_detail":"another capture session is active"}}"#
        )
        let foregroundAPI = CaptureForegroundAPISpy(
            foregroundResponses: [try foreground(state: "ready", packageName: "com.example.music")],
            target: try foregroundTarget(packageName: "com.example.music", name: "Melody")
        )
        let state = AppState(
            foregroundAPI: foregroundAPI,
            captureWorkflowAPI: captureAPI,
            workflowPollInterval: .milliseconds(1)
        )

        await state.startCaptureWorkflow()

        #expect(state.activeSessionID == 77)
        #expect(state.captureWorkflowState == .restored(name: "Melody"))
        let calls = await captureAPI.callCounts()
        #expect(calls.startCapture == 1)
    }

    private func device(
        id: String = "device-1",
        adbOnline: Bool,
        bootCompleted: Bool,
        unlocked: Bool,
        activePackage: String? = nil
    ) throws -> CaptureDevice {
        let activeSession = activePackage.map {
            #", "active_session":{"id":77,"status":"running","mode":"flutter-socks","package_name":"\#($0)"}"#
        } ?? ""
        return try decode(
            CaptureDevice.self,
            """
            {
              "device_id": "\(id)",
              "name": "QA Device",
              "emulator": {
                "adb_online": \(adbOnline),
                "boot_completed": \(bootCompleted),
                "unlocked": \(unlocked),
                "process_running": \(adbOnline)
              }
              \(activeSession)
            }
            """
        )
    }

    private func foreground(state: String, packageName: String? = nil) throws -> ForegroundAppState {
        let component = packageName.map { "\"\($0)/.MainActivity\"" } ?? "null"
        let package = packageName.map { "\"\($0)\"" } ?? "null"
        return try decode(
            ForegroundAppState.self,
            """
            {
              "state": "\(state)",
              "package_name": \(package),
              "activity": \(component),
              "component": \(component)
            }
            """
        )
    }

    private func foregroundTarget(packageName: String, name: String) throws -> ForegroundTargetResponse {
        try decode(
            ForegroundTargetResponse.self,
            """
            {
              "state": "ready",
              "package_name": "\(packageName)",
              "activity": "\(packageName)/.MainActivity",
              "component": "\(packageName)/.MainActivity",
              "capture_state": "ready",
              "app": {
                "id": 9,
                "platform": "android",
                "environment": "test",
                "name": "\(name)",
                "package_name": "\(packageName)",
                "activity": "\(packageName)/.MainActivity",
                "default_mode": "auto"
              }
            }
            """
        )
    }

    private func captureResponse(packageName: String) throws -> CaptureStartResponse {
        try decode(
            CaptureStartResponse.self,
            """
            {
              "session": {
                "id": 91,
                "status": "running",
                "mode": "flutter-socks",
                "device_id": "device-1",
                "package_name": "\(packageName)"
              }
            }
            """
        )
    }
}

private func decode<Value: Decodable>(_ type: Value.Type, _ json: String) throws -> Value {
    try JSONDecoder().decode(type, from: Data(json.utf8))
}

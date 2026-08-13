import Foundation
import Testing
@testable import AICaptureNativeApp


private actor ForegroundAPISpy: ForegroundTargetAPI {
    private var foregroundResponses: [ForegroundAppState]
    private let resolvedTarget: ForegroundTargetResponse
    private(set) var foregroundCalls = 0
    private(set) var resolveCalls = 0

    init(foregroundResponses: [ForegroundAppState], resolvedTarget: ForegroundTargetResponse) {
        self.foregroundResponses = foregroundResponses
        self.resolvedTarget = resolvedTarget
    }

    func getForegroundApp(deviceID: String) async throws -> ForegroundAppState {
        foregroundCalls += 1
        if foregroundResponses.count > 1 {
            return foregroundResponses.removeFirst()
        }
        return foregroundResponses[0]
    }

    func resolveForegroundTarget(deviceID: String) async throws -> ForegroundTargetResponse {
        resolveCalls += 1
        return resolvedTarget
    }

    func getAppReadiness(appID: Int, deviceID: String) async throws -> ForegroundReadinessResponse {
        throw TestError.unexpectedReadinessRequest
    }

    func callCounts() -> (foreground: Int, resolve: Int) {
        (foregroundCalls, resolveCalls)
    }
}

private enum TestError: Error {
    case unexpectedReadinessRequest
}


@Suite(.serialized)
@MainActor
struct ForegroundTargetTests {
    @Test
    func resolvesOnlyWhenForegroundComponentChanges() async throws {
        let foreground = try decode(
            ForegroundAppState.self,
            """
            {
              "state": "ready",
              "package_name": "com.example.music",
              "activity": "com.example.music/.MainActivity",
              "component": "com.example.music/.MainActivity"
            }
            """
        )
        let target = try decodeTarget(packageName: "com.example.music", captureState: "ready")
        let spy = ForegroundAPISpy(
            foregroundResponses: [foreground, foreground],
            resolvedTarget: target
        )
        let state = AppState(foregroundAPI: spy)
        state.selectedDeviceID = "device-1"

        await state.refreshForegroundTarget()
        await state.refreshForegroundTarget()

        let counts = await spy.callCounts()
        #expect(counts.foreground == 2)
        #expect(counts.resolve == 1)
        #expect(state.foregroundTarget?.app?.packageName == "com.example.music")
        #expect(state.canStartForegroundCapture)
    }

    @Test
    func blocksCaptureWhenActiveSessionTargetsAnotherPackage() throws {
        let state = AppState()
        state.selectedDeviceID = "device-1"
        state.foregroundTarget = try decodeTarget(
            packageName: "com.example.front",
            captureState: "ready"
        )
        state.devices = [
            try decode(
                CaptureDevice.self,
                """
                {
                  "device_id": "device-1",
                  "name": "QA Device",
                  "active_session": {
                    "id": 42,
                    "status": "running",
                    "mode": "flutter-socks",
                    "package_name": "com.example.running"
                  }
                }
                """
            )
        ]

        #expect(state.hasForegroundSessionMismatch)
        #expect(!state.canStartForegroundCapture)
        #expect(state.foregroundCaptureGuidance.contains("先停止"))
    }

    @Test
    func allowsOneClickPreparationForDetectedBlockedTarget() throws {
        let state = AppState()
        state.selectedDeviceID = "device-1"
        state.foregroundTarget = try decodeTarget(
            packageName: "com.example.front",
            captureState: "blocked"
        )

        #expect(state.canStartForegroundCapture)
        #expect(state.foregroundCaptureGuidance.contains("自动准备"))
    }

    @Test
    func stoppingCaptureClearsStaleCapturableState() throws {
        let state = AppState()
        state.selectedDeviceID = "device-1"
        state.activeSessionID = 42
        state.foregroundTarget = try decodeTarget(
            packageName: "com.example.front",
            captureState: "capturable"
        )

        state.didStopCapture()

        #expect(state.activeSessionID == nil)
        #expect(state.foregroundTarget?.captureState == "ready")
        #expect(state.canStartForegroundCapture)
    }

    private func decodeTarget(
        packageName: String,
        captureState: String
    ) throws -> ForegroundTargetResponse {
        try decode(
            ForegroundTargetResponse.self,
            """
            {
              "state": "ready",
              "package_name": "\(packageName)",
              "activity": "\(packageName)/.MainActivity",
              "component": "\(packageName)/.MainActivity",
              "capture_state": "\(captureState)",
              "app": {
                "id": 9,
                "platform": "android",
                "environment": "production",
                "name": "\(packageName)",
                "package_name": "\(packageName)",
                "activity": "\(packageName)/.MainActivity",
                "default_mode": "auto"
              },
              "version": {
                "version_name": "1.2.3",
                "version_code": "12"
              },
              "readiness": {
                "state": "warn",
                "flow_count": 0
              }
            }
            """
        )
    }

    private func decode<Value: Decodable>(_ type: Value.Type, _ json: String) throws -> Value {
        try JSONDecoder().decode(type, from: Data(json.utf8))
    }
}

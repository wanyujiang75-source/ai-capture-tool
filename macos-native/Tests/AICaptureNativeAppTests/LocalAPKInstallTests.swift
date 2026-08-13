import Foundation
import Testing
@testable import AICaptureNativeApp


private actor LocalPackageInstallAPISpy: LocalPackageInstallAPI {
    let response: CaptureApp?
    private(set) var calls: [(fileName: String, deviceID: String, environment: String)] = []

    init(response: CaptureApp?) {
        self.response = response
    }

    func installLocalAPK(
        fileURL: URL,
        deviceID: String,
        environment: String
    ) async throws -> CaptureApp? {
        calls.append((fileURL.lastPathComponent, deviceID, environment))
        return response
    }

    func lastCall() -> (fileName: String, deviceID: String, environment: String)? {
        calls.last
    }
}


@Suite(.serialized)
@MainActor
struct LocalAPKInstallTests {
    @Test
    func installsAPKOnSelectedReadyDeviceAndWaitsForUserToOpenIt() async throws {
        let response = try JSONDecoder().decode(
            JenkinsInstallResponse.self,
            from: Data(
                """
                {
                  "app": {
                    "id": 14,
                    "platform": "android",
                    "environment": "production",
                    "name": "Installed Local App",
                    "package_name": "com.example.local",
                    "default_mode": "auto"
                  }
                }
                """.utf8
            )
        )
        let spy = LocalPackageInstallAPISpy(response: response.app)
        let state = AppState(packageInstallAPI: spy)
        state.selectedDeviceID = "device-1"
        state.devices = [try readyDevice()]
        let fileURL = FileManager.default.temporaryDirectory.appendingPathComponent("Local Build.apk")
        try Data("apk".utf8).write(to: fileURL)
        defer { try? FileManager.default.removeItem(at: fileURL) }

        await state.installLocalAPK(fileURL)

        let call = try #require(await spy.lastCall())
        #expect(call.fileName == "Local Build.apk")
        #expect(call.deviceID == "device-1")
        #expect(call.environment == "production")
        #expect(state.localInstallState == .loaded)
        #expect(state.localInstallMessage.contains("请在模拟器中打开"))
        #expect(state.selectedAppID == nil)
    }

    @Test
    func rejectsNonAPKBeforeStartingAnInstall() async throws {
        let state = AppState()
        state.selectedDeviceID = "device-1"
        let fileURL = FileManager.default.temporaryDirectory.appendingPathComponent("notes.txt")

        await state.installLocalAPK(fileURL)

        #expect(state.localInstallState == .failed("请选择扩展名为 .apk 的 Android 安装包。"))
        #expect(state.localInstallMessage == "请选择扩展名为 .apk 的 Android 安装包。")
    }

    @Test
    func foregroundTargetIsClearedAfterPackageInstallation() throws {
        let state = AppState()
        state.foregroundTarget = try JSONDecoder().decode(
            ForegroundTargetResponse.self,
            from: Data(
                """
                {
                  "state": "ready",
                  "package_name": "com.example.old",
                  "activity": "com.example.old/.MainActivity",
                  "component": "com.example.old/.MainActivity",
                  "capture_state": "ready",
                  "app": null,
                  "version": null,
                  "readiness": null
                }
                """.utf8
            )
        )

        state.didInstallPackage()

        #expect(state.foregroundTarget == nil)
        #expect(state.selectedAppID == nil)
    }

    private func readyDevice() throws -> CaptureDevice {
        try JSONDecoder().decode(
            CaptureDevice.self,
            from: Data(
                """
                {
                  "device_id": "device-1",
                  "name": "QA Device",
                  "emulator": {
                    "adb_online": true,
                    "boot_completed": true,
                    "unlocked": true,
                    "process_running": true
                  }
                }
                """.utf8
            )
        )
    }
}

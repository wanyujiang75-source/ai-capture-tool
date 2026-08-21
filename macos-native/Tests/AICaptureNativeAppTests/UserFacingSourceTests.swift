import Foundation
import Testing
@testable import AICaptureNativeApp

@Suite
struct UserFacingSourceTests {
    @Test
    func ordinaryScreensDoNotReintroduceInternalOrDeprecatedCopy() throws {
        let sourceDirectory = try sourceDirectory()
        let ordinaryScreens = [
            "CaptureView.swift",
            "DeviceAppView.swift",
            "FlowViews.swift",
            "LogsView.swift",
        ]
        let forbiddenCopy = [
            "Session #",
            "active session",
            "执行中",
            "未就绪",
            "Android 日志",
            "清除当前接口",
            "刷新接口",
            "选择本地 APK",
            "Logcat",
            "Frida",
        ]

        for fileName in ordinaryScreens {
            let source = try String(
                contentsOf: sourceDirectory.appendingPathComponent(fileName),
                encoding: .utf8
            )
            let userFacingLiterals = source
                .split(separator: "\n")
                .filter { $0.contains("\"") }
                .joined(separator: "\n")
            for forbidden in forbiddenCopy {
                #expect(
                    !userFacingLiterals.contains(forbidden),
                    "\(fileName) still contains user-facing copy: \(forbidden)"
                )
            }
        }
    }

    private func sourceDirectory() throws -> URL {
        let testFile = URL(fileURLWithPath: #filePath)
        let packageRoot = testFile
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let sourceDirectory = packageRoot
            .appendingPathComponent("Sources", isDirectory: true)
            .appendingPathComponent("AICaptureNativeApp", isDirectory: true)
        #expect(FileManager.default.fileExists(atPath: sourceDirectory.path))
        return sourceDirectory
    }
}

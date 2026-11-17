import Foundation

enum DesktopUpdateBlocker: Equatable {
    case captureBusy, phoneNeedsRecovery, backendUnavailable

    var message: String {
        switch self {
        case .captureBusy: "请先结束正在进行或准备中的抓包，再检查更新。"
        case .phoneNeedsRecovery: "请先结束手机连接并确认手机网络已恢复，再检查更新。"
        case .backendUnavailable: "暂时无法确认本机抓包状态。请在运行检查通过后重试，或退出应用后手动安装。"
        }
    }
}

@MainActor
enum DesktopUpdateSafety {
    static func blocker(
        runtime: URL,
        pendingWork: () -> Bool,
        captureActive: () async throws -> Bool
    ) async -> DesktopUpdateBlocker? {
        func localBlocker() -> DesktopUpdateBlocker? {
            if AndroidPhysicalQuitSafety.requiresWarning(runtimeDirectory: runtime)
                || IOSQuitSafety.requiresWarning(runtimeDirectory: runtime) { return .phoneNeedsRecovery }
            return pendingWork() ? .captureBusy : nil
        }

        if let blocked = localBlocker() { return blocked }
        do {
            if try await captureActive() { return .captureBusy }
            return localBlocker()
        } catch {
            return .backendUnavailable
        }
    }
}

struct DesktopUpdateBackendStatus: Decodable {
    struct Identity: Decodable {
        let enabled: Bool
        let buildID: String
        let runtimeDirectory: String

        enum CodingKeys: String, CodingKey {
            case enabled
            case buildID = "build_id", runtimeDirectory = "runtime_dir"
        }
    }

    let desktop: Identity
    let captureActive: Bool

    enum CodingKeys: String, CodingKey {
        case desktop
        case captureActive = "capture_active"
    }

    func matches(buildID: String, runtime: URL) -> Bool {
        desktop.enabled && desktop.buildID == buildID
            && URL(fileURLWithPath: desktop.runtimeDirectory, isDirectory: true).resolvingSymlinksInPath().path
                == runtime.resolvingSymlinksInPath().path
    }
}

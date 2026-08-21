import Foundation

enum AppCopy {
    enum Navigation {
        static let capture = "抓包"
        static let installApps = "安装应用"
        static let flows = "接口"
        static let logs = "日志"
        static let runtimeCheck = "运行检查"
    }

    enum Capture {
        static let start = "开始抓包"
        static let stop = "停止抓包"
        static let startEmulator = "启动模拟器"
        static let showEmulator = "显示模拟器"
        static let stopAndSwitch = "停止并切换"
        static let continueCurrent = "继续当前任务"
    }

    enum Install {
        static let pageDescription = "从 Jenkins 获取最新测试包，或安装本地 APK。"
        static let chooseAPK = "选择 APK"
        static let searchPlaceholder = "搜索任务或安装包"
        static let emulatorOffline = "模拟器未启动，暂时无法安装应用。"
        static let emulatorBooting = "Android 系统仍在启动，请稍后再安装。"
        static let emulatorLocked = "请先解锁模拟器，再安装应用。"
        static let captureConflict = "当前模拟器正在抓包，停止后才能安装应用。"
        static let signatureConflict = "新安装包与现有版本签名不一致。为保护应用数据，工具不会自动卸载旧版本。"
        static let jenkinsUnavailable = "无法连接 Jenkins，请确认已连接公司网络后重试。"
        static let missingArtifact = "当前 Jenkins 任务没有可安装的 APK。"

        static func installingJenkins(jobName: String, buildNumber: Int) -> String {
            "正在下载并安装“\(jobName)”#\(buildNumber)…"
        }

        static func installingLocal(fileName: String) -> String {
            "正在校验并安装“\(fileName)”…"
        }

        static func installed(appName: String) -> String {
            "“\(appName)”已安装，请在模拟器中打开应用。"
        }
    }

    enum Flow {
        static let clearList = "清空列表"
        static let clearExplanation = "仅清空当前显示；抓包不会停止，新接口仍会继续出现。"
        static let notStarted = "尚未开始抓包"
        static let waiting = "等待接口，请在模拟器中操作应用。"
        static let cleared = "列表已清空，新的接口会继续实时显示。"
        static let noSearchResults = "没有匹配的接口，请更换关键词或筛选条件。"
        static let noResponse = "暂无响应"
        static let noRequestBody = "此请求没有请求体"
        static let waitingSync = "等待同步"
        static let syncing = "同步中"
        static let live = "实时"

        static func captureNumber(_ id: Int) -> String {
            "本次抓包 #\(id)"
        }

        static func responseWithoutBody(statusCode: String) -> String {
            "已捕获 HTTP \(statusCode)，但没有可展示的响应正文。"
        }

        static let responsePending = "尚未捕获响应，请求可能仍在进行或连接已提前结束。"
    }

    enum Log {
        static let pageDescription = "实时查看当前应用的运行日志、系统日志和崩溃信息。"
        static let pauseDisplay = "暂停显示"
        static let resumeDisplay = "继续显示"
        static let clear = "清空日志"
        static let copyAll = "复制全部"
        static let allLevels = "全部级别"
        static let tag = "标签"
        static let emulatorOffline = "模拟器未连接，启动模拟器后日志会自动连接。"
        static let waitingForApp = "等待应用运行，请在模拟器中打开要查看的应用。"
        static let disconnected = "日志连接中断，请检查模拟器连接后重试。"
    }
}

enum CaptureWorkflowAction: Equatable, Sendable {
    case startCapture
    case stopCapture
    case showEmulator
    case stopAndSwitch
    case continueCurrent
    case openRuntimeCheck
}

enum CaptureWorkflowTone: Equatable, Sendable {
    case neutral
    case progress
    case warning
    case success
    case error
}

struct CaptureWorkflowPresentation: Equatable, Sendable {
    let title: String
    let message: String
    let primaryAction: CaptureWorkflowAction?
    let primaryButtonTitle: String?
    let secondaryAction: CaptureWorkflowAction?
    let secondaryButtonTitle: String?

    init(
        title: String,
        message: String,
        primaryAction: CaptureWorkflowAction? = nil,
        primaryButtonTitle: String? = nil,
        secondaryAction: CaptureWorkflowAction? = nil,
        secondaryButtonTitle: String? = nil
    ) {
        self.title = title
        self.message = message
        self.primaryAction = primaryAction
        self.primaryButtonTitle = primaryButtonTitle
        self.secondaryAction = secondaryAction
        self.secondaryButtonTitle = secondaryButtonTitle
    }
}

struct UserFacingIssue: Error, Equatable, Sendable {
    let code: String
    let title: String
    let message: String
    let recoveryAction: String?
    let technicalDetail: String?

    init(
        code: String,
        title: String,
        message: String,
        recoveryAction: String? = nil,
        technicalDetail: String? = nil
    ) {
        self.code = code
        self.title = title
        self.message = message
        self.recoveryAction = recoveryAction
        self.technicalDetail = technicalDetail
    }
}

enum UserNoticeTone: Equatable, Sendable {
    case success
    case failure
}

struct UserNotice: Identifiable, Equatable, Sendable {
    let id: UUID
    let tone: UserNoticeTone
    let title: String
    let message: String
    let duration: Duration

    static func success(title: String, message: String) -> Self {
        .init(
            id: UUID(),
            tone: .success,
            title: title,
            message: message,
            duration: .seconds(3)
        )
    }

    static func failure(title: String, message: String) -> Self {
        .init(
            id: UUID(),
            tone: .failure,
            title: title,
            message: message,
            duration: .seconds(4)
        )
    }
}

enum CaptureWorkflowState: Equatable, Sendable {
    case ready
    case emulatorOffline
    case startingEmulator
    case bootingAndroid
    case waitingForUnlock
    case waitingForApp
    case appDetected(name: String)
    case preparing(name: String)
    case startingCapture(name: String)
    case capturing(name: String, flowCount: Int)
    case stopped
    case restored(name: String)
    case conflict(currentApp: String)
    case failed(UserFacingIssue)

    var tone: CaptureWorkflowTone {
        switch self {
        case .ready, .emulatorOffline, .stopped:
            .neutral
        case .startingEmulator, .bootingAndroid, .appDetected, .preparing, .startingCapture:
            .progress
        case .waitingForUnlock, .waitingForApp, .conflict:
            .warning
        case .capturing, .restored:
            .success
        case .failed:
            .error
        }
    }

    var presentation: CaptureWorkflowPresentation {
        switch self {
        case .ready:
            return .init(
                title: "准备开始抓包",
                message: "打开模拟器中的应用，工具会自动识别并抓取接口。",
                primaryAction: .startCapture,
                primaryButtonTitle: AppCopy.Capture.start
            )
        case .emulatorOffline:
            return .init(
                title: "尚未启动模拟器",
                message: "点击“开始抓包”，工具会自动启动模拟器。",
                primaryAction: .startCapture,
                primaryButtonTitle: AppCopy.Capture.start
            )
        case .startingEmulator:
            return .init(
                title: "正在启动模拟器…",
                message: "首次启动可能需要几分钟，请保持窗口打开。"
            )
        case .bootingAndroid:
            return .init(
                title: "正在启动 Android…",
                message: "系统启动完成后会自动继续。"
            )
        case .waitingForUnlock:
            return .init(
                title: "等待解锁",
                message: "请在模拟器中解锁屏幕，解锁后会自动继续。",
                secondaryAction: .showEmulator,
                secondaryButtonTitle: AppCopy.Capture.showEmulator
            )
        case .waitingForApp:
            return .init(
                title: "等待应用",
                message: "请在模拟器中打开需要分析的应用。",
                secondaryAction: .showEmulator,
                secondaryButtonTitle: AppCopy.Capture.showEmulator
            )
        case let .appDetected(name):
            return .init(
                title: "已识别“\(name)”",
                message: "正在检查该应用的抓包环境。"
            )
        case .preparing:
            return .init(
                title: "正在准备抓包环境…",
                message: "正在检查模拟器网络和抓包组件。"
            )
        case let .startingCapture(name):
            return .init(
                title: "正在启动抓包…",
                message: "即将开始记录“\(name)”的接口。"
            )
        case let .capturing(name, flowCount):
            if flowCount == 0 {
                return .init(
                    title: "正在抓取“\(name)”",
                    message: "请操作应用以触发接口请求。",
                    primaryAction: .stopCapture,
                    primaryButtonTitle: AppCopy.Capture.stop
                )
            }
            return .init(
                title: "已捕获 \(flowCount) 个接口",
                message: "新接口将继续实时显示。",
                primaryAction: .stopCapture,
                primaryButtonTitle: AppCopy.Capture.stop
            )
        case .stopped:
            return .init(
                title: "抓包已停止",
                message: "已保留本次抓包结果。",
                primaryAction: .startCapture,
                primaryButtonTitle: AppCopy.Capture.start
            )
        case let .restored(name):
            return .init(
                title: "已恢复正在运行的抓包",
                message: "继续操作“\(name)”即可。",
                primaryAction: .stopCapture,
                primaryButtonTitle: AppCopy.Capture.stop
            )
        case let .conflict(currentApp):
            return .init(
                title: "其他应用正在抓包",
                message: "当前正在抓取“\(currentApp)”。",
                primaryAction: .stopAndSwitch,
                primaryButtonTitle: AppCopy.Capture.stopAndSwitch,
                secondaryAction: .continueCurrent,
                secondaryButtonTitle: AppCopy.Capture.continueCurrent
            )
        case let .failed(issue):
            return .init(
                title: issue.title,
                message: issue.message,
                primaryAction: issue.recoveryAction == nil ? nil : .openRuntimeCheck,
                primaryButtonTitle: issue.recoveryAction
            )
        }
    }
}

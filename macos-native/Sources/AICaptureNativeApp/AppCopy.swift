import Foundation

enum AppCopy {
    enum WeakNetwork {
        static let title = "弱网模拟"
        static let scope = "仅影响当前模拟器，可与抓包同时使用。其他应用（包括 Google Play）也会变慢；不会改变 Mac 网络。"
        static let profile = "网络场景"
        static let unlimited = "不限制"
        static let twoG = "2G"
        static let threeG = "3G"
        static let fourG = "4G"
        static let units = "2G、3G、4G 为测试预设，不改变模拟器的网络制式。速率为每个网卡的共享上限，实际速度取决于网络和应用。"
        static let unlimitedDescription = "不限制上传和下载速度，不额外增加延迟。点击“恢复网络”清除本工具的弱网设置。"
        static let apply = "应用弱网"
        static let restore = "恢复网络"
        static let normal = "不限制"
        static let active = "弱网已开启"
        static let pending = "等待恢复网络"
        static let failed = "弱网设置失败"
        static let checking = "正在检查网络设置…"
        static let changing = "正在调整模拟器网络…"
        static let offline = "请先启动模拟器，再应用弱网。退出工具时会恢复网络；异常退出后将在下次打开时恢复。"
        static let selectProfile = "请选择网络场景后应用。"
        static let connectionFailed = "无法确认网络设置，请检查本机服务和模拟器连接，再点击恢复网络。"
        static let technicalDetail = "弱网技术详情"
        static let close = "关闭检查"
        static func selected(_ profile: WeakNetworkProfile) -> String {
            "所选预设：上传 \(profile.uploadKbps) kbps，下载 \(profile.downloadKbps) kbps，额外往返延迟 \(profile.latencyMs) ms。点击“应用弱网”生效。"
        }
        static func applied(_ profile: WeakNetworkProfile) -> String {
            "当前生效：上传 \(profile.uploadKbps) kbps，下载 \(profile.downloadKbps) kbps，额外往返延迟 \(profile.latencyMs) ms。"
        }
    }

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
        static let stoppedTitle = "抓包已停止"
        static let stoppedMessage = "已保留本次抓包结果。"
        static let stoppedWithNetworkPending = "模拟器网络暂未恢复，重新连接后运行检查会继续处理。"
        static let stopFailedTitle = "抓包停止失败"
        static let stopFailedMessage = "请打开运行检查并重试停止操作。"
    }

    enum Install {
        static let pageDescription = "从 Jenkins 获取最新测试包，或安装本地 APK。"
        static let chooseAPK = "选择 APK"
        static let searchPlaceholder = "搜索任务或安装包"
        static let refreshPackages = "刷新安装包"
        static let loadingPackages = "正在获取 Jenkins 最新安装包…"
        static let refreshingPackages = "正在刷新安装包，当前列表仍可查看…"
        static let partialRefresh = "部分任务刷新失败，未更新的任务保留上次结果，请稍后刷新重试。"
        static let refreshFailedWithPrevious = "安装包刷新失败，当前显示上次获取的列表。请确认已连接公司网络后重试。"
        static let noMatchingPackages = "没有匹配的安装包，请更换搜索关键词。"
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
        static let pageDescription = "查看请求与响应，支持搜索和筛选。"
        static let startHint = "请前往“抓包”页开始抓包，或打开“历史记录”查看已有结果。"
        static let search = "搜索 URL、方法或状态码"
        static let clearSearch = "清空搜索"
        static let selectDetail = "选择一条请求查看详情。"
        static let loadingDetail = "正在加载请求详情…"
        static let generatingCurl = "正在生成 cURL…"
        static let historyEmpty = "此抓包记录没有可显示的请求。"
        static let historyCleared = "当前列表已清空，原始抓包记录未删除。"
        static let historyClearExplanation = "仅清空当前列表显示，不删除原始抓包记录。"
        static let clearedTitle = "列表已清空"
        static let syncFailed = "加载失败"
        static let historyLoaded = "已加载"
        static let onlyInterfaces = "仅看接口"
        static let filterExplanation = "隐藏静态资源、网页及已识别的统计和系统检查请求；未知请求仍保留。仅影响显示，不删除记录。"
        static let noFilteredResults = "没有符合条件的接口，请关闭“仅看接口”或更换搜索关键词。"
        static func filteredCount(_ count: Int) -> String { "已过滤 \(count) 条" }
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
        static let showFullBodyFile = "在 Finder 中显示正文文件"
        static let requestData = "Request 数据"
        static let responseData = "Response 数据"
        static let queryParameters = "查询参数"
        static let requestHeaders = "请求头 · Headers"
        static let responseHeaders = "响应头 · Headers"
        static let requestBody = "请求正文 · Body"
        static let responseBody = "响应正文 · Body"
        static let noHeaders = "此记录未保存 Headers。"
        static let emptyHeaders = "Headers 为空。"
        static let unavailableBody = "此记录没有可展示的正文文本，请查看已归档的正文文件（如有）。"
        static let binaryBody = "正文为二进制数据，不作为文本展示。"
        static let metadataPreview = "参数或 Headers 较长，仅显示部分内容。"
        static func responseStatus(_ value: String) -> String { "响应状态：\(value)" }

        static func captureNumber(_ id: Int) -> String {
            "本次抓包 #\(id)"
        }

        static func historyNumber(_ id: Int) -> String { "历史抓包 #\(id)" }
        static func count(shown: Int, total: Int) -> String {
            shown == total ? "\(total) 条请求" : "\(shown) / \(total) 条请求"
        }

        static func responseWithoutBody(statusCode: String) -> String {
            "已捕获 HTTP \(statusCode)，但没有可展示的响应正文。"
        }

        static func largeBodyPreview(sizeBytes: Int) -> String {
            let size = ByteCountFormatter.string(fromByteCount: Int64(sizeBytes), countStyle: .file)
            return "正文预览不完整（记录大小 \(size)），可能已截断或未完整解码；仅展示已获取的内容。"
        }

        static let responsePending = "尚未捕获响应，请求可能仍在进行或连接已提前结束。"
    }

    enum FlowSource {
        static let current = "当前抓包"
        static let history = "历史记录"
        static let switchCapture = "切换抓包"
        static let returnToCurrent = "返回当前抓包"
        static let refresh = "刷新记录"
        static let close = "关闭"
        static let search = "搜索应用、平台、日期或记录编号"
        static let noHistory = "暂无历史抓包记录"
        static let noMatches = "未找到匹配的记录，请更换搜索关键词。"
        static let running = "抓包中"
        static let stopped = "已结束"
        static let failed = "已中断"
        static let unknown = "状态未知"
        static let unknownTime = "时间未知"
        static func unnamed(platform: String) -> String { "\(platform) 抓包" }
    }

    enum Log {
        static let pageDescription = "实时查看当前应用的运行日志、系统日志和崩溃信息。"
        static let refreshDevices = "刷新设备"
        static let refreshingDevices = "正在刷新…"
        static let pauseDisplay = "暂停显示"
        static let resumeDisplay = "继续显示"
        static let clear = "清空日志"
        static let copyAll = "复制全部"
        static let allLevels = "全部级别"
        static let tag = "标签"
        static let deviceOffline = "未连接可调试的 Android 设备。请启动模拟器，或连接并授权 Android 真机。"
        static let waitingForApp = "等待应用运行，请在当前 Android 设备中打开要查看的应用。"
        static let disconnected = "日志连接中断，请检查 Android 设备连接后刷新。"
        static let physicalAuthorization = "已检测到未授权真机。USB 连接请在手机上允许调试；无线连接请先完成配对，然后刷新设备。"
        static let physicalOffline = "Android 真机当前未连接，无法读取日志。请检查 USB 或无线调试连接后刷新。"
        static let deviceLocked = "请先解锁当前 Android 设备，再打开要查看的应用。"
        static let physicalSetup = "真机无需 Root：USB 连接请开启 USB 调试并授权；无线连接请开启无线调试并先与此 Mac 配对。"
        static let noApplicationRequired = "系统和崩溃日志无需选择应用"
        static let expandFullContent = "展开完整内容"
        static let collapseContent = "收起内容"

        static func repeated(_ count: Int) -> String {
            "连续出现 \(count) 次"
        }
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
                title: AppCopy.Capture.stoppedTitle,
                message: AppCopy.Capture.stoppedMessage,
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

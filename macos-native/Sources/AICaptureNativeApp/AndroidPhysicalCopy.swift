import Foundation

extension AppCopy {
    enum AndroidPhysical {
        static let heading = "Android 真机抓包"
        static let subtitle = "通过 USB 连接手机，自动准备单应用抓包连接。"
        static let device = "Android 真机"
        static let chooseDevice = "使用手机"
        static let discover = "检测手机"
        static let terminate = "终止任务并重新检测"
        static let terminateHelp = "结束当前任务，保留抓包记录并重新检测 USB 手机；未确认的旧手机网络恢复会单独保留提醒，不会自动开始新抓包。"
        static let pendingTitle = "待恢复的手机"
        static let pendingHelp = "这些手机的抓包已终止，但原网络尚未确认恢复。请重新连接对应手机，打开原 VPN 恢复连接，再检查网络恢复；不影响其他手机开始新任务。"
        static let originalDisconnected = "原手机已断开或未授权。可终止当前任务并重新检测，稍后再连接原手机检查网络恢复。"
        static let currentDevice = "当前任务手机"
        static let noDevices = "未检测到 USB 真机。请连接手机、开启 USB 调试并允许此电脑调试。"
        static let unauthorized = "请解锁手机，并在 USB 调试提示中选择允许。"
        static let consent = "我了解实验能力限制，并允许临时接管所选应用的 VPN 转发。"
        static let boundary = "仅部分应用支持解密，应用或系统更新后可能失效。不需要 Root，不修改原应用，也不修改原 VPN 节点和配置。每次连接最长 15 分钟，到期自动停止。"
        static let network = "临时连接会替换手机当前 VPN，测试应用经电脑出网；其他应用不进入抓包隧道，也不再由原 VPN 保护。测试期间请勿操作无关敏感应用。"
        static let instructions = "操作步骤"
        static let steps = [
            "连接并解锁手机，确保手机与 Mac 在同一 Wi-Fi。在手机中打开需要分析的应用。",
            "点击“开始抓包”。工具自动安装独立连接助手、生成参数并配置单应用转发，无需填写 IP、端口或业务域名。",
            "首次使用时，仅在手机确认连接助手安装和 VPN 授权。准备完成后会自动返回测试应用。",
            "操作应用后点击“查看接口”。结束时点击“停止并恢复网络”，确认原 VPN 已连接。"
        ]
        static let automatic = "自动处理：设备检查、连接参数、应用范围、启动抓包、记录归档及网络恢复检查。"
        static let recovery = "USB 断开或电脑无响应时，临时 VPN 将在约 20 秒内释放。若原 VPN 未自动重连，请打开原 VPN 点击连接；不要改节点或配置。重新连接 USB 后点击“检查网络恢复”。"
        static let start = "开始抓包"
        static let stop = "停止并恢复网络"
        static let recover = "检查网络恢复"
        static let results = "查看接口"
        static let details = "技术详情"
        static let quitTitle = "手机临时连接尚未恢复"
        static let quitHelp = "建议先停止抓包并确认原 VPN 已连接。直接退出后，临时连接会自动停止，但可能需要在手机打开原 VPN 恢复网络。"
        static let connectionFailed = "无法连接真机抓包服务，请检查本机服务后重试。"
        static let discoveryFailed = "无法检测手机，请检查 USB 连接和 Android 连接组件。"
        static let tlsFailure = "部分连接未通过 HTTPS 校验。当前应用可能不支持此实验方式，安装证书不保证能够解密。"
        static func count(_ status: AndroidPhysicalStatus) -> String {
            "已记录 \(status.flowCount ?? 0) 个请求，收到 \(status.responseCount ?? 0) 个响应"
        }
        static func phoneLabel(name: String, serial: String) -> String {
            "\(name.isEmpty ? device : name) · \(serial.suffix(4))"
        }
        static func title(_ phase: AndroidPhysicalPhase) -> String {
            switch phase {
            case .idle: "准备连接手机"
            case .preparing: "正在准备真机连接…"
            case .waitingInstall: "等待确认安装"
            case .waitingVPN: "等待手机授权"
            case .capturing: "正在抓取手机应用"
            case .stopping: "正在恢复原网络…"
            case .terminating: "正在终止任务…"
            case .recoveryRequired: "原网络尚未恢复"
            case .stopped: "抓包已停止"
            case .failed: "真机抓包未启动"
            case .unknown: "请更新桌面端后重试"
            }
        }
    }
}

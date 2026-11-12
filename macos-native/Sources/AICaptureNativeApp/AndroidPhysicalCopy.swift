import Foundation

extension AppCopy {
    enum AndroidPhysical {
        static let heading = "Android 真机抓包"
        static let subtitle = "连接 Android 手机，抓取指定应用的请求与响应。"
        static let device = "Android 真机"
        static let chooseDevice = "使用手机"
        static let discover = "检测手机"
        static let terminate = "结束流程并重新检测"
        static let terminateHelp = "取消准备或结束抓包，保留抓包记录并重新检测手机。未确认恢复的原手机会保留提醒，不会自动开始新抓包。"
        static let pendingTitle = "待恢复的手机"
        static let pendingHelp = "这些手机的抓包已终止，但原网络尚未确认恢复。请重新连接对应手机，打开原 VPN 恢复连接，再检查网络恢复；不影响其他手机开始新任务。"
        static let originalDisconnected = "原手机已断开或未授权。换机时请点击“结束流程并重新检测”，稍后重新连接原手机检查网络恢复。"
        static let currentDevice = "当前任务手机"
        static let noDevices = "未检测到 USB 真机。请连接手机、开启 USB 调试并允许此电脑调试。"
        static let unauthorized = "请解锁手机，并在 USB 调试提示中选择允许。"
        static let consent = "我已了解适用范围和网络影响，同意临时替换手机 VPN，仅转发目标应用。"
        static let boundary = "不需要 Root，不修改原应用。仅部分应用和版本支持 HTTPS 解密，兼容性可能随更新变化。每次抓包最长 15 分钟，到期自动停止。"
        static let network = "原 VPN 节点和配置不会修改。抓包期间，目标应用经电脑出网；其他应用不被抓取，但不再由原 VPN 保护。请勿操作无关敏感应用。"
        static let instructions = "操作步骤"
        static let steps = [
            "连接并解锁手机，确保手机与 Mac 在同一 Wi-Fi。在手机中打开需要分析的应用。",
            "点击“开始抓包”。工具自动安装独立连接助手、生成参数并配置单应用转发，无需填写 IP、端口或业务域名。",
            "首次使用时，仅在手机确认连接助手安装和 VPN 授权。准备完成后会自动返回测试应用。",
            "操作应用后点击“查看接口”。结束时点击“停止并恢复网络”，确认原 VPN 已连接。"
        ]
        static let automatic = "工具自动检查设备、识别前台应用、准备连接并保存接口。每轮仅抓取开始时识别的应用；切换应用后需停止并重新开始。"
        static let recovery = "USB 断开或电脑无响应时，临时连接会在停止续约约 20 秒后释放，不代表原 VPN 已恢复。若未自动重连，请打开原 VPN 连接，不要改节点或配置；重新连接 USB 后点击“检查网络恢复”。"
        static let start = "开始抓包"
        static let stop = "停止并恢复网络"
        static let recover = "检查网络恢复"
        static let results = "查看接口"
        static let details = "技术详情"
        static let compatibility = "HTTPS 解密依赖部分客户端的证书信任缺陷，已修复或启用独立证书锁定的应用可能不支持。请正常更新应用与系统，不要降级或关闭安全更新。"
        static let quitTitle = "手机临时连接尚未恢复"
        static let quitHelp = "建议先停止抓包并确认原 VPN 已连接。直接退出后，临时连接会自动停止，但可能需要在手机打开原 VPN 恢复网络。"
        static let connectionFailed = "无法连接真机抓包服务，请检查本机服务后重试。"
        static let discoveryFailed = "无法检测手机，请检查 USB 连接和 Android 连接组件。"
        static let tlsFailure = "部分连接未通过 HTTPS 校验，可能无法显示对应的请求或响应。当前应用或版本可能不支持此抓包方式，重复安装证书不保证能够解决。"
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
            case .waitingInstall: "正在准备连接助手…"
            case .waitingVPN: "等待 VPN 授权"
            case .capturing: "正在抓取手机应用"
            case .stopping: "正在恢复原网络…"
            case .terminating: "正在结束流程…"
            case .recoveryRequired: "原网络尚未恢复"
            case .stopped: "抓包已停止"
            case .failed: "抓包流程未完成"
            case .unknown: "请更新桌面端后重试"
            }
        }
    }
}

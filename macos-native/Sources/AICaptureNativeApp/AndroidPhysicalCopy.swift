import Foundation

extension AppCopy {
    enum AndroidPhysical {
        static let heading = "Android 真机抓包"
        static let subtitle = "连接 Android 手机，抓取指定应用的请求与响应。"
        static let device = "Android 真机"
        static let chooseDevice = "使用手机"
        static let discover = "检测手机"
        static let terminate = "结束流程并重新检测"
        static let terminateHelp = "结束当前流程，保留抓包记录并重新检测手机；未恢复的手机会保留提醒。"
        static let pendingTitle = "待恢复的手机"
        static let pendingHelp = "抓包已结束，网络恢复待确认。请连接对应手机，开启原 VPN，再点击“检查网络恢复”。其他手机可继续使用。"
        static let originalDisconnected = "原手机已断开或未授权。换机时请点击“结束流程并重新检测”，稍后重新连接原手机检查网络恢复。"
        static let currentDevice = "当前任务手机"
        static let noDevices = "未检测到手机。请连接 USB，开启 USB 调试并授权此电脑。"
        static let unauthorized = "请解锁手机，并在 USB 调试提示中选择允许。"
        static let consent = "同意临时替换手机 VPN，抓取目标应用并加密转发 Google 登录服务。"
        static let boundary = "每次限时 30 分钟，到期自动停止。"
        static let network = "请保持电脑 HTTP 代理开启。目标应用经 Mac 出网，原节点和配置保留；其他应用不被抓取，但不再由原 VPN 保护。请勿操作无关敏感应用。"
        static let googleLogin = "Google Play 服务登录失败时，点击“停止并恢复网络”，先通过手机原 VPN 完成 Google 登录再重试。"
        static let instructions = "操作步骤"
        static let steps = [
            "连接 USB 并解锁手机，与 Mac 接入同一 Wi-Fi，打开目标应用。",
            "保持电脑 HTTP 代理开启，点击“开始抓包”。",
            "首次使用时，在手机确认连接助手安装和 VPN 授权，等待连接完成。",
            "操作应用后“查看接口”；结束时“停止并恢复网络”，确认原 VPN 已连接。"
        ]
        static let connectionHelp = "连接与恢复说明"
        static let automatic = "设备检测、应用识别和连接准备自动完成。每轮仅抓取开始时的应用；更换应用需停止后重新开始。"
        static let recovery = "USB 断开或电脑无响应时，临时连接在停止续约约 20 秒后释放，原 VPN 不一定自动恢复。请开启原 VPN，重新连接 USB 并点击“检查网络恢复”，无需修改节点或配置。"
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
        static let tlsFailure = "部分连接未通过 HTTPS 校验，无法展示对应正文。当前应用版本可能不支持解密，重复安装证书不保证有效。"
        static let phoneNetwork = "手机到电脑检查"
        static let upstreamNetwork = "电脑代理出网检查"
        static let bannerHelp = "Banner 不能作为联网依据。请刷新应用并核对新请求和响应，无需点击广告。"
        static func applicationTitle(_ state: String?) -> String {
            switch state {
            case "waiting": "等待应用响应"
            case "responded": "已收到应用 HTTPS 响应"
            case "partial": "应用部分连接异常"
            case "server_error": "应用服务返回错误"
            case "connection_failed": "应用连接出现异常"
            case "quiet": "近期未收到新响应"
            default: "应用联网尚未验证"
            }
        }
        static func applicationMessage(_ state: String?) -> String {
            switch state {
            case "waiting": "转发已连接，尚无应用响应。请刷新应用，再查看接口。"
            case "responded": "最近 30 秒收到 HTTPS 响应，请查看接口确认业务结果；不代表登录或广告加载成功。"
            case "partial": "最近 30 秒收到响应，但部分连接失败。请核对失败接口，单独确认登录或广告结果。"
            case "server_error": "最近一次 HTTPS 响应为服务错误。请查看接口状态码和正文，无需仅因此更换 VPN。"
            case "connection_failed": "最近 30 秒连接失败且无新响应。请检查电脑代理及运行检查详情，暂不能确定为证书问题。"
            case "quiet": "最近 30 秒无新响应，不代表断网。请刷新应用或切换页面后观察。"
            default: "尚未验证应用联网。代理或 VPN 已连接，不代表应用请求成功。"
            }
        }
        static func networkResult(_ value: String?) -> String {
            switch value {
            case "ready": "检查通过"
            case "failed": "连接失败"
            default: "等待检查"
            }
        }
        static func count(_ status: AndroidPhysicalStatus) -> String {
            "请求 \(status.flowCount ?? 0) 条 · 响应 \(status.responseCount ?? 0) 条"
        }
        static func phoneLabel(name: String, serial: String) -> String {
            "\(name.isEmpty ? device : name) · \(serial.suffix(4))"
        }
        static func title(_ phase: AndroidPhysicalPhase) -> String {
            switch phase {
            case .idle: "准备连接手机"
            case .preparing: "正在准备真机连接…"
            case .checkingNetwork: "正在检查网络…"
            case .waitingTunnel: "正在连接手机…"
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

import Foundation

extension AppCopy {
    enum IOSSetup {
        static let title = "连接 iPhone（试用）"
        static let summary = "电脑端自动准备连接；手机端确认安装、信任测试证书后即可检查连接。"
        static let wifi = "当前 Wi-Fi 名称"
        static let wifiHelp = "手机与 Mac 需连接同一网络。仅支持普通密码 Wi-Fi；企业账号网络请勿使用此配置。工具不读取或保存 Wi-Fi 密码。"
        static let prepare = "准备连接"
        static let preparing = "正在准备 iPhone 连接…"
        static let stopping = "正在结束 iPhone 测试…"
        static let share = "发送配置到 iPhone"
        static let shareHelp = "在共享菜单中选择隔空投送，仅发送给自己的测试 iPhone。无需手填代理地址或认证信息。"
        static let install = "1. 接收并安装配置"
        static let installHelp = "在 iPhone 接收文件，进入“设置 → 通用 → VPN 与设备管理”安装“抓包工具 iPhone 临时配置”。若要求 Wi-Fi 密码，只在手机上输入。"
        static let trust = "2. 信任本次测试证书"
        static func trustHelp(_ name: String) -> String {
            "进入“设置 → 通用 → 关于本机 → 证书信任设置”，开启“\(name)”的完全信任。请核对名称，勿信任其他证书。该证书用于解密测试流量。"
        }
        static let verify = "3. 检查连接并操作 PokeHub"
        static let verifyHelp = "点击手机桌面的“检查抓包连接”，或用相机扫描右侧二维码。通过后操作 PokeHub，工具会自动更新结果，无需刷新。"
        static let stop = "结束测试"
        static let remove = "请先从 iPhone 删除测试配置"
        static let removeHelp = "在“设置 → 通用 → VPN 与设备管理”删除“抓包工具 iPhone 临时配置”，确认 Wi-Fi 恢复正常后再结束。若曾手动设置代理，请恢复原设置。退出桌面端会停止代理，但无法代你删除手机配置。"
        static let confirmRemoved = "已删除配置，结束测试"
        static let cancel = "继续测试"
        static let close = "返回"
        static let failed = "无法连接本机测试服务，请检查运行环境后重试。"
        static let invalidSSID = "请填写与手机一致的完整 Wi-Fi 名称。"
        static let results = "最近接口预览"
        static let limited = "试用范围：PokeHub 已知 API 域名。最多展示最近 20 条，每段正文预览 16 KB；不是完整抓包归档，也不代表支持所有 iOS 应用。"
        static let emptyBody = "没有可展示的正文"
        static let truncated = "此条正文仅展示部分内容，或已按大正文流式转发。"

        static func status(_ phase: IOSSetupPhase, count: Int) -> (String, String) {
            switch phase {
            case .idle: ("准备连接 iPhone", "确认 Wi-Fi 名称后点击“准备连接”，其余电脑端设置自动完成。")
            case .preparing: (preparing, "正在生成独立测试配置并检查本机代理。")
            case .waitingPhone: ("等待手机安装配置", "电脑端已准备好，请将配置发送到 iPhone 并完成下方步骤。")
            case .waitingTrust: ("已收到手机连接", "还没有通过 HTTPS 检查。请确认本次证书已完全信任，再打开手机上的“检查抓包连接”。")
            case .ready: ("手机 HTTPS 连接已通过", "尚未收到 PokeHub 接口，请在手机上操作 PokeHub；部分应用可能不使用系统代理。")
            case .capturing: ("已收到 \(count) 个目标接口", "继续操作 PokeHub，下方预览会自动更新。")
            case .stopped: ("测试已结束", "本次代理已关闭。需要再次测试时请重新准备连接。")
            case .failed: ("测试代理已中断", "请先删除手机测试配置，再结束本次测试并重新准备；不要保留失效代理。")
            }
        }
    }
}

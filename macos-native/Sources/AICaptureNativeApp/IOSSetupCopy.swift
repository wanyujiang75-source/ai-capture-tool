import Foundation

extension AppCopy {
    enum IOSSetup {
        static let title = "连接 iPhone"
        static let summary = "电脑端自动准备连接；手机端确认安装、信任测试证书后即可检查连接。"
        static let reconnectSummary = "已信任当前证书时，只需恢复本工具测试路由并重新验证手机连接。"
        static let wifi = "当前 Wi-Fi 名称"
        static let wifiHelp = "手机与 Mac 需连接同一网络。仅支持普通密码 Wi-Fi；企业账号网络请勿使用此配置。工具不读取或保存 Wi-Fi 密码。"
        static let prepare = "准备连接"
        static let reconnect = "重新连接 iPhone"
        static let reinstall = "首次安装或已删除配置？查看安装步骤"
        static let reuseHelp = "若已安装并信任这台 Mac 的当前证书，无需重装。请保持手机 VPN 开启，启用本工具专用测试路由，再打开“检查抓包连接”；尚未安装或已删除配置时才需重新发送。"
        static let lifetimeHelp = "证书默认有效一年，重启和隔天使用可复用。退出会停止代理但保留本机钥匙串身份，不会自动开始抓包。"
        static let preparing = "正在准备 iPhone 连接…"
        static let stopping = "正在结束 iPhone 连接…"
        static let share = "发送配置到 iPhone"
        static let shareHelp = "仅在首次安装或配置已移除时发送给自己的测试 iPhone。保留小火箭 VPN 时使用专用抓包节点和域名规则，不覆盖原配置；当前版本仍需人工确认这些设置。"
        static let install = "1. 接收并安装配置"
        static let installHelp = "在 iPhone 接收文件，进入“设置 → 通用 → VPN 与设备管理”安装“抓包工具 iPhone 测试配置”。旧临时配置不能自动升级，首次迁移需移除旧配置。若要求 Wi-Fi 密码，只在手机上输入。"
        static let trust = "2. 信任本次测试证书"
        static func trustHelp(_ name: String) -> String {
            "进入“设置 → 通用 → 关于本机 → 证书信任设置”，开启“\(name)”的完全信任。请核对名称，勿信任其他证书。该证书用于解密测试流量。"
        }
        static let verify = "3. 验证手机连接"
        static let verifyHelp = "点击手机桌面的“检查抓包连接”，或用相机扫描右侧二维码。通过后返回抓包页点击“开始抓包”，无需填写业务域名。连接验证不会自动开始记录。"
        static let stop = "结束连接并移除授权"
        static let remove = "请先从 iPhone 删除测试配置"
        static let removeHelp = "请先停用本工具的专用测试路由，保留原 VPN，再删除手机上的“抓包工具 iPhone 测试配置”（旧版为“临时配置”），恢复曾手动设置的 Wi-Fi 代理。确认后将删除本机抓包身份，下次需要重新安装证书。仅暂停使用请停止抓包，不必移除授权。"
        static let confirmRemoved = "已恢复手机网络，结束连接"
        static let cancel = "保留连接"
        static let close = "返回"
        static let failed = "无法连接本机测试服务，请检查运行环境后重试。"
        static let invalidSSID = "请填写与手机一致的完整 Wi-Fi 名称。"

        static func pairingFailure(_ error: Error, fallback: String) -> String {
            switch (error as? APIClientError)?.userFacingIssue.code {
            case "ios_pairing_storage": "无法访问本工具的钥匙串身份。请解锁 Mac 后重试；证书不会被自动更换。"
            case "ios_pairing_invalid": "原抓包身份缺失或损坏。请恢复手机网络，再结束连接并移除授权，重新配置。"
            case "ios_pairing_expired": "抓包证书已到期。请恢复手机网络，再结束连接并移除授权，更新证书。"
            case "ios_pairing_clock": "本机时间早于证书生效时间。请检查 Mac 日期与时间后重试。"
            case "ios_pairing_port": "原抓包地址无法使用，端口可能被其他程序占用。请检查 Mac 网络与占用程序后重试；工具不会结束其他程序或更换连接凭据。"
            default: fallback
            }
        }

        static func status(_ phase: IOSSetupPhase, count: Int) -> (String, String) {
            switch phase {
            case .idle: ("准备连接 iPhone", "确认 Wi-Fi 名称后点击“准备连接”，其余电脑端设置自动完成。")
            case .preparing: (preparing, "正在生成独立测试配置并检查本机代理。")
            case .waitingPhone: ("等待手机安装配置", "电脑端已准备好，请将配置发送到 iPhone 并完成下方步骤。")
            case .waitingTrust: ("已收到手机连接", "还没有通过 HTTPS 检查。请确认本次证书已完全信任，再打开手机上的“检查抓包连接”。")
            case .ready: ("iPhone 已连接，尚未开始抓包", "点击“开始抓包”，随后在 iPhone 操作目标应用。")
            case .capturing: ("已捕获 \(count) 个目标接口", "继续操作目标应用，在“接口”页查看结果。")
            case .stopped: ("连接已结束", "本次连接已关闭。需要再次抓包时请重新准备连接。")
            case .failed: ("测试代理已中断", "请先删除手机测试配置，再结束本次测试并重新准备；不要保留失效代理。")
            }
        }
    }
}

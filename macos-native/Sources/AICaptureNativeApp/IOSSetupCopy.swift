import Foundation

extension AppCopy {
    enum IOSSetup {
        static let title = "连接 iPhone"
        static let summary = "电脑端自动准备连接；手机端确认安装、信任测试证书后即可检查连接。"
        static let reconnectSummary = "当前 iPhone 已信任证书时可直接验证；更换新 iPhone 后，仍需在新手机安装并信任证书。"
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
        static let shareHelp = "发送仅含测试证书和检查入口的配置，不修改手机 Wi-Fi 或 VPN。请只投送到本次测试的 iPhone；新手机必须单独安装并信任。"
        static let wifiAlternative = "不使用小火箭？查看 Wi-Fi 代理方式"
        static let wifiAlternativeHelp = "仅在不使用 VPN 转发时选择此方式。该配置会设置当前 Wi-Fi 的抓包代理，不能与小火箭方式叠加；结束后需恢复手机 Wi-Fi 代理。"
        static let airdropHelpTitle = "隔空投送找不到手机？"
        static let airdropHelp = "在 iPhone 打开 Wi-Fi 和蓝牙，保持屏幕解锁并靠近 Mac。进入“设置 → 通用 → 隔空投送”，临时选择“所有人（10 分钟）”，再在 Mac 的投送窗口选择这台手机。\n若 Mac 提示需要“隔空投送代码”，在手机按提示获取，并自行填入 Mac 输入框；不要发送到聊天。核对接收设备名称，不要选择旧手机或他人设备。完成后恢复原隔空投送接收设置。"
        static let vpnTitle = "使用小火箭时"
        static let vpnPreparation = "切换前：保持 VPN 开启，记下首页当前节点名称和“全局路由”模式，作为结束后的恢复依据。不要导出订阅，也不要修改原节点或配置文件。"
        static let vpnSwitch = "证书安装并信任后，先完成下方“导入抓包节点”。随后在小火箭首页点选 Capture-Mac 名称行（不是右侧详情按钮），将“全局路由”临时设为“代理”，再验证连接。VPN 保持开启，不修改原节点、订阅、DNS 或配置；流量经 Mac 出网，出口 IP 可能变化。"
        static let vpnRestore = "结束时：先停止抓包，再在小火箭恢复原节点和全局路由模式，VPN 保持开启。确认手机能正常联网后再退出桌面端；工具不会自动替手机恢复。"
        static let install = "1. 接收并安装配置"
        static let installHelp = "在 iPhone 接收文件，进入“设置 → 通用 → VPN 与设备管理”安装“抓包工具 iPhone 测试配置”。锁屏密码只在手机输入。小火箭方式的文件应只有证书和检查入口；若包含 Wi-Fi 或 VPN 设置，请取消并核对所选文件。旧临时配置首次迁移需先移除。"
        static let trust = "2. 信任本次测试证书"
        static func trustHelp(_ name: String) -> String {
            "进入“设置 → 通用 → 关于本机 → 证书信任设置”，开启“\(name)”的完全信任。请核对名称，勿信任其他证书。该证书用于解密测试流量。"
        }
        static let verify = "4. 验证手机连接"
        static let nodeTitle = "3. 导入抓包节点"
        static let nodeSummary = "优先通过已信任的 USB 连接打开小火箭导入确认；请在手机确认添加，不会自动选用节点或切换 VPN。已有 Capture-Mac 时，请核对本次参数，不要重复添加。"
        static let nodeImport = "导入抓包节点"
        static let nodeRefresh = "刷新连接信息"
        static let nodeDevice = "接收手机"
        static let nodeChoose = "请选择接收手机"
        static let nodeLoading = "正在读取本机节点信息…"
        static let nodeSending = "正在发送节点导入请求…"
        static let nodeSent = "导入请求已发送。请在手机确认添加；若未出现确认，请使用下方手动方式。发送成功不代表节点已导入或连接已通过。"
        static let nodeFallback = "无法自动打开手机导入。请解锁并信任 USB 连接后重试，或使用下方二维码或手动参数；无需为抓包安装 Xcode。"
        static let nodeLoadFailed = "无法读取当前节点信息。请确认本机服务为新版且已准备连接，再刷新；不要沿用旧地址或密码。"
        static let nodeManual = "未出现导入确认？查看手动方式"
        static let nodeManualHelp = "在小火箭点右上角“＋”，类型选 HTTP，按下列参数新增 Capture-Mac。已有本工具节点时只更新该节点，不编辑原 VPN 节点。也可使用小火箭首页的扫描入口扫描节点二维码。"
        static let nodeQR = "显示节点二维码"
        static let nodeSecretHelp = "二维码和密码包含本机代理凭据，请勿分享。导入后仍需手动点选 Capture-Mac，并临时选择“代理”路由。"
        static let nodeHost = "服务器"
        static let nodePort = "端口"
        static let nodeUsername = "用户名"
        static let nodePassword = "密码"
        static let showPassword = "显示密码"
        static let hidePassword = "隐藏密码"
        static let nodeMigrationTitle = "更换电脑、手机或网络时"
        static let nodeMigrationHelp = "换手机、Mac 与网络不变：通常沿用地址和端口，新手机仍需安装并信任证书、导入节点和验证。\n换 Mac：使用新 Mac 当前生成的地址、端口和凭据，并安装信任新 Mac 的证书，不复制私钥。\nMac 换网络或 IP 改变：重新准备连接，更新 Capture-Mac 的当前参数；同一有效证书无需重装。端口同一身份优先复用，冲突时提示处理，不自动结束其他程序。始终以本页最新参数为准。"
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
            case .waitingPhone: ("等待手机接入", "电脑端已准备好，请依次完成证书安装与信任、节点导入、临时转发及连接验证。")
            case .waitingTrust: ("已收到手机连接", "还没有通过 HTTPS 检查。请确认本次证书已完全信任，再打开手机上的“检查抓包连接”。")
            case .ready: ("iPhone 已连接，尚未开始抓包", "点击“开始抓包”，随后在 iPhone 操作目标应用。")
            case .capturing: ("已捕获 \(count) 个目标接口", "继续操作目标应用，在“接口”页查看结果。")
            case .stopped: ("连接已结束", "本次连接已关闭。需要再次抓包时请重新准备连接。")
            case .failed: ("测试代理已中断", "请先删除手机测试配置，再结束本次测试并重新准备；不要保留失效代理。")
            }
        }
    }
}

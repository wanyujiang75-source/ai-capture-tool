import Foundation

extension AppCopy {
    enum IOSCapture {
        static let title = "iPhone 抓包"
        static let platform = "抓包设备"
        static let summary = "连接 iPhone 后点击“开始抓包”，再打开需要测试的应用，无需填写业务域名。"
        static let scope = "记录经过本工具的 HTTP(S) 请求，不按应用或域名限制。测试期间请勿操作无关敏感应用；未经过本工具或拒绝测试证书的连接无法解密。"
        static let start = "开始抓包"
        static let stop = "停止抓包"
        static let viewResults = "查看接口"
        static let configure = "连接说明"
        static let stopHelp = "停止抓包会保留手机连接，不再记录新接口。再次开始无需重新安装配置。"
        static let startFailed = "iPhone 抓包未能启动。请检查手机连接后重试。"
        static let stopFailed = "无法确认 iPhone 抓包已停止。请检查连接状态，必要时恢复手机网络并结束连接。"
        static let endFailed = "无法确认连接已结束。请保持手机代理关闭，检查本机服务后重试。"
        static let projectsFailed = "无法加载抓包项目，请检查本机服务后重试。"
        static let checkConnection = "检查连接"
        static let starting = "正在启动 iPhone 抓包…"
        static let stopping = "正在停止 iPhone 抓包…"
        static let saving = "正在保存项目…"
        static let resultsUnavailable = "无法打开接口"
        static let invalidProject = "请填写项目名称和至少一个目标域名，最多 64 个。"
        static let saveFailed = "项目未能保存。请检查域名格式及本机服务后重试。"
        static let sourcesFailed = "无法获取抓包记录，请检查本机服务后重试。"
        static let flowsFailed = "接口同步失败，请检查本机服务后重试。"
        static let detailFailed = "无法加载接口详情，请重新选择接口或检查本机服务。"
        static let curlUnavailable = "暂时无法生成可重放的 cURL。请求可能尚未完成、正文被截断或连接中断；已捕获的 Request 和 Response 仍可查看。"
        static let waiting = "等待接口，请在 iPhone 中操作目标应用。"
        static let androidOnly = "此页面仅支持 Android。iPhone 应用请在手机安装；iPhone 运行日志暂不支持。"
        static let quitTitle = "退出前请恢复 iPhone 网络"
        static let quitHelp = "退出会停止电脑端代理。请先停用本工具专用测试路由，恢复曾手动设置的 Wi-Fi 代理，保留原 VPN。新版证书与本机钥匙串身份会保留，下次可重新连接；旧临时配置失效后仍需移除。工具无法自动修改手机路由。"
        static let cancelQuit = "返回处理"
        static let confirmQuit = "继续退出"

        static func presentation(_ status: IOSSetupStatus) -> (String, String) {
            if status.canResume == true {
                return ("iPhone 连接已暂停", "证书与专用连接信息已保留。点击“连接 iPhone”后重新连接，再在手机验证；不会自动恢复抓包。")
            }
            if status.requiresPhoneSetup && status.identityReused == true {
                if status.routeChanged == true {
                    return ("请更新手机抓包地址", "Mac 的地址或网络已改变，证书无需重新信任。请只更新本工具专用测试路由后验证，原 VPN 保持不变。")
                }
                return ("等待手机重新验证", AppCopy.IOSSetup.reuseHelp)
            }
            if !status.isConnected { return AppCopy.IOSSetup.status(status.phase, count: status.flowCount) }
            switch status.recordingState {
            case .recording:
                return ("正在抓包 · 已捕获 \(status.flowCount) 个接口", "请在 iPhone 操作目标应用，在“接口”页查看 Request 和 Response。")
            case .stopped:
                return ("抓包已停止，手机仍保持连接", "已保留本次结果。点击“开始抓包”创建新的记录。")
            case .limitReached:
                return ("本次抓包已达到保存上限", "已停止记录并保留手机连接。请查看已有结果，或开始新的抓包。")
            case .failed:
                return ("本次抓包已中断", "已有结果已保留。请检查手机连接后重新开始。")
            case .idle, nil:
                return ("iPhone 已连接，尚未开始抓包", "点击“开始抓包”，随后在 iPhone 操作目标应用。")
            }
        }
    }
}

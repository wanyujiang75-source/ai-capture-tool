# macOS 桌面更新

当前用户使用的原生 SwiftUI App 在应用菜单提供「检查更新…」。旧预览版手动安装首个正式版，之后手动检查，由 Sparkle 展示版本、下载进度和确认。关闭定时检查和自动安装。保留手动下载路径。

- 使用 SwiftPM 锁定 Sparkle 官方二进制版本。手工打包时把 Framework 和必要辅助程序放入 App，签名后执行严格签名验证。正式包使用现有 Apple Developer ID 公证路径。
- 正式版使用 `TRACEDECK_VERSION` 和显式递增的 `TRACEDECK_BUILD_NUMBER`。保持 bundle ID 和原数据目录，正式包内置更新公钥及 GitHub 正式 Release 的固定 HTTPS appcast URL。开发预览包沿用手动分发。
- 菜单检查与安装确认前都检测正在执行的本地操作、手机恢复标志和对应内嵌后端的活跃会话。查询失败时提示稍后重试或手动安装。更新期间暂停桌面操作，取消后恢复可操作。保留已有退出与重启流程。
- 正式分发生成现有手动安装 ZIP 和独立的签名更新 ZIP。签名输入为公证后最终归档。由 Sparkle 工具生成 appcast，指向当前版本的固定 Release asset。正式 Release 在所有资产就绪后发布。保留 GitHub 中旧发行资产。
- 用单测覆盖捕获中、待恢复、后端不匹配、后端失败和正常路径。校验版本、框架运行路径、签名及生成后的 appcast 和 archive，以隔离构建验证，不触碰真实运行数据。Developer ID 公证和 GitHub 资源上线需正式凭据及发布授权。

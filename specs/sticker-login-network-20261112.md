# StickerHub Google 登录链路定位与最小修复

## 约束

- 仅 PKG110 上原版 StickerHub，用户已授权选择第一个 Google 账号。不得改包、Root、清数据、复制登录态、编辑原 VPN 节点或配置。测试后恢复实际基线。
- 保持客户端及上游证书校验。Google 认证流量若需出网支持，只可加密透传，不保存 Token、账号、正文；不得以整机抓包替代目标应用隔离。跨进程支持必须明确范围并保持默认采集边界。
- 原始有界日志仅在私有临时目录，仓库仅存脱敏原因/计数/状态；安全确认和密码输入交由用户。

## 定位顺序

1. 记录安装版本、原 APK 身份、USB/网络/VPN/代理基线，检查真实 Google 登录错误（不要用统计组件 TLS 错误代替）。
2. 有界元数据定位：目标 app 发起连接与客户端 TLS 失败域名；GMS 是否进入单应用隧道。检查现有代理在 TLS 前后生效的差异，不默认使用 requestheaders 能覆盖 TLS 透传。
3. 一次只改变一项：先验证登录安全端点加密透传，再判断跨进程 Google 服务出网是否必要。透传必须通过已有电脑代理、不能回退直连；不能将仍为密文的流量记为已解密。
4. 确定原因后写失败回归、实现最小隔离模块，再运行后端/助手/Swift 相关回归及完整构建。保留模拟器/iPhone 原链路。
5. 从桌面启动，按授权选首个账号；验证进入首页与关联业务 Request/Response，停止恢复，记录未覆盖项。若证书策略/跨进程范围无法在约束内解决，则停止并明确剩余条件，不反复换证书或隐藏失败。

## 验收

- 环境隔离的 unittest 针对路由、透传不归档、错误诊断、停止与原配置不变；独立本机 HTTPS/CONNECT 端到端，不涉及账号。
- 必要时 Java/Swift 测试及 macOS 构建验签。
- 真机登录结果、目标业务正文、原包未变、原 VPN/系统代理恢复独立记录。
- 不推送、不发布；失败保留 DOING 排查，实质外部阻塞才标 BLOCKED。

## 2026-11-12 对照结果与已交付范围

- 恢复任务后短暂未检测到 USB，随后 PKG110 重新授权在线。基线无活动 VPN、系统 HTTP 代理 null，无桌面抓包。
- 原版 StickerHub 3.18.14(195)：无抓包、无 VPN 时选择首个 Google 账号立即复现“登录服务出现问题”。只启动已有 Clash（规则模式/新配置，不编辑节点或配置），同一首账号进入应用首页。账号选择页属于 com.google.android.gms，当前 IncludedApplications 只含目标应用，助手还强制单包隔离。证据支持 Google 外网/跨进程通路缺口，不能将上一轮 CctTransportBackend 的证书 blocklist 错误当作登录根因；尚未采集 GMS 精确失败端点，不宣称其所有内部步骤均已定位。
- 登录后通过桌面启动 #102：7 请求/7 响应，get_app_config POST 200，4 B 请求/405 B 响应；get_latest_messages POST 200，2 B/2255 B。JSON 可解析、truncated=false，桌面 Request/Response 已打开核对。101 仅握手，不声称完整 WebSocket；后台有 update_user_active 写入，未手工修改业务数据。82 次其他 TLS 失败仍保留，不宣称全部域名支持。
- 本轮中途电脑代理 Google HTTPS 探针失败，保护机制自动终止，未绕过检查或改代理。助手退出后自动恢复 Clash 未完成，通过原应用既有启动按钮恢复，再由桌面“检查网络恢复”确认 stopped。之后关闭本轮临时启用的 Clash，恢复整个对照开始时的无 VPN 状态；原节点/配置/系统代理保持，登录状态保留。旧 PHK110 待恢复提醒未删除。
- 实施范围为已验证的操作流程提示修正：开始按钮前明确先用原 VPN 完成 Google 登录；重登录先停止恢复；不记录 Google 登录阶段。未增加 GMS UID、未改 TLS、未安装证书、未改 APK，不声称实现抓包中无缝 Google 登录。
- 文案显示契约先 RED 后 GREEN，后端 28 项、Swift AndroidPhysicalTests 11 项通过；完整构建与签名通过，build=sticker-login-guidance-20261112。旧 App 备份于 CaptureToolBackups/20261112-before-login-guidance.IIFmh4。
- 剩余工程：若要求抓包过程中直接 Google 登录，需独立的登录依赖加密转发和身份隔离，避免 GMS 为其他应用产生的流量被归档；当前无法仅靠扩大 IncludedApplications 安全完成。总体修复仍 DOING，本轮只确认原因边界和可用绕行，不标完整修复。

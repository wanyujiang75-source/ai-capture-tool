# StickerHub Google 登录链路定位与最小修复

## 约束

- 仅 PKG110 上原版 StickerHub，用户已授权选择第一个 Google 账号。不得改包、Root、清数据、复制登录态、编辑原 VPN 节点或配置。测试后恢复实际基线。
- 保持客户端及上游证书校验。Google 认证流量若需出网支持，只可加密透传，不保存 Token、账号、正文；不得以整机抓包替代目标应用隔离。跨进程支持必须明确范围并保持默认采集边界。
- 原始有界日志仅在私有临时目录，仓库仅存脱敏原因/计数/状态；安全确认和密码输入交由用户。

## 定位顺序

### 跨进程转发实现契约（本轮）

- Android 10+ 使用 VPN 所属 UID 的 ConnectivityManager.getConnectionOwnerUid 查询原始 TCP 四元组。助手仅允许目标非共享 UID 与系统 com.google.android.gms 进入隧道；不能靠域名猜进程。
- 私有 USB 文件下发每次随机认证令牌；localabstract 名称使用令牌的 SHA-256，不暴露认证值，控制端仅返回 target/login/unknown。查询/回复用 HMAC-SHA256 双向认证，绑定方向、随机 nonce、原四元组和角色，控制连接不发送令牌，防端口冒充与旧回复重放。ADB 仅新增本任务 tcp:0 转发，停止时核对序列号、端口、远端名称后只删除该项；记录归属以支持重启后的清理。请求/响应有长度、超时和并发上限，不包含账号或正文；断线/租约到期关闭。
- worker 在 TLS 解密前查询连接身份。target 走现有采集；login 使用原电脑 HTTP 代理的 CONNECT 与不生成 flow 的原始 TCP 转发，保留端到端 TLS。UDP 仅允许 WireGuardMode 的既有虚拟 DNS 地址 10.0.0.53:53，其由 Mac 原系统 resolver 解析（Android netd 可能持有 DNS socket，明确豁免 UID 查询，不承诺 DNS 经 HTTP CONNECT）；任意其他 UDP/53 和 QUIC 拒绝以回落 TCP。除该既有 DNS 例外，身份未知或控制通道失败拒绝，不直连、不回落采集。
- 本轮只实现系统 Google 服务 UID 的加密转发；目标应用内仍按既有范围抓包。未证实需要新增目标进程内 Google 端点旁路，不凭域名猜测扩大特殊处理。普通业务归档不扩大到系统服务，不关闭原有 TLS 校验。
- 自动验收覆盖角色分类、错误/未知/失效控制通道、未解密 TLS 字节完整性、上游失败不直连、归档排除、单应用旧路径回归、停止清理。真机需抓包持续运行时首账号登录进入首页与业务完整响应，不清除登录态；如已登录导致无法重复登录，记录需要的用户动作，不自行清数据。

### 前一子项：真实应用联网证据（历史范围）

- 当前仅检查手机到 Mac 与 Mac 代理到 Google，不能推导目标应用的完整链路。保留这些准入保护，不增加 GMS 转发或 TLS 绕过。
- worker 只对实际上游完成的 HTTPS 响应记录时间及状态码；排除 HTTP、重放、本地合成响应和 101。4xx/5xx 是服务有响应但请求失败，不标业务成功。错误及响应同时存在时显示部分连接异常。
- 最近 30 秒响应为近期证据，超过窗口为近期无新响应，不判为断网。仅握手/计数/图片显示不产生成功状态；每次任务从空证据开始。
- worker 快照超过 15 秒、停止、重连及读取失败不展示实时成功。数据结构固定大小，无 URL、账号、正文或广告标识。
- Banner 仅人工观察是否新加载，不自动识别广告域名、不点击广告，不据此判断 VPN。
- 范围：android_physical_evidence.py、android_physical_worker.py、android_physical_service.py；AndroidPhysicalModels/Copy/View.swift；对应 Python/Swift 测试、隔离 UI 夹具；docs/desktop-user-guide.md。
- 验收：Python 单元/worker钩子与服务回归、Swift 状态测试、完整构建验签、隔离原生 UI。手机无缝 Google 登录不属于此子项完成声明。

验收结果：真实应用联网判定子项完成。Python 聚焦 87 通过/1 跳过，独立真实 worker 1 通过；Swift 205 项（另1项 opt-in跳过）；完整构建与严格验签通过。隔离 UI 验证等待、近期响应、部分异常、静默和503清除，均为合成数据而非新增真机抓包证据。APK、手机 VPN、节点及配置未修改；原安装应用未覆盖，构建位于 macos-native/build/抓包工具.app。真实登录和 Banner 是否加载仍不可从本轮结果推导。

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

## 跨进程转发实际验收（2026-11-12 续做）

- 原因与修复：Google 账号选择/认证由系统 Google Play 服务参与，原先仅目标包入隧道导致该进程没有电脑代理出网路径。新增原始 TCP 四元组 UID 查询，在 TLS 前区分目标应用和系统 Google 服务；同签名、系统级共享 UID 组全部视为仅加密转发，不能作为采集目标。Google 服务原始 TLS 经现有 HTTP CONNECT，不终止 TLS、不生成归档 flow。
- 真机 PKG110 / Android 16 / 原版 StickerHub 3.18.14(195)：桌面启动 #103 后在登录页选择用户授权的首个 Google 账号，进入画册首页。22 请求/22 响应，仅业务 Supabase 主机；应用自身 /auth/v1/token POST 200 请求1534B/响应1716B，get_dice_event POST200 请求4B/响应402B，complete=true、truncated=false。未读取或导出认证正文到代码/证据文档。系统 Google 服务无归档。
- #103 后出现一次局域网探测失败，保护机制停止并恢复基线；复测实际链路恢复。增加仅对已经就绪连接的一次新鲜重试，不放过首次准入失败、Wi-Fi 关闭、取消或连续失败。RED 复现后 GREEN。
- 最终哈希通道构建的 #104：桌面启动后得到6请求/6响应；get_active_announcements POST200 请求27B/响应4180B，完整且未截断，Request/Response 页面已核对。已登录状态保留，没有为了重复登录退出账号或清数据。抓包持续数分钟、两项网络准入检查通过，然后从桌面点击“停止并恢复网络”成功。
- 恢复：两轮测试前均无活动 VPN，结束后 active VPN type=-1、HTTP proxy=null、助手进程退出。仅本次 capture-owner USB 转发被移除，原有3条转发保留；本机 recovery.json 已清除，旧 PHK110 待恢复提醒原样保留。未改原节点、订阅、配置或目标 APK，未新增证书。
- 边界：#103另有40次 TLS 失败，#104另有37次；101只代表握手。未验证广告 Banner、所有域名、其他版本、非系统Google服务或其他登录组件，不宣称通用成功。USB控制通道断开会拒绝新连接并依既有租约停止，不静默回退解密/直连。
- 自动验收：Android真机相关107项（106通过、1 opt-in跳过）；iOS相关101项（96通过、5 opt-in跳过）；Swift205项通过（另1 opt-in跳过）；Android助手9项单元测试与APK构建通过；完整macOS构建严格验签通过。真实loopback TLS对照原站证书不变、HTTP钩子零调用，上游403不直连、unknown身份不接入；角色缓存并发上限RED=1031、修复GREEN=1024。
- 收尾审查发现并修复控制端口被接管后冒充角色的P1，以及任意UDP/53放行的P2；两者先RED后GREEN。新增HMAC nonce/角色绑定、旧回复重放和跨Java/Python签名向量测试；复审未发现新的可复现P1/P2。仅保留上文明确的DNS例外，不改原DNS配置。
- 加固版 #105 真机：桌面启动5请求/5响应，仅业务主机；get_latest_messages POST200 请求2B/响应2255B，get_active_announcements POST200 请求27B/响应4180B，均完整无截断。手动停止后助手退出、无活动VPN、HTTP proxy=null，本任务控制通道与本次mobile工具额外通道清理，保留原3条USB映射。最终版保留已有登录态，未再次注销重登；首次抓包中登录的证据为#103，身份认证加固后的业务链路证据为#105。
- 最终本机构建：macos-native/build/抓包工具.app，build=google-routing-auth-20261112，并更新 /Applications/抓包工具.app；旧版备份于 CaptureToolBackups/20261112-google-routing.1uNlkY。仅更新独立连接助手，原APK保持；未推送或发布远程包。

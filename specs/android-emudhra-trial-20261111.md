# Android 原版 PokeHub 受损 CA 隔离验证

## 范围

- 唯一手机 d5f39352 / PHK110，唯一业务应用 com.mi.poketrade，禁止使用测试副本或模拟器结果替代。
- 用户授权临时抓包转发以验证此前公开研究线索；保留原 VPN 节点和配置，结束恢复。不修改 Mac 系统代理或原上游。
- 不 Root、不改源码/APK、不注入、不降级系统或安全补丁、不关闭更新、不读取应用私有数据、不复制登录态。
- 该路线是特定证书信任漏洞验证，不是正常用户 CA 导入，不是产品可用性承诺。先核对官方实现及副作用；不能限制范围或保证恢复则不开始。
- 只读业务页触发；登录/权限确认由用户完成；不进行交易、发帖或业务修改。仅 PokeHub 进入临时 VPN 隧道；无关应用不解密/归档。

## 验收

1. 记录设备、原版版本与 APK/split 哈希，当前 VPN 所有者/模式/可见节点/配置，系统代理及原 USB 映射；不复制订阅密码。
2. 官方 mitmproxy 版本与 eMudhra 行为核实，独立运行时，不升级桌面现用服务。保留上游校验，不全局设置 ssl_insecure。
3. 本机受控自检与电话业务实测分开。普通浏览器可能正确拒绝受损链，不能用浏览器失败直接否定目标客户端或为此降低浏览器安全。
4. 只让 PokeHub 进入独立临时转发；有限时间/字节记录，原始正文仅私有临时文件，用摘要、大小、结构与哈希记录证据，避免 Token/个人信息进入仓库。
5. 成功需至少一条真实业务的关联 Request/Response，检查方法、URL、请求头/响应头、状态及完整正文；请求本身无正文时明确记录，不伪造。TLS/CONNECT/密文或仅状态码不算成功。
6. 失败需区分接入、DNS/上游、TLS信任、pinning证据和正文完整性。不从 unknown_ca 单独断言 pinning；最多两种官方证书链排序对照，失败后停止，不盲目换工具。
7. 停止本轮服务、恢复原 Clash 与原模式/节点/配置，核对网络可用性/系统代理/原包哈希；删除本轮隧道、导出文件、私钥和抓包正文，只回收新增 USB 映射。
8. 脱敏证据更新与 git diff --check。未恢复或未取得正文不标完成，不发布桌面安装包。

## 官方线索

- https://www.mitmproxy.org/posts/releases/mitmproxy-12.3/
- https://github.com/dart-lang/sdk/security/advisories/GHSA-frr6-h895-5pxp
- https://emanuele-f.github.io/PCAPdroid/tls_decryption

## 本轮记录

### 身份与隔离

- 2026-11-11，PHK110 / d5f39352，Android 16，安全补丁 2026-05-01，user 构建、ro.debuggable=0。
- Play 原版 PokeHub com.mi.poketrade 2.1.1(98)，当前已安装 12 个 APK/split 的 SHA-256 与此前提取的原版逐一相等；试验后再次全部相等。对应原包 libflutter.so 的 Dart 版本标识为 3.10.7。未将测试工程版本推定为线上版本。
- 独立 Python 3.12.5 / mitmproxy 12.3.1 / OpenSSL 4.0.3；未升级桌面现用服务。仅启用本轮验证选项，上游 ssl_insecure=false，未取消真实服务器证书校验。
- 临时 WireGuard 隧道 IncludedApplications 仅 com.mi.poketrade；只解密本轮目标业务主机，其他主机透传。仅操作原版启动及市场只读页面，不使用浏览器结果替代业务通过。
- 复用 Mac 已存在的 127.0.0.1:7897 上游，不改其节点、配置或系统代理。本轮没有在手机安装任何新 CA，也没有 Root、Frida 注入、改源码/包或降级。
- 独立目录权限 0700，原始归档/隧道密钥 0600；单正文 8 MiB、归档 100 条/30 MiB、代理 900 秒自动停止。最终在超时前主动结束。

### 失败定位与修正

1. 首次独立代理因禁用 dumper 后设置未知 flow_detail 选项而无法启动；在手机切换前去掉该无关选项。本机隔离 HTTPS 自检通过，客户端仅使用从手机读取的公有系统根证书，不加入测试 CA。
2. 手机业务 TLS 握手已成功，但归档按 request.host 匹配漏掉请求。增加目标 SNI 诊断后确认真实 HTTP 请求存在，不能将归档 0 条误判成解密失败。
3. 目标进程沿用了 Clash 缓存的 fake-IP 198.18.1.99；临时透明隧道把它作为路由目的地址，因此虽能解密，请求没有正常出网。
4. 在独立代理内严格核对 TLS SNI 与 HTTP Host 一致，再将内部路由目的主机规范化为该域名，经原 Mac 上游发出。逐次断言原 HTTP headers.fields 与 authority 未变；未改业务请求正文、手机 DNS、VPN 原配置或应用数据。
5. 仅使用默认官方受损证书链排序即通过，没有尝试第二套排序或扩大业务主机范围。

### 真实正文结果

最终 14 次目标 TLS 握手全部完成，27 条目标请求均有对应 HTTP 响应，未记录 target_tls_failed_client、target_tls_failed_server 或 target_http_error。客户端与上游均为 TLS 1.3。27 条包含静态资源/缓存响应及 WebSocket 升级，不能表述为 27 个业务接口。

| 方法与路径 | HTTP | 请求体字节 | 响应体字节 | 结构验证 |
| --- | --- | --- | --- | --- |
| POST /rest/v1/rpc/get_app_config | 200 | 80 | 2774 | 请求为 3 字段 JSON 对象，响应为 10 字段 JSON 对象 |
| POST /rest/v1/rpc/get_latest_messages | 200 | 4 | 613 | 请求是 JSON null，响应为 3 元素数组；未记录消息内容 |
| POST /rest/v1/rpc/get_active_lucky_draw | 200 | 4 | 3760 | 请求是 JSON null，响应为 3 字段 JSON 对象 |
| POST /rest/v1/rpc/trainer_match | 500 | 27 | 106 | 请求为 2 字段对象，响应为 4 字段错误对象，属于真实上游错误而非 TLS 失败 |

- 卡牌页在实机 UI 显示列表；训练家页仍出现重试，同时抓到上述 500。不把页面业务失败隐藏为全功能通过，也不在本轮修复服务端。
- 独立 FlowReader 验收退出码 0：27 条 ID 与摘要一一对应，所有 request/response 正文均存在、非流式、时间戳结束字段存在，字节数与 SHA-256 一致；适用响应的 Content-Length 与原始正文长度一致，RPC JSON 全量解析成功。
- 每条原始记录含 Request/Response 头；200 RPC 的请求头 10 项、响应头 23 项。确认客户端 Host 与 TLS SNI 一致、真实上游经既有代理、未禁用上游校验。没有在仓库记录 Authorization、Cookie、参数值或个人响应数据。
- get_app_config 请求体 SHA-256：3df1157ef46cd397f7514ca4391e0e59e5cdefc41bc594a9cd096ac285e9cd63；响应体 SHA-256：b96a91b420803a9a0610bf51768aaf028d0db97760bf51474daba1d5036b2813。
- WebSocket 仅验证 101 握手，不宣称已验收其后消息帧；304 无正文为协议正常结果，不冒充有正文的业务成功。

### 恢复与验证命令

- 关闭并删除本轮 Capture-CA-1111 隧道，WireGuard 列表恢复空列表；删除手机 Download 中同名 .conf。未删除用户其他工具或配置。
- 原 Clash 恢复 CONNECTED/VALIDATED；UI 独立核对规则模式、原“自动”配置、Proxies → US → 原“日用 专线 美国[0.2]”节点。未编辑原节点或订阅；这里是行为及 UI 核对，不冒充原配置私有文件逐字节哈希验证。
- baseline.py final 退出码 0：设备身份、原版 12 文件摘要、手机 http_proxy=null、reverse 空列表、Mac scutil --proxy 与原 VPN 所有者均与基线一致。
- 原 USB forward tcp:23761→10156、tcp:36166→10157 保留；仅回收本轮 mobilecli-server 新增的 tcp:57038 映射，最终 forward 列表与最初两项一致。
- 仅 SIGTERM 本轮已核对命令行的代理 PID 64204，进程正常退出码 0；lsof 检查 UDP 65112 与 TCP 60196 无监听。未杀死其他服务。
- 私有 verify.py（SHA-256 abd26f70be7012876e93a6d4b6dd42051cf90424dafc16f012f92c2bedc01342）完成上述正文验收；独立代理最终脚本 SHA-256 30e913fc2d891c00ec22254de70615ad6364f8ba14b15d05a66792a1388f85cd。
- 本轮私有目录 /private/tmp/pokehub-ca-trial-20261111.KO5APa 的归档、密钥、独立运行时和诊断文件在记录脱敏结论后统一移除；最终清理及 git diff --check 状态见 progress.md。
- 清理完成：test ! -e 本轮目录退出码 0；带 force 的首次删除命令被命令保护拒绝，改用同一明确目录的不带 force 递归删除成功，未扩大范围。差异检查通过；没有运行产品构建或现用服务回归，因为本轮未改产品代码/运行时。

### 结论及边界

本设备、本原版构建的完整 HTTPS Request/Response 验证通过，之前“普通用户 CA 不被信任”的结果不等于本轮新链路仍不可行。没有使用应用日志、服务端日志、重放合成响应或修改包代替业务抓包。

这是受影响客户端信任受损 CA 的安全漏洞验证，不是通用或永久方案。Dart 官方公告列出稳定版 3.13.7 / Flutter 3.47.8 的修复；不能承诺修复后的构建、证书固定客户端或其他应用同样有效。应将安全风险告知项目维护者并升级重建，不能为了持续抓包而建议降级、停止更新或保留漏洞。

本轮仅完成隔离技术验证；没有接入桌面 UI/后端、没有产品回归/打包/推送。既有 NR-1 的历史失败记录保留，本轮新证据另行记录，不据此将整个免 Root 产品计划标为已交付。

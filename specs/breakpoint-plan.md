# 抓包工具断点功能调研与实施计划 V1

日期：2026-11-04。交付状态：BP-0至BP-3的阶段验收已通过。BP-2接入默认关闭的产品传输与归档；BP-3接入原生规则、队列、请求/响应编辑及归档对照。BP-3通过Swift152项、后端75项、真实链路45项、既有抓包249项和独立原生窗口验收，证据见`breakpoint-bp3.md`；BP-2完整安全矩阵见`breakpoint-bp2.md`。BP-4真实设备、安装包与使用说明综合验收尚未开始，未替换当前安装包或远端发布。原addon-only的NO-GO及BP-0隔离实验历史保留；仅在支持的mitmproxy版本与安全适配条件下装载产品能力。

## 1. 结论与边界

建议做。沿用现有 mitmproxy 转发链路，在桌面端“接口”页加入断点规则、待处理队列和编辑面板，不要求安装或启动 Charles。首版覆盖已经接入且能展示明文 Request/Response 的 Android 和 iPhone 流量。

核心不是修改已经保存的接口记录，而是在网络转发前真正暂停、修改、继续：

```text
应用 -> [请求断点：修改参数] -> 服务器
应用 <- [响应断点：修改返回内容] <- 服务器
```

- 请求断点：服务器尚未收到该次请求的 HTTP 头和正文，修改会影响服务器收到的参数。建立 TCP/TLS 连接不等于已经发送 HTTP 请求。
- 响应断点：服务器已执行请求，应用尚未收到最终响应头和正文。可以测试空列表、异常状态和边界值，但不能撤销服务器已经执行的操作。
- 对历史接口设置规则，只影响之后重新触发的请求，不会倒退修改已经发生的通信。不自动重放请求，尤其不重发支付、提交等有副作用的操作。
- BP-P1 只规划的历史交付已结束。本轮经用户授权，仅修订评审意见并实施 BP-0 测试原型，不接入产品、不构建或重启现有应用、不拦截真实手机、不改变 VPN/原节点配置、不推送或更新安装包。

## 2. 竞品与底层调研

| 工具 | 官方确认的能力 | 本项目借鉴点 |
| --- | --- | --- |
| Charles | 按 URL 条件匹配，请求/响应/双阶段暂停；队列中可应用修改、终止或忽略修改后继续 | 清楚区分三个动作，不能把“取消编辑”误解为终止网络请求。[官方说明](https://www.charlesproxy.com/documentation/proxying/breakpoints/) |
| Proxyman | URL、方法、参数、头、正文及响应状态码编辑；可从已抓到的接口创建规则，再次触发时拦截；HTTPS 需先能解密 | 从接口行创建规则，降低手工填写成本；编辑和抓包准入分开。[官方说明](https://proxyman.com/docs/advanced-features/breakpoint) |
| Fiddler Everywhere | 规则暂停实际转发，可处理单条或恢复全部；正文修改涉及编码和长度头；等待期间客户端可能超时并重试 | 全部放行、协议字段自动维护、超时和重试提示是必要能力。[官方说明](https://www.telerik.com/fiddler/fiddler-everywhere/documentation/modify-and-filter-traffic/breakpoints) |
| mitmproxy | Flow 提供 intercept/resume/wait_for_resume；非流式事件可在转发前处理完整内容，流式的 request/response 事件发生时正文已转发 | 复用底层能力，但必须按实际事件顺序接入，不能只给详情页增加输入框。[Flow API](https://docs.mitmproxy.org/stable/api/mitmproxy/flow.html)、[事件语义](https://docs.mitmproxy.org/stable/api/events.html) |

以上是官方文档调研，不是对三款商业工具的本机操作验收。下文的默认值、交互及接口均为本项目设计，不声称与竞品默认配置相同。

## 3. 当前代码与接入位置

调研基线：`3f1284f`；本轮执行基线：工作树 `codex/ios-device-trial`，HEAD `c4a7d6c`。`requirements-console.txt` 固定 mitmproxy 12.2.3，本机开发环境读取到的安装版本相同。

| 已核对位置 | 现状 | 断点改造要求 |
| --- | --- | --- |
| `scripts/start_mitm_socks_stack.sh`、`scripts/start_mitm_stack.sh`、`capture_console/runner.py` | Android 由受托管的 mitmweb 转发，分别涉及 SOCKS/普通代理模式 | 两种启动路径均装载本工具 addon，不另起争用端口的代理，不修改 Frida 导流实现 |
| `scripts/ai_capture_export.py` | 从 mitmweb 获取 flow 和正文并保存文件，是导出器 | 不能在这里才修改请求；需接收断点元数据，正确归档最终版本 |
| `capture_console/ios_pairing_proxy.py` | iPhone 独立 DumpMaster 进程，负责认证、手机隔离、连接检查和录制；配置大包流式阈值 | 共用断点引擎，保留认证/手机隔离和流式保护；检查页不参与断点 |
| `capture_console/ios_recording.py` | requestheaders/responseheaders 安装逐块归档回调，块被立即原样转发 | 命中可编辑断点时必须在转发前决定有界缓冲，不能等归档后再改 |
| `capture_console/ios_recording.py` 的 stop 与代理 switch | 停止时先关闭归档，再切换透传；切换会关闭既有连接 | 新增停止接收断点、结算待处理项、有限排空，再关闭归档，不能假称所有在途请求必定完成 |
| `capture_console/results.py`、`capture_console/ios_results.py` | Android 文件与 iPhone SQLite/正文文件两套读路径 | 同时支持原始/有效版本，旧记录继续可读，不在列表批量读取正文 |
| `macos-native/Sources/AICaptureNativeApp/FlowViews.swift` | 原生接口列表、搜索、过滤、详情和清空列表 | 原界面增加入口；待处理队列独立于搜索和“仅看接口”过滤 |

本机 mitmproxy 源码额外确认：头事件位于转发头部之前；超过 `stream_large_bodies` 时可切换流式，包括未知长度正文。该路径会改变 stream 状态，不能假设自定义归档回调始终保留。需要先以 12.2.3 的真实代理测试固定契约，不修改 site-packages、不依赖私有方法打补丁。

## 4. 用户流程与界面

保留“抓包 / 安装应用 / 接口 / 日志”四个导航，不新增顶级页面。

### 4.1 普通使用

1. 用户按现有流程开始抓包，在“接口”页选中一条接口。
2. 点击行菜单“设置断点”，自动带入方法、协议、域名、有效端口、路径；默认不带查询参数或认证信息，不增加手填步骤。
3. 选择“发送请求前”“返回响应前”或“两者”，默认“仅下一次”。点击“启用断点”。
4. 在应用中再次触发接口，桌面显示“待处理 1”，打开编辑面板；不会连续弹窗抢焦点。
5. 编辑后点击“应用修改并继续”，或选择“保留原始内容并继续”“终止本次请求”。
6. 在原接口记录中查看“原始内容 / 生效内容”与修改标识，继续正常抓包。

这里的域名是断点匹配条件，不是抓包白名单，也不需要在手机新增域名规则。它只决定哪些已接入的请求需要暂停，其他请求照常经过现有通道。

### 4.2 列表上方

```text
[仅看接口]  [断点规则]  [启用断点：关/开]  [待处理 2]
```

- 默认总开关关闭；新建规则并启用后，仅绑定当前正在录制的设备和抓包轮次。切换查看历史记录不改变实际绑定目标。
- 规则支持方法、精确 origin（scheme、规范化 host、有效 port）、精确路径或路径前缀，条件为 AND。缺省端口按 HTTP=80/HTTPS=443 规范化，同域名不同协议或端口不命中；V1 不提供跨 origin 通配、任意正则和默认全流量拦截。不能用“禁止跨源改写”替代匹配范围隔离。
- 同一阶段多条规则命中时按用户可见顺序选第一条，最多暂停一次；双阶段规则在请求头到达时绑定，同一 flow 可先后停两次。
- “仅下一次”按一整个 flow 原子占用，双阶段不会消耗两次；持续拦截需用户主动选择。规则修改只对新请求生效，在途 flow 保持创建时的快照。
- “保留原始内容”只恢复当前暂停阶段的草稿。例如请求已修改发出后，在响应阶段选原样继续，不会撤销已经发送的请求修改。
- 规则可保存复用，但重启桌面端、结束抓包、换设备后不自动启用。
- 全局待处理入口始终可见并显示来源设备。搜索、仅看接口、切换历史、清空列表都不删除或隐藏待处理项。

### 4.3 编辑面板与精准文案

| 状态或操作 | 文案/行为 |
| --- | --- |
| 请求暂停 | “请求已暂停，尚未发送到服务器。” |
| 响应暂停 | “响应已暂停，尚未返回应用。服务器已执行本次请求。” |
| 等待处理 | “剩余 {秒数} 秒；超时后将保留原始内容并继续。” |
| 应用修改 | “应用修改并继续”；服务端确认动作后再禁用编辑，不能点击即宣告成功 |
| 忽略草稿 | “保留原始内容并继续”；明确丢弃未应用草稿 |
| 终止 | “终止本次请求”；响应阶段说明“不会撤销服务器已执行的操作” |
| 批量恢复 | “全部保留原始内容并继续”；不批量套用未确认的草稿 |
| 已放行或连接结束 | “此断点已结束，不能再修改。请重新触发接口。” |
| 正文受限 | “此正文为流式、二进制或超过编辑上限，本次不支持正文修改。” |

正文提供 JSON/文本/表单编辑，保留全文连续选中复制。JSON 格式化为显式动作，不在打开时自动重排字段。编辑面板展示修改前后差异；表格中敏感头默认遮盖，详情由用户主动显示，不把遮盖文本作为真实值发送。

## 5. V1 能力范围

| 范围 | 首版决定 |
| --- | --- |
| 请求 | 修改同源 URL 的路径、Query、常规 HTTP 方法、业务 Headers、JSON/UTF-8 文本/URL-encoded 表单 |
| 响应 | 修改最终 HTTP 状态码、业务 Headers、JSON/UTF-8 文本正文；可模拟空内容、错误和边界值 |
| 空正文 | 支持无正文请求的路径/参数/头编辑；正文增删受方法与状态语义校验 |
| Header/Query | 保持重复键及其顺序，不用字典无意合并；支持 Cookie/Authorization/Set-Cookie，默认不泄漏到概要和诊断日志 |
| URL 改写边界 | V1 不改 scheme/host/port；防止原 Cookie/Token 被无意带到另一个站点，跨源改写另行设计 |
| 大包/二进制/长连接 | 不提供完整正文编辑；仅在尚未转发、协议允许且头暂停内存有界已验证时编辑头或状态，否则原样通过并说明原因 |
| 加密与签名 | 仅限已解密内容，不解决证书绑定、应用层加密或业务签名；参数改变后可能被服务器拒绝，不自动伪造/重算业务签名 |
| 非 HTTP 内容 | V1 不支持 WebSocket 消息、gRPC/Protobuf 二进制正文、原始 TCP、HTTP/3 或 1xx/升级握手编辑；不强制修改手机协议选择 |
| 后续能力 | 自动 Rewrite、Map Local、本地直接生成响应、重放、脚本、跨域改写不混入首版 |

HTTP/1.1 和 HTTP/2 的普通最终请求/响应均需验收。HTTPS 前置条件仍是现有代理接入和证书信任；新增断点不应让用户重装证书、重复添加手机业务域名或改原 VPN 节点。

## 6. 技术设计

### 6.1 共用引擎与控制通道

```text
SwiftUI 规则/队列/编辑器
  -> 本机 FastAPI 断点 API（认证、校验、目标隔离）
  -> 当前 worker 专用 IPC
  -> 共用 BreakpointEngine（规则、暂停、倒计时、原子决策）
  -> Android mitmweb addon / iPhone DumpMaster adapter
  -> 现有转发与归档
```

- 新功能放独立模块，既有大型 AppState/app.py 只负责组装，不继续堆放整个编辑器或引擎。
- 控制操作在代理所属 asyncio 事件循环执行，使用异步等待；不用 sleep 阻塞事件循环，不在 FastAPI 线程直接修改另一个进程的 Flow。
- 优先用权限受限的 Unix domain socket，运行目录 0700/socket 0600；每个 worker 有独立随机世代标识和认证。验证路径长度与打包后可用性，不复用 iPhone 当前单一覆盖式 control.json 传送并发编辑命令。
- API 只监听 loopback，新增读写接口均校验每次桌面启动生成的令牌，不通过 URL 传递；拒绝未授权浏览器来源和跨设备指令。loopback 本身不能代替认证。
- IPC、API、待处理事件均有长度上限；列表只给摘要，不反复传送整段正文。正文按选中项获取，编辑请求上限 1 MiB，并校验最终解码字节上限。

### 6.2 字段与候选 API

下列为拟新增协议，不是现有 API。实施时用版本化数据模型兼容旧客户端，失败映射到 `UserFacingIssue`。

| 对象 | 关键字段 |
| --- | --- |
| Rule | id、revision、enabled、capture_id、device_id、method、scheme、host、port（有效端口）、path_match、stage、once/continuous、timeout_seconds |
| Pending | id、worker_epoch、capture_id、flow_id、stage、revision、state、deadline、matched_rule、editable_fields、body_limit_reason |
| Resolution | operation_id、expected_revision、action（apply/original/abort）、结构化 patch；不能传任意文件路径或命令 |
| Audit | 原始/有效版本引用、动作、命中阶段、暂停时长、自动放行/失败原因；不包含诊断日志中的正文和认证值 |

| 接口 | 用途 |
| --- | --- |
| `GET /api/captures/{id}/breakpoints` | 规则、开关、待处理数量与能力摘要 |
| `PUT /api/captures/{id}/breakpoints/rules/{rule_id}` | 带 expected_revision 创建/更新规则 |
| `POST /api/captures/{id}/breakpoints/enable` / `disable` | 本次启停；disable 同时原样放行待处理项 |
| `POST /api/captures/{id}/breakpoints/heartbeat` | 当前已认证桌面实例续租；切换页面仍发送，不由后端替失联桌面永久续租 |
| `GET /api/captures/{id}/breakpoints/pending?cursor=...&limit=...` | 有界分页摘要，前台最多每 500ms 拉取一次；无重复并行轮询 |
| `GET /api/captures/{id}/breakpoints/pending/{pending_id}` | 单条当前可编辑内容与版本 |
| `POST /api/captures/{id}/breakpoints/pending/{pending_id}/resolve` | 原子应用、原样继续或终止 |
| `POST /api/captures/{id}/breakpoints/release-all` | 全部原样放行，返回逐项已处理/已结束结果 |

重复 operation_id 返回相同决策结果，不二次发送；过期世代、旧抓包、错误 revision 拒绝。无效输入保持暂停与原期限，不能重置倒计时造成无限挂起。

### 6.3 转发、缓冲与编码

官方文档明确：启用 streaming 后，request/response 事件触发时正文已发送。因此在完整事件中改历史正文不能满足断点语义。[mitmproxy Streaming](https://docs.mitmproxy.org/stable/overview/features/#streaming)、[事件说明](https://docs.mitmproxy.org/stable/api/events.html)

1. 在 requestheaders 记录规则快照，响应阶段在 responseheaders 判定正文是否适合编辑；未命中请求走原有路径。
2. 候选小正文仅在有界缓冲完成且确认尚未转发时进入完整编辑。已知超限、SSE、下载、multipart 等仅在 BP-0 已证明安全时进入受限头阶段，否则原样透传，不加载全量正文。
3. 未知长度/chunked/HTTP2 无长度正文须先通过 BP-0：验证小包可暂停、大包越界能恢复流式且数据不丢不重。头阶段暂停也可能使 mitmproxy 内部队列积压正文，不能直接当作安全兜底；必须测量持续发送时的背压和整个 worker 的内存，而非仅计算引擎数组。完整正文模式不成立时，仅可退到已单独证明安全的头模式；两者都无法保证就跳过断点并说明原因。不能靠无限缓冲、修改依赖私有源码或降低全局大包保护实现。
4. 编码前和解码后均限 256 KiB；先做有界解压再交给文本编辑器，防止小压缩包解成超大正文。超限时不呈现可应用的截断正文。
5. 未编辑正文不重新编码；编辑后由协议层维护长度和压缩编码，不能由用户手填 Content-Length。mitmproxy 的 content setter 会处理编码及长度，但仍需组合场景实测，不能把它当成全部协议正确性的保证。[HTTP API](https://docs.mitmproxy.org/stable/api/mitmproxy/http.html)
6. Host/:authority、Content-Length、Transfer-Encoding、Content-Encoding、Connection、Trailer 等运输字段由工具管理；拒绝 CR/LF 注入和非法方法。HEAD/204/304 不允许添加正文，1xx/101 不作为普通响应编辑。仅头编辑模式不允许改变正文有无语义的方法/状态转换，不在正文尚未掌握时生成不合法报文。
7. gzip/deflate/br 先纳入真实压缩回归；未支持或损坏编码禁用正文编辑，不关闭 TLS 校验、不伪装解码成功。修改响应正文后移除失效的 ETag/Content-MD5/Digest/Content-Digest 等字节校验字段，并在差异里展示；业务签名仍不保证有效。

不把 Android 所有流量改为流式而导致现有导出器丢正文，也不把 iPhone 所有流量改成全量缓存。两种模式必须分别验证 addon 顺序、超限降级和归档一致性。

### 6.4 状态、资源和退出

```text
matching -> collecting -> paused_request / paused_response
collecting -> bypassed / disconnected (deadline, quota, unsupported)
paused -> applying -> continued_modified / continued_original
paused -> aborted / timed_out / disconnected
```

- 每个阶段唯一终态；worker 用原子决策处理“点击继续、超时、停止、客户端断开”的竞争。终止后取消等待与定时器，不能仅改 UI 状态留下悬挂协程。
- 默认暂停 30 秒，可选 15/30/60 秒，硬上限 60 秒，不无限续期。默认超时保留原始内容并继续，不悄悄发送未确认的编辑草稿。应用自身可能更早超时，此时结束断点且不自动重发。
- 收集正文独立采用单调时钟：总时限 10 秒、连续无数据 3 秒，二者均不能被编辑、心跳或空 DATA 重置，不能等进入编辑器才开始计时。超时仅在已验证可无损恢复时切回流式，否则结束目标请求、释放占用并报告原因；H1 关闭目标连接，H2 只取消该流，不能关闭共享连接牵连其他请求。addon-only 的 flow.kill 不满足该契约，必须禁用该候选。BP-0 续修使用显式版本校验的隔离传输适配（见下节）；没有通过适配安全矩阵时仍不得接入产品，不修改安装的依赖源码。测试可缩短时间但不删除计时语义。
- 最多 20 个在途断点名额，覆盖匹配预留、collecting、暂停、应用决策和双阶段之间等待响应，不能只数 UI 队列。所有缓冲中和待处理正文合计预算 16 MiB，需在接收/解压前预留预算；规则最多 100 条，摘要分页最多 50 条，决策去重记录有数量/期限上限。达到限制后新命中原样通过并显示原因。收集超时/断连释放名额；尚未进入任何可编辑暂停的“仅下一次”占用归还规则，已进入暂停后不因超时重新启用。
- 编辑副本的头最多 200 项/64 KiB，URL 最长 8 KiB；超限原始报文不因编辑器限制而被切断，而是禁用该次编辑并按原链路处理。IPC/事件只发送有界摘要，不能把未设上限的原始头塞入列表。
- 双阶段按原请求匹配快照执行，即使请求路径被改也不会意外漏掉原定响应断点。批量关闭/停止时对这些在途 flow 跳过后续断点。
- 不拦截本工具健康检查、证书交付、认证握手或控制接口，不拦截未录制的设备。

| 情况 | 恢复行为与限制 |
| --- | --- |
| 关闭断点/全部放行 | 丢弃草稿，原样继续；不停止正常抓包 |
| 停止抓包 | 先禁止新命中，结算并原样放行待处理项，最多 3 秒有限排空，再按现有生命周期停止；未完成项明确记为连接结束，不声称全部送达 |
| 退出桌面端 | 正常退出先执行上述清理，再回收自有进程；不得先杀代理、再尝试放行 |
| UI/控制通道暂时失联，所属进程仍存活 | worker 独立租约 5 秒内禁止新命中并原样放行已完成收集的待处理项；收集中执行收集期限契约，不假称只调 resume 即可排空；使用单调时钟，UI 卡顿不能永久堵住手机 |
| 桌面所属进程/后端实际退出或崩溃 | 进程所有权退出高于心跳续租；先禁止新命中、取消等待、有限排空最多 3 秒，再关闭自有代理，无法完成的请求标记连接结束。不承诺持续透传，不遗留无人管理的解密代理。iOS 现有 maintain 的直接 master.shutdown 必须在 BP-2 改为此受限顺序，不能仅加心跳却保留抢先关闭的分支 |
| worker 崩溃/电脑休眠 | 不能保证透传，连接可能失败；恢复后显示已结束，不重发、不续用旧 pending，不宣称自动恢复手机 VPN 路由 |
| 客户端断开/重试 | 旧断点结束，新请求新 ID；不合并成同一可编辑请求，不擅自重放写操作 |

停止 iPhone 录制仍与断开手机代理是两件事；现有恢复手机路由步骤不被断点功能取消。不得为断点功能切换或关闭用户 VPN。

### 6.5 归档与安全

- 任何有效修改（Query、方法、头、状态码或正文）都保留不可变的原始报文元数据和有效版本，包含无正文 GET、仅 Header/状态码修改及大包仅头模式。元数据记录两者关系；正文未改时共享原正文引用，不复制文件；正文确实修改时再保留受限双正文。原接口 ID 不变，列表不因每次编辑产生重复记录。
- “生效内容”指代理已采用并尝试转发的版本，不等于应用已消费或业务成功；连接失败仍保留失败标记。终止记录不得伪装为服务器返回成功。
- Request 断点开始时归档可能只有原始头，应用修改后必须更新有效摘要/头；响应归档同理。Android exporter 必须识别暂停/最终版本，不能提前保存一次后永远保留旧正文。
- iPhone 流式改为缓冲的记录不可重复追加正文；正常流式记录仍保持现有截断和磁盘配额。原始/修改副本计入原有总配额，不额外无限存储。
- cURL 默认使用有效 Request，并标注是否被终止/未发出；历史旧记录不依赖新字段，默认按原有内容展示。
- 编辑草稿仅内存保存，不把 Token、Cookie、完整正文写入错误日志、规则文件或发布包；本机归档沿用权限隔离，导出分享前提醒敏感内容。

## 7. 分阶段实施任务

### BP-0 续修约束（2026-11-04）

原始 addon-only 候选的 NO-GO 证据保留。续修只在测试子进程通过公开 `next_layer` 入口选择显式版本适配，不修改 site-packages 或全局 monkey patch；内部 HTTP 层不是稳定公共 API，校验 mitmproxy 12.2.3 并拒绝其他版本。当前矩阵还绑定 h2 4.3.0 / h11 0.16.0 / Brotli 1.2.0；后续升级任一依赖须重新验证，不能把原型直接复制到产品当作无风险接线。[事件入口](https://docs.mitmproxy.org/stable/api/events.html)

- 收集取消以传输事件真正结束请求；绝对/空闲时限分别覆盖已知长度滴流、未知长度停发与响应停发，不能只设置 flow.error。
- 完整编辑保留 256 KiB 正文界限。头暂停只允许已知且小于 128 KiB 的正文；大包/未知长度在暂停前明确跳过头编辑并原样流式传输，不再把大包头暂停作为默认兜底。H2 无 Content-Length 时按 END_STREAM 判断空正文，不能套用 H1 的无正文规则。
- H2 初始流窗口 65535 字节、每连接最多32并发流；按流计账暂停队列、上游并发名额等待队列和发送缓冲，以256 KiB水位停止返还该流信用，独立返还连接窗口以保持其他流前进。水位不等于整个worker的精确分配上限，还存在已发放窗口、TLS/解释器开销；必须通过64 MiB额外RSS门槛，不能只查引擎数组。
- H1 在等待上游握手等阻塞事件期间也可能积压大包。测试适配仅扩展自有worker中对应handler实例的读取循环排空检查，按来源读任务、256 KiB水位等待队列下降；不阻塞上游TLS、定时器或hook，不暂停整个事件派发器，H2仍使用逐流窗口。一次持续背压等待最多10秒（事件唤醒不得续期），超时结束目标H1来源；客户端来源同时回收它拥有的上游握手，不能遗留GetConnection等待。已流式/未命中正文不再产生收集计时唤醒。该实例扩展同样是版本相关内部契约，BP-2必须审查，不是修改安装的包或全局类。验收必须包括延迟TLS后无损恢复、握手不恢复时客户端断开后的有界回收、等待中的正常退出。超出期限是明确结束请求，不能描述成无限慢消费者也能无损继续。
- 空 DATA 不增加事件队列或延长空闲期限；相邻正文碎片合并为最多16 KiB块，保留独立 END_STREAM/EOM 语义。远端 RST、DATA+RST、GOAWAY、DATA+GOAWAY 和 EOF 也要清理信用与未发送队列，不能等消费者恢复才回收。
- 安全测试包含同一H2连接慢消费者与健康大流并行、上游MAX_CONCURRENT_STREAMS=1的排队上传/取消、20路慢消费者、100 MiB请求/响应与哈希、暂停/解压/异常退出及版本拒绝；未通过不进入下一阶段。

本轮支持证据仅为隔离 TLS H1->H1 / H2->H2。H3、混合协议、Android exporter/iPhone归档组合、真实设备及全局生产配额属于后续验收，未验证模式不启用断点。生产传输接入仍属于 BP-2；BP-1只先实现状态/预算/控制契约，本轮不改用户正在使用的代理。

以下是执行顺序及验收门槛。本轮仅领取 BP-0，四项评审补充为其必要前置修订；后续逐项写入任务池、一次领取一项，正常细节无需重复审批。BP-0 可交付有实测证据的“不支持/禁用”结论，但不能因此声称产品准入通过。

| 阶段 | 文件范围（新文件为拟新增） | 交付与验收门槛 |
| --- | --- | --- |
| BP-0 能力原型 | 新 `tests/test_breakpoint_transport.py`、`tests/test_breakpoint_guard.py`、`tests/fixtures/breakpoints/`、`specs/breakpoint-bp0-acceptance.md`；本规格与目标/进度 | loopback 隔离 client/proxy/origin 证明请求在放行前未到源站、响应在放行前未到客户端；HTTP/1.1/2、压缩、未知长度、超限、慢速收集/名额释放及并发均有实际证据；特别验证头暂停时对端持续发送大包的内部队列/背压和整体 RSS，无法证明有界则不启用该模式；确定正文模式与降级策略，未通过不接真机 |
| BP-1 引擎和控制 | 新 `capture_console/breakpoints/{models,engine,validation,control,ipc,api}.py`、包初始化；独立API工厂（app.py生产组装明确延期BP-2）；新 `tests/test_breakpoint_{engine,api,ipc}.py`及独立worker夹具；契约见`breakpoint-bp1.md` | 规则匹配、单次占用、双阶段、倒计时、鉴权、幂等、客户端断开、队列预算、停止竞争全部 RED/GREEN；未经认证不能读取正文或修改流量 |
| BP-2 双平台适配与归档 | 新 `capture_console/breakpoints/{addon,archive,runtime,guard,read_gate,android,ios,supervisor}.py`；控制API组装、Android启动/停止脚本、runner/exporter/results；iOS代理/准备/归档；新adapter/archive/lifecycle/boundaries/integration测试；详见`breakpoint-bp2.md` | Android两模式和iPhone产品适配器隔离对照源站/客户端；原始/有效正文及cURL一致，100MiB透传哈希/RSS；停止需等待真实传输及发送队列，配额/退出收敛，旧记录可读；默认关闭，不接用户手机/VPN |
| BP-3 原生交互 | 新 `Breakpoint*.swift`（模型、独立认证API、控制器、模板库、规则/编辑/归档/根生命周期界面与文案）；FlowViews/Models/APIClient/AppState/RuntimeManager/ContentView最小接线；对应Swift tests；认证context与有界归档预览Python实现/测试；提前建立`tests/breakpoint_native_ui_fixture.py`；契约见`breakpoint-bp3.md` | 正常/等待/空/失败界面、键盘和多行复制；源切换/清空/过滤不丢待处理；停止清理和错误提示准确；按钮状态与真实确认一致。已完成，未替换用户安装包 |
| BP-4 综合验收与使用说明 | `tests/test_breakpoint_e2e.py`、只读身份真机夹具及信号清理测试、`tests/fixtures/breakpoints/production.py`来源报告；复用既有Python/Swift/UI测试；`docs/{desktop-user-guide,breakpoint-user-guide}.md`、`release/{package.sh,安装说明.md}`及打包测试、`specs/breakpoint-acceptance.md` | 部分通过：iPhone真机、原生界面、最终ZIP真实链路和回归已验证；2026-11-04用户明确延后Android真机验收，不作为本轮门槛，仅整机休眠/唤醒现场条件保留BLOCKED。本地包不变，不推送或发布。矩阵按此范围调整执行，Android仍注明未实测，不以合成流量代替真机 |

使用项目现有 unittest，不为此向生产环境安装 pytest/httpx。BP-0 是隔离能力实验，先建立证据断言与负对照，实际结果允许得出候选模式不可用；正常产品实现仍需 RED/GREEN。后续文件创建后按阶段从项目根执行：

```bash
CAPTURE_TEST_BREAKPOINT_TRANSPORT=1 python -m unittest tests.test_breakpoint_transport -v
CAPTURE_TEST_BREAKPOINT_TRANSPORT=1 CAPTURE_REQUIRE_BP0_SAFE=1 python -m unittest tests.test_breakpoint_guard -v
python -m unittest tests.test_breakpoint_engine tests.test_breakpoint_api tests.test_breakpoint_ipc -v
python -m unittest tests.test_breakpoint_adapters tests.test_breakpoint_archive tests.test_breakpoint_e2e -v
python -m unittest tests.test_ios_capture tests.test_ios_results tests.test_ios_lifecycle tests.test_exporter_timing -v
swift test --package-path macos-native
bash macos-native/scripts/build-app.sh
```

Python 使用已安装 `requirements-console.txt` 的隔离环境；集成测试启用自有临时端口/目录，不占用用户当前抓包端口，不读取真实手机凭据。打包前补充执行现有 iOS 真实 TLS opt-in 与打包生命周期用例，按现有测试要求建立隔离环境，不能把跳过当通过。

## 8. 验收矩阵

| 场景 | 必须看到的结果 |
| --- | --- |
| 请求参数修改 | 回显服务在放行前请求计数为 0，放行后只收到一次修改后的 Query/Header/Body；原值只在原始版本 |
| 响应修改 | 源站已响应，但客户端尚未收到最终头/正文；继续后客户端读取到修改后的状态和内容 |
| 原样继续 | 原始正文、重复头、Query 顺序和压缩字节保持；不把 UI 格式化结果发送出去 |
| 请求/响应终止 | 请求阶段源站未执行；响应阶段客户端连接结束，但明确记录源站已执行；不伪造成功 |
| 双阶段/并发规则 | 下一次只占一个 flow；两阶段各停一次；非命中接口不等编辑，无全局事件循环堵塞 |
| origin 隔离 | 相同 host/path/method 的 HTTP/HTTPS、不同端口仅精确 origin 命中；缺省端口等价，不扩大到其他环境 |
| 慢正文与占用 | 小于 256 KiB 但始终不结束、间歇滴流、完全停发均在收集绝对/空闲期限内收敛；无已验证的安全适配则禁用该模式；H2不关闭共享连接；收集加暂停合计不超过20，未暂停的单次占用归还 |
| 长度与编码 | gzip/deflate/br、中文/emoji、重复 Query/Set-Cookie、空正文、HEAD/204/304、无效 JSON/CRLF 均按契约处理 |
| 大包和恶意输入 | 100 MiB 流、压缩膨胀、未知长度、20 个等待项、100 条规则下有界；头暂停期间对端持续发送也不让代理内部队列无限增长，否则禁用该模式；未编辑流原样到达，超限不生成可应用的截断正文 |
| 性能 | 同环境对照关闭断点，未命中请求 p95 新增延迟目标不超过 10ms；断点带来的额外 RSS 目标不超过 64 MiB；慢客户端/并发下记录实际值，超标先优化不直接宣称通过 |
| 清空与筛选 | 清空列表、仅看接口、关键词、切换历史不会遗失待处理项；可从全局入口继续/终止 |
| 超时/竞态 | 继续与超时/停止同时发生也只决策一次；过期编辑明确拒绝；重试不重复转发 |
| 生命周期 | 关闭断点、停止、正常退出、UI卡顿/IPC失联、后端进程崩溃、桌面所属进程退出、worker崩溃、休眠/唤醒分别记录结果；所有权关闭不抢先于有限排空，也不被心跳无限延后；下一次启动关闭，无旧断点恢复 |
| 归档回归 | 同一 flow 暂停期间、改写后、重开历史的原始/有效版本正确；GET Query-only、Header-only、status-only、大包仅头各验证不可变原始元数据和正文复用；暂停不被误标普通“暂无响应”，无超量读取和重复正文 |
| 安全隔离 | 无令牌、跨来源、跨设备、旧世代、任意路径和过大 payload 均被拒绝；错误日志与发布包没有凭据/正文 |
| 原生与真实设备 | 桌面实际完成规则创建、编辑、三个动作、全部放行；Android + iPhone 各验证一组无副作用的参数与响应改写，手机 VPN/原配置不变 |

真实应用建议先选只读列表/配置查询：把 pageSize 从 10 改为 2，或把测试响应列表改为空，核对应用展示。若接口不提供该参数，改用受控测试服务，不猜测生产参数；不用订单、支付、删除、权限升级等接口做首轮验收。合成代理通过不能代替真实手机和原生界面证据。

## 9. 风险与评审决定

- 最大技术风险是流式正文与暂停时机，不是 UI 按钮；BP-0 为必要工程门槛。头编辑同样须验证内部队列/背压，不能作为未经验证的安全降级；没有安全模式时跳过该次断点，不以部分能力冒充完整正文断点。
- 暂停会使应用超时或重试；倒计时降低风险，不能保证应用永不超时。停止的有限排空也不能保证每个在途业务执行成功。
- iPhone 当前统一接入的是设备流量，不能可靠根据代理层断言进程归属。规则绑定设备/接口，不把其他应用请求误称为所选应用独占流量。
- 用户原有 VPN、节点、订阅、DNS 和手机配置不由本功能改变；现有通道若不可解密，断点也无法凭空取得明文。
- 规则过滤与“仅看接口”是不同能力；断点不以界面启发式分类作为唯一判定依据，否则可能漏掉尚未获得响应类型的请求。
- 本轮自审目标：对行为、生命周期、安全和验证作出明确约束；技术可行性标注为有基础、待原型验证，不提前报告完成实现或所有应用支持。

推荐推进顺序：BP-0 隔离原型 -> BP-1/2 共用后端与两套适配 -> BP-3 桌面交互 -> BP-4 实际验收。首版做好手动断点闭环，再考虑自动改写与重放。

前期文档复核补充了响应阶段原样继续、仅头编辑语义、桌面租约及头暂停内部队列风险。原addon-only实验确认风险真实存在，历史失败不删除。BP-0续修通过逐流取消、有限窗口/队列、H1读取节流及大包跳过头编辑达到隔离安全门槛，36项严格验收通过。BP-1独立引擎与控制契约已通过53项验收，产品传输接入必须经过BP-2版本/协议与归档组合验收，不能将本原型直接上线。

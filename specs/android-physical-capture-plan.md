# Android 真机抓包调研与实施计划 V1

> 日期：2026-11-05。状态：评审稿，仅调研与规划，尚未实施或重新实测手机。
> 后续执行者按本文件阶段顺序使用 executing-plans 或显式授权的单任务委派；不得把本计划视为Root、修改VPN、安装证书、重签应用或发布的授权。

**Goal：** 在桌面端为Android真机提供可验证的接入与抓包流程，优先验证未经修改的Release包，准确说明不支持的条件，并可靠恢复本工具创建的临时资源。

**Architecture：** 将设备识别、传输、TLS/应用能力和会话生命周期分开。新增真机适配器，复用现有接口归档、详情、过滤、最近7次历史和已验收的断点引擎，不把模拟器自动修复流程直接用于真机。

**Tech Stack：** macOS SwiftUI、FastAPI/Python、ADB、现有mitmproxy/exporter/断点运行时。Frida仅用于另行授权的已具备Root能力的测试机；未Root设备不自动注入。

## 1. 评审结论

1. Android真机可以抓包，但不存在“任意未Root手机 + 未修改线上Release + 不调整任何流量接入/信任条件”都能解密HTTPS的通用保证。
2. 保留VPN不等于同时启动第二个抓包VPN。Android同一用户或工作资料（profile）只允许一个活动VpnService，新服务会替换旧服务。[Android VPN](https://developer.android.com/develop/connectivity/vpn)
3. 连接USB只提供调试和端口传输能力，不会自动获取其他应用的HTTPS正文；日志、PCAP、CONNECT成功和浏览器通路都不能代替应用业务验收。[ADB命令参考](https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/main/docs/user/adb.1.md)
4. 建议采用“只读准入 + 免Root兼容路径 + 独立高级路径”。当前一加默认维持未Root、VPN与原配置不变；不具备条件时给出具体限制，不继续盲目重试。
5. 如目标是提高多款原版Release的覆盖率，专用、已由设备负责人准备好的Root测试机是更值得评估的候选；不对当前一加自动Root，不保证硬件校验、反调试或所有TLS栈均兼容。[Frida Android](https://frida.re/docs/android/)

## 2. 已有证据与未确认项

### 2.1 本项目已有证据

以下是2026-11-03的历史实测，不是本轮重新读取的手机状态：

- `specs/android-physical-debug-trial.md`：一加PHK110、Android16，按未Root处理；Jenkins当时保留的PokeHub #583至#588均为Release构建，#588实物`debuggable=false`。Android Debug签名不代表Flutter Debug模式。
- #588的包名为`com.test.tcgp`，它是测试环境Release，不是Google Play的`com.mi.poketrade`。安装、启动、登录后只读页面已验证，完整业务Request/Response未取得。原版线上包需要另行核实包名、版本和实际安装的全部APK/split摘要。
- `specs/charles-android-trial.md`：USB显式HTTP/HTTPS对照曾成功，但实际PokeHub未接入；用户当时拒绝手机代理和测试CA，因此未实施。不重复要求用户走已拒绝的步骤。
- `capture_console/device_discovery.py`和`/api/log-devices/discover`具备真机识别基础，`capture_console/logcat.py`使用ADB Logcat。日志能力不代表抓包准入。
- `scripts/ai_capture.sh`的Flutter导流仍固定使用`10.0.2.2`；该地址属于模拟器主机访问设计，不能作为真机Mac地址。
- `capture_console/runner.py`的`enter_capture_network()`会清空Android全局代理；`capture_console/app.py`的启动/失败清理多处调用此逻辑。必须为真机建立独立分发和恢复边界。
- `scripts/start_frida_server.sh`要求已有uid=0/su，并可能结束已有frida-server、移除指定转发；不能原样用于用户真机或与其他调试任务共用。
- 现有`capture_console/breakpoints/android.py`、接口详情、历史与过滤可以作为复用入口；只有真正进入代理的HTTP流量才可使用断点。

### 2.2 必须在后续只读准入阶段确认

当前一加的连接/授权状态、Android版本、目标应用原版安装来源与版本、VPN客户端及活动状态、是否已有可用的本地HTTP/SOCKS入口、是否存在企业策略/多用户/始终开启VPN限制。未知值返回unknown，不能凭su文件存在、VPN图标或APK文件名直接判定可抓包。

本轮不连接设备、不探测端口、不读取VPN订阅或密钥。前述历史结果不能证明最新Jenkins依然没有Debug包，也不能证明所有Release都不支持代理。

## 3. 必须分开的技术问题

| 层次 | 要回答的问题 | 不能替代它的证据 |
| --- | --- | --- |
| 设备接入 | 是否指定了正确手机、用户、应用及版本，USB是否授权？ | 模拟器可用、另一台设备在线 |
| 流量接入 | 目标业务流量是否真正到达Mac的采集器？ | 手机能上网、ADB端口连接成功 |
| TLS解密 | 目标应用是否接受本工具证书，或具备已验证的进程级采集方式？ | 安装过用户CA、浏览器HTTPS成功 |
| 协议与正文 | 能否配对方法、URL、请求和响应，正确处理压缩与截断？ | TLS握手、域名、统计SDK日志 |
| 应用归属 | 流量来自已锁定进程，还是只能按操作时间关联？ | 手机前台应用名、域名搜索 |
| 交互能力 | 能否安全暂停/修改/放行请求响应？ | 仅能旁路观察正文 |

Android对目标API24及以上应用默认不信任用户添加CA；应用可显式配置其他信任策略，自带TLS实现还需独立验证。安装CA不等于绕过证书绑定。[Android网络安全配置](https://developer.android.com/privacy-and-security/security-config)

Dart `HttpClient`有自己的代理解析机制，不能假定所有Flutter流量都跟随Android Wi-Fi代理。Android VPN公开的HTTP代理本身也只是建议，应用可以忽略。[Dart HttpClient](https://api.dart.dev/dart-io/HttpClient-class.html)、[VpnService.Builder](https://developer.android.com/reference/android/net/VpnService.Builder#setHttpProxy(android.net.ProxyInfo))

## 4. 候选路径比较

| 路径 | 原版Release | Root要求 | 对原VPN/配置影响 | 决策 |
| --- | --- | --- | --- | --- |
| 系统/应用HTTP代理 + 被应用信任的CA | 条件支持，取决于代理与信任实现 | 不要求 | 需接入设置，可能与VPN代理冲突；任何更改需单独授权 | 免Root兼容路径，不承诺任意Release |
| 现有VPN协作转发到Mac | 路由可兼容时仍需解决TLS信任 | 不要求 | 不开第二VPN；可能仍需切换转发或独立配置，不能称为零改动 | 先只读探测能力，不自动导入/切换 |
| 已Root测试机 + 指定应用Frida + USB代理 | 不重签原APK，但运行环境被插桩 | 需要已有Root授权 | 可避免改全局代理；目标请求实际出口需单独验证 | 原版Release的高级候选，先POC再集成 |
| 进程内TLS明文观察 | 可保持原网络路径，依赖可插桩及协议适配 | 通常需要Root或应用自带诊断 | 不必重定向流量，但不等于保留完整HTTP语义 | 研究备选，不纳入V1断点承诺 |
| 正确的Debug/诊断构建 + DevTools/应用诊断 | 不是原版线上包 | 不要求 | 可以不调整VPN网络 | 辅助开发，不算线上包验收 |
| Gadget重打包 | 不再是未经修改的原包 | 可免Root | 改包/签名，可能破坏登录、完整性或覆盖安装 | V1不采用，不自动重签/卸载 |
| PCAPdroid/HTTP Toolkit配套VPN/WireGuard | 只能保证适用条件下的接入，TLS仍另算 | 部分模式不要求 | 第二VpnService会影响原VPN | 当前保留VPN约束下不作为默认路径 |
| Wi-Fi网关、USB网卡镜像、tcpdump/Wireshark | 可观察网络包 | 依采集位置而定 | 可能需路由变更；通常只能看到VPN外层或TLS密文 | 排错辅助，不能当作HTTPS正文方案 |

Charles官方也要求目标Android应用具备适当信任配置；换代理软件不改变应用信任边界。[Charles证书说明](https://www.charlesproxy.com/documentation/using-charles/ssl-certificates/)

HTTP Toolkit公开说明未Root应用的HTTPS信任前提，其手机配套使用VPN；PCAPdroid同样区分VPN接入和TLS解密。[HTTP Toolkit Android](https://httptoolkit.com/docs/guides/android/)、[PCAPdroid工作方式](https://emanuele-f.github.io/PCAPdroid/quick_start.html)、[PCAPdroid TLS](https://emanuele-f.github.io/PCAPdroid/tls_decryption.html)

Flutter DevTools可查看受支持的Dart网络请求，但Release关闭调试与服务扩展。只改Manifest的debuggable或使用Debug签名，不能补回编译时移除的能力。[Flutter构建模式](https://docs.flutter.dev/testing/build-modes)、[DevTools Network](https://docs.flutter.dev/tools/devtools/network)

## 5. 推荐的分层方案

### 5.1 默认：只读检查，保持当前一加不变

用户连接USB并自行授权调试，桌面显示“Android真机”，识别当前应用；不触发模拟器启动、rootAVD、代理清理、证书安装、应用重启或VPN探测性切换。

返回两组结果：设备/日志是否可用；当前应用是否有已验证的HTTP采集通道。只读检查无法证明TLS支持时明确显示“需要验证”，而不是误报“可抓包”。

若当前仍是未经修改Release、未Root、无已存在的应用信任/转发能力，且不允许调整任何代理/证书，结果应是“当前条件下无法采集HTTPS正文”。此结果是能力判断通过，不是抓包验收成功；不得用日志冒充接口或继续盲目重试。

### 5.2 免Root兼容路径

前提：目标应用本身支持代理并接受已具备的测试信任，或用户后续明确允许本工具所需的临时接入/证书确认。过去拒绝的调整不会因本计划自动获得授权。

优先USB `adb reverse`建立“手机本地端口 -> Mac loopback采集器”，避免依赖固定Wi-Fi地址和公司网络客户端隔离；它只搬运明确接入的TCP流量，不负责强制导流或解密。使用`--no-rebind`和动态空闲端口，只清理本工具创建的映射。

无线局域网作为另选入口，必须核对手机可达性、监听接口和认证。控制API仅loopback，代理不成为无认证局域网开放服务。不能因桌面能访问源站就认定手机通路有效。

普通兼容路径的应用归属标为“设备代理流量”，不宣称只属于前台应用。用户无需逐个维护域名白名单；采集范围与归属限制在开始前说明。

### 5.3 原版Release高级路径

另用已具备Root的测试机，设备负责人自行准备；本工具不提供或执行Root/刷机/解锁。解锁bootloader可能触发恢复出厂设置，不得将其包装成自动修复。[AOSP解锁说明](https://source.android.com/docs/core/architecture/bootloader/locking_unlocking)

候选数据流：

```text
指定应用进程 -> 经验证的进程级导流/TLS适配
             -> 手机loopback专用端口 -> USB reverse
             -> Mac mitmproxy -> 经验证且获准的出网路径 -> 业务服务
```

- 复用现有Flutter/native适配能力，但移除真机路径对`10.0.2.2`的假设；按ABI、Frida版本、ROM/API和目标Flutter/TLS版本验证。
- 只操作指定包及已核实的关联进程。WebView隔离进程、多进程、Cronet/QUIC覆盖不自动推定。
- 不注入VPN应用，不改iptables/nftables/SELinux，不写系统CA目录，不调用现有脚本中的全局pkill或清空全局代理。
- 已有他人frida-server或转发存在时不接管/重启；无冲突复用需明确确认所有权，否则返回冲突。
- Root只能提供部分操作能力，不自动解决证书绑定、客户端证书、反调试或硬件完整性检测；失败时保留具体证据。

### 5.4 VPN保留与出口必须分别处理

“VPN仍显示开启”“节点/配置未变”“目标请求仍走原VPN出口”是三个不同断言，必须分别验收。目标请求转到Mac后，不能默认继续使用手机VPN，也不能悄悄改为Mac直连。

优先研究的严格保留候选（尚未验证）：如果现有VPN客户端已经提供本地HTTP/SOCKS代理，且允许使用该现有入口，可用单独ADB forward将其桥接到Mac，再作为采集器的受限上游。候选为“目标应用 -> Mac采集器 -> 手机现有代理入口 -> 原VPN策略”。这可能保留原节点，但必须验证客户端协议、认证、策略匹配、实际出口和循环；现有mitmproxy upstream与SOCKS入口不能直接视为兼容，需要先独立POC。[mitmproxy模式](https://docs.mitmproxy.org/stable/concepts/modes/)

若现有入口不存在、被锁定或无法证明没有循环，则该候选不通过。不开启“允许局域网”、不导出订阅、不改原端口或节点；不得自动退回另一出口。另选Mac已有上游必须明确获准，并说明出口可能变化，不修改其配置。

用户自行切换VPN节点后：不重建证书，不自动改回旧节点；显示“网络路径已变化，正在检查连接”，重验采集器到源站通路。已有未完成请求标记中断且不自动重放。若不能可靠读取节点选择，则通过连接健康变化提示复检，不假装能自动识别节点名。恢复时只撤销本工具变更，保留用户后来选择的节点。

## 6. 桌面交互与安全恢复

维持“抓包、安装应用、接口、日志”四个导航。抓包页区分Android模拟器、Android真机和iPhone，不在真机上显示“启动模拟器”。已安装应用可直接测试，Jenkins安装不是前提。

主流程：`连接手机 -> 确认USB调试 -> 打开目标应用 -> 检查抓包条件 -> 条件满足时开始抓包 -> 操作应用 -> 查看接口 -> 停止并检查恢复`。

自动处理：识别设备与前台应用、能力检查、受授权范围内的USB通道/代理生命周期、采集与归档、诊断和恢复。本人处理：USB授权、解锁/登录；仅在另行允许时确认系统证书或Root管理器弹窗。不能承诺消除Android系统安全确认。

用户文案：

| 状态 | 标题 | 提示 |
| --- | --- | --- |
| 未授权 | 等待USB调试授权 | 请解锁手机，并在手机上允许此电脑调试。 |
| 仅日志 | 手机已连接 | 可以查看运行日志；当前应用尚未通过抓包验证。 |
| 不具备条件 | 当前应用暂不支持直接抓包 | 当前安装包没有已验证的流量接入或HTTPS解密通道，原网络设置未更改。 |
| 未收到业务流量 | 正在等待应用请求 | 请操作目标应用；当前仅确认连接可用。 |
| TLS失败 | 无法解密应用连接 | 应用拒绝测试证书或使用了其他安全机制，请查看运行检查。 |
| 正文成功 | 已捕获应用接口 | 在“接口”中查看Request和Response。仅进程归属已验证时使用“应用接口”。 |
| 恢复未完成 | 抓包已停止，连接待恢复 | 显示本工具仍占用的项目与对应恢复操作，不显示“全部恢复”。 |

首次成功后才启用完整能力标识。CA/专用身份可复用并提示到期，不因停止、USB重连或节点切换而反复生成；私钥仅本机保存，不进入日志或发布包。

安全恢复必须做到：

- 开始前保存有限基线与变更账本：设备身份、包版本、可见网络状态、原代理值、自有端口/映射/进程身份；不保存VPN配置全文、订阅或密码。
- 只有当前值仍等于本工具写入值时才自动回滚；用户或第三方后来修改时提示冲突，不覆盖新值。移除映射前同时核对设备序列号、端口及目标映射。
- 正常停止按“停止接入/撤销应用导流 -> 解除或终止待处理断点 -> 收尾归档 -> 释放自有通道”有界执行；顺序在POC中实测，避免先断代理导致应用持续断网。
- USB断开、应用/后端异常退出、手机重启、Mac睡眠场景分别验证。不能承诺失联后还能远程恢复设备；设为recovery_required，重连后按账本恢复，并提供不改VPN的人工恢复说明。
- 拦截器或Root管理器需要重启目标应用才能恢复时，不自动强退造成数据丢失；明确提示，取得授权后再处理。
- 不调用`adb kill-server`、`forward/reverse --remove-all`、按端口杀进程、wipe-data、pm clear、uninstall；不主动解除企业设备策略或降低系统TLS安全。

## 7. 模块和接口契约（拟新增）

| 模块 | 文件 | 责任 |
| --- | --- | --- |
| 真机能力 | `capture_console/android_physical_capabilities.py` | 有界只读设备/应用/网络能力与证据；unknown保留 |
| USB传输 | `capture_console/android_physical_transport.py` | 精确serial、forward/reverse所有权、冲突、健康、失联清理 |
| 真机生命周期 | `capture_console/android_physical_capture.py` | 接入适配器、审批边界、状态机、变更账本、与现有记录联动 |
| 路由接口 | `capture_console/android_physical_api.py`；`app.py`只注册/分发 | 不扩大既有巨型app.py；旧模拟器和iPhone接口保持兼容 |
| UI与控制 | `macos-native/Sources/AICaptureNativeApp/AndroidPhysical{Models,Controller,View,Copy}.swift` | 设备入口、能力分层、授权操作清单与恢复状态 |
| 现有集成点 | `device_discovery.py`、`runner.py`、`CaptureView.swift`、`AppState.swift`、`APIClient.swift` | 按device kind分流，限制最小修改，保留既有日志与采集功能 |

拟新增端点，尚未实现：

- `GET /api/devices/{device_id}/capture-capabilities?package_name=...`：只读；返回`device_kind`、`package_identity`、`recommended_mode`、`transport_state`、`tls_state`、`app_http_state`、`breakpoint_state`、`required_actions`、`issues`及`evidence_at`。未知能力不返回true。
- `POST /api/devices/{device_id}/physical-capture/prepare`：显式选择模式与允许操作，仅准备不录制；返回短期`preparation_id`，绑定精确设备/应用版本及基线；权限或状态改变后失效。
- `POST /api/captures/start`：真机增加可选`preparation_id`，校验绑定后分发到新适配器，不落入旧代理清理/AVD路径；旧客户端字段不改变。
- `POST /api/devices/{device_id}/physical-capture/recover`：只恢复本工具账本所有权范围；重复调用幂等；返回成功、冲突或待重连。

模式：`proxy_compatible`、`root_assisted`；诊断包和TLS旁路只列能力建议，V1不自动选择。接口沿用`UserFacingIssue`风格的code/message/recovery_action/technical_detail，不直接显示原始JSON。

状态机：`disconnected -> unauthorized/checking -> blocked/confirmation_required/ready -> capturing -> restoring -> idle/recovery_required`。设备换接或包升级使prepare失效；另一个活跃任务不得被自动覆盖。

## 8. 分阶段实施与停止条件

本轮只完成ANDROID-PLAN1文档；以下AP阶段均未开始，不表示已得到真机变更授权。

| 阶段 | 内容及范围 | 验收与进入下一阶段的条件 |
| --- | --- | --- |
| AP-0 能力与边界 | 新增capabilities及测试；既有一加仅在后续授权后只读检查。核对真实Release、VPN、代理与可用诊断 | 模拟无设备/未授权/多设备/未Root/已有Root信息/企业策略等状态；命令记录中无写设置、su授权、安装、Root或VPN动作；给出至少一条具备全部前提的候选，或明确blocked |
| AP-1 接入与恢复POC | transport及账本；合成HTTP/TLS源站；只测试已允许的USB及现有出网入口 | 错设备/端口冲突/异物进程拒绝；重复准备与清理幂等；USB反向和上游正向无循环；VPN保持与目标出口分别验证。只代表链路，不宣称业务抓包 |
| AP-2 原版Release可行性 | 先用同一加已具备条件的兼容模式；如无条件，等待另选已Root测试机的明确授权，不自行Root | 先单款PokeHub真实业务Request/Response；失败分类为未接入/TLS拒绝/协议不支持/无正文。兼容失败不重复改证书；Root/诊断包不能冒充当前手机原版成功 |
| AP-3 产品接入 | 新API/controller/view，复用归档与断点，真机生命周期分流 | 开始/停止/取消/重连、Request/Response分行、搜索/过滤/7次保留与断点权限通过；模拟器、iPhone、日志、Jenkins现有回归不退化 |
| AP-4 实机与交付 | PokeHub、MelodyCraft、Wishly、StickerHub的可获得原版AndroidRelease；干净配置桌面包验收与教程 | 每款至少两条只读业务请求、完整JSON响应及归属证据；其中至少一条有请求体以核对两侧正文。停止/异常/节点切换/USB断开恢复通过；记录包版本、系统、VPN客户端、模式与限制后才可发布 |

每阶段先补失败用例，再最小实现、回归、本地单任务提交。预计耗时取决于AP-0设备与授权结论，本计划不以固定工期承诺未知Release兼容性。

AP-0可独立完成；如果当前授权内没有可行采集通道，不开展AP-1实机变更或AP-2产品试错。可交付只读诊断能力，但不能将其称为“Android真机抓包已支持”。

## 9. 验收矩阵与命令

### 9.1 必测行为

| 场景 | 判定 |
| --- | --- |
| 当前一加未Root，原Release，禁止代理/证书/VPN更改 | 返回明确能力边界，零设置变更；日志继续可用，但抓包不记通过 |
| 浏览器对照成功、目标应用拒绝CA | 报应用解密失败，不显示“可抓包”，恢复本工具临时资源 |
| VPN开启、普通代理被忽略或覆盖 | 区分流量未接入，不停VPN、不安装第二VPN、不自动改出口 |
| 已授权Root专机 | 原APK/split集合与签名不变，目标进程范围明确；真实方法/URL/状态/正文对应，无其他VPN进程注入 |
| 包名冲突、不同签名或另一个项目共用测试包名 | 不卸载或覆盖，不自动把测试环境Release当线上包 |
| HTTP/1.1、HTTP/2、压缩、流式、二进制、慢正文和大包 | 可支持者正确归档，不支持者明确提示；继续采用已有有界正文与断点预算，不无限读取/渲染 |
| QUIC/HTTP3、WebSocket、gRPC、mTLS、证书绑定 | 单独记录覆盖；V1不默认拦UDP、禁QUIC或降低协议，不宣称全部支持；二进制不强行显示JSON |
| 请求/响应断点 | 只在可控HTTP路径启用；用自有合成源站验证改写、原样放行、终止、超时和退出；不修改登录、付款或生产写入请求 |
| 用户中途改节点/代理，或拔USB/退出/崩溃/睡眠/重启 | 有界收尾和持久恢复标记；不重放请求，不还原掉用户新选择，不误删已有转发；恢复失败不报成功 |
| 多设备和并发任务 | exact serial不漂移；不接管其他设备或会话；本轮暂不承诺多真机并发 |

Release身份验收须记录实际base/split安装集合的摘要、包名、版本、签名和来源；安装包安装成功不计抓包成功。没有观察到流量不能单凭静态APK配置判定证书绑定，先区分接入与TLS层。

### 9.2 后续自动化入口

AP-0新增`tests/test_android_physical_capabilities.py`；AP-1新增`tests/test_android_physical_transport.py`；AP-2/3新增`tests/test_android_physical_capture.py`与`tests/test_android_physical_api.py`；AP-4扩充已有`tests/test_breakpoint_device_acceptance.py`，所有设备测试必须显式传入serial与包身份，默认跳过真实写操作。

Swift新增`AndroidPhysicalControllerTests.swift`与`AndroidPhysicalPresentationTests.swift`，验证未知能力、授权提示、USB失联、错误平台分支及恢复状态。执行环境使用安装包内嵌Python或项目已配置的等价环境，不要求用户为真机安装完整模拟器镜像。

以下是未来实现后在仓库根目录执行的命令，本轮不运行：

```bash
PYTHON="/Applications/抓包工具.app/Contents/Resources/runtime/bin/python3"
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -B -m unittest tests.test_android_physical_capabilities -v
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -B -m unittest tests.test_android_physical_transport -v
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -B -m unittest tests.test_android_physical_capture tests.test_android_physical_api -v
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -B -m unittest tests.test_console_api tests.test_logcat_service tests.test_device_network tests.test_ios_lifecycle tests.test_capture_retention tests.test_breakpoint_lifecycle -q
swift test --package-path macos-native
```

真实恢复测试先在隔离夹具中通过，再在获准测试机上验证；锁屏或需要系统确认时明确等待，不拿模拟结果代替。每个兼容性结论绑定设备/Android/客户端/应用版本，换ROM、升级APK或VPN后重新校验，不保证“一台通过就所有用户可用”。

## 10. V1排除项与评审自查

V1不实现自动Root、bootloader解锁、刷机、重签Release、静默安装系统CA、完整VPN客户端、企业策略绕过或任意TLS解密。Debug诊断、TLS旁路重建及全面UDP协议支持是备选研究，不扩张当前阶段范围。iOS日志不在此次Android真机计划中。

- [x] 原版Release和测试环境Release/Debug/重打包分别定义，不以安装/日志/域名/浏览器成功替代业务正文。
- [x] VPN服务状态、原配置和目标出口分开验收；未验证的USB回接手机代理方案标为候选。
- [x] 无需逐域名白名单；但普通设备代理不伪造应用归属，进程级路径需验证覆盖。
- [x] 每阶段有明确文件、测试与停止条件，未知或未授权条件不会引发无限试错。
- [x] 清理只限本工具所有权；异常恢复不能覆盖用户后来变更或承诺失联时远程恢复。
- [x] 不改变现有模拟器/iPhone/断点行为，先POC再UI与发布；本轮只交付计划。

本轮依据为当前工作树5ba8771的只读源码、仓库既有试验文档，以及本文件直接链接的一手公开资料；未重新实测手机、Jenkins或第三方工具。外部资料作为技术证据，不作为设备操作指令。

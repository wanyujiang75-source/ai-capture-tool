# 进度记录

## 2026-11-10 新 iPhone 接入

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| IOS-NEWDEVICE1 | DOING | 桌面端新iPhone验收及用户追加引导补齐 | goal.md、progress.md、specs/ios-new-device-20261110.md；IOSSetupCopy.swift、IOSSetupView.swift、tests/test_ios_setup_guidance.py、docs/desktop-user-guide.md；桌面/手机UI证据；Downloads本轮证书副本；私有节点导入脚本/测试 | 引导结构回归/Swift测试/构建及隔离UI检查；新机HTTPS与桌面状态一致、真实PokeHub请求响应、停止及网络恢复 | 引导3回归/Swift184项/隔离UI通过；USB截图定位原节点仍选中，临时选Capture-Mac后新机HTTPS实际通过/client_ip .236；桌面开始#89收到10条SDK请求并原生停止；PokeHub停登录页 | 等本人登录首页后录制业务请求响应；最后恢复美国[0.2]/配置及验证网络。当前录制已停、临时连接保留，完整业务验收未完成 |

## 2026-11-10 PokeTrade 原版

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| ANDROID-POKETRADE1 | BLOCKED | PokeTrade正式版HTTPS代理对照 | goal.md、progress.md、specs/android-poketrade-original-trial.md；私有诊断脚本/摘要/临时配置/证书 | 身份及原APK摘要确认；本机/浏览器对照；业务完整请求响应或准确失败层；恢复VPN原配置及清理 | 本机/手机浏览器解密通过；api.pockettrade.app 6次TLS证书拒绝、0条业务HTTP响应；原配置节点恢复，VPN实例189未变，13个APK摘要一致，首页列表恢复；本轮CA/配置/代理/密钥/正文/转发清理 | 诊断及恢复完成，完整业务正文受证书信任限制；不把UnityAds错误当业务证据，详见专项记录 |

## 2026-11-10 StickerHub TLS透传

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| ANDROID-TUNNEL1 | DONE | 原版StickerHub独立代理透传对照 | goal.md、progress.md、specs/android-sticker-tunnel-trial.md；私有有界代理脚本/测试/临时配置 | 本机认证与TLS对照通过；业务目标连接和应用状态核对；VPN保持开启；恢复原模式节点并清理自有资源；不宣称取得HTTPS正文 | 原型4测试通过；认证对照200/TLS验证0、未认证407；业务12条隧道，上传56479/下载139051加密字节，画册正常、无证书错误；原VPN配置/节点恢复、实例189未变；临时配置/转发/服务/凭据清理，12个APK摘要一致 | 仅透传对照验收完成，ANDROID-STICKER1完整正文目标仍BLOCKED；不把连接数当接口数 |

## 2026-11-09 StickerHub 正式包对照

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| ANDROID-STICKER1 | BLOCKED | 一加StickerHub正式包临时代理/CA验收 | goal.md、progress.md、specs/android-sticker-original-trial.md；私有诊断脚本/原包摘要/证据；本轮临时配置/证书/转发 | 正式包身份与摘要前后一致；VPN保持开启；浏览器对照及真实业务完整正文或明确失败层；原配置节点恢复、临时资源清理 | 3.18.14(195)原版12个APK摘要不变；浏览器200及正文通过，业务41次TLS失败、0条HTTP响应，应用报unable to get local issuer certificate；原VPN模式/节点恢复，本轮CA/配置/转发/服务/密钥已清理，画册恢复7/216且新进程证书错误0 | 诊断和恢复已完成；完整正文采集受应用信任限制阻塞，不在当前免Root/不改包边界内盲试其他CA；详见专项记录 |

## 2026-11-09 原版临时代理试验

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| ANDROID-ORIGINAL-PROXY1 | BLOCKED | 原版经现有VPN临时转发与用户CA兼容性验证 | goal.md、progress.md、specs/android-original-proxy-trial.md；私有临时代理/测试/配置/证据；一加自有临时配置和CA | 原包12摘要不变；VPN开启；手机对照TLS通过；原版业务Request/Response或明确失败层；恢复配置节点并移除自有资源 | 浏览器HTTPS200/正文通过；原版33次TLS失败，日志unable to get local issuer certificate，业务响应0。原配置/US恢复、VPN仍连接、12摘要一致；本轮CA/配置/文件/转发/进程及私钥回收。恢复后训练家页另有后端57014查询超时，未宣称全正常 | 诊断与清理完成，原版完整正文仍阻塞于证书信任；不改包/Root/原配置，不盲试、不发布 |

ANDROID-COPY1停止：用户明确改为只验证原版，不再继续副本路线。副本启动与Gadget连接通过，但登录失败、未取得业务正文；11:52已移除诊断钩子和自有转发，原12个APK摘要一致。保留既有私有产物，不发布、不继续安装。

## 2026-11-09 ANDROID-COPY1 恢复执行

继续同一 DOING：范围扩展至私有目录的 rebuild.py/test_rebuild.py、独立构建/身份/验收产物和副本进程诊断脚本；goal.md、progress.md、specs/android-copy-capture-trial.md及脱敏实验补丁。不触及桌面产品代码或发布。验收身份重试/失败不污染测试、12包签名/包名/原文件不变、无客户端启动及后附加、真实请求响应、原代理/VPN/转发基线与收尾；登录需要本人完成。

## 2026-11-09 macOS 发布

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| RELEASE-1109 | DONE | 构建验证并发布新版 macOS 桌面预览包 | goal.md、progress.md、specs/desktop-release-20261109.md、release/notes-20261109.md；构建产物和新 GitHub Release | 打包回归、最终包隔离生命周期/签名/身份/敏感文件检查、公开下载 SHA256 一致 | 固定6432488；21项打包/准入、最终包126项通过；测试运行目录污染已隔离复验，严格签名通过；GitHub上传digest与匿名下载/源文件逐字节相同，99,437,665字节；未改手机或已安装应用 | 交付公开下载地址；无main合并，无PokeHub副本发布 |

## 2026-11-09 ANDROID-COPY1 启动修复子范围

继续已有 DOING，不领取其他任务。范围：/tmp/pokehub-copy-7Bfcmp/{clone.py,finish.py,verify.py,test_startup.py}，goal.md、progress.md、specs/android-copy-capture-trial.md 及启动修复补丁。验收：配置回归先 RED 后 GREEN、身份隔离回归、Python 编译与 diff 检查。本轮不运行安装/签名步骤，不操作手机或 VPN。整体真机抓包验收仍未完成。

结果：P1 源码已改为 resume；四项配置/身份测试通过（启动四个子场景先 RED 后 GREEN），四文件 AST 通过。旧 APK 七项验收中六项通过，启动策略一项失败，明确拒绝旧包交付；并非新包验收成功。补丁与回归测试留存 specs/android-copy-startup-p1.patch。整体任务保持 DOING，下一步是解决签名凭据 P2 后再重建和真机验收；本轮未实施其他 P2，未安装、未改变网络配置。

## 2026-11-06 原版副本免Root试验

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| ANDROID-COPY1 | BLOCKED | 独立重签副本和进程内USB诊断验证 | goal.md、progress.md、specs/android-copy-capture-trial.md；独立临时APK/脚本/测试证据；仅com.mi.poketrade.capturetrial | 独立包安全检查、签名、安装/启动/诊断连接、真实业务Request/Response及原包/网络不变/转发回收；阻塞如实记录 | 副本登录失败；用户停止改包路线，不得继续；原包及网络已复核 | 仅保留历史证据，不恢复副本试验 |

## 2026-11-05 AP-0 Android真机只读准入

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| AP-0 | DONE | 独立只读能力检查及一加原版PokeHub准入验收 | goal.md、progress.md、specs/android-physical-capture-plan.md、specs/android-physical-ap0-acceptance.md、capture_console/android_physical_capabilities.py、tests/test_android_physical_capabilities.py | 安全边界与状态测试通过；指定真机/包身份/网络证据及前后基线对照；未知不冒充成功 | 13项新增、相关回归共33项通过；多用户RED已修复；Play来源包12个APK验签及前后摘要一致；VPN/代理/转发有限基线一致，无写设置操作；当前抓包条件blocked而非抓包成功 | 本地交付检查结果；无已验证通道，不进入AP-1、不推送或发布 |

## 2026-11-05 Android 真机抓包调研与计划

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| ANDROID-PLAN1 | DONE | 调研Android真机抓包并交付评审计划 | goal.md、progress.md、specs/android-physical-capture-plan.md | 官方来源与源码/历史证据对应；原版Release、VPN、Root及证书边界明确；阶段与恢复验收可执行；diff检查通过且无产品/设备变更 | 已核对官方来源、历史一加/Charles试验及现有源码；完成10节方案自审，git diff --cached --check通过，变更仅三份规划文件；无产品测试或本轮真机操作 | 交付评审稿；AP-0至AP-4未开始，不推送或实施 |

## 2026-11-05 更新 GitHub 下载包

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| RELEASE-1105 | DONE | 发布当前已验收桌面预览安装包 | goal.md、progress.md、specs/desktop-release-20261105.md、release/notes-20261105.md、release/安装说明.md；release构建资产及新GitHub标签/Release；当前功能分支 | 打包回归与最终包隔离启动/签名通过；说明包含删除警告及前置条件；远端标签、资产digest和匿名下载SHA一致；原应用/VPN不变 | 固定源码4933585；8项打包回归及最终包239项通过，签名/来源/说明一致。首次夹具路径失败已修正复验，既有开发依赖审计见规格。14:36:57公开desktop-preview-20261105-4933585；两项资产uploaded且digest一致。匿名下载经低速续传和瞬时TLS错误重试后，全部99,434,512字节与源ZIP一致、sha256 99ef9459…匹配；校验文件cmp一致。旧Release/main/当前本机应用/VPN及身份不变 | 本轮发布完成；交付验收记录与公开下载链接 |

## 2026-11-05 推送及本地桌面更新

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| DELIVERY-1105 | DONE | 推送当前分支并更新本地原生桌面 | goal.md、progress.md、specs/capture-history-retention.md；macos-native/build/抓包工具.app；/Applications/抓包工具.app；origin/codex/ios-device-trial | release构建、安装包重启/签名通过；应用程序目录启动与版本一致、历史七条；远端分支SHA与本地一致；不改VPN/原配置 | 产品5f70d0d已push并经ls-remote核对；release构建/ditto安装成功，安装包三轮正常/异常重启1项通过(3.957秒)，启动后严格签名通过。原生历史#87至#81，后端build_id=5f70d0db9dc1，app87759/backend87765均来自/Applications，无旧进程；275归档/3身份文件及应用表摘要一致。产品源码未变，复用此前238后端及184 Swift报告。main仍c4a7d6c，未发布Release | 交付证据随分支同步；本轮完成 |

## 2026-11-05 自动删除超额历史

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| FLOW-RETENTION7 | DONE | 后端自动保留七次历史并删除旧归档 | goal.md、progress.md、specs/capture-history-retention.md；capture_console/{store,capture_retention}.py；tests/{test_capture_retention,test_console_core,test_ios_lifecycle,test_ios_packaged_lifecycle}.py；macos-native/Sources/AICaptureNativeApp/{AppState,AppCopy,CaptureSourcePicker,CaptureSourcePresentation}.swift；macos-native/Tests/AICaptureNativeAppTests/{CaptureSourcePresentationTests,IOSCaptureIntegrationTests}.swift；docs/desktop-user-guide.md；本机独立构建与已授权超额历史目录 | 后端/Swift RED-GREEN及回归；文件边界、失败重试、活动保护；本机七条与旧文件删除核对、保留配置摘要不变 | 后端238项（含11项清理回归）、Swift报告184项/24 suites（1项既有条件跳过）通过；安装包三轮重启及严格签名通过。初次测试pyc污染签名，重构建并使用-B后复验通过。实际删除#80至#77及4目录，保留#87至#81的275文件、3身份文件和应用表摘要一致；新版retention7-20261105已启动，原生历史刷新、旧编号无结果、#87加载75条通过；VPN/原配置未改。详见规格证据 | 本地单任务提交；未推送或更新远端包 |
## 2026-11-05 历史记录最近七次

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| FLOW-HISTORY7 | DONE | 历史记录仅展示最近七次 | goal.md、progress.md、specs/flow-source-presentation.md；macos-native/Sources/AICaptureNativeApp/{CaptureSourcePresentation,CaptureSourcePicker,AppCopy}.swift；macos-native/Tests/AICaptureNativeAppTests/CaptureSourcePresentationTests.swift；docs/desktop-user-guide.md；独立 /tmp/capture-history7-20261105 验收应用与只读网关 | 数量/倒序/搜索范围/当前任务隔离 RED/GREEN；Swift 全套、release、原生历史搜索刷新验收 | 新增2项RED/GREEN；Swift报告181项/24 suites通过（1项既有条件实链路跳过）；release14.77秒/签名通过。原生只列#87至#81，刷新仍七条，#80搜索为空，#81可选；原数据11条未删，原app65730/backend65750未动，验收进程已退出。详见规格 | 本地单任务提交；当前窗口未切换新版，未推送/更新GitHub安装包 |

## 2026-11-05 请求与响应数据展示

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| FLOW-DETAIL1 | DONE | 完整呈现已捕获参数、Headers、Body并格式化键值对 | goal.md、progress.md、specs/flow-detail-presentation.md；macos-native/Sources/AICaptureNativeApp/{AppCopy,Models,FlowViews,FlowListPresentation,FlowDetailPresentation,FlowJSONFormatter}.swift；macos-native/Tests/AICaptureNativeAppTests/FlowDetailPresentationTests.swift；tests/flow_detail_native_ui_fixture.py；docs/desktop-user-guide.md；独立 /tmp/capture-detail-ux-20261105 验收应用 | 格式/转义/数值/重复键/空态/截断/大包边界 RED/GREEN；Swift 全套、release 构建签名、隔离原生窗口 Request/Response/cURL 与连续复制 | 首轮及独立复核边界、JSON null均RED/GREEN；新增14项，最终Swift报告179项/24 suites通过（1项条件实链路跳过）；release/签名及合成原生窗口、连续复制通过。超长元数据转换前后有界，旧二进制回退保留；原7001/PID45594/签名不变，自有fixture/app已退出。详见规格 | 本地单任务提交；未推送、未更新GitHub安装包或覆盖原已打开应用 |

## 2026-11-05 接口来源与专业文案

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| FLOW-UX1 | DONE | 当前与历史分离、精简接口页文案与选项 | goal.md、progress.md、specs/flow-source-presentation.md；macos-native/Sources/AICaptureNativeApp/{AppState,AppCopy,FlowViews,IOSCaptureModels,IOSCaptureCopy,CaptureSourcePresentation,CaptureSourcePicker}.swift；macos-native/Tests/AICaptureNativeAppTests/CaptureSourcePresentationTests.swift；docs/desktop-user-guide.md；临时只读网关 /tmp/capture-flow-ux-20261105/slow-readonly-api.py | 来源/选择/日期兼容及状态回归、Swift全套、release构建/签名、原生窗口当前空态/历史/详情/返回/刷新通过 | 两轮RED/GREEN，最终Swift报告165项/23 suites通过（1项既有条件实链路跳过）；release/独立签名通过；原生历史搜索/状态/清空/返回/详情验收通过，30秒慢响应切换新记录立即加载且不串数据；评审问题已处理。原PID45594/idle/null及签名不变，未改VPN和原配置；详见规格证据 | 本地提交，保留分支；未推送或更新安装包，原已打开应用未替换 |

## 2026-11-04 BP-4 综合验收

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| BP-4 | BLOCKED | 真机、安装包、性能与生命周期综合验收，补使用说明 | tests/{test_breakpoint_e2e,breakpoint_device_acceptance,test_breakpoint_device_acceptance,test_native_app_packaging}.py、tests/fixtures/breakpoints/production.py；复用既有断点/iOS/Swift测试；release/{package.sh,安装说明.md}；docs/{desktop-user-guide,breakpoint-user-guide}.md；goal.md、progress.md、specs/breakpoint-{plan,acceptance}.md | 迁移包真实控制/转发/归档、未命中p95新增<=10ms/RSS<64MiB、生命周期/旧抓包/Swift回归、签名与私有数据扫描、原生及iPhone请求响应改写；Android真机按2026-11-04用户要求延后，不作为本轮门槛 | iPhone改写手机确认；324后端、45传输、36严格、Swift152、TLS3、最终包7项通过；ZIP说明1项RED/GREEN；信号/prepare清理与子进程来源缺口已RED/GREEN修复，限定复核无剩余P1/P2。包99,393,290bytes，签名/SHA/无私有数据通过。原7001与身份未变，自有进程/敏感临时数据已回收。Android尚未实测但不再阻塞本轮；整机休眠/唤醒及第二台新Mac实装未覆盖；详见acceptance | 仅等待安全休眠/唤醒条件补本轮现场矩阵；Android后续另行考虑，不自动验收；仅本地提交和预览包，不推送/发布 |

## 2026-11-04 BP-3 桌面断点

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| BP-3 | DONE | 桌面规则、全局队列、请求/响应编辑与归档呈现 | 新 macos-native/Sources/AICaptureNativeApp/Breakpoint*.swift，现有 {AppState,ContentView,FlowViews,Models,RuntimeManager,APIClient}.swift 最小组装；对应 Swift 测试；capture_console/breakpoints/{api,archive}.py、capture_console/{ios_results,breakpoint_preview}.py；tests/test_breakpoint_{api,archive}.py、tests/breakpoint_native_ui_fixture.py；goal.md、progress.md、specs/breakpoint-{plan,bp3}.md | Swift全套、认证与隔离/旧抓包回归、真实loopback编辑、原生正常/空/加载/失败与复制验收，无用户环境变化 | 基线fd215df；Swift152项、后端75项、真实链路45项、旧抓包249项通过；显式Swift实链路1项通过。最终原生窗口验证改写/放行/终止/复制/过滤清空/慢详情/失败恢复/归档；复核问题已RED/GREEN修复。自有进程与临时凭据已回收，7001仍be6d0543b498/running/idle/null，未改VPN或原配置；详见bp3规格 | 仅本地提交并保留分支；BP-4真实设备及安装包综合验收未领取，不推送/发包 |

## 2026-11-04 BP-2 真实链路与归档

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| BP-2 | DONE | 默认关闭的真实传输接线、控制生命周期与原始/有效归档 | `capture_console/breakpoints/**`, `capture_console/{app,runner,results,ios_pairing_proxy,ios_recording,ios_setup,ios_results}.py`, `scripts/{ai_capture.sh,start_mitm_stack.sh,start_mitm_socks_stack.sh,ai_capture_stop.sh,ai_capture_export.py,breakpoint_addon.py}`, `tests/test_breakpoint_*.py`, `tests/fixtures/breakpoints/**`, `goal.md`, `progress.md`, `specs/breakpoint-{plan,bp2}.md` | 新adapter/archive/lifecycle真实loopback验收；BP-1/BP-0及既有归档回归；大包/取消/停止无退化；不改实际运行环境 | 基线0d27300；最终45项真实链路108.923秒、73项核心16.451秒、严格36项49.087秒、249项原有8.632秒通过（共403项）。100MiB响应额外RSS约4.9-5.8MiB且哈希完整；停止/单流取消/配额/短写/204等RED已修复，两组限定复核无残余P1/P2。shell/AST/diff通过；现有服务build/running/idle/null不变。详见bp2规格完整失败与复验记录 | 仅本地提交，保留分支；BP-3未领取，尚无桌面断点编辑入口，不推送/发包，不操作手机/VPN |

## 2026-11-04 断点 BP-0 隔离能力验收

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| BP-0 | DONE | 修复隔离原型的收集取消和有界传输 | `goal.md`, `progress.md`, `specs/breakpoint-plan.md`, `specs/breakpoint-bp0-acceptance.md`, `tests/test_breakpoint_transport.py`, `tests/test_breakpoint_guard.py`, `tests/fixtures/breakpoints/**` | 真实H1/H2慢正文绝对/空闲期限取消并回收；H2同连接其他流不受影响；100MiB请求/响应暂停或自动降级及慢消费者额外RSS<64MiB、字节哈希完整；原有18项及37项回归；默认关闭/版本不符拒绝适配；自有进程清理 | 最终严格36项49.116秒通过；18项负对照/能力实验34.860秒、37项既有回归0.875秒通过；默认54项中49跳过/5契约通过。100MiB约3.2-4.4MiB、20路约21.2MiB；取消/背压/断连/TLS/GOAWAY与哈希通过。独立复核问题均RED/GREEN修复。前后现有服务build/idle/null一致；自有进程和临时目录回收，历史NO-GO保留。详见验收规格 | 准入BP-1，仅本地提交；生产接线仍属于BP-2，未验证协议/组合不启用，不推送发包 |
| BP-1 | DONE | 实现独立断点状态、预算和认证控制契约 | 新 `capture_console/breakpoints/{__init__,models,engine,validation,control,ipc,api}.py`；新 `tests/test_breakpoint_{engine,api,ipc}.py`, `tests/fixtures/breakpoints/control.py`；`goal.md`, `progress.md`, `specs/breakpoint-plan.md`, `specs/breakpoint-bp1.md` | 三项BP-1套件；匹配/单次占用/双阶段/期限/预算/鉴权/幂等/失联与停止竞争RED/GREEN；真实UDS和loopback API串联；既有37项回归及BP-0矩阵；不接真实传输或手机，不改VPN | 基线27f5c6a；53项11.691秒、37项0.861秒、BP-0严格36项47.367秒均通过。真实独立worker及HTTP→UDS验收；不读响应客户端退出、陈旧决策、正文副本/规则帧预算等RED已修复，详细失败/验证记录见bp1规格。两组限定静态复核无剩余P1/P2；现有服务前后be6d0543b498/running/idle/null，产品入口无新导入，自有资源回收 | 仅本地提交；下一阶段BP-2接真实传输/归档，本轮不领取；尚无用户可用桌面断点，不推送发包 |

BP-0 首轮记录：HTTP/1.1/2 双阶段改写、gzip/deflate/br 原样及改写、未知长度越界、并发20名额和origin排除通过。慢正文负对照确认公开 flow.kill 调用后连接仍不结束。10项首次全跑有2项失败：头暂停测试第二轮误把第一轮已转发记录计入“尚未转发”，属夹具断言范围错误；H2 100 MiB 透传 worker RSS 超64 MiB，属需与关闭断点基线对照的能力风险，不能降低门槛冒充通过。继续同一 DOING，拆分每协议独立worker、补响应头与基线对照后记录禁用结论；没有产品改动。

BP-0 续修中的复核：首版适配24项通过后，独立复核发现上游并发排队未计账、远端RST信用残留、聚合背压阻塞其他流、夹具接收循环被慢流阻塞四项边界。新增RED已复现：取消后credits仍为{1:7}、健康同连接流3秒未完成、上游只允许1流时排队上传半秒接收36,864,000字节。修复为逐流预算（包含stream_queue）、取消未发送队列和RST/GOAWAY清理；夹具按消费返回逐流窗口，控制帧不等待消费者。定向4项3.805秒通过，上游排队限制到294,912字节后背压、取消后源站不收到该请求。完整严格矩阵与原基线重跑中，仍保持DOING；未动产品、VPN或设备。

补充退出路径：上游GOAWAY/EOF时含未获并发名额的排队请求，新增用例RED暴露ResponseProtocolError缺少code导致代理异常、仅部分请求结束。补全错误码，并在上游ID映射外发送未admit流的错误通知；定向用例0.996秒通过。错误证据扩为最多4096字符异常尾部，失败时临时目录清理由独立cleanup保证。最终28项严格矩阵复跑中，未把此前27项通过当作新增用例已通过。

第二轮补强：28项通过后，DATA+GOAWAY同批输入的信用返还触发ProtocolError，空/细碎DATA在暂停和发送队列累积4001/4000项，新增RED后修复CLOSED检查、空事件过滤和16KiB合并；31项45.376秒通过。复核夹具Wire同类GOAWAY错误也新增独立RED并修复。另对H1内存波动补源站延迟TLS场景，复现1604个排队事件；新增仅测试handler实例的H1读取节流（不改全局类），恢复TLS后100MiB哈希完整、额外RSS3,833,856 bytes，1.926秒通过。第一版延迟TLS夹具不能回放已收ClientHello，改为延迟TCP转发桥；初次夹具清理顺序错误导致wait_closed挂起，仅向已核对的自有测试进程发SIGINT，父/worker均退出，修正为先关连接再有界等待。继续DOING，最终矩阵和退出门槛复跑，不回避这些失败记录。

第三轮退出复核：H1读取节流阻挡EOF，源站握手永久停顿且客户端断开时缺少独立退出路径。新增RED在3秒等待取消事件超时（1项4.461秒失败）；补不因事件唤醒续期的10秒绝对读取等待上限，仅回收该H1连接及其自有上游，停止已流式/未命中收集计时，避免唤醒刷新底层空闲看门狗。断连回收/握手恢复后100MiB完整转发/等待期间退出三项4.987秒通过，内存增量4,177,920 bytes。完整矩阵未重跑前仍DOING。

最终复核补正：35项严格测试48.419秒、18项原对照34.860秒、37项既有回归0.875秒通过后，审查发现响应头入队但response对象尚未创建时，收集计时两处解引用None。新增真实HTTPFlow/HttpStream定时契约测试，在未占用/已占用两子场景分别RED复现AttributeError；补消息对象防护、等待实际创建，创建后流式状态正常退订计时，GREEN1项0.002秒。此单项是状态契约复现，不冒充真实网络竞态观测；36项最终严格矩阵重新运行中，仍DOING。

最终收口：36项49.116秒全部通过；限定静态复核确认None response修复，无剩余具体P1/P2。18项原对照及37项回归对应文件/依赖未再变化，复用上述结果；默认opt-out重新执行54项0.018秒（5契约通过、49跳过，无代理）。7001仍为be6d0543b498/running/idle/null；自有worker枚举为空，回归临时目录唯一数据库及目录已删除。BP-0写DONE，BP-1仅TODO，不接入产品、不碰手机/VPN、不发包。

## 2026-11-04 接口过滤发布

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| FLOW-R1 | DONE | 推送接口过滤并更新可下载桌面安装包 | `goal.md`, `progress.md`, `specs/flow-filter-release-20261104.md`, `README.md`, `release/安装说明.md`, `release/notes-20261104-filter.md`；已有打包脚本/产物与GitHub main/功能分支/新预发布 | 源码与回归对应；包内筛选说明、arm64、严格签名、隔离启动/归档通过；无本机数据；快进推送与标签一致；公开下载SHA-256一致 | Python358项（353通过/5个opt-in另行全部通过）、Swift126项通过；最终包内13项摘要测试、三轮归档重启、原生6/6→3/6→搜索1/6→恢复6/6、签名通过。源码be6d054和同名新预发布已公开，ZIP99,719,780字节；匿名下载SHA-256/字节完全一致。首次上传408保留草稿，重试成功后才公开；详见规格 | 发布完成，旧包和用户无关文档保留；手机/VPN未改。仅显示启发式筛选，不包含断点实现；未公证/新设备兼容与NSTableView警告边界如实记录 |

## 2026-11-04 断点功能调研与计划

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| BP-P1 | DONE | 调研并交付请求/响应断点计划书 | `goal.md`, `progress.md`, `specs/breakpoint-plan.md` | 官方依据可追溯；核对实际转发链路；交互、字段范围、流式/大包/并发/失联/退出/原始与有效数据明确；阶段任务与验收可执行；不实施功能 | Charles/Proxyman/Fiddler官方资料、mitmproxy事件/API及本机12.2.3源码核对完成；形成交互、5阶段任务与验收矩阵。自审修正阶段恢复语义/租约/非法头转换；独立只读评审的头暂停内部队列风险已纳入BP-0。三文件格式与范围检查通过，无真实连接凭据；未构建、运行代理或修改产品/手机 | 交付计划供评审；实现尚未开始，后续首先执行BP-0隔离能力与内存原型；本轮仅本地文档提交，不推送发包 |

## 2026-11-04 接口列表过滤

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| FLOW-F1 | DONE | 增加可恢复的仅看接口筛选 | `goal.md`, `progress.md`, `specs/flow-interface-filter.md`, `macos-native/Sources/AICaptureNativeApp/{FlowTrafficFilter,FlowListPresentation,FlowViews,Models,AppCopy,AppState}.swift`, `macos-native/Tests/AICaptureNativeAppTests/{FlowTrafficFilterTests,FlowListPresentationTests}.swift`, `capture_console/{results,ios_results}.py`, `tests/{test_flow_summary_types,test_ios_results,ios_native_ui_fixture}.py`, `docs/desktop-user-guide.md`；本地构建/隔离UI | 分类及摘要RED/GREEN；搜索/恢复全部/失败请求/清空/实时更新/异步详情回归；Python/Swift通过；原生按钮、计数、空态及搜索视觉验收；不改手机或采集、不发布 | 代码未改变，复用既有Python199项、另iOS75项（重叠）、隔离HTTPS3项和Swift126项通过证据。解锁后CUA原生补验：6/6切3/6、401搜索1/6、无匹配0/6、增量4/8、全过滤0/3、清空后1/2及关闭筛选2/2，旧详情不残留，失败提示及恢复通过。严格签名再次通过；自有App/夹具已退出，7001无监听，未操作手机/VPN | 本地功能验收完成；仅提交验收记录，未推送或更新GitHub安装包；合成UI不是新增真机采集证据，系统全键盘导航未作完整验收 |

## 2026-11-04 iOS 说明与安装包发布

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| IOS-R1 | DONE | 发布已验收的iPhone统一接入与新手说明 | `goal.md`, `progress.md`, `specs/ios-release-20261104.md`, `README.md`, `INSTALL.md`, `docs/desktop-user-guide.md`, `release/安装说明.md`, `release/notes-20261104.md`, `macos-native/Sources/AICaptureNativeApp/IOSSetupCopy.swift`；现有打包产物、GitHub main/功能分支/新预发布资产 | 前置条件/一次性节点/重连/恢复完整无矛盾；相关Python、Swift、隔离TLS、包迁移运行与签名通过；无用户数据/凭据；远端源码和包摘要可核对 | 356项Python套件351通过/5项opt-in另行全部通过，Swift121项通过；最终ZIP独立启动/三轮归档重启/严格签名通过。源码d2795fe已原子快进推送，desktop-preview-20261104-d2795fe公开，99,695,714字节；匿名重新下载SHA-256与本地一致。说明已同步仓库和包内，合成配置脚本校验通过；详见发布规格中的校验修正、公开Tornado fixture与覆盖边界 | 本轮交付完成；保留其他IOS任务状态，不等同于自动手机配置或全新设备整体验收；手机VPN/原配置未改，旧发布及用户文档保留 |

## 2026-11-04 iPhone 多应用兼容实测

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| IOS-C3 | DONE | 移除桌面域名准入并继续三款自有iPhone应用实测 | `goal.md`, `progress.md`, `specs/ios-multi-app-acceptance.md`, `capture_console/{ios_recording,ios_pairing_proxy,ios_setup,ios_setup_api}.py`, `tests/test_ios_{capture,setup,setup_integration}.py`, `macos-native/Sources/AICaptureNativeApp/{IOSCaptureView,IOSCaptureCopy,IOSSetupCopy,IOSSetupController,IOSCaptureModels,APIClient}.swift`, `macos-native/Tests/AICaptureNativeAppTests/{IOSCaptureIntegrationTests,APIClientTests}.swift`, `docs/desktop-user-guide.md`；本地构建及指定手机验收 | 无项目/域名直接开始；多域名Req/Resp、停止透传、不自动续录、认证和手机隔离、配额与旧调用兼容回归；Swift与真实代理测试、构建签名、原生UI无域名输入；三款真实Req/Resp；VPN持续开启、原选择测试后恢复，无敏感数据提交 | 统一接入实测完成：临时Capture-Mac/代理，无新增域名。MelodyCraft #85/32条、Wishly #86/22条、StickerHub #87/75条；三条业务POST200、完整未截断JSON Req/Resp及原生展示通过。用户确认恢复配置模式/VPN开启，USB核对原节点重新选中；手机HTTPS网页实际加载，三个stopped及计数断言通过。此前259项Python、121项Swift、3项真实TLS及构建对应未改变代码；本轮只更新操作指南和验收文档 | 本地提交并保留桌面ready/stopped及历史记录；无推送/发包。自动导入/手机自动切换与恢复、新设备兼容、原出口多级代理均不在本次通过范围 |

## 2026-11-03 iPhone 新证书迁移实测

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| IOS-C2 | DONE | 启动新版桌面、迁移本工具证书并验证指定iPhone的PokeHub | `goal.md`, `progress.md`, `specs/ios-certificate-migration.md`；现有新版App、真实运行目录与本工具Keychain条目、私有临时公开配置、仅固定文字且自动关闭的局域网诊断端点及指定手机UI/USB只读诊断 | 版本匹配；旧配置已移除；新CA/期限匹配且无Wi-Fi/VPN载荷；手机HTTPS实际验证；PokeHub业务Request/Response进入桌面；停止后保留连接且不新增记录；VPN/原节点不变，仅授权的专用节点更新与检查规则补回；临时日志恢复；无凭据入库 | 一年期证书-only配置安装一致，手机HTTPS及PokeHub真实业务Req/Resp通过。2026-11-04原生按钮停止#78，页面/API为stopped、connection ready；手机目标域名只读访问返回预期响应且有代理连接，重新打开PokeHub后仍166条。接口页显示166/166已停止，版本配置20/2142字节完整JSON仍可读，8项只读断言通过；USB截图确认临时代理日志关闭。原VPN节点/订阅/DNS/默认路由未修改，证书和连接保留 | 本轮迁移实测完成，仅本地证据提交；无损自动导入、切换节点、跨重启手机及新用户整体验收仍按其他IOS任务推进，不视为本任务已全部覆盖，不推送或发包 |

## 2026-11-03 iPhone 长期证书复用

IOS-C1必要验收修复范围补充：`macos-native/Tests/AICaptureNativeAppTests/RuntimeManagerTests.swift`。完整测试及单独运行均在既有NSWindow测试退出时SIGSEGV；NSZombieEnabled定位为`-[NSWindow release]: message sent to deallocated instance`。仅修正该测试的窗口所有权，不改变产品行为、不跳过测试。

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| IOS-C1 | DONE | 独立一年期身份、Keychain保管、跨重启复用并修正桌面重连操作 | `goal.md`, `progress.md`, `specs/ios-certificate-reuse.md`, `specs/ios-setup-automation-plan.md`, `capture_console/{ios_keychain,ios_pairing_identity,ios_setup,ios_setup_api,ios_pairing_proxy}.py`, `tests/test_ios_{identity,keychain,setup,setup_integration}.py`, `tests/ios_native_ui_fixture.py`, `macos-native/Sources/AICaptureNativeApp/{IOSSetupController,IOSSetupView,IOSSetupCopy,IOSCaptureView,IOSCaptureCopy}.swift`, `macos-native/Tests/AICaptureNativeAppTests/{IOSSetupTests,RuntimeManagerTests}.swift`, `docs/desktop-user-guide.md`, `release/安装说明.md`；隔离测试运行目录/自有Keychain测试条目和本地App构建 | 相同CA/凭据/端口跨24小时及3次重启；退出回收明文材料，不恢复ready/录制；真实TLS、撤销、到期、Keychain拒绝、占用端口、旧版状态保护；Python/Swift与构建签名通过 | 相关Python253项、真实TLS与隔离Keychain4项、Swift119项通过；独立审查四项风险均RED复现并修复，复审无遗留具体发现。最终App内嵌后端15项身份测试、严格签名及隔离原生窗口检查通过。既有NSWindow测试重复释放已修正，未跳过测试；详细证据见规格 | 本地实现和构建完成，未推送/发包；旧手机证书仍需一次人工迁移，真实手机重连未在本轮验收；其他IOS任务状态不变 |

## 2026-11-03 Charles兼容连接试验

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| CHARLES-D1 | BLOCKED | 保持上游和VPN配置不变，恢复Charles联网并验证一加PokeHub采集条件 | `goal.md`, `progress.md`, `specs/charles-android-trial.md`；本机临时loopback转发、Charles UI、指定一加诊断及自有临时USB反向转发/公开证书文件 | HTTP/HTTPS联网分层验证；必须实际取得PokeHub Req/Resp才能整体通过；未经新增授权不改手机代理或证书；不改上游/VPN；仅回收自有临时进程 | 17:26临时透传完成Mac/一加USB HTTP和HTTPS 200、verify 0对照，但未取得PokeHub业务接口。17:32用户明确拒绝手机代理和测试CA；核对PID44191身份后SIGTERM退出0，7890无监听；Charles 8888及原7897保留。反向转发为空、原23761/36166保留；手机全局代理null、VPN CONNECTED、Mac系统代理7897；临时证书文件早已删除，未安装到系统 | 试验已停止并完成自有资源清理；保持用户限制，不重试或反复索取相同授权。当前配置下没有已验证的PokeHub明文采集通道，不标记整体DONE |

## 2026-11-03 一加真机免Root试验

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| ANDROID-D1 | BLOCKED | 检查Jenkins包并在一加真机安全安装PokeHub Release、验证免Root接口采集 | `goal.md`, `progress.md`, `specs/android-physical-debug-trial.md`；本地临时APK/脱敏诊断；指定一加上的com.test.tcgp及自有USB转发（仅需要时） | 安全安装并运行；有界诊断区分普通日志与真实Req/Resp；有完整证据才算抓取通过；不Root或改VPN/代理/证书，不卸载/清数据/重签；移除自有临时转发 | #588安装/摘要校验通过，用户登录后卡牌列表/详情/寻找帖子/训练家页面已查看。16:58:28至16:59:46有界日志135条记录，仅应用状态及统计SDK请求响应线索，没有完整业务Req/Resp。Release不可调试；只读确认现有Frida启动脚本要求Root，未执行。代理null、网络184、VPN transport与基线一致；新增tcp:65282已移除、原两项转发保留 | 安全范围内试验已完成但抓包未通过；需要真正Flutter Debug构建及USB诊断验收，或应用内请求诊断支持。无需继续反复登录或改VPN；不擅自触发Jenkins构建、Root或重签 |

## 2026-11-02 iPhone 配置流程优化规划

以下为规划及实施任务池。2026-11-02已交付IOS-A0；2026-11-03按用户请求只领取IOS-A1，其他任务不同时实施。

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| IOS-A0 | DONE | 评审 iPhone 自动配置流程并形成优化计划书 | `goal.md`, `progress.md`, `specs/ios-desktop-integration.md`, `specs/ios-setup-automation-plan.md` | 首次/重连/停止/退出分流；导入能力验证门槛、安全边界、真实手机证据与任务验收齐全；文档自审及 diff 检查通过 | 已完成代码/官方资料核对、8项风险评审、6阶段任务和验收矩阵；只读复核session 77 ready/recording、26条；文档自审、占位/敏感信息扫描及diff检查通过。未运行构建/产品测试，未改手机或当前连接 | 交付规划；本轮不实施、不推送。后续先执行A1，无损导入未验证前不承诺全自动 |
| IOS-A1 | BLOCKED | 验证小火箭安全增量导入与撤销能力 | `goal.md`, `progress.md`, `specs/ios-setup-automation-plan.md`, `specs/ios-shadowrocket-compatibility.md`, `tests/fixtures/ios_setup_import/`, `tests/ios_import_probe.py`, `tests/test_ios_import_probe.py` | 节点与精确域名免手填导入，重复导入不重复，原节点/DNS/FINAL与其他流量不变；关闭测试配置恢复；切换普通VPN节点后的目标/非目标路径；记录支持版本与证据；空模块交付器只返回固定无设置元数据、未知路径拒绝、有到期清理 | Safari下载成功，远程.module/.sgmodule均报无效URL；本地Name Here空模板默认勾选，未证明远程导入/幂等/恢复。探针既有8项测试通过、监听已释放。镜像现已选正确测试机，但账户更新、重启与锁屏后仍未通过远程解锁配对；按用户要求停止排障。16:09恢复USB截图，手机被现有抓包代理认证弹窗阻挡；后端77仍ready/recording/27条且监听存在，不代表手机实时连通 | 等待用户取消认证弹窗并进入模块页，核对自有空模块信息和清理入口；若弹窗循环，先定位来源。保留原VPN与当前抓包，不重置凭据，不继续镜像或A2 |
| IOS-A2 | TODO | 分离证书、网络路由与短期交付，支持受限复用 | 计划第6节 A2 所列 Python/Swift/测试文件 | 24小时有效期内重开不换CA；下载凭据过期/撤销有效；私钥不交付；端口冲突不杀进程；旧状态不能伪造ready | 待A1确定可支持的导入方式 | 先RED测试，再实现身份与安全交付契约 |
| IOS-A3 | TODO | 提供模式化配置导入与分层诊断 | 计划第6节 A3 所列导入/诊断模块及测试 | 普通Wi-Fi与保留小火箭模式分离；配置生成免手填；检查域名通过不等于应用接口已收到；错误可定位至有证据的阶段 | 依赖A1/A2；不得承诺任意第三方VPN | 实现已验收适配器及只读诊断 |
| IOS-A4 | TODO | 原生向导与精准状态文案 | 计划第6节 A4 所列 Swift/测试文件 | 当前动作唯一；实际手机HTTPS回调推动状态；无重复配置/凭据展示；开始抓包有明确用户意图；正常/空/加载/失败视觉验收 | 复用四导航与既有接口页 | 实现首次/重连向导及错误恢复入口 |
| IOS-A5 | TODO | 停止、重连、断开与异常退出恢复 | 计划第6节 A5 所列生命周期与测试文件 | 停止只停记录；重开不自动录制；失效配置提示准确；手机恢复与本机清理分开确认；Android不受影响 | 不得把关闭Mac代理当作手机已恢复 | 验证重复停启、地址变化、过期与崩溃路径 |
| IOS-A6 | TODO | 新用户真机、回归与本地安装包验收 | 计划第6节 A6 所列测试、说明及打包文件 | 计划第7节矩阵全部有结果；PokeHub与第二受控域名真实Req/Resp；Android共存；新用户不手填技术参数；包无密钥配置与抓包数据 | 第二台Mac/第二台iPhone未实测时必须保留缺口 | 完成端到端与安装说明；未另获发布请求前不上传 |

## 2026-10-30 iPhone 统一桌面接入

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| IOS-D1 | DONE | 项目域名、连接/记录分离、统一会话与有界结果 | `goal.md`, `progress.md`, `specs/ios-desktop-integration.md`, `capture_console/ios_*.py`, `capture_console/{app,store,results}.py`, `tests/test_ios_*.py`, `tests/ios_proxy_worker_fixture.py`, `tests/test_console_{api,core}.py` | Python RED/GREEN；真实隔离 HTTP(S) 启停、透传、代际隔离、限额；Android 相关回归 | 项目/记录控制/SQLite有界存储及共用结果路由已实现；最终239项Python回归7.225秒、2项真实隔离代理4.404秒通过，diff检查通过。独立复核三项状态问题及一项恢复重复断连已RED/GREEN修复，最终窄范围复核无剩余发现 | 本地提交并保留分支；下一轮领取 D2，整体验收仍待 D3 |
| IOS-D2 | DONE | 原生统一抓包入口、接口来源和退出恢复 | `macos-native/Sources/AICaptureNativeApp/`、相关 Swift 测试（含 `CaptureWorkflowTests.swift`）、`tests/ios_native_ui_fixture.py`；本任务 spec/progress；本地隔离构建与视觉证据 | Swift 回归、构建、四导航兼容及新增流程正常/空/加载/失败视觉验收；切换来源及停止保留连接行为 | 最终116项Swift、构建、运行后严格签名通过；同打包配置8项测试已通过。3项竞态及微秒清空边界RED/GREEN修复；旧测试真实服务依赖已隔离并覆盖成功/失败。原生正常/空/加载/失败、正文/cURL、清空、停启新编号、退出/结束确认均验收；锁屏恢复后补齐最后窗口。详见spec证据，合成UI不是手机证明 | 保留本地分支提交；下一轮D3实机、跨重启历史索引与最终包验收；未推送或发布 |
| IOS-D3 | BLOCKED | 实机与最终安装包验收、使用说明 | `capture_console/{app,store}.py`及必要生命周期修复、相关 Python/Swift 验收测试、打包脚本、`README.md`、`INSTALL.md`、`docs/desktop-user-guide.md`、`release/安装说明.md`、本任务 spec/progress | iPhone PokeHub真实Request/Response及第二受控域名；Android共存；停启/结束恢复与iPhone历史索引跨重启；最终包与签名、新用户路径 | 2026-11-02已补齐手机HTTPS及PokeHub实际业务Req/Resp：保留小火箭VPN并人工添加精确域名规则后，#77记录由5条增至26条；桌面已检查200的JSON正文。本轮只读复核仍ready/recording、26条。证据见spec追加记录；未重新运行旧回归，也未把人工配置视为自动配置成功 | 剩余真实第二域名、Android同时抓包、停启/彻底恢复及新包新用户验收需恢复实机执行，本轮规划不操作手机。先交付IOS-A0；后续与IOS-A6合并核验清单，不能宣称D3完成 |

用户已允许正常关闭旧桌面和切换构建，不再受旧版持续运行限制。IOS-TRIAL-1 作为历史试验保留，未完成的手机证明由 IOS-D3 继续完成。

IOS-D1 验证记录：首批测试确认缺少项目模块、记录控制和共享路由；实现后测试覆盖连接已验证但不自动录制、命令版本确认、停止后连接保留、重新开始隔离旧回调、Android/iPhone并存、分页与正文预览限额、磁盘异常、元数据限额、配置保存上限和配置到期清理。
审查复现了失败状态仍满足ACK、连接清理改写历史状态、手机换地址仍报告可抓包三项问题，已先添加失败回归再修复。追加了全局停止入口保护失败历史记录的回归。旧试验长URL测试超过新增128KiB元数据准入限制，已将正常输入与超限拒绝拆为独立验收。
复核进一步发现重新验证期间的CONNECT/请求头事件会重复重置连接；新增事件顺序回归确认3次重置而非2次后，修复为等待验证状态下幂等，最终全部相关测试通过。复核工具首次因模型容量失败，重试后完成独立审查；最终评审仅覆盖生命周期修复，存储/分页由主执行者及边界测试验证。
真实代理测试使用临时本地HTTP/TLS服务、独立认证代理及一次性测试CA；仅测试子进程将本机请求视为合成手机，生产代码仍排除本机自检。验证未认证请求407、目标域名Request/Response、非目标域名不记录、停止后HTTP/HTTPS透传、复用原配置重新开始、记录限额后透传、桌面退出回收和恢复标记。此证据不能替代真实iPhone安装/信任/业务验收。
本轮未改动现有手机配置、旧桌面和Android运行任务，未推送或发布安装包。

## 2026-10-29 iOS 真机可行性试验

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| IOS-TRIAL-1 | BLOCKED | 自动准备 iPhone PokeHub 抓包并只保留必要手机确认 | `goal.md`, `progress.md`, `specs/ios-device-trial.md`, `capture_console/ios_setup.py`, `capture_console/ios_setup_api.py`, `capture_console/ios_pairing_proxy.py`, `capture_console/app.py`, `tests/test_ios_setup.py`, `tests/test_ios_setup_integration.py`, `macos-native/Sources/AICaptureNativeApp/{IOSSetupController,IOSSetupView,IOSSetupCopy,ContentView,APIClient}.swift`, `macos-native/Tests/AICaptureNativeAppTests/IOSSetupTests.swift`, `docs/desktop-user-guide.md`；隔离构建与测试运行目录 | 配置文件不含 Wi-Fi 密码且可移除；代理认证、手机证据与 Mac 自检区分、进程清理和重复启动回归；Swift 引导回归；隔离真实代理验证与桌面构建；手机实际抓包单独记录 | 自动化代码与文档已实现；126 项 Python、101 项 Swift、8 项打包回归通过；隔离代理及包内运行时完成 407/HTTPS 200、自检归属、桌面退出清理及恢复标记验证；最终构建与签名通过。缺少手机网络名及本人安装/信任后的 PokeHub 实测，不记为整体验收完成；未替换活动旧桌面，视觉验收也待完成 | 用户提供 Wi-Fi 名称后继续手机配置与真实接口验收；保留 Android 抓包；仅本地提交，不推送或发布 |

IOS-TRIAL-1 验证记录：初始缺模块/状态类型的 RED 已复现；非 UTF-8 与 gzip 正文回归先失败后修复。
评审发现桌面异常退出、WebSocket 历史、重启清理标记、JSON 转义体积和 Wi-Fi 输入被轮询覆盖五项问题，已加测试修复。
打包首次因新工作树无 `web/dist` 失败，复用同源构建资源后构建通过；随后测试因人为设置 `AI_CAPTURE_BUILD_ID=ios-setup-20261029` 不符合现有默认哈希断言失败，已移除该测试环境覆盖后重跑。
新增混合类型请求体曾导致 Swift 编译失败，已改为类型化 Encodable 请求并通过 6 项专项测试。
补充复核发现状态写失败可能使退出监测失效，已用注入磁盘错误先复现 RED，再验证自动停止及独立凭据清理；iOS 清理失败不再跳过 Android 退出处理，新增回归先失败后通过。最终静态复核无剩余发现。

## 2026-10-26 Jenkins 刷新性能修复

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| J2 | DONE | 减少 Jenkins 列表查询并保留刷新期间的列表 | `goal.md`, `progress.md`, `specs/jenkins-refresh-performance.md`, `capture_console/jenkins_source.py`, `capture_console/app.py`, `tests/test_jenkins_source.py`, `tests/test_console_api.py`, `macos-native/Sources/AICaptureNativeApp/{APIClient,Models,AppState,AppCopy,DeviceAppView}.swift`, `macos-native/Tests/AICaptureNativeAppTests/{JenkinsRefreshTests,APIClientTests}.swift`；本地构建 | 查询/缓存/并发/失败 Python 回归与 Swift 刷新回归通过；同网耗时、请求量及结果一致性验证；桌面构建、刷新和签名通过 | RED 已复现旧查询与缺少状态接口；Python 210 项、Swift 94+1 项通过。旧版 10.962 秒/36 请求/5.19 MB，新版冷加载 1.697 秒/39 请求/29.6 KB，后续 0.249/0.175 秒各 1 请求；最终 API 0.204 秒，前后 31 个包完整数组一致。原生刷新、构建 jenkins-refresh-20261026、运行后严格签名和 diff 检查通过；一次启动请求 502 后恢复已如实记录 | 本机桌面保持打开；仅本地提交，未推送或更新 GitHub 下载包 |

## 2026-10-22 内嵌网页证书修复

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | DONE | 修复 Frida 17 下 Android 证书注入跳过与内嵌网页白屏 | `goal.md`, `progress.md`, `specs/webview-certificate-trust.md`, `scripts/flutter_proxy_unpin_capture.py`, `tools/httptoolkit-frida/android/android-system-certificate-injection.js`, `tests/test_flutter_proxy_unpin_capture.py`, `tests/test_native_app_packaging.py`，本地构建与目标设备验收 | TDD RED/GREEN、脚本与打包回归、App 构建签名、真实证书注入及页面链路验证；不清数据、不改宿主机信任、不发布 | 198 项相关回归与 8 项打包测试通过；Frida 17 显式加载内置 Java bridge，等待 CA ready，失败不再静默跳过或无限存活。#67 捕获同步页与资源 HTTP 200，用户确认“可以了”；无关自签名证书仍拒绝。验收发现包内日志破坏签名，经 RED 修复到 CAPTURE_RUNTIME_DIR；最终 r2 启动 #68、CA ready、包内无 runtime 目录，运行后严格签名及 diff 检查通过 | 保持桌面与 #68 抓包运行；仅本地提交，未推送或更新下载包 |

## 2026-10-22 Jenkins 刷新性能问题记录

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| J2-RECORD | DONE | 记录安装包刷新慢的证据、根因及后续验收标准 | `goal.md`, `progress.md`, `specs/jenkins-refresh-performance.md` | 与只读实测一致，明确尚未修复，git diff --check 通过；不修改产品代码或 Jenkins | 完整列表约 9.21 秒；36 次串行查询约 10.06 秒，ai-music-apitest 单任务约 6.8 秒且无安装包；记录包含 43,020 条产物与约 5.7 MB 的复核证据及后续验收，diff --check 通过 | 问题保留待修复；仅本地文档提交，不推送；当前白屏另做只读诊断 |

## 2026-10-20 远端合并交付

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| W3 | DONE | 将已验收的安装、网络恢复和弱网改动推送并快进合并到远端 main | `goal.md`, `specs/weak-network.md`, `progress.md`；当前分支已有提交及本地/远端分支引用 | 相关 Python/Swift 回归通过；无强推、无无关文件；远端 main 与功能分支提交一致；本地 main 快进且用户未提交文档保留 | 源代码 a70bb46 的 Python 217 项、Swift 89+1 项重新通过，diff --check 通过；构建/签名/真实弱网复用同源 W1/W2 证据。原子推送将远端 main 从 cce3065 快进至 01928bd，ls-remote 确认 main 与 codex/weak-network 一致；本地 main 已快进。用户文档 SHA-256 前后同为 3273ffb68135fb7c2bc633f667fc9cb3a2d4e0aea67bbe501e7bee0016a97a25 | 保留工作树和现有运行中的桌面；不发布安装包 |

## 2026-10-20 网络场景预设调整

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| W2 | DONE | 改为 2G/3G/4G/不限制，默认不限制 | `goal.md`, `specs/weak-network.md`, `progress.md`, `macos-native/Sources/AICaptureNativeApp/{WeakNetworkController,WeakNetworkView,AppCopy}.swift`, `macos-native/Tests/AICaptureNativeAppTests/WeakNetworkTests.swift`, `docs/desktop-user-guide.md` | Swift 测试覆盖默认不修改设备、三个预设应用、不限制调用恢复、失败/设备切换与已生效状态同步；构建签名、原生四档切换与实际规则验证、最终恢复不限制 | TDD RED 复现默认值/预设/恢复/同步不符后修复；7 项弱网回归、Swift 89+1 项分批通过；四档原生操作与设备 qdisc 一致；切换页面正确选回 4G；最终无 netem/IFB、API enabled=false、pending_restore=false；构建、运行后严格签名、diff 检查通过 | 仅本地提交，不推送；新版桌面已打开且保持不限制 |

## 2026-10-19 弱网模拟任务

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| W1 | DONE | 桌面弱网面板、设备限速和恢复机制及完整测试 | `goal.md`, `specs/weak-network.md`, `progress.md`, `capture_console/weak_network*.py`, `capture_console/app.py`, `tests/test_weak_network*.py`, `tests/fixtures/WeakNetworkProbe.java`, `scripts/qa_weak_network*.py`, `macos-native/Sources/AICaptureNativeApp/{WeakNetwork*,APIClient,AppCopy,CaptureView,RuntimeManager}.swift`, `macos-native/Tests/AICaptureNativeAppTests/{WeakNetworkTests,APIClientTests,RuntimeManagerTests}.swift`, `macos-native/scripts/build-app.sh`, `tests/test_native_app_packaging.py`, `docs/desktop-user-guide.md` | 单元/API/Swift 测试、真实上下行/延迟测量、抓包共存、恢复和桌面 UI 验收、构建签名通过；不影响其他设备/主机网络 | 217 项后端、Swift 分批 88+1 项通过；真实直连/SOCKS5 测量和 9 条 HTTP 200 响应通过；孤儿后端、崩溃重开和优雅退出恢复通过。原生验收发现缺资源包、焦点误改预设及 4 秒清理截断，均经 RED 回归修复。r7 原生冷启动、全部场景/无效输入/手动恢复/退出重开通过，设备规则和恢复记录清空，7001 退出释放；重开 build_id 正确、无活动抓包、严格签名通过 | 本地提交；不推送、不发布 |

W1 续验：r5 内嵌 Python + 包内后端通过隔离生命周期测试，清理 3.158 秒，异常重启恢复及运行后签名通过。二进制直接 cmp 因重签名不相同，改核对 Mach-O UUID 一致并验证严格签名。此前 Mac 锁屏，UI 验收未完成，不记为 DONE。

2026-10-20 UI 验收发现：r5 缺少 web/dist/index.html，实际桌面启动脚本拒绝启动后端（之前直启 uvicorn 的测试未覆盖）；弱网字段仅切换焦点也会把预设改成自定义。W1 保持 DOING，Scope Files 补充 `macos-native/scripts/build-app.sh`、`tests/test_native_app_packaging.py`；验收补充构建缺资源时不替换旧包、包内真实启动脚本冷启动、焦点切换保留预设。旧抓包已通过桌面正常停止并保留结果，未动登录与应用数据。

续验：以上两处已通过回归及原生操作；217 项 Python、88+1 项 Swift、缺资源保护和搬移后正式启动脚本通过。r6 桌面退出仍发现旧 4 秒清理窗口截断弱网恢复，设备尚有部分规则及恢复记录，不能判通过。继续修复有界退出等待，增加超过 4 秒的清理回归，再重复原生退出验收。npm audit 开发依赖报告 8 项，生产依赖 0 项；未扩大本任务修改依赖。

最终验收（2026-10-20）：延迟 5 秒清理回归在旧 4 秒窗口失败，调整为有界 15 秒后通过，超时退出与外部进程保护回归保持通过。r7 实际桌面应用弱网后 Command-Q，设备恢复默认 qdisc、系统 clsact 保留、IFB 与恢复记录清除，后端日志完整 shutdown、端口 7001 释放；重开界面“未启用弱网”，API enabled=false / pending_restore=false / active_session=null。最终 App 运行后严格签名、git diff --check 通过。界面与使用说明已验收，本次仅本地交付。

## 2026-05-12

- 读取了当前 README、FastAPI 后端入口、抓包脚本和核心测试。
- 确认当前项目已具备本机 Web 控制台、应用库、启动/停止抓包、接口详情和 cURL 导出能力。
- 确认当前 Web 服务重启后会清空页面里的抓包任务记录，保留应用库和原始文件。
- 创建 `task_plan.md`、`findings.md`、`progress.md`。
- 创建详细规划书：`docs/长期安卓抓包平台规划书.md`。
- 根据用户反馈调整规划边界：当前先做 Android，iOS 只预留入口，不进入本期实现。
- 对规划书进行了评审，发现 P0/P1 顺序、iOS 数据模型预留、测试保护登录态、敏感信息导出策略需要进一步收敛。
- 开始执行 P0 第一批稳定性改造。
- 新增 `capture_console/platforms.py`，统一 platform 校验、iOS 预留状态和 unsupported detail。
- 更新 `capture_console/store.py`，为 `apps` 和 `capture_sessions` 增加 `platform` 字段和迁移逻辑。
- 更新 `capture_console/app.py`，应用 payload 支持 platform，并在启动抓包前拒绝 iOS 预留应用。
- 更新 `capture_console/runner.py`，增加保留登录态模拟器检查和破坏性命令拒绝。
- 新增 `tests/test_console_api.py`，覆盖 iOS 预留应用不能启动抓包且不触碰 Runner。
- 扩展 `tests/test_console_core.py`，覆盖 platform 默认值、iOS 预留、破坏性命令拒绝、非保留模拟器配置失败。
- 更新 `web/src/main.jsx` 和 `web/src/styles.css`，新增“选择目标应用”区域，应用添加支持平台选择，启动抓包前明确选择目标 App。
- 更新 `capture_console/static/index.html`，让无 Vite 构建时的静态兜底页也支持平台添加、应用选择和 iOS 预留阻断。

## 验证

- 本次是规划文档输出，不涉及代码运行逻辑变更。
- 没有执行新的抓包任务。
- 已检查规划书章节并完成边界修订。
- `python3 -m unittest tests/test_console_core.py` 通过。
- `.venv-console/bin/python -m unittest tests/test_console_api.py` 通过。
- `PYTHONPATH=. .venv-console/bin/python -m py_compile capture_console/*.py` 通过。
- 已启动 `http://127.0.0.1:7001`，应用库中 MelodyCraft 已迁移出 `platform: android`。
- 已用临时 iOS 预留应用做 smoke test：`/api/captures/start` 返回 501，随后已删除临时条目。
- `npm run build` 通过，已生成新的 `web/dist`。
- 已在浏览器重新加载 `http://127.0.0.1:7001/`，确认页面包含“添加应用”“选择目标应用”、平台下拉和默认模式启动入口。
- 已执行页面验收：通过浏览器新增临时 Android 应用和 iOS 预留应用，验证应用库展示、目标应用选择、Android 启动按钮可用、iOS 启动按钮禁用。
- 验收结束后已删除临时应用记录，应用库恢复为 MelodyCraft。
- 将项目产品名统一为 `TraceDeck`，页面标题改为 `TraceDeck · Mobile Traffic Intelligence Console`，主视觉改为“移动端接口观测与取证工作台”。
- 同步更新 React 页面、静态兜底页、FastAPI 标题、README 和 Vite package 名称。
- 已在浏览器刷新 `http://127.0.0.1:7001/`，确认新品牌标题显示正确，旧的“长期安卓抓包控制台 / Android Capture Console”页面标题已移除。
- 尝试执行 TraceDeck + 保留模拟器端到端抓包验收，已启动 `Medium_Phone_API_36.1 / emulator-5554`。
- 修复后端健康检查：应用库已保存 Activity 时，不再因为 Android 自动 launcher 解析失败而误拦截抓包启动。
- 当前端到端验收暂停在模拟器锁屏：系统状态是 `RUNNING_LOCKED`，需要用户手动解锁后才能继续启动 App 和抓包。

## 2026-05-14

- 修复 `flutter-socks` 健康检查：Frida 不再依赖 `init.svc.frida_server`，改为检查 `frida-ps -H 127.0.0.1:27042`、adb forward 和进程权限。
- 修复 Frida 启动脚本：在 Google Play/rootAVD 这类 `adb root` 不可用的镜像上，自动使用 Magisk `su -c` 启动 root 权限的 `frida-server`。
- 修复多设备误连问题：`flutter_proxy_unpin_capture.py` 固定连接 `127.0.0.1:27042`，避免 `frida.get_usb_device()` 选到真实设备 `d265cb0a`。
- 已在 Magisk Superuser 中启用 `[SharedUID] Shell / com.android.shell` root 权限，解决 `frida.PermissionDeniedError`。
- 已重新启动 TraceDeck Web 服务和 MelodyCraft `flutter-socks` 抓包 session 21。
- 验证 session 21 正常：`exporter` 和 `frida hook` 均为 running，`runtime/captures/web-20260514-162532-MelodyCraft/candidates.tsv` 已产生业务接口。
- 已确认可抓到 `www.blockdance-test.xyz` 的 MelodyCraft 业务接口，包括 `song/featuresList`、`user/updateUserInfo`、`config/appLaunchActions`、`notification/hasUnreadNotifications` 等。
- 已验证接口详情和 cURL 导出可读；原始文件仍保留真实 headers/token，仅限本机可信环境使用。

## 2026-05-27

- 针对 Mac mini 服务器上模拟器 Google 登录和网络不可用问题，整理了网络链路修复计划。
- 新增计划文档：`docs/服务器模拟器网络修复计划.md`。
- 计划核心决策：区分 Maintenance Mode 和 Capture Mode，避免 Android `http_proxy` 与 `flutter-socks` 抓包链路冲突。
- 计划要求新增主机网络、代理网络、模拟器网络、Google 登录链路、抓包出口的分层准入检查。
- 根据“服务器上还有其他项目运行、端口可能已被占用”的约束，重写计划为 V2。
- V2 计划将 Server Isolation 作为 P0：先做端口/进程/launchd/代理/设备归属预检，再做网络模式切换。
- V2 明确禁止按端口无差别 kill，所有停止操作必须基于项目 pidfile、screen、launchd label 或设备池归属。

## 2026-05-28

- 开始对服务器部署地址 `http://192.168.77.150:7001` 做全量验证，范围限定为 AI 抓包工具。
- 浏览器打开服务器页面成功，首页显示 `AI抓包工具`，当前设备在线，常驻设备 `2/2` 在线。
- 页面初始化状态显示环境、设备、Frida 已通过，但仍停留在抓包冒烟测试阶段。
- 页面顶部 `mitmweb` 链接仍指向 `http://127.0.0.1:9091/?token=android-capture`，远程访问场景下不可直接打开。
- 只读 API 验证完成：首页、状态、环境检查、设备、应用、版本、已安装应用、历史会话、资源接口均返回 200。
- `/api/system/preflight` 返回 `ok=false`，阻塞项是 `19097/19098` 被 `emulator-preview/ws-scrcpy` 占用；按服务器隔离约束未处理这些进程。
- `/api/system/network-check` 返回 `ok=false`，失败目标是 `https://www.google.com/generate_204` 超时。
- 临时 iOS 预留应用 CRUD 验证通过：可保存，启动抓包返回 501，删除后应用库恢复为 MelodyCraft 单条记录。
- 页面“启动抓包测试”执行完成，新建 session 16，抓包链路能启动并自动停止，但结果为 warning：30 秒内未捕获可解析接口，`flow_count=0`。
- 普通抓包启动/停止 API 验证完成，新建 session 17；运行中 `health=running`、9090 代理开放、exporter 和 Frida hook 均为 running；停止后回到 `health=idle`。
- session 16 导出接口可返回产物列表，包含 `all-flows.tsv`、`candidates.tsv`、`exporter.log`、`frida.log`、`summary.md` 等，但 flows 为空。
- `/api/devices/device-1/preview` 返回的模拟器预览地址可访问，预览页标题为 `Emulator Preview`，能看到 `Capture_AVD_01 / emulator-5554` 在线。
- 本地自动化验证完成：`tests/test_console_core.py`、`tests/test_console_api.py`、`tests/test_readiness.py`、`tests/test_exporter_timing.py` 共 81 个 unittest 通过。
- 本地前端构建完成：`npm --prefix web run build` 通过。
- 按用户要求启动 MelodyCraft APK 做完整抓包测试，新建 session 18：`/Users/jenkins/ai-capture-tool/shared/runtime/captures/web-20260528-183809-MelodyCraft`。
- session 18 运行期间 `health=running`、9090 代理监听、exporter 和 Frida hook 均为 running；结束后已停止并恢复 `health=idle`。
- 通过 adb 操作了登录页：点击 `Sign in with Google`、`Privacy Policy`、`Terms of Service`；Google 登录被取消，Privacy/Terms 被系统交给 Chrome 首次使用页，无法进入 App 登录后的业务页。
- session 18 捕获到 2 条候选业务接口，均为 `POST https://www.blockdance-test.xyz/aisong/portal/user/livestatus`，状态 200，request/response JSON 均可解析。
- session 18 导出验证通过：18 个文件，详情接口和 cURL 导出接口可读。
- 排查 Google 登录失败：在无抓包代理干扰、Android `http_proxy=null` 的直连状态下复现，点击 `Sign in with Google` 后进入 `com.google.android.gms/.auth.uiflows.minutemaid.MinuteMaidActivity`，页面停留在 `Checking info…` 超过 30 秒。
- Google 登录日志显示 `Auth ... 5004`，系统日志反复出现 `No network time available`；设备账号状态仍为 `Accounts: 0`。
- 服务器和模拟器到 Google 登录核心域名不可达：`accounts.google.com`、`oauth2.googleapis.com`、`www.googleapis.com`、`play.googleapis.com`、`android.clients.google.com` 的 HTTPS/TCP 或 ping 均失败；`connectivitycheck.gstatic.com` 和部分 `mtalk.google.com` 可达。
- Android 网络时间服务 `time.android.com` 从未成功同步，`mLastSuccessfulNtpServerUri=null`、`mTimeResult=null`。

## 2026-05-29

- 按用户要求验证服务器上的 7890 代理，范围限定为 AI 抓包工具和 `device-1 / emulator-5554`。
- 服务器本机 `127.0.0.1:7890` 可连接，进程监听在本机回环地址；通过该代理访问 `accounts.google.com` 返回 200，访问 `www.google.com/generate_204` 返回 204。
- 通过 AI 抓包工具 API 将 `device-1` 切到维护代理模式，Android `http_proxy` 已设置为 `10.0.2.2:7890`。
- 模拟器内到宿主机 7890 端口连通，点击 MelodyCraft 的 `Sign in with Google` 后，Google 登录流程从 `Checking info…` 进入 `Sign in - Google Accounts` 邮箱输入页。
- 当前没有输入 Google 账号；设备仍显示 `Accounts: 0`，`/api/devices/device-1/google-state` 为 `not_logged_in`。
- AI 抓包工具当前没有活跃抓包任务，`/api/status` 显示 `health=idle`、`active_session=null`；维护代理仍保留为 `10.0.2.2:7890`，便于用户手动完成 Google 登录。
- 用户完成 Google 登录后，`/api/devices/device-1/google-state` 返回 `ok=true`、`google_account_present=true`。
- 启动 MelodyCraft `flutter-socks` 抓包 session 19，输出目录为 `/Users/jenkins/ai-capture-tool/shared/runtime/captures/web-20260529-114342-MelodyCraft`。
- session 19 运行期间 `health=running`、9090 代理监听、exporter 和 Frida hook 均为 running；抓包模式下 Android `http_proxy` 按预期清为 `null`。
- MelodyCraft 成功进入登录后首页并产生业务流量，但页面出现系统 ANR 弹窗 `MelodyCraft isn't responding`。
- session 19 已停止并恢复 `health=idle`、`active_session=null`；停止输出显示 exporter、Frida hook、mitmweb 代理和 Web 监听均已停止。
- session 19 捕获到 78 条候选流量，其中 60 条 HTTP 200，47 条包含 JSON 请求，44 条包含 JSON 响应；代表接口包括 `user/updateUserInfo`、`song/play`、`user/livestatus`、`notification/hasUnreadNotifications`、`music/get_running_tasks`。
- session 19 导出验证通过：`/api/captures/19/export` 返回 346 个文件；抽查 `POST /aisong/portal/user/updateUserInfo` 的详情接口和 cURL 导出均可读。
- 测试收尾后仅对目标包执行 `am force-stop com.meta.inno.monopoly_sticker` 关闭 ANR 状态，未清数据、未卸载、未操作服务器其他项目。
- 已将 `device-1` 恢复到维护代理 `10.0.2.2:7890`，当前 Google 账号仍为已登录状态。
- 按用户反馈优化服务器模拟器预览页 `/Users/jenkins/emulator-preview`：降低默认推流档位为极速，参数调整为 1Mbps、15fps、420x936；流畅/高清档位也整体降码率和帧率。
- 优化预览页布局：将模拟器舞台高度从固定大尺寸改为视口内自适应，1440x900 下页面级 `scrollHeight` 从 993 降到 900，预览画面无需整页上下滚动即可完整显示。
- 仅覆盖并构建 `/Users/jenkins/emulator-preview/frontend/src/App.tsx` 和 `styles.css`，构建通过；原文件已备份到服务器 `/Users/jenkins/emulator-preview/backups/codex-preview-fit-20260529121004`。
- 按用户要求收敛预览页 AVD 列表：服务器 `/Users/jenkins/emulator-preview/server.mjs` 现在读取 `/Users/jenkins/ai-capture-tool/shared/config/devices.macmini.json`，只返回 `enabled=1` 的项目 AVD。
- 预览服务已重启；`/api/devices` 当前只返回 `Capture_AVD_01`、`Capture_AVD_02`、`Capture_AVD_03`，不再展示 Jenkins 账户下历史遗留的 Pixel/Medium/Small/Tablet/Fold AVD。
- 浏览器验证通过：在线设备页只显示 `Capture_AVD_01`；切到“可启动 AVD”只显示 `Capture_AVD_02` 和 `Capture_AVD_03`。
- 服务器原 `server.mjs` 已备份到 `/Users/jenkins/emulator-preview/backups/codex-avd-filter-20260529174830/server.mjs`；未删除任何历史 AVD。

## 2026-06-01

- 按用户要求重新启动服务器上的 MelodyCraft `flutter-socks` 抓包测试，新建 session 20，输出目录为 `/Users/jenkins/ai-capture-tool/shared/runtime/captures/web-20260601-103407-MelodyCraft`。
- session 20 运行期间抓包链路正常：`health=running`、9090 代理监听、exporter 和 Frida hook 均为 running，前台应用为 `com.meta.inno.monopoly_sticker.MainActivity`。
- session 20 已停止并恢复 `health=idle`、`active_session=null`；9090 代理、exporter、Frida hook 均已停止。
- session 20 捕获 129 条候选流量，其中 90 条 HTTP 200、120 条包含 JSON 请求、93 条包含 JSON 响应。
- 代表接口 `POST https://www.blockdance-test.xyz/aisong/portal/config/upgrade` 的详情接口返回 200，cURL 导出返回 200 且内容以 `curl` 开头。
- session 20 导出接口验证通过：`/api/captures/20/export` 返回 610 个文件。
- 测试收尾后已将 `device-1` 恢复到维护代理 `10.0.2.2:7890`，Google Play 可用且 Google 账号仍为已登录状态。
- 复查预览服务 AVD 列表仍只返回 `Capture_AVD_01`、`Capture_AVD_02`、`Capture_AVD_03`。
- 按用户要求尝试抓取 MelodyCraft 流量表，新建 session 21，输出目录为 `/Users/jenkins/ai-capture-tool/shared/runtime/captures/web-20260601-113616-MelodyCraft`。
- session 21 中通过目标模拟器执行轻量滑动和点击触发；共捕获 49 条候选流量，其中 35 条 HTTP 200、40 条 JSON 请求、32 条 JSON 响应。
- session 21 导出接口验证通过：`/api/captures/21/export` 返回 228 个文件；抽查 `GET /aisong/portal/reward/bannerDetailV2` 的详情接口和 cURL 导出均可读。
- 已生成本地流量表文件 `output/melody_session21_traffic_table.md`；测试收尾后 `device-1` 已恢复维护代理 `10.0.2.2:7890`。
- 按用户反馈优化服务器模拟器预览页顶部：移除 header 中间的状态胶囊标签 `在线 / 启动中 / Jenkins APK / ADB`，保留标题和右侧操作按钮。
- 已重新构建 `/Users/jenkins/emulator-preview/frontend`；当前页面加载新产物 `/assets/index-BfBq_2Uj.js` 和 `/assets/index-tuhzHDm4.css`，验证产物中已无 `health-strip`。

## 2026-06-05

- 用户确认新的重构方向选择“本机开箱工具”：别人 clone 当前项目后在本机运行 `./start_capture.sh`，通过本机页面完成设备和 App 配置。
- 用户明确本轮不处理服务器上的部署和预览服务，修改范围只限当前本机项目。
- 后续设计应把服务器/Mac mini/Jenkins 相关路径从主流程中移除或降级为非默认能力，但本轮不需要连接或修改服务器文件。
- 用户进一步澄清目标不是只给当前本机使用，而是要做成“单独的项目，所有人都可以下载使用”。后续范围需要覆盖项目命名、安装脚本、默认配置、首次向导、README、发布包、敏感历史数据清理和服务器部署降级。
- 已创建计划书：`docs/独立可下载项目重构计划书.md`。计划覆盖目标形态、非目标、当前问题、推荐架构、配置模型、设备模型、App 模型、重构阶段、测试计划、风险和完成标准。
- 已按 V2 计划实现 TraceDeck 独立可下载项目化改造：
  - 新增 `setup.sh`、`start.sh`、`config/local.example.json`、`release/package.sh` 和 `docs/legacy/README.md`。
  - 后端新增本机配置读取 `capture_console/local_config.py`、ADB 设备发现/端口分配 `capture_console/device_discovery.py`。
  - `CaptureStore` 默认不再种入固定设备池；新增 `upsert_device`，设备改为运行期发现后写入。
  - 新增 `/api/devices/discover` 和 `/api/apps/installed`，并让 `/api/status` 在空设备状态下返回 idle。
  - React 页面和静态兜底页移除 MelodyCraft、固定 AVD、服务器默认语境，新增“发现设备”和“读取当前设备已安装 App”入口。
  - README 改为外部用户快速开始：`./setup.sh`、`./start.sh`、打开 `http://127.0.0.1:7001`。
- 验证完成：
  - `npm --prefix web run build` 通过。
  - `python -m unittest discover tests` 通过，95 个测试 OK。
  - `./release/package.sh` 通过，生成 `release/TraceDeck-20260605-184159.tar.gz`。
  - 发布包清单包含 `setup.sh`、`start.sh`、`web/index.html`、`web/src/main.jsx`、`web/dist/index.html`、`config/local.example.json`。
  - 发布包排除项检查通过：未包含 `runtime/`、`.venv*`、`web/node_modules`、`config/local.json`。
  - 干净目录 smoke 通过：解压最新 release 后运行 `./setup.sh`，再用独立端口执行 `./start.sh`，`/api/status` 可访问，测试服务已停止且端口无遗留监听。

## 2026-06-08

- 继续收尾本机 TraceDeck 项目化改造。
- 发现旧 `.venv-console` 使用 Python 3.9.6，无法安装 `mitmproxy>=12`；新增 `scripts/console_python.sh`，统一 `setup.sh`、`scripts/start_web_services.sh`、`scripts/start_console.sh` 的 Python 选择和 venv 检查逻辑。
- 新逻辑要求 Python 3.12+；默认项目 venv 不兼容时会重建，避免继续复用低版本 venv。
- 停止旧 session 60：已通过 `/api/captures/stop?device_id=device-1` 停止 exporter、Frida hook、mitmweb，并标记 session 为 stopped。
- 重启本机 `http://127.0.0.1:7001` 到新版本，当前 `.venv-console` 为 Python 3.12.5。
- 修复 discovery 后旧 runtime 仍显示历史固定设备的问题：`/api/devices/discover` 现在会禁用本次未发现且无活跃 session 的旧设备。
- 修复所有设备被禁用时 `/api/status` 返回 409 的问题；现在无在线设备时返回 idle 空状态和用户可读提示。
- 验证完成：
  - `npm --prefix web run build` 通过。
  - `python -m unittest discover tests` 通过，98 个测试 OK。
  - 最新 release：`release/TraceDeck-20260608-143750.tar.gz`。
  - 包内包含 `scripts/console_python.sh`、`setup.sh`、`start.sh`、`web/dist/index.html`、`config/local.example.json`。
  - 发布包排除项检查通过：未包含 `runtime/`、`.venv*`、`web/node_modules`、`config/local.json`。
  - 干净目录 smoke 通过：解压最新 release 后运行 `./setup.sh` 和独立端口 `./start.sh`，`/api/status` 可访问，测试服务已停止且端口无遗留监听。

## 2026-06-10

- 按用户要求继续做 TraceDeck 本机独立项目的自主收尾验收。
- 修正文档：README 依赖说明统一为 Python 3.12+，新增 PyPI/npm 镜像和 `PIP_PROXY=` 代理排错说明。
- 页面验收发现 `web/index.html` 标题仍为 `AI抓包工具`；已改为 `TraceDeck` 并重新构建。
- 本机服务验收：
  - `./start.sh` 可启动 `http://127.0.0.1:7001`。
  - `/api/status`、`/api/setup/state`、`/api/devices/discover`、`/api/devices` 均可返回。
  - 无在线设备时 `/api/devices` 返回空列表，不进入异常状态。
- 启动本机 `Capture_AVD_02 / emulator-5554` 做通用设备验收：
  - `/api/devices/discover` 成功发现并写入 `device-1`。
  - `/api/apps/installed?device_id=device-1` 可读取当前设备用户安装 App。
- 完成非 MelodyCraft App 抓包验收：
  - 临时添加 `Chrome 验收临时应用`，包名 `com.android.chrome`，Activity `com.android.chrome/com.google.android.apps.chrome.Main`，模式 `system`。
  - `/api/apps/11/readiness?device_id=device-1` 返回 App 已安装且 Activity 可启动。
  - `/api/captures/start` 新建 session 61，输出目录 `runtime/captures/web-20260610-140451-Chrome`。
  - 抓包运行中 `health=running`、9090 代理监听、exporter running、Chrome 前台、Android `http_proxy=10.0.2.2:9090`。
  - 通过 Chrome 打开 `http://neverssl.com/online` 后，`/api/captures/61/flows` 捕获到 17 条 flow。
  - 抽查 `POST http://update.googleapis.com/service/update2/json` 的详情接口和 cURL 导出接口可访问；`/api/captures/61/export` 返回 70 个文件并包含 `summary.md`。
- 验收发现并修复 system 模式停止后的代理残留问题：
  - 复现：停止 session 61 后 mitmproxy 已退出，但 Android `http_proxy` 仍为 `10.0.2.2:9090`。
  - 修复：`/api/captures/stop`、`/api/captures/{session_id}/stop`、`/api/cleanup` 统一调用 `clear_android_proxy()`。
  - 新增回归测试 `test_stop_capture_clears_android_proxy` 和 `test_stop_capture_session_clears_android_proxy`。
  - 复测 session 62：启动 system 抓包后代理为 `10.0.2.2:9090`，停止后代理恢复为 `null`。
- 页面 DOM 验收确认：
  - 页面标题为 `TraceDeck`。
  - 页面无 `preview token` 登录入口。
  - Browser 截图接口本轮出现 CDP screenshot timeout；已用 DOM 指标完成页面可视化关键检查。
- 自动化验证完成：
  - `python -m unittest discover tests` 通过，101 个测试 OK。
  - `npm --prefix web run build` 通过。
  - `./release/package.sh` 通过，生成 `release/TraceDeck-20260610-141015.tar.gz`。
  - 最新 release SHA256：`fd7a9c8c5f351d60c043a73e096fb81aeca656d60b39ec44d24b9ed105f21a58`。
  - 发布包必需文件检查通过：`README.md`、`setup.sh`、`start.sh`、`requirements-console.txt`、`scripts/console_python.sh`、`scripts/start_web_services.sh`、`web/dist/index.html`、`config/local.example.json` 均存在。
  - 发布包排除项检查通过：未包含 `runtime/`、`.venv*`、`web/node_modules`、`config/local.json`、抓包结果或上传文件。
  - 干净目录 smoke 通过：解压最新 release 后运行 `./setup.sh`，再用独立端口 `17071` 执行 `./start.sh`，`/api/status` 和 `/api/devices` 可访问，测试服务已停止。

### 本机卸载重装验收

- 按用户要求在本机执行“卸载已安装产物后重装”流程，仅清理当前项目可再生内容：`.venv-console`、`.venv-console312`、`web/node_modules`、`web/dist`、`runtime`、`config/local.json`，未删除源码、未操作服务器。
- 重新执行 `./setup.sh` 成功：
  - 重新生成 `config/local.json`。
  - 重建 `.venv-console` 并安装 `requirements-console.txt`。
  - 重新执行 `npm install` 和 `npm run build`，Vite 构建通过。
- 重新执行 `OPEN_WEB=0 ./start.sh` 成功，服务监听 `http://127.0.0.1:7001`。
- API 与页面验收：
  - `/api/status` 返回 idle 空设备状态。
  - `/api/setup/state` 返回环境检查通过、`app_count=0`。
  - 浏览器实际打开 `http://127.0.0.1:7001`，页面标题为 `TraceDeck`，无 token 登录入口。
- 启动本机 `Capture_AVD_02 / emulator-5554` 后，页面点击“发现设备”可显示 `device-1 · Android Emulator emulator-5554`。

## 2026-08-06

- 用户明确最终目标是“完整桌面端”，并补充要求：其他用户下载到自己 Mac 后也能本机安装和使用。
- 确认 Tauri/WebView 方案不作为最终桌面端方向；保留现有 Web/Tauri 能力作为过渡和调试入口。
- 新增原生 SwiftUI 可分发版设计文档：`docs/superpowers/specs/2026-08-06-macos-native-distributable-design.md`。
- 新增原生 SwiftUI 可分发版实施计划：`docs/superpowers/plans/2026-08-06-macos-native-distributable.md`。
- 创建 `macos-native/` SwiftUI 原生桌面端骨架：
  - `Package.swift`
  - `AICaptureNativeApp.swift`
  - `AppState.swift`
  - `ContentView.swift`
  - `README.md`
- 第一阶段只实现原生窗口、原生侧边栏和运行时状态占位，不接抓包业务逻辑。
- 第二阶段接入本机后端运行时检测：
  - 新增 `RuntimeManager.swift`，解析 `~/Library/Application Support/AI抓包工具/runtime-native/` 并检测 `http://127.0.0.1:7001/api/status`。
  - `AppState` 增加运行目录、最近检测时间和 `refreshRuntimeStatus()`。
  - 原生 App 启动和点击“重新检测后端”时会自动刷新后端状态。
  - 后端检测使用禁用代理的 `URLSessionConfiguration.ephemeral`，避免本机 `http_proxy/ALL_PROXY` 把 `127.0.0.1:7001` 错误转发到代理。
  - 新增 `macos-native/scripts/build-app.sh` 生成最小 `.app`，解决 SwiftPM 裸可执行文件无法稳定打开 SwiftUI 窗口的问题。
- 第三阶段接入原生设备与应用列表：
  - 新增 `Models.swift`，兼容解析 `/api/devices` 和 `/api/apps` 的现有 JSON。
  - 新增 `APIClient.swift`，统一禁用代理、设置超时并封装设备/应用读取。
  - 新增 `DeviceAppView.swift`，原生展示设备池、应用库和测试包/生产包分组。
  - 默认入口调整为“设备与应用”，减少用户打开后还要手动找设备列表的步骤。
- 第四阶段开始接入原生抓包控制：
  - `APIClient` 新增 `prepareFrida`、`launchApp`、`startCapture`、`stopCapture`。
  - `AppState` 新增选中设备、选中应用、抓包动作状态和当前 session 记录。
  - 新增 `CaptureView.swift`，提供“启动 Frida / 打开应用 / 一键开始抓包 / 停止抓包”原生按钮。
  - 当前已完成代码接入和页面展示，真实抓包启动/停止验收尚未完成。
- 第五阶段开始接入原生接口分析：
  - `APIClient` 新增 flow list/detail/cURL 读取。
  - `Models.swift` 新增 `FlowSummary`、`FlowDetail` 和通用 `JSONValue`。
  - `AppState` 新增 active session flows、选中 flow、详情和 cURL 状态。
  - 新增 `FlowViews.swift`，支持 active session 下每 2 秒轮询，点击接口后展示 Request、Response 和 cURL。
  - 当前没有 active session，真实 Request/Response 数据验收尚未完成。
- 修复本机启动脚本代理问题：`scripts/start_web_services.sh` 的健康检查改用 `curl --noproxy '*'`，避免用户本机设置 `http_proxy/ALL_PROXY` 时误判后端不可用。

## 验证

- 本机环境确认：Xcode 26.2，Swift 6.2.3。
- `cd macos-native && swift build` 通过，生成原生可执行目标 `AI抓包工具`。
- `cd macos-native && ./scripts/build-app.sh` 通过，生成 `macos-native/build/AI抓包工具.app`。
- 实际打开 `.app` 通过：进程保持运行，原生窗口显示“内部服务已就绪：http://127.0.0.1:7001”。
- 发现并规避本机代理干扰：普通 `curl` 因 `ALL_PROXY/http_proxy=http://127.0.0.1:7897` 返回 502；`curl --noproxy '*' http://127.0.0.1:7001/api/status` 返回 200，原生检测已按直连处理。
- 原生设备/应用页验收通过：
  - `/api/apps` 返回 2 个应用，原生页面显示测试包应用卡片。
  - `/api/devices` 当前约 17 秒返回，原生页面异步加载后显示 3 台设备。
  - 实际打开 `.app` 后截图确认“设备池 3 台 / 应用库 2 个”已显示。
- 原生抓包页编译与展示通过：实际打开 `.app` 可看到“启动 Frida / 打开应用 / 一键开始抓包 / 停止抓包”按钮。
- 原生接口分析页编译通过；空 active session 状态可展示“先启动抓包”的提示。
- `OPEN_WEB=0 CONSOLE_SKIP_INSTALL=1 ./start.sh` 通过，确认健康检查在代理环境下不再超时。
- 通用 App 抓包复测：
  - 临时添加 `Chrome reinstall QA`，包名 `com.android.chrome`，Activity `com.android.chrome/com.google.android.apps.chrome.Main`，模式 `system`。
  - readiness 显示模拟器在线、App 已安装、Activity 可启动、Chrome 在前台。
  - 启动抓包后 `health=running`、9090/9091 监听、Android `http_proxy=10.0.2.2:9090`。
  - Chrome 访问 `http://neverssl.com/online` 后，session 1 捕获 13 条 flow；抽查 `GET http://edgedl.me.gvt1.com/...crx3` 的详情和 cURL 导出成功。
  - 停止抓包后 session 标记 stopped，9090/9091 关闭，Android 代理恢复为 `null`。
- 收尾清理：
  - 删除临时 Chrome App 记录，`/api/apps` 回到空列表。
  - 关闭测试模拟器，`adb devices` 为空，无 `Capture_AVD_02` 相关 emulator/qemu 进程残留。
  - 本机 TraceDeck 服务保留运行在 `127.0.0.1:7001`，抓包端口无监听。
- 回归验证：
  - `./.venv-console/bin/python -m unittest discover tests` 通过，101 个测试 OK。
  - `npm --prefix web run build` 通过。

### 抓包模式真实矩阵测试

- 按用户要求继续真实测试“是否存在通用抓包模式”和“不可用时如何切换”。
- 测试环境：
  - 本机 TraceDeck：`http://127.0.0.1:7001`。
  - 模拟器：`Capture_AVD_02 / emulator-5554`。
  - Frida 准入：`/api/devices/device-1/prepare-frida` 返回 ok，`frida-ps reachable on 127.0.0.1:27042`。
- 矩阵结果：
  - `Chrome/system`：启动成功，捕获 4 条 flow，包含 `neverssl.com /online`；停止后 Android 代理恢复为 `null`。
  - `MelodyCraft/system`：启动成功但 15 秒内捕获 0 条 flow，说明“启动成功”不能等同于“模式适配”。
  - 页面轮询开启时，`Chrome/flutter-socks` 和 `MelodyCraft/flutter-socks` 初次均返回 500。
- 500 根因：
  - 后端日志显示 `sqlite3.IntegrityError: UNIQUE constraint failed: capture_sessions.device_id`。
  - 根因是启动抓包创建 `starting` session 后，页面轮询 `/api/status`、`/api/devices` 会触发 `reconcile_active_session()`，把启动中的 session 改写为 stopped 或恢复其它运行态，和启动请求自身的 `starting -> running` 状态迁移竞争。
- 修复：
  - `reconcile_active_session()` 遇到 `status == "starting"` 的 active session 时不再改写，交给启动请求或显式停止/清理收尾。
  - 新增回归测试 `test_reconcile_leaves_starting_session_untouched_during_capture_start`，先复现失败，再修复通过。
  - 额外补充 Store 层状态迁移测试 `test_store_promotes_starting_session_to_running_without_unique_conflict`。
- 修复后真实复测：
  - 浏览器重新打开 TraceDeck 页面并保持轮询。
  - `MelodyCraft/flutter-socks` 启动成功，session 9 running。
  - 操作 App 后捕获 1 条 200 接口：`POST www.blockdance-test.xyz /aisong/portal/user/livestatus`。
  - 停止后 Android 代理恢复为 `null`。
  - 停止页面轮询后，`Chrome/flutter-socks` 也可启动并捕获 `GET neverssl.com /online`。
- 当前结论：
  - 没有单一模式适配所有 App。
  - `system` 对 Chrome 这类遵守系统代理的应用有效。
  - `flutter-socks` 对 MelodyCraft 这类 system 无流量的应用有效。
  - 后续应实现 `auto` 策略：优先推荐最近成功模式，否则先 system，再 fallback 到 flutter-socks，并把“启动成功但无流量”标记为需要切换模式的 warning。
- 回归验证：
  - `./.venv-console/bin/python -m unittest discover tests` 通过，103 个测试 OK。
  - `npm --prefix web run build` 通过。
- 收尾：
  - 临时 Matrix/Retry App 记录已删除，`/api/apps` 为空。
  - 测试模拟器已关闭，`adb devices` 为空。
  - 9090/9091 无监听，7001 主服务保留运行。

### auto 抓包模式实现与验收

- 已实现通用 `auto` 抓包策略：
  - 新建 App 默认 `default_mode=auto`。
  - Store 允许 App 默认模式为 `auto/system/flutter-socks`，session 仍只允许真实底层模式 `system/flutter-socks`。
  - App 新增 `last_success_mode`，停止成功后记录真实成功模式。
  - `auto` 候选顺序为：上次成功模式 -> App 默认底层模式 -> `system` -> `flutter-socks`，自动去重。
- 启动抓包接口：
  - `/api/captures/start` 支持 `mode=auto`。
  - 返回 `requested_mode` 和 `mode_attempts`，UI 可展示 `auto -> system/flutter-socks`。
  - 若某个候选模式健康检查、网络切换或启动失败，会停止临时状态、清理 Android 代理后继续尝试下一个候选。
- 冒烟校验接口：
  - `/api/apps/{app_id}/validate-capture` 支持 auto fallback。
  - 某个候选模式 30 秒内无 JSON 请求/响应时，标记 `reason=no_json`，停止临时抓包、清理代理，再尝试下一个模式。
  - 所有模式都无 JSON 时返回 warning，不误标成功。
- 前端更新：
  - 主按钮改为“自动抓包”。
  - 应用表单和静态兜底页新增 `auto（自动选择）`。
  - 接口分析区新增模式尝试摘要，显示 auto 实际落到哪个模式及每个候选的状态。
- 文档更新：
  - README 首次抓包流程改为默认使用 `auto`。
  - README 补充 auto 策略、成功模式记忆和自动清理说明。
- 自动化验证：
  - 目标测试通过：`test_start_capture_auto_falls_back_to_flutter_socks_when_system_is_not_ready`、`test_validate_capture_auto_falls_back_to_flutter_socks`、`test_store_allows_auto_default_mode_and_records_last_success_mode`。
  - 全量 Python 测试通过：`./.venv-console/bin/python -m unittest discover tests`，106 个测试 OK。
  - 前端构建通过：`npm --prefix web run build`。
- 页面与 API 验收：
  - 重启本地服务，入口为 `http://127.0.0.1:7001`。
  - Browser 实际打开页面，首屏为 `TraceDeck` 通用入口，空设备状态正常，无固定 Melody/Jenkins/服务器语境。
  - 启动 `Capture_AVD_02 / emulator-5554` 后，页面点击“发现设备”可显示 `device-1 · Android Emulator emulator-5554`。
- 真实 App 验收：
  - 非 Melody：临时添加 `Chrome Smoke`，默认 `auto`，启动后实际选择 `system`；Chrome 访问 `http://example.com/` 后 session 10 捕获候选 flow，详情接口和 cURL 导出成功；停止后 Android 代理恢复为 `null`，9090/9091 无监听，App 记录 `last_success_mode=system`。
  - Melody：临时添加 `Melody Smoke`，默认 `auto`，执行冒烟校验；`system` 30 秒无 JSON 后自动切换 `flutter-socks`，第二轮无人操作仍无 JSON，最终返回 warning 和完整 `mode_attempts`；校验结束后 Android 代理为 `null`，9090/9091 无监听，抓包进程无残留。
- 发布包验收：
  - `./release/package.sh` 通过，生成 `release/TraceDeck-20260611-162421.tar.gz`。
  - tar 内容抽查通过：包含 `README.md`、`setup.sh`、`start.sh`、`requirements-console.txt`、`web/dist/index.html`、`config/local.example.json`。
  - tar 排除项抽查通过：未发现 `runtime/`、`.venv*`、`web/node_modules`、`config/local.json`、抓包结果或本机数据库。
- 收尾：
  - 临时 `Chrome Smoke` / `Melody Smoke` App 记录已删除，`/api/apps` 回到空列表。
  - 测试模拟器已关闭，`adb devices` 为空。
- `127.0.0.1:7001` 本地服务保留运行。

## 2026-08-07 桌面端完整功能验收任务池

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | DONE | 建立验收基线和矩阵 | `goal.md`, `specs/functional-acceptance.md`, `task_plan.md`, `findings.md`, `progress.md` | 范围、边界、命令和真实链路均可追踪 | App 内嵌后端运行；Doctor 依赖通过；Google Play 镜像通过；项目端口无冲突；目标 AVD 按需关闭；现有 5558 未被选中 | 无 |
| A2 | DONE | 自动化与构建验收 | `tests/**`, `web/**`, `macos-native/**`, `release/**` | 后端测试、Web 构建、Swift 构建、发行打包均成功且 App 可分发 | 完成整包签名、发布/公证门禁、253 MB 自包含 App、受限 PATH HTTP smoke、正常 AppKit 退出资源清理 | 正式公证最终通过仍需公司 Developer ID 外部凭据 |
| R1 | DONE | 修复完整 App bundle 签名 | `macos-native/scripts/build-app.sh`, `tests/test_native_app_packaging.py` | 真实构建后 `codesign --verify --deep --strict` 返回 0 | focused test 1/1 通过；codesign 报告 valid on disk | 无 |
| R2 | DONE | 增加开发/正式发布模式 | `release/package.sh`, `tests/test_native_app_packaging.py` | 开发 zip 明确标记；正式模式缺凭据时构建前失败 | `python -m unittest -v tests.test_native_app_packaging` 3/3 通过；开发 ZIP 解压后整包签名仍有效 | 无 |
| R3 | DONE | 增加 notarization 边界 | `release/notarize-app.sh`, `release/package.sh`, `tests/test_native_app_packaging.py` | notary/stapler/spctl 门禁存在且缺 profile 时明确失败 | 聚焦测试 4/4 通过；正式 ZIP 只在 notarytool/stapler/spctl 全部成功后产生 | 真实 Apple 公证需导入公司 Developer ID 和 notary profile |
| R4 | DONE | 文档与发布回归 | `README.md`, `macos-native/README.md`, `tests/test_console_core.py` | 全量测试、构建、开发归档通过 | Python 132/132、Web build、Swift build、codesign、开发 ZIP/TAR 实物检查均通过；源码 TAR 隐私检查 538 项通过 | 无 |
| B1 | DONE | 构建并内嵌可重定位 Python 运行时 | `macos-native/scripts/build-runtime.sh`, `macos-native/scripts/build-app.sh`, `release/package.sh`, `tests/**` | App 内含 Python/uvicorn/mitmweb/frida wrappers，复制后仍可导入依赖 | 真实 App 复制后 `import fastapi,frida,mitmproxy,uvicorn` 通过；CLI 版本校验通过；运行时 248 MB，无绝对软链 | 无 |
| B2 | DONE | 无 venv/npm 启动内嵌后端 | `scripts/start_console.sh`, `macos-native/Sources/AICaptureNativeApp/RuntimeManager.swift`, `tests/**` | 限制 PATH 下 `/api/status` 返回 200，不调用 pip/npm | 复制 App 后仅使用 runtime bin + `/usr/bin:/bin` 启动成功，HTTP 200，禁止 venv 未创建；Swift build 通过 | 无 |
| B3 | DONE | 收敛桌面运行时 Doctor 依赖 | `capture_console/runner.py`, `scripts/start_frida_server.sh`, `tests/**` | Node/npm/xz 不再是桌面阻塞，Android SDK 仍强制校验 | 单元测试 3/3 通过；内嵌后端 `/api/system/env-check` 真实验证 runtime 路径且无 node/npm/xz | 无 |
| B4 | DONE | 托管并清理后端子进程 | `macos-native/Sources/AICaptureNativeApp/RuntimeManager.swift`, `macos-native/Sources/AICaptureNativeApp/AICaptureNativeApp.swift`, `macos-native/Tests/**` | 正常退出后无孤儿 uvicorn，不终止外部后端 | `swift test` 2/2 通过：自有进程退出并删 PID，外部进程不受影响 | 补真实 AppKit 退出验收 |
| A3 | DONE | 桌面端和设备准入验收 | `capture_console/**`, `macos-native/**`, `scripts/**`, `tests/**` | UI、Doctor、Google Play、网络、Frida 与拦截符合规格 | 桌面端在全新 `AI_Capture_Clean_QA3_20260810 / emulator-5564` 上一键准备通过；网络、Google Play、Magisk root、Frida 17.17.0 均正常；140 项 Python 回归通过 | 无 |
| A4 | DONE | Jenkins/APK/抓包闭环验收 | `capture_console/**`, `macos-native/**`, `scripts/**`, `tools/httptoolkit-frida/**`, `tests/**` | Jenkins、安装、App、session、flow、详情、停止清理形成闭环 | 全新 `AI_Capture_Clean_QA3_20260810 / emulator-5564` 仅通过原生桌面端完成 Jenkins `glp-1-tracker_158.apk` 复用安装、Session #4、4 条 `POST 200` 业务流量、Request/Response/cURL 详情与停止清理；退出后目标模拟器和 `7001/9140/9141/27542` 全释放；Python 157 项、Web build、Swift 5 项、App 深度签名均通过 | 无 |
| A5 | DONE | 分发包与最终复测 | `release/**`, `README.md` | 发布边界通过，全量回归无失败，输出残余风险 | 生成 96 MB `AI-Capture-Desktop-20260810-desktop-e2e-development-arm64.zip` 与源码归档；SHA-256、解压后深度签名、内嵌后端启动/退出和隐私边界均通过；Python 157 项、Web 44 项/build、Swift 5 项、生产依赖 audit 0 漏洞 | 残余：正式对外包仍需公司 Developer ID + Apple notarization；真实第二台全新 Mac 尚未实装；最终检查时 Jenkins LAN 临时超时（本轮此前 27 个任务读取与安装已通过） |
| A6 | DONE | 六应用桌面端启动抓包兼容性复测 | `findings.md`, `progress.md` | 仅通过原生桌面端依次安装/启动目标 Jenkins 包、创建抓包任务、核验接口详情并停止任务；对未通过项保留可复现证据 | GLP、BiteCal、WakeQuest 捕获到 `POST 200` 且 Response JSON 可读；StickerHub、PokeHub 抓包链路启动但 0 flow；Melody 因同包名已安装版本更高被降级保护拦截。Session #5-#9 均已停止，9140/9141 无监听 | PokeHub/StickerHub 需人工通过权限或业务页面后复测；Melody 需独立干净设备或明确允许卸载/降级安装 |
| A7 | DONE | 生成并接入 macOS “数据包透镜”应用图标 | `macos-native/Resources/AppIcon.png`, `macos-native/scripts/build-app.sh`, `tests/test_native_app_packaging.py`, `progress.md` | 生成 1024px 主图；构建产出有效 `AppIcon.icns`；Info.plist 正确引用；严格签名测试通过；Dock/Finder 实机显示新图标 | 1024px 透明源图通过尺寸/Alpha 契约；原生打包测试 7/7 通过；最终 ICNS 1,164,279 bytes 且含 10 个标准尺寸；`CFBundleIconFile=AppIcon`；`codesign --verify --deep --strict` 通过；最终 `.app` 实际启动正常，Finder 实机显示数据包透镜图标，运行中的最终 bundle 由 `NSRunningApplication` 成功加载 32x32 Dock 图标资源 | 无 |
| L1 | DONE | 实现按设备隔离的 Logcat 服务与 API | `capture_console/logcat.py`, `capture_console/app.py`, `capture_console/runner.py`, `tests/test_logcat_service.py`, `tests/test_console_api.py`, `progress.md` | 应用/系统/崩溃命令正确；增量 cursor、有界缓冲、应用 PID 重连和 30 秒回收通过自动化测试；API 错误为明确 4xx | TDD 红绿链路完成；`env -u CAPTURE_DEVICES_CONFIG -u CAPTURE_RUNTIME_DIR python -m unittest discover -q tests`：180 tests OK；`py_compile` 通过；OpenAPI 四个 Logcat 路由校验通过 | 下一轮领取 L2，接入原生桌面“日志”Tab |
| L2 | DONE | 实现原生桌面“日志”Tab | `macos-native/Sources/AICaptureNativeApp/ContentView.swift`, `macos-native/Sources/AICaptureNativeApp/LogsView.swift`, `macos-native/Sources/AICaptureNativeApp/LogcatController.swift`, `macos-native/Sources/AICaptureNativeApp/APIClient.swift`, `macos-native/Sources/AICaptureNativeApp/Models.swift`, `macos-native/Tests/AICaptureNativeAppTests/LogcatControllerTests.swift`, `macos-native/Tests/AICaptureNativeAppTests/APIClientTests.swift`, `progress.md` | 三类日志可切换；应用日志自动启动；暂停/继续/清空/搜索/级别过滤/自动滚动可用；Swift 测试通过 | API 与 controller 均完成 TDD 红绿验证；`swift test --package-path macos-native` 14/14 通过；真实 `.app` 构建及 `codesign --verify --deep --strict` 通过；LaunchServices 实际启动后 `/api/status`=200，辅助功能树确认“日志”Tab、三来源控制台、本机敏感信息提示和离线 409 友好状态均已渲染 | 下一轮领取 L3，在真实模拟器完成三类日志、PID 重连、资源回收与最终打包回归 |
| L3 | DONE | 完成 Logcat 桌面闭环验收与打包 | `capture_console/app.py`, `macos-native/**`, `tests/**`, `progress.md` | 真实模拟器三类日志验收；App 重启自动换 PID；页面离开和设备释放无残留进程；Python 全量、Swift、最终 App 构建通过 | 原生桌面端在 `device-1 / emulator-5564` 启动 Stickerhub 后，应用日志、系统日志、崩溃日志分别产生唯一 `adb logcat --pid 5965`、`adb logcat -v threadtime`、`adb logcat -b crash` 子进程并返回真实数据；应用 PID 从 5075 变为 5965 时状态自动经过 `waiting_app` 回到 `streaming`，无重复进程；暂停、继续、清空实机可用；离开日志页 35 秒后 API 回到 `stopped` 且无子进程，设备释放后日志停止、模拟器退出且 `adb devices` 为空；Python 180/180、Swift 14/14、最终 App 构建、Info.plist、深度签名和重启后 3 秒内 `/api/status`=200 全部通过 | 无 |
| L4 | DONE | 补齐桌面端使用文档并发布功能分支 | `.gitignore`, `README.md`, `macos-native/README.md`, `docs/desktop-user-guide.md`, `specs/functional-acceptance.md`, `task_plan.md`, `progress.md` 及已完成实现变更 | 普通用户、开发和排错说明与当前实现一致；提交不含凭据、运行数据、APK、抓包结果或临时产物；全量验证通过后提交并推送 | 新增普通用户完整指南并同步源码构建、签名发布、Google 登录策略和验收状态；文档链接/代码块/占位符检查通过，暂存内容无凭据、APK、数据库、抓包结果或本机运行目录；Python 180/180、Swift 14/14、Web build、生产依赖 audit 0、开发 ZIP/TAR SHA-256、深度签名、解压启动与正常退出清理均通过；功能提交 `96181d8` 已推送到 `origin/codex/desktop-one-click-ready` | 创建 PR 并评审后合并到 `main` |
| F1 | DONE | 实现前台 App 解析与动态登记 API | `capture_console/foreground.py`, `capture_console/runner.py`, `capture_console/app.py`, `tests/test_foreground_target.py`, `tests/test_console_api.py`, `progress.md` | 解析三类 resumed component；系统界面不登记；未知已安装 App 幂等创建；已有 App 元数据不被覆盖；设备异常返回稳定状态；目标测试通过 | TDD RED 先确认模块/API 缺失导致 4 项失败；实现后 6 项目标测试通过；隔离本机设备配置后 `tests.test_console_api + tests.test_foreground_target` 共 79 项通过；`py_compile` 和 `git diff --check` 通过 | 领取 F2 |
| F2 | DONE | 原生桌面端改为前台目标驱动 | `macos-native/Sources/AICaptureNativeApp/APIClient.swift`, `macos-native/Sources/AICaptureNativeApp/Models.swift`, `macos-native/Sources/AICaptureNativeApp/AppState.swift`, `macos-native/Sources/AICaptureNativeApp/CaptureView.swift`, `macos-native/Tests/AICaptureNativeAppTests/APIClientTests.swift`, `macos-native/Tests/AICaptureNativeAppTests/ForegroundTargetTests.swift`, `progress.md` | 每 2 秒轻量检测；包变化才 resolve；目标状态控制抓包按钮；Session 不匹配时阻止切换；Swift 测试通过 | TDD RED 确认模型、API 和状态字段缺失；3 项目标测试通过；Swift 全量 20/20 通过；真实 App 构建并通过 `codesign --verify --deep --strict` | 领取 F3 |
| F3 | DONE | 增加本地 APK 安装入口并解耦 Jenkins 目标 | `macos-native/Sources/AICaptureNativeApp/APIClient.swift`, `macos-native/Sources/AICaptureNativeApp/AppState.swift`, `macos-native/Sources/AICaptureNativeApp/DeviceAppView.swift`, `macos-native/Sources/AICaptureNativeApp/CaptureView.swift`, `macos-native/Tests/AICaptureNativeAppTests/APIClientTests.swift`, `macos-native/Tests/AICaptureNativeAppTests/LocalAPKInstallTests.swift`, `progress.md` | 本地 APK 可安装到所选在线设备；Jenkins 仅负责安装；两种来源安装后都以前台 App 为目标；Swift 测试通过 | TDD RED 确认本地安装 API、状态和安装后目标重置缺失；实现本地 APK 文件选择与上传，Jenkins 安装不再绑定抓包目标；Swift 全量 24/24 通过；真实 `.app` 构建和 `codesign --verify --deep --strict` 通过；`git diff --check` 通过 | 领取 F4 |
| F4 | DONE | 完成动态目标抓包闭环与文档回归 | `README.md`, `docs/desktop-user-guide.md`, `specs/functional-acceptance.md`, `tests/**`, `macos-native/**`, `progress.md` | 外部安装和 Jenkins 安装各完成一次真实识别；抓包状态从 waiting_traffic 变为 capturable；停止清理通过；Python 全量、Swift、Web build、App build 通过 | 外部安装 `ApiDemos-debug.apk` 后 2 秒内自动登记 `io.appium.android.apis / production / auto`；桌面端安装 Jenkins `PokeHub #531` 和 `glp-1-tracker #164` 后均无需目标选择即可识别前台 App；修复 Frida 未启动时按钮死锁及停止后陈旧 `capturable` 状态；GLP Session #21 从 waiting_traffic 进入 capturable，捕获 4 条 `POST 200`，Request/Response/cURL 可读；停止后 Session=stopped、9140/9141 释放、exporter/hook=0、Android proxy=null，冷启动后同一 App 可再次抓包；Python 186/186、Swift 26/26、Web build、最终 App 构建、Info.plist 与深度签名均通过 | 无 |
| F5 | DONE | 支持清除当前接口并保持实时续抓 | `macos-native/Sources/AICaptureNativeApp/AppState.swift`, `macos-native/Sources/AICaptureNativeApp/FlowViews.swift`, `macos-native/Tests/AICaptureNativeAppTests/FlowListPresentationTests.swift`, `progress.md` | 点击清除后仅隐藏当前 Session 已显示接口，不停止抓包、不删除原始文件；后续新接口自动出现；Swift、Python、App 构建和签名验证通过 | TDD 覆盖清除基线、实时续抓、停止重置以及列表/详情慢响应竞态；真实 Session #4 从 130 条清为 0 条，模拟器继续操作后自动出现 5 条新接口及 200 响应；Swift 35/35、Python 197/197、最终 App 构建、深度签名和 `git diff --check` 均通过 | 无 |

## 2026-08-21 桌面端交互与精准文案 V1.1 任务池

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| UX1 | DONE | 建立集中式文案、流程状态和错误模型 | `goal.md`, `specs/desktop-copy-workflow-v1-1.md`, `progress.md`, `macos-native/Sources/AICaptureNativeApp/AppCopy.swift`, `macos-native/Sources/AICaptureNativeApp/Models.swift`, `macos-native/Tests/AICaptureNativeAppTests/CaptureWorkflowStateTests.swift` | 每个流程状态的标题、说明和按钮均由模型生成；用户错误与技术详情分离；目标 Swift 测试通过 | TDD RED 确认模型缺失；实现 `AppCopy`、`CaptureWorkflowState`、`UserFacingIssue` 后目标 Swift 测试 4/4 通过 | 无 |
| UX2 | DONE | 实现单按钮自动抓包编排与四导航 | `macos-native/Sources/AICaptureNativeApp/AppState.swift`, `macos-native/Sources/AICaptureNativeApp/ContentView.swift`, `macos-native/Sources/AICaptureNativeApp/CaptureView.swift`, `macos-native/Tests/AICaptureNativeAppTests/CaptureWorkflowTests.swift`, `progress.md` | 默认进入抓包；单设备隐藏选择器；开始抓包可自动推进至等待应用/运行；冲突可停止切换或继续当前任务；目标 Swift 测试通过 | TDD RED 覆盖协议、状态和导航缺失；目标流程 5/5、Swift 全量 44/44 通过 | 无 |
| UX3 | DONE | 收敛安装、接口、日志和运行检查文案 | `macos-native/Sources/AICaptureNativeApp/AppCopy.swift`, `macos-native/Sources/AICaptureNativeApp/AppState.swift`, `macos-native/Sources/AICaptureNativeApp/Models.swift`, `macos-native/Sources/AICaptureNativeApp/DeviceAppView.swift`, `macos-native/Sources/AICaptureNativeApp/FlowViews.swift`, `macos-native/Sources/AICaptureNativeApp/FlowListPresentation.swift`, `macos-native/Sources/AICaptureNativeApp/LogsView.swift`, `macos-native/Sources/AICaptureNativeApp/LogcatController.swift`, `macos-native/Sources/AICaptureNativeApp/APIClient.swift`, `macos-native/Sources/AICaptureNativeApp/ContentView.swift`, `macos-native/Tests/AICaptureNativeAppTests/**`, `progress.md` | 四页面使用批准文案；普通界面无原始 JSON/HTTP 409/Frida/AVD/Session；接口清空后续抓；日志按钮与空状态准确；Swift 全量通过 | 安装/接口/日志页已简化；结构化错误与技术详情分离；通知成功 3 秒、失败 4 秒自动消失；禁用文案扫描通过；`swift test --package-path macos-native` 50/50 通过 | 无 |
| UX4 | DONE | 扩展后端结构化错误并完成全量视觉验收 | `capture_console/app.py`, `capture_console/http_errors.py`, `tests/test_console_api.py`, `macos-native/Sources/AICaptureNativeApp/AppState.swift`, `macos-native/Sources/AICaptureNativeApp/ContentView.swift`, `macos-native/Tests/AICaptureNativeAppTests/CaptureWorkflowTests.swift`, `README.md`, `docs/desktop-user-guide.md`, `progress.md` | 后端错误兼容新增 code/recovery_action/technical_detail；Python、Swift、App 构建、签名、禁用词扫描和四页面视觉验收全部通过 | 后端保留旧 `detail/user_message/fix` 并补充结构化字段；停止失败与并发启动冲突回归已修复并复审无 P1/P2；Python 204/204、Swift 53/53、Web build、py_compile、禁用文案与敏感信息扫描、`git diff --check`、最终 App 构建及严格签名全部通过；原生桌面抓包/安装/接口/日志四页及运行检查已完成正常、加载、空、失败状态视觉验收 | 无 |
| UX5 | DONE | 清理模拟器重启后的旧实时抓包任务 | `capture_console/app.py`, `tests/test_console_api.py`, `progress.md` | 抓包链路完整时仍可恢复；exporter/Frida 半失效时结束旧任务并清理本设备运行时；历史文件保留 | TDD 新增 2 项回归并先确认旧逻辑失败；Python 206/206 通过；最终 App 重建与严格签名通过；真实 #12 脏状态已自动停止，`active_session=null`、9090/9091 无监听、Android proxy=`null`，模拟器数据未清除 | 无 |
| UX6 | DONE | 修复独立启动模拟器后界面停留在“启动中” | `macos-native/Sources/AICaptureNativeApp/AppState.swift`, `macos-native/Tests/AICaptureNativeAppTests/CaptureWorkflowTests.swift`, `progress.md` | 启动命令返回后持续检测 ADB、Android 启动和解锁状态；就绪后自动恢复“准备开始抓包”；超时有明确错误 | TDD 先复现旧逻辑停留在 `.startingEmulator`；Swift 54/54 通过；最终 App 构建和严格签名通过；使用 macOS 辅助功能真实点击桌面端“启动模拟器”，后端收到 POST 并持续 GET 设备状态，8 秒后达到 `adb_online=true/boot_completed=true/unlocked=true`，界面自动显示“准备开始抓包” | 无 |
| UX7 | DONE | 修复升级后误连接旧版内嵌后端并重发桌面包 | `capture_console/app.py`, `tests/test_console_api.py`, `macos-native/Sources/AICaptureNativeApp/RuntimeManager.swift`, `macos-native/Tests/AICaptureNativeAppTests/RuntimeManagerTests.swift`, `macos-native/scripts/build-app.sh`, `tests/test_native_app_packaging.py`, `README.md`, `docs/desktop-user-guide.md`, `progress.md` | `/api/status` 返回构建标识；同版本后端可复用；不匹配版本只接管 PID 文件记录且可验证为本应用运行时的进程；未知端口占用不被结束；全量测试、解压启动、签名、SHA-256 和 GitHub Release 验证通过 | TDD 覆盖版本握手、未知进程保护、活动抓包保护、同版本接管和孤儿父进程判定；Python 206/206、Swift 61/61、Web build、生产依赖 audit 0 通过；真实将七天前孤儿后端 PID `18716` 替换为 QA ZIP 内嵌后端，再验证崩溃重开接管和正常退出释放 `7001`；最终 ZIP 深度签名、arm64、macOS 14、隐私扫描与 SHA-256 通过；GitHub 预发布标签 `desktop-preview-20260902-24b4ece` 指向提交 `24b4eceac9b0`，远端 145,038,196 字节资产 digest 与本地一致 | 残余：当前仍为 ad-hoc 内部预览包，公开免拦截分发需要 Developer ID 与 Apple 公证；尚未在第二台真实全新 Mac 实装 |
| UX8 | DONE | 修复 Android 36.1 上 Frida 进程枚举崩溃 | `scripts/start_frida_server.sh`, `tests/test_console_core.py`, `progress.md` | 默认保留 Android 动态库搜索路径；Frida 准入恢复；桌面端可启动真实抓包；聚焦测试和 Python 全量通过 | TDD RED 捕获旧脚本强制 APEX `LD_LIBRARY_PATH`；同一 Frida 17.17.0 在移除覆盖后正常枚举进程；聚焦测试 3/3、Python 207/207、`bash -n`、最终 App 严格签名均通过；桌面端 Session #21 正在抓取 WakeQuest，核验时已有 12 条接口且最近 10 条均为 HTTP 200 | 无 |

## 2026-09-11 Android 真机日志任务池

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| L5 | DONE | 优化日志模块并支持已授权 USB/无线 Android 真机 | `goal.md`, `specs/android-logcat-console.md`, `docs/superpowers/plans/2026-09-11-physical-device-logcat.md`, `README.md`, `docs/desktop-user-guide.md`, `progress.md`, `capture_console/device_discovery.py`, `capture_console/runner.py`, `capture_console/app.py`, `capture_console/logcat.py`, `tests/test_console_core.py`, `tests/test_console_api.py`, `tests/test_logcat_service.py`, `macos-native/Sources/AICaptureNativeApp/APIClient.swift`, `macos-native/Sources/AICaptureNativeApp/Models.swift`, `macos-native/Sources/AICaptureNativeApp/LogsView.swift`, `macos-native/Sources/AICaptureNativeApp/LogcatController.swift`, `macos-native/Sources/AICaptureNativeApp/AppCopy.swift`, `macos-native/Tests/AICaptureNativeAppTests/APIClientTests.swift`, `macos-native/Tests/AICaptureNativeAppTests/LogcatControllerTests.swift`, `macos-native/Tests/AICaptureNativeAppTests/UserFacingCopyTests.swift` | 真机发现不破坏 AVD；USB/无线/未授权状态准确；前台应用日志无需旧应用选择；断连停止轮询；离页立即停止；Python 全量、Swift 全量、App 构建与签名通过 | TDD RED 覆盖未授权设备丢失、设备 ID 不稳定、无关端口探测、真机错误文案和并发切换孤儿进程；Python 216/216、Swift 69/69、Web 44/44 与 Vite build 均通过；最终 `.app` 为 arm64、257 MB 且严格签名有效；隔离模拟器真实完成设备发现、前台应用识别及应用/系统/崩溃日志，3 轮并发切换的 6 个请求均为 HTTP 200、始终仅 1 个子进程，停止后为 0；隔离后端与模拟器已关闭，原 `7001/9090/9091` 监听保持不变 | 无真实 Android 手机在线，USB、无线、未授权和断连路径由模拟 ADB 与 Swift 自动化验证；后续接入实机时仅需补 OEM 兼容性证据 |

## 2026-09-11 桌面退出清理任务池

| ID | Status | Task | Scope Files | Acceptance | Evidence Or Reason | Next Step |
| --- | --- | --- | --- | --- | --- | --- |
| L6 | DONE | 修复退出桌面端后抓包任务残留 | `goal.md`, `specs/desktop-exit-capture-cleanup.md`, `progress.md`, `capture_console/app.py`, `tests/test_console_api.py`, `macos-native/Sources/AICaptureNativeApp/RuntimeManager.swift`, `macos-native/Tests/AICaptureNativeAppTests/RuntimeManagerTests.swift` | 退出自有桌面后端前停止全部活动抓包；历史结果和模拟器保留；外部后端不受影响；失败/超时仍可退出；Python、Swift、App 构建及真实退出重开验收通过 | TDD 覆盖多设备清理、单设备异常后继续清代理、后端优雅关闭顺序、桌面退出请求、超时退出与外部进程保护；Python 218/218、Swift 71/71、Web build、py_compile、严格签名和 `git diff --check` 通过；真实 Session #25 运行时退出桌面端后 `7001/9090/9091`、mitmproxy、导出器与 Frida hook 均退出，Android proxy=`null`，模拟器和 13 个抓包文件保留；重开后 `active_session=null`、`health=idle`，安装页无错误拦截提示 | 无 |
| L7 | DONE | 修复日志清空回写并降低高频多行日志噪声 | `goal.md`, `specs/android-logcat-console.md`, `progress.md`, `capture_console/logcat.py`, `tests/test_logcat_service.py`, `macos-native/Sources/AICaptureNativeApp/LogcatPresentation.swift`, `macos-native/Sources/AICaptureNativeApp/LogcatController.swift`, `macos-native/Sources/AICaptureNativeApp/LogsView.swift`, `macos-native/Tests/AICaptureNativeAppTests/LogcatPresentationTests.swift`, `macos-native/Tests/AICaptureNativeAppTests/LogcatControllerTests.swift` | 新连接不回放历史缓冲；多行异常合并、连续相同异常折叠；清空前在途分页不能回写；搜索、复制和计数使用逻辑日志；Python、Swift、App 构建与真实日志抽样通过 | TDD RED 分别捕获展示层缺失和清空后旧分页回写；Python 218/218、Swift 74/74、Vite build、py_compile、`git diff --check`、App 构建及运行后严格签名均通过；真实进程命令包含 `logcat --pid 4004 -T 1 -v threadtime`，重连只读到附近 6 条而非历史 1000 条；桌面日志页显示 14 条逻辑日志，并将相同警告折叠为“连续出现 8 次”和“连续出现 2 次”；真实清空返回 cursor=2，后续轮询无旧 cursor 回流且状态保持 `streaming`；未执行 `adb logcat -c` | 无 |
| L8 | DONE | 修复超长日志默认铺满表格 | `goal.md`, `specs/android-logcat-console.md`, `progress.md`, `macos-native/Sources/AICaptureNativeApp/AppCopy.swift`, `macos-native/Sources/AICaptureNativeApp/LogcatPresentation.swift`, `macos-native/Sources/AICaptureNativeApp/LogsView.swift`, `macos-native/Tests/AICaptureNativeAppTests/LogcatPresentationTests.swift` | 超过 3 行或 360 字符的消息默认紧凑展示且可单条展开；完整搜索、纯文本和复制不截断；Swift 全量、App 构建、签名与真实 UI 验收通过 | 先确认链路无漏取：PID 3912、cursor 1...159 连续，原始 159 条压缩为 12 条；TDD RED 捕获紧凑预览模型缺失，Swift 77/77、`git diff --check`、App 构建和严格签名通过；真实将 `com.test.tcgp` 切到后台再前台后捕获 21 条启动日志，超长 Flutter 编码/调用栈默认显示 3 行和“展开完整内容”，展开后全文可见且按钮变为“收起内容”，收起后恢复紧凑表格 | 无 |
| L9 | DONE | 修复超大接口响应导致桌面端卡死 | `goal.md`, `specs/large-flow-response.md`, `progress.md`, `capture_console/results.py`, `capture_console/app.py`, `tests/test_console_core.py`, `macos-native/Sources/AICaptureNativeApp/AppCopy.swift`, `macos-native/Sources/AICaptureNativeApp/Models.swift`, `macos-native/Sources/AICaptureNativeApp/FlowListPresentation.swift`, `macos-native/Sources/AICaptureNativeApp/FlowViews.swift`, `macos-native/Tests/AICaptureNativeAppTests/FlowListPresentationTests.swift` | 大正文只内联 256 KiB 且完整文件可定位；详情使用长文本原生视图；cURL 不重复读取 Response；使用真实约 2 MB JSON 响应不再卡死；Python、Swift、App 构建及签名通过 | 两份系统 hang report 证实旧版主线程在 SwiftUI/CoreText 排版约 2 MB JSON 时分别阻塞 44.80 秒和 38.99 秒；TDD 覆盖 256 KiB UTF-8 安全截断、原文件留存、cURL 跳过 Response 和 Swift 展示元数据；真实 2,016,157 字节响应经当前 SOCKS5/mitmproxy/exporter 链路回放后，详情 API 返回 308,383 字节且耗时 91 ms，桌面端显示 256 KB 预览并可切换、滚动和定位完整文件；进程抽样主线程处于事件等待，峰值物理内存 132.4 MB，未新增 hang report；Python 220/220、Swift 78/78、`py_compile`、`git diff --check`、App 构建与严格签名全部通过 | 无 |
| L10 | DONE | 在桌面发行包中提供安装说明和前置准备条件 | `goal.md`, `specs/release-install-guide.md`, `progress.md`, `release/安装说明.md`, `release/package.sh`, `tests/test_native_app_packaging.py` | ZIP 根目录包含 App 与安装说明；说明覆盖前置条件、安装、首次使用和常见问题；开发与正式包共用；打包、SHA、签名、架构、冷启动及远端资产校验通过 | TDD 先后复现 ZIP 缺少中文说明、源码归档缺少说明和通用 ZIP 工具无法读取 ASCII 说明；Python 全量 220/220、最终原生打包测试 7/7、Shell 语法、`git diff --check` 与敏感信息扫描通过；最终 ZIP 根目录含 `抓包工具.app`、`安装说明.md`、`INSTALL.md`，大小 98,867,749 字节，SHA-256 `18ff8419543d76c788f1a7a3ae57a7e6a8c53f91320de70532e99debc8ea0f6d`；解压后 arm64、严格签名、冷启动和内嵌后端 `build_id=cc11d8f` 通过；GitHub 预发布标签 `desktop-preview-20260916-cc11d8f` 指向同一提交，远端资产大小与 digest 和本地一致 | 残余：当前仍为 ad-hoc 内部预览包，公开免拦截分发需要 Developer ID 与 Apple 公证 |
| L11 | DONE | 修复停止抓包后界面仍保持运行状态 | `goal.md`, `specs/capture-stop-semantics.md`, `progress.md`, `capture_console/app.py`, `tests/test_console_api.py`, `macos-native/Sources/AICaptureNativeApp/AppCopy.swift`, `macos-native/Sources/AICaptureNativeApp/Models.swift`, `macos-native/Sources/AICaptureNativeApp/AppState.swift`, `macos-native/Tests/AICaptureNativeAppTests/CaptureWorkflowTests.swift` | 停止成功与代理恢复分别报告；部分清理失败不阻塞停止；真正停止失败保留活动任务；Python、Swift、App 构建、签名及离线设备真实接口验收通过 | 根因复现为 Session #43 已写为 `stopped`，但离线代理清理令旧接口返回 `ok=false`；TDD 覆盖部分清理失败、真正停止失败和旧组合响应兼容；Python 222/222、Swift 80/80、`py_compile`、`git diff --check`、arm64 App 构建与严格签名通过；真实 Session #44 运行后关闭本项目模拟器，桌面端仍成功停止并提示网络待恢复，后端 `active_session=null`、数据库为 `stopped`、9090/9091 和抓包子进程均释放，安装页无抓包冲突 | 无 |
| L12 | DONE | 发布包含停止抓包修复的 GitHub 桌面安装包 | `goal.md`, `progress.md`, `release/**`, `macos-native/build/抓包工具.app` | 新 Release 指向 `27340c6`；ZIP 含 App 与双语安装说明；SHA-256、arm64、深度签名、内嵌后端隔离启动、版本和远端资产摘要全部通过 | 新预发布 `desktop-preview-20260920-27340c6` 已指向 `27340c65a9b2`；ZIP 为 98,869,293 字节，SHA-256 `46162ca32d47825d1ed03ddef92fe6c6fde68582eceb6267586ee3b34fe39e91`，远端 digest/大小一致；根目录仅含 App、`安装说明.md`、`INSTALL.md`；arm64、深度签名、自包含运行时导入、生产依赖 audit 0、打包测试 7/7 通过；解压包内嵌后端在隔离端口启动并返回 `build_id=27340c65a9b2` 与新停止契约。为保护用户正在运行的 PokeHub Session #49，未关闭现有桌面端重复 GUI 冷启动，当前抓包链路复核仍为 running | 无 |
| J1 | DONE | 修复 Jenkins 安装冲突恢复及真实安装错误 | `goal.md`, `progress.md`, `specs/jenkins-install-recovery.md`, `capture_console/runner.py`, `capture_console/http_errors.py`, `tests/test_package_install.py`, `tests/test_console_core.py`, `macos-native/Sources/AICaptureNativeApp/AppState.swift`, `macos-native/Sources/AICaptureNativeApp/DeviceAppView.swift`, `macos-native/Tests/AICaptureNativeAppTests/CaptureWorkflowTests.swift`，本机项目 AVD 与完整备份 | Python/Swift 回归、桌面构建/签名、真实 Jenkins WakeQuest 安装与设备包验证通过 | 复现根因为设备空间不足却误报 Jenkins 断网；修复缓存回收重试、错误分类、旧抓包冲突清除及安装恢复入口。Python 229 项、受影响 core 最终 86 项通过；Swift 分批 81+1 项通过（原窗口测试整套运行 AppKit 崩溃、单独运行通过）。完整备份比较一致；虚拟磁盘 16 GiB，当前文件系统约 10 GiB，在线扩展达到限制后未继续强制调整，离线处理保护检查在仍有占用时停止；正常重启 e2fsck 五项检查完成，原有 12 个应用与 Google 记录保留。桌面实际安装 WakeQuest #121 成功，剩余 2.6 GiB；最终构建 d863f44dcb7c 启动、签名和重复安装 cached=true 均通过 | 本机修复已生效；未推送/发包。完整利用旧磁盘 16 GiB 的后续迁移不属于本次安装验收 |
| N1 | DONE | 修复模拟器失效抓包代理及 Google Play 断网 | `goal.md`, `progress.md`, `specs/emulator-network-recovery.md`, `capture_console/runner.py`, `scripts/ai_capture.sh`, `tests/test_device_network.py`，本机项目模拟器代理 | 代理清理回归通过；设备代理实际解除；Google Play 在模拟器中实际加载；桌面运行保持正常 | 代理修复、设备 HTTPS 与 196 项回归已通过；桌面 c2d85e1f34d8 构建签名及启动通过。2026-10-16 复查代理 :0、host 为空、port=0，无活动抓包、Google 账号记录保留。独立 QEMU 窗口不支持自动化绑定；用户随后亲自打开 Google Play，明确确认“看了能正常打开了”，以用户实测补齐最终页面验收，不记为自动截图验收 | 本机修复验收通过；未推送 GitHub 或更新安装包 |

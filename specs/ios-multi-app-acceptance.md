# IOS-C3 Multi-App Acceptance

## Scope

按用户最新要求，继续同一IOS-C3，先取消桌面域名准入，再测试三个自有应用。用户否定每应用手填域名流程，因此本节新设计取代原逐项目验收流程，不接管IOS-A自动导入任务。复用一年期证书，保留#78及其他历史结果。

手机VPN始终开启，原节点、订阅、DNS、默认路由与其他规则不改。桌面不再按业务域名限制当前连接的录制，但不据此擅自改手机为全局节点或认为所有应用都已接入。测试期间不操作无关敏感应用；手机路由仍需独立验证。证书、登录、凭据和设置变更由用户本人确认，不擅自安装自动化agent。

## Implementation Plan

Goal: 已验证iPhone连接可直接开始，无需项目或业务域名。
Architecture: 新客户端以空请求体启动通用录制；旧project_id请求保留原语义以兼容已发布客户端。控制命令显式标记device范围，worker在此范围不按host过滤；停止仍恢复仅检查域名解密与其他TLS透传。认证、绑定手机来源、存储配额和有界正文保持不变。
Tech Stack: 既有SwiftUI、FastAPI、mitmproxy。

- [x] RED: 在test_ios_capture加入无项目启动、多未知域名正文、排除检查请求、未认证/本机来源不录制、停止后不记录回归；API空body测试；Swift不加载项目直接启动测试。已复现422、旧域名校验和按钮不可用。
- [x] GREEN: IOSRecordingPayload.project_id可缺省；服务生成device-scope记录；worker用None表示不限域名，[]仅表示停止；不将空的旧项目域名解释成全域。
- [x] UI: 删除项目卡和编辑表单；开始按钮仅依赖已验证连接，发送空body；文案明确记录经过Mac的HTTP(S)，不声称自动识别应用。
- [x] Verify: 使用App内嵌`macos-native/build/抓包工具.app/Contents/Resources/runtime/bin/python3 -B`运行unittest（本工作树无.venv）；最终相关Python259项、`CAPTURE_TEST_IOS_PROXY=1`真实代理3项、`swift test --package-path macos-native`121项/17套通过。最终构建ios-c3-general-20261104与运行后深度严格签名通过。
- [x] Evidence: 原生界面无项目/域名输入；三款实际尝试均未取得业务响应，以下记录具体缺口；停止和历史保留、git diff --check通过。仅本地提交，不发布。
- [x] Review fix: 独立审查发现device模式的全局allow_hosts会让已认证但非绑定手机的客户端进入TLS解密；两项回归先RED后修复。使用弱引用认证CONNECT记录和tls_clienthello握手前检查隔离手机，检查页例外仍需认证与对应SNI。真实TLS比较启动期间的代理证书与停止/限额后的源站证书；复审无剩余具体发现，审查者独立运行10项录制测试通过。

## Targets

| Application | Bundle | Version | Build | Selection |
| --- | --- | --- | --- | --- |
| MelodyCraft | com.mi.ai.music | 1.19.0 | 74 | 正式版，不使用同名com.niubi.test.sticker开发包 |
| Wishly | com.shapley.wishly | 1.3.1 | 1 | 用户指定的已安装版本 |
| StickerHub | com.meta.inno.sticker | 3.18.13 | 194 | 用户指定的已安装版本 |

## Procedure

本轮统一接入续验：先读取小火箭当前路由/节点选择作为恢复基线，不导出订阅或凭据。候选是临时切换全局转发模式与已有Capture-Mac选择，而非新增域名规则；必须先获得这项临时选择变更的明确允许，原配置文件/节点参数保持不变。选择变化不等于原VPN出口不变，需明确由Mac出网。手机VPN不关闭；Mac停止录制后保持透传，恢复原选择并验证手机联网，再结束本轮。未获允许时只读诊断，不继续重复0条的应用试验。

1. 只读核对当前连接、手机身份、已安装版本及可用域名线索，Android历史域名只能作为候选，不冒充iOS实际来源。
2. 原生桌面不创建项目或填写域名，直接开始录制；业务域名仅用于脱敏证据归属，不能成为准入条件。手机流量未接入时，明确路由阻塞，不自行修改原VPN配置。
3. 原生桌面开始一款项目后打开对应手机应用，使用只读页面触发网络。只输出域名、路径、方法、状态、正文大小和完整性，不输出凭据、个人数据或完整日志。
4. 通过原生接口页核对实际Request/Response；只有来源确为手机且至少一条业务响应有可解析正文，才能记录该项目抓取通过。检查页、本机请求或仅页面缓存不计通过。
5. 每款结束通过桌面停止，保留记录再切下一款；最终连接保留、无活动记录、原VPN不变。未通过项记录具体阶段和必要下一步，不笼统判定应用不支持。

## Acceptance

- 三款分别有实际结果或有证据的阻塞，未实测项明确标记。
- 抓取通过必须有手机真实业务Req/Resp和原生界面证据，不用Android历史或Mac对照代替。
- 无域名输入或预设应用前置条件，按次结果独立，停止有效，历史保留。
- 不新增证书、不改变原VPN节点/订阅/DNS/默认路由、不清除应用数据、不进行购买、发消息或内容发布。
- 允许本地代码、测试、构建和脱敏文档提交；不推送、不发包。

## Evidence

2026-11-04：工作树干净，真实桌面连接ready、recording_state=stopped、#78共166条。USB应用清单确认上述三个正式版本，首次默认查询只含开发应用，已通过include-default-apps补齐，不能把默认清单误认为全部安装应用。当前桌面项目只有PokeHub和原有网络验收项目，其余项目域名仍待核实。

三款均已通过USB打开并核对页面；StickerHub进程元数据含pbzhiqxtoqqgizddjblb.supabase.co，不含解密正文证据。#79按旧项目流程录制0条，现已在原生桌面停止。用户拒绝继续逐域名配置，改为无域名准入；此前三条新增规则询问未执行，原手机配置未更改。

### Final Local Verification

- Python: `-B -m unittest -q tests.test_ios_identity tests.test_ios_setup tests.test_ios_capture tests.test_ios_results tests.test_ios_lifecycle tests.test_console_core tests.test_console_api`，259项通过，10.122秒。
- 真实隔离代理: `CAPTURE_TEST_IOS_PROXY=1 .../python3 -B -m unittest -v tests.test_ios_setup_integration`，3项通过，12.181秒。使用两个不同主机名的合成请求验证通用模式，不冒充手机证据。
- Swift: `swift test --package-path macos-native`，121项/17套通过，6.855秒。
- 构建: `AI_CAPTURE_BUILD_ID=ios-c3-general-20261104 macos-native/scripts/build-app.sh`；`codesign --verify --deep --strict --verbose=2 macos-native/build/抓包工具.app`，启动后通过。
- 原生UI: 连接暂停时开始按钮禁用；重新连接沿用原证书/身份，真实iPhone检查通过，identity_reused=true、route_changed=false；无需项目直接开始，接口页可搜索和显示Request/Response，停止后保留连接。未执行证书重装或手机路由修改。

| Phone test | Record | Observed result | Remaining gap |
| --- | --- | --- | --- |
| MelodyCraft | #81 | USB冷启动成功，创作页显示；0条进入Mac | 未取得真实业务Req/Resp，不能确认支持；需验证统一流量接入及实际联网操作 |
| Wishly | #82 | USB冷启动后首页显示；0条进入Mac | 同上；首次截图是启动白屏，稍后重截已正常首页，不误报应用白屏故障 |
| StickerHub | #83 | USB冷启动后画册页显示；0条进入Mac | 同上；之前网络元数据仅证明曾产生连接，不是本轮正文抓取证据 |
| PokeHub control | #84 | 同手机/证书/VPN，通用模式成功记录；中途59条，停止时65条 | 仅证明既有接入路径及新桌面录制正常，不代表另外三款已接入 |

PokeHub只读版本配置POST返回200，Request为20字节，Response为4165字节，两者为完整可解析JSON且均未截断。原生接口页搜索该路径并实际查看Request/Response。#84停止后再次冷启动PokeHub，归档仍为65条，connection_state=ready、recording_state=stopped；旧#78保持166条，#80-83未被删除。

Current task remains BLOCKED for three-app business acceptance. No tested traffic reached the Mac for those apps; without changing the phone's existing VPN routing, desktop-only filter removal cannot prove or force that ingress. Do not infer certificate pinning or application incompatibility from zero records. Next work must validate one general, reversible ingress path with the original VPN configuration preserved, not resume per-domain setup. No automatic phone taps or network changes were performed, and no code was pushed or release uploaded.

### General Ingress Follow-up (2026-11-04)

用户继续要求统一接入、不逐域名配置。本轮恢复DOING并只读核对：iPhone14_Test仍在线；USB启动既有小火箭后截图确认停在代理日志页，日志记录关闭；原生桌面显示抓包已停止、手机连接保留。只读API为ready/stopped、#84、65条，未开始新记录。

Mac通过不使用环境HTTP代理的HEAD请求检查已知服务域名：Melody候选域名TLS校验0、HTTP200、0.778秒；Wishly候选域名TLS校验0、HTTP404、0.846秒；StickerHub域名TLS校验0、HTTP404、0.790秒。404只表示根路径无资源，TLS连接已完成；这是宿主机出网检查，不是手机业务证据，也没有将域名加入任何路由或录制条件。

候选接入为小火箭临时全局代理选择已有Capture-Mac，VPN保持开启、原配置文件/节点参数/订阅不改，测试后恢复原选择。这会改变当前路由选择，可能更换出口IP，且范围可能包含手机后台HTTP(S)；不能冒充原VPN出口原样保留。已通过一个异步问题说明这项必要例外，尚未收到明确答复。因此本轮未操作手机设置、未新增规则/证书/代理、未录制无关流量，任务回写BLOCKED等待该实质边界明确；不反复复现原路线的0条。

本轮仅更新目标/验收记录，无产品代码变化，不重跑已有构建或将历史自动化结果当作新手机验收。`git diff --check`通过；原生桌面继续打开、连接保留、录制停止。若用户不允许当前转发选择有任何临时变化，应明确该限制下无法强制统一接入，不能偷偷采用替代全局配置。

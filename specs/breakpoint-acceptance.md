# BP-4 综合验收记录

基线541e878，2026-11-04。只处理BP-4；不发布、不覆盖现有应用、不更改手机VPN/节点/原配置，不中断已有任务。

## 验收矩阵

| 项目 | 验证步骤 | 结果 |
| --- | --- | --- |
| 发布包完整性 | 构建开发签名ZIP，移至含空格/中文的新目录，验证签名、独立运行时、版本、addon与依赖、无开发运行数据 | 通过；arm64、严格签名、自包含运行时、说明、SHA-256、105个后端文件隐私边界检查；未Apple公证 |
| 真实断点闭环 | 使用迁移后的包内Python/后端，三种适配的H1/H2请求响应改写、原始放行、停止、归档及控制拒绝 | 45项真实传输及4项最终包验收通过；包内产品模块路径和源码字节相等已验证 |
| 性能/资源 | 同环境未启用/启用未命中对照p95新增<=10ms；100MiB哈希与额外RSS<64MiB；自有进程回收 | 通过；详细样本见下，未修改门槛 |
| 既有功能 | Swift全套、Python断点与既有抓包、iOS真实TLS和迁移生命周期；不能把opt-in跳过算通过 | Python324、Swift152、真实TLS3、迁移生命周期1、严格guard36通过；opt-in均显式开启 |
| 原生安装包 | 迁移后的原生应用四导航与断点编辑/队列/归档，独立目录端口，不接7001 | 本次原生创建规则、双阶段改写、对照、关闭断点、停止录制通过；BP-3其余UI证据可复用，Swift源码未变 |
| iPhone真机 | 原身份/节点/配置不改，已有通道请求响应改写，优先只读业务；不能安全修改则用受控请求并标明边界 | 通过；iPhone14_Test真实HTTPS、PokeHub普通业务200、Safari只读参数/响应改写；用户确认手机显示修改内容，不等同PokeHub业务UI改写 |
| Android真机 | 已具备抓包条件的真实Android设备端到端改写 | 用户确认暂无设备，未覆盖 |
| 使用说明 | 实际按钮、匹配/双阶段、正文限制、敏感信息、放行/终止/超时/停止、失败恢复与版本边界 | 新独立指南、主教程和安装说明已补；ZIP含同字节BREAKPOINTS.md，打包RED/GREEN通过 |

整体状态：**BLOCKED（部分验收通过）**。Android真机缺席，不能把loopback或模拟器当作真机；完整双平台现场验收尚未结束。没有新进入其他阶段，也不自动发布。

## 安全执行

- 新目录/随机loopback端口/私有合成凭据验收，不写现有runtime；不复用当前控制令牌。
- iPhone只允许读本工具已有身份以核对能否恢复相同连接；不读取其他应用凭据，不重置证书、不写原配置或钥匙串。没有无改动路径时记录阻塞。
- 不进行支付、删除、账户/权限修改、自动重放；真实业务正文和令牌不进入验收文档或安装包。
- 休眠或系统网络变更会影响现有环境，因此以隔离故障测试及已有证明覆盖，若未现场休眠需明确记录。
- 综合门槛缺失时保持未完成，不以本地测试代替真实设备。

## 实机证据与收尾

设备为iPhone14_Test（iPhone 14 Pro、iOS 26.5.2），原抓包证书身份未轮换。验收夹具使用隔离runtime及随机loopback控制端口，只读复用本工具既有钥匙串身份，在空闲的原抓包端口运行相同身份；钥匙串create/delete被显式拒绝。未操作小火箭、VPN、原节点、规则、Wi-Fi代理或证书信任，也未安装手机自动化组件。

PokeHub 2.1.0 (96)打开后，既有链路记录到业务200及WebSocket握手；这些业务请求及响应均未修改，也未导出用户正文/令牌。另在Safari发起同站点根路径的无认证只读GET作为受控对照，避免猜测生产参数：

1. 原生界面创建GET、精确路径、请求和响应、仅下一次、60秒规则并启用。
2. 请求暂停，桌面将Query从`bp4=original`改为`bp4=modified`，核对差异后继续。
3. 响应暂停，原始404/路径错误JSON改为200/`{"bp4":"iPhone response edit confirmed"}`，核对后继续。
4. 归档同一flow保留原始/生效URL、状态码、两阶段apply和对应正文。用户明确反馈“手机已显示 iPhone response edit confirmed”，无手机截图，不伪称自动读取到手机渲染。
5. 桌面关闭断点、停止录制，UI与API均为stopped/idle、待处理0。退出独立UI并回收自有服务；未点击“结束连接并移除授权”，原身份保持。

原生验收复制了同一release构建到临时路径，只为避免与已运行旧桌面冲突，临时改bundle ID并adhoc重签；不将该临时ID副本作为分发包。最终未改ID的ZIP另行验证严格签名及独立启动。用户原有7001全程保留，最终仍为`build_id=be6d0543b498/health=idle/active_session=null`，iOS状态恢复原有`needs_cleanup/idle`；本轮结束后临时代理不再提供手机转发，后续使用需由正常工具恢复连接，未代用户改手机路由。

本轮生成的原始真机记录、临时代理私钥/控制凭据和隔离runtime已删除，未加入源码或ZIP；原身份元数据前后哈希一致。修复夹具后再次真实启停验证输出`original_identity_unchanged=true; owned_proxy_stopped=true`且exit0，覆盖钥匙串身份完整值不变和自有session目录释放。

## 自动化证据

Python3.12.12、mitmproxy12.2.3、uvicorn0.49.0来自自包含包。下列真实代理均为自有临时端口/合成数据，不更改手机配置。

| 命令/套件 | 实际结果 |
| --- | --- |
| `python -m unittest tests.test_breakpoint_api tests.test_breakpoint_engine tests.test_breakpoint_archive tests.test_breakpoint_ipc tests.test_breakpoint_lifecycle tests.test_breakpoint_boundaries tests.test_breakpoint_adapters tests.test_console_api tests.test_console_core tests.test_ios_setup tests.test_ios_capture tests.test_ios_results tests.test_ios_lifecycle tests.test_exporter_timing tests.test_flow_summary_types -q` | 324项，26.583s，0失败；清除外部runtime/config环境变量，产品测试使用源码 |
| `CAPTURE_TEST_BREAKPOINT_TRANSPORT=1 python -m unittest tests.test_breakpoint_integration -q` | 包内产品+外部测试夹具，45项，145.219s，0失败 |
| `CAPTURE_TEST_BREAKPOINT_TRANSPORT=1 CAPTURE_REQUIRE_BP0_SAFE=1 python -m unittest tests.test_breakpoint_guard -q` | 36项，69.193s，0失败；慢正文、单流取消、背压、H2共享连接、100MiB及20并发 |
| `CAPTURE_TEST_IOS_PROXY=1 python -m unittest tests.test_ios_setup_integration -q` | 3项，12.242s，0失败，实际TLS/认证代理，非手机替代验收 |
| `CAPTURE_TEST_BP4_APP=<解压App> CAPTURE_TEST_IOS_APP_PATH=<解压App> python -m unittest tests.test_breakpoint_e2e tests.test_ios_packaged_lifecycle tests.test_breakpoint_device_acceptance -v` | 最终ZIP解压后7项，27.879s，0失败；含三适配双阶段H1/H2、终止不达源站、子进程来源、未命中性能、3轮正常/异常重启归档和信号清理 |
| `python -m unittest tests.test_native_app_packaging.NativeAppPackagingTests.test_development_release_creates_explicitly_labeled_app_zip -v` | 修改后1项29.213s通过；真实构建ZIP、SHA、说明字节、源码归档和解压签名；不是宣称全部打包用例通过 |
| `python -m unittest tests.test_breakpoint_device_acceptance -v` | 2项1.473s通过，真实子进程SIGINT/SIGTERM两种信号及准备阶段SIGTERM；也纳入最终7项 |
| `swift test --package-path macos-native -q` | 152项、22套件、7.219s通过，Swift源文件本轮未变 |
| `bash -n release/package.sh macos-native/scripts/build-app.sh`、`git diff --check` | 通过 |

包内验收从临时目录启动，`PYTHONPATH`第一项指向解压App的`Contents/Resources/backend`，第二项才是源码测试夹具；显式断言6个父进程产品模块位于包内、addon存在、依赖版本一致。三适配子进程还通过provenance命令返回实际已加载的全部产品模块路径及解释器路径，逐一验证属于包内backend/runtime，必要模块不得缺失。最终包全部Python后端文件与源码/已验收迁移包逐字节一致；最终与原生实测构建的Mach-O二进制SHA-256也完全相同。

## 性能样本

最终ZIP：每种适配关闭/开启未命中规则交替两轮，每轮20请求，剔除前5次，分别30个计时样本；持续heartbeat并断言enabled实际状态、in_flight/reserved_bytes为0。RSS保留首次启用前关闭轮的基线，取开启轮最大高水位，避免第二次关闭的累积峰值掩盖初次开启开销。该小样本只是本机门槛检查，不代表跨主机性能保证，负差值不宣称“开启更快”。

| 适配 | 关闭p95(ms) | 开启未命中p95(ms) | 额外峰值RSS(bytes) |
| --- | --- | --- | --- |
| regular | 25.884 | 22.982 | 770048 |
| socks | 22.973 | 22.574 | 786432 |
| ios | 40.940 | 23.371 | 933888 |

严格guard另测未命中p95为18.68→19.48ms，新增0.8ms。真实产品100MiB响应额外RSS：regular 2,637,824、socks 4,816,896、ios 4,292,608 bytes，完整哈希一致。guard 20路慢消费者合计160MiB，额外峰值17,055,744 bytes；均低于64MiB阈值。

## 修复与未覆盖

- 验收夹具首次启动时未创建ios-setup目录，`private_json`失败；补创建后恢复原身份并完成真机测试，未修改产品。
- 新打包测试先失败：ZIP不存在`BREAKPOINTS.md`；补打包复制与缺文件检查后GREEN。安装与主教程均指向独立指南。
- SIGTERM收尾先exit143，uvicorn默认重抛使夹具finally跳过；其代理看门狗已退出但临时目录保留。两信号RED后增加夹具专用AcceptanceServer信号上下文，GREEN及真实只读身份启停通过，旧临时目录显式回收。未改产品uvicorn行为。
- 独立复核指出prepare期间仍可能被SIGTERM打断；合成身份/服务测试先以-15失败，再扩大信号保护到prepare/serve/finally全过程，最终2项通过，真实只读身份重新启停exit0。还指出子进程来源未直接验证；三适配先均超时RED，增加仅测试用的实际模块来源命令后最终7项GREEN。RSS自查修正累积高水位基线，最终样本仍达标。
- 本轮没有Android真机，没有第二台全新Mac，也未为验收强制整机休眠/断网。生命周期故障由隔离进程/租约/停止测试覆盖，不能声称实际休眠唤醒矩阵完成。
- 构建输出8项开发依赖告警（2 low/1 moderate/5 high）；`npm audit --omit=dev --json`为0。未在本任务无关升级依赖，开发依赖风险仍需后续处理。
- 本轮未发现需要修改正式断点引擎或现有抓包链路的问题；最终限定只读复核无剩余P1/P2，复核不冒充测试执行，7项结果由主代理实跑确认。没有推送或GitHub发布，亦未覆盖/卸载原安装应用。

## 本地安装包

`release/AI-Capture-Desktop-20261104-541e878-bp4-development-arm64.zip`

- 大小：99,393,290 bytes。
- SHA-256：`6f9d864b3b5b363cb0e284392a4776674daf9e2f7290fc2ab07ff30a8538f137`。
- build_id：`541e878-bp4`，表示541e878产品实现加本轮文档/打包与验收增量，不冒称另一个已发布提交。
- 根目录：`抓包工具.app`、`安装说明.md`、`INSTALL.md`、`BREAKPOINTS.md`（并有ditto资源元数据）。
- 解压到含中文/空格路径后，arm64、`codesign --verify --deep --strict`、内嵌依赖和运行时相对链接、独立后端启动/正常与异常重启、说明字节及校验和全部通过。
- 这是本地开发签名预览包，不是已公证公开发行版；Android现场缺项尚未解除，不自动推送为“全部验收完成”版本。

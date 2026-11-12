# Android 真机桌面入口 V1

## 范围

2026-11-12 发布授权更新：用户要求推送并更新下载包，本轮允许作为开发预览发布当前分支与对应标签；不将其视为上述硬件缺口已通过，不合并 main、不覆盖旧安装包或本机 /Applications。后文“不发布”均为此前验收阶段的历史边界。
- Android 下二级选择“模拟器 / 真机（实验）”，默认模拟器，不改变 iPhone。
- USB 真机授权、解锁、前台应用识别。仅选择单个应用，不采集其他应用。
- 独立 `com.local.capture.bridge` 连接助手，使用官方 WireGuard tunnel 库；只对助手使用 run-as 下发私有配置，不读取原应用或 VPN 私有目录。助手自身可调试不改变目标应用可调试状态。
- 助手安装、Android VPN 同意及锁屏验证由用户确认，不自动点击安全弹窗。桌面自动准备监听、临时密钥、单应用路由、启动目标应用、保存请求/响应。
- mitmproxy 12.3.1 独立运行时启用实验 eMudhra；上游 TLS 校验保持开启。已经修复的客户端可能拒绝，不降级，不安装系统 CA，不修改请求内容。
- 自动发现当前 Mac 的既有 HTTP 上游，缺失时明确显示直连；不改系统代理。原 VPN 节点、订阅、配置不写入。

## 状态与接口
`GET /api/android-physical` 返回阶段、设备、应用、记录编号、计数和用户动作，不返回密钥。
`POST /api/android-physical/start` 接受 serial、desktop_pid、experimental_consent。阶段 idle/preparing/waiting_install/waiting_vpn/capturing/stopping/recovery_required/stopped/failed。
`POST /api/android-physical/stop` 幂等停止并请求恢复；`POST /api/android-physical/recover` 重试恢复。新连接禁止覆盖未完成恢复的旧连接。
本机控制接口验证 loopback、Origin 和桌面请求头；工作目录0700、配置0600，API/日志不回传原始密钥、正文或节点密码。

## 生命周期
助手仅租约存活时维持临时隧道；桌面定时通过USB续约，失联/桌面退出后短时到期释放VPN。不修改 Always-on/lockdown，若已启用则拒绝接管。每次都记录原VPN应用；打开原VPN或对已识别的Clash连接按钮恢复，不能验证恢复时显示待恢复，不声称原网络已恢复。
正常退出先关闭助手隧道，确认原VPN连接，再终止监听。崩溃、睡眠、USB拔出不能保证系统自动拉起第三方VPN，因此保留恢复说明和持久标记，重启时先恢复而非自动开始新抓包。
代理进程通过桌面身份和租约自退出；只操作自有进程，不杀端口占用者。每轮配置及临时密钥删除；抓包归档按已有最近7条保留策略管理。

## 验收
1. Python单元/接口测试：设备与权限检查、单应用配置、并发启动禁止、取消/退出、租约失效、原VPN恢复核验、无密钥响应、归档接口兼容。
2. Swift状态/文案/按钮测试；默认模拟器，真机不调用模拟器启动或Root命令。
3. 原生助手构建及桌面构建；独立代理依赖不改变原环境版本。
4. 真机系统授权后从桌面进入抓包、查看实际头与JSON正文、停止并核验原VPN；记录未覆盖项，不把模拟测试当作实机证据。
5. 不推送、发布或覆盖现有安装包；用户另行要求后再执行。

## 2026-11-12 恢复验收
- 用户换回 PHK110，继续同一任务；目标为 PokeHub 正式版 `com.mi.poketrade`、测试版 `com.test.tcgp`，Wishly 正式版 `com.shapley.wishly`、测试版 `com.niubi.testapp`。应用名和安装版本已从当前设备确认。
- 每个包独立从桌面启动、查看 Request/Response、停止并核对原 Clash 恢复；仅操作只读页面，登录由用户自行完成。不使用独立改包试验副本。
- 修复上一轮实测发现的导航状态丢失：进入接口再返回抓包时应保留真机选择及同一控制器，不能跳回模拟器。
- 恢复本轮时的基线为 Python 聚焦 102 项、Swift 195 项（另有 1 项显式跳过）、助手 4 项及独立代理租约实测通过；最终源码的结果见下方。此前 PKG110 的 PokeHub 正式包取得 6 条记录及完整 JSON，并通过桌面停止恢复 Clash；不将其代替本轮四包验收。

## 本轮实际结果（2026-11-12）

使用仓库构建的原生桌面、独立验收后端和 PHK110。每轮从“Android → 真机（实验）”开始，在“接口”页切换 Request/Response，再从抓包页停止。

| 应用 | 版本 | 记录 | 正文证据 |
| --- | --- | --- | --- |
| PokeHub 正式包 | 2.1.1 (98) | #3，5 条 | `get_app_config` 200，请求 80 B、响应 2759 B；`get_latest_messages` 200，4 B / 1108 B；均含头与完整 JSON |
| PokeHub 测试包 | 1.0.0 (1) | #4，3 条 | `get_latest_messages` 200，4 B / 505 B；`trainer_match` 200，27 B / 2 B，响应是空 JSON 数组而非缺失 |
| Wishly 正式包 | 1.3.0 (17) | #5，7 条 | `gratitude/week/listByDate` 200，26 B / 174 B；`affirmation/query/today` 200，空请求体 / 640 B JSON |
| Wishly 测试包 | 1.3.0 (1) | #6，8 条 | `gratitude/week/listByDate` 200，26 B / 172 B；`affirmation/query/today` 200，空请求体 / 578 B JSON |

- 上述抽样正文的 complete=true、truncated=false；桌面请求/响应头和逐键换行 JSON 已实际显示。原始认证头、账号信息及正文不入库到 Git。
- 安全补修后的构建又从桌面验证 PokeHub 正式包 #7：24 条（包含静态资源及 101），`get_latest_messages` 200 的 4 B / 1108 B JSON 可读。停止协议的最后一次加固在此轮之后，单独列出验证，不冒充四包全部在最后源码上重跑。
- 正式 PokeHub 的 `trainer_match` 有一次真实 HTTP 500，正文 106 B 已捕获；这是服务端结果，不计作抓包失败。101 仅握手，不声称采集到 WebSocket 帧。
- 四轮仍分别出现 99 / 44 / 21 / 18 次 TLS 失败；最后 #7 为 415 次。只确认列出的业务接口成功，不能称所有流量都能解密。
- 浏览 Wishly 肯定语页面时应用自动发送 `affirmation/view/add`，没有点击生成、签到、购买或发布；不能把这轮描述为服务器完全无写入。
- 拒绝首次 VPN 授权后 #2 为失败零记录，原 Clash 仍连接；用户随后明确允许，重试成功。
- 进入接口后返回仍为真机入口、同一控制器与已勾选实验确认，不再跳回模拟器。重开桌面不自动开启真机抓包。
- 每轮停止均停止录制/隧道，但这台手机的 `uiautomator dump` 返回 137，自动点击 Clash 连接未成功。由验收代理读取手机界面并点击原“点此启动”，随后桌面“检查网络恢复”确认为 stopped。这是已验证的辅助恢复路径，不算全自动恢复通过。
- 最后核对 Clash 为规则模式、配置“自动”、原 US 组与美国节点；26 个原 APK SHA-256、Android 全局代理 null、Mac 系统代理、原 ADB 转发/反向映射与基线一致。助手只余状态文件，临时隧道与密钥已清理。

## 复审补修与剩余验证

- 首次没有助手时 `pm path` 非零不再误报 USB 失败，使用精确包名列表判断，真正 USB 失败仍传播。
- 代理子进程启动失败也先创建空归档，历史不会因缺少索引而不可读。
- 主机两次检查单一 UID，助手在授权前和启动隧道前拒绝 sharedUserId、系统 UID 和非主用户。仅声明 launcher 查询范围，不增加读取其他应用私有数据的权限。
- 停止使用新的随机确认令牌；助手主线程先通过 `finishActivity` 关闭自己发起的授权页，再返回匹配确认。桌面只终止本项目助手进程以排空延迟启动，确认退出后才恢复原 VPN；无法确认时保留恢复标记。`cancelled` 为终态，不再继续续租。
- HTTPS authority 校验支持与目标端口一致的非 443 端口，仍拒绝域名/端口不匹配，不改原请求内容。
- `finishActivity` 使用 Android 官方的关闭自身子 Activity API：[Activity 文档](https://developer.android.com/reference/android/app/Activity#finishActivity(int))。
- 必须明确保留的实机缺口：最终停止协议下授权未决时取消/迟到同意的竞态、真实拔线后的 20 秒超时，以及第二台设备的新协议复验。单元测试和独立 worker 租约测试不能替代这些硬件证据。
- 本轮不推送、不发包，不覆盖 `/Applications` 已安装版本。

## 最终验证记录

文档优化约束（2026-11-12）：第 14 节使用“适用范围、首次准备、四步操作、停止恢复、故障处理”的结构。按钮须对应当前 `AndroidPhysicalCopy`；安装和 VPN 确认由本人操作，拒绝后需等待结束/恢复再重试，不要求关闭安全保护。单应用、VPN 替换影响、15 分钟时限、辅助恢复与未完成硬件验证均不得省略。只修改说明，不将文档更新表述为功能或发布验收完成。

文档验证结果：9 个操作名称与现有入口/文案对应，7 个小节和 4 步主流程完整，内部跳转可解析，模拟器前置条件不再混用于真机。已补充误拒绝后的重试、正式包/测试包独立轮次、换机/换电脑与恢复操作；差异格式检查通过。此结果仅覆盖文档，不改变下方产品验收边界。

- Swift：`swift test --package-path macos-native`，196 项通过，另有 1 项显式 opt-in 跳过。
- 后端：`.venv-console/bin/python -m unittest tests.test_android_physical_desktop tests.test_android_physical_service tests.test_android_physical_api tests.test_android_physical_capabilities tests.test_ios_results tests.test_ios_capture tests.test_ios_setup tests.test_ios_lifecycle`，98 项通过。
- 既有链路回归：取消 `CAPTURE_DEVICES_CONFIG`，关闭默认设备种子，在新的 `CAPTURE_RUNTIME_DIR` 中运行 `tests.test_console_api tests.test_console_core tests.test_capture_retention`，197 项通过。此前空文件及不存在的设备配置导致测试导入失败，不是产品测试通过；隔离环境修正后完整重跑。
- 助手：5 项 Java 测试通过（4 项租约、1 项应用 UID 隔离）；独立代理 `CAPTURE_TEST_PHYSICAL_WORKER=1` 租约实测 1 项通过。
- 最后停止协议的新版助手已安装到本机指定 PHK110。在空闲状态验证新的停止令牌被确认、助手进程退出、原 Clash 仍连接；没有把这一结果当作授权弹窗竞态验收。
- 构建：`AI_CAPTURE_BUILD_ID=android-physical-qa-20261112 bash macos-native/scripts/build-app.sh` 成功；`codesign --verify --deep --strict macos-native/build/抓包工具.app` 和 `git diff --check` 均通过。
- 二次只读代码复审未发现剩余可操作 P1/P2；这不是硬件测试。最终确认无实验抓包 worker，活动 VPN 为原 Clash，保留上方明确列出的硬件缺口与辅助恢复限制。

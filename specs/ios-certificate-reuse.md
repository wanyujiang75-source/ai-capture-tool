# iPhone Certificate Reuse Implementation Plan

**Goal:** 同一Mac正常重启和隔天抓包不要求重装证书或重填专用节点。

**Architecture:** 长期身份与临时worker分离。一年期CA、独立随机认证、固定端口与检查标识存入本机Keychain；运行时临时目录仅存worker必要材料，权限700/600，退出删除。非敏感元数据用于展示重连入口，不构成ready证据。

**Tech Stack:** Python 3 / cryptography / macOS Security.framework / mitmproxy / SwiftUI。

## 单项 IOS-C1 契约

- 新版身份默认365天，不在每次重启时续期；证书notAfter、服务expires_at与手机描述文件RemovalDate对齐。到期/损坏/Keychain拒绝不悄悄生成另一张CA，不降级为长期明文文件。
- Keychain只操作本工具service与运行目录哈希account；不读取其他密码，不通过命令参数传递私钥，不同步iCloud。通过注入存储运行普通测试；真实Keychain仅使用独立测试namespace并清理。
- 新建身份首次选择空闲端口；重连只复用原端口，冲突明确报错，不改端口/密码或结束其他程序。Mac地址变化保留证书，提示更新本工具路由；不声称手机节点会自动更新。
- 启动不监听、不录制；用户点击准备/重新连接才恢复代理。每次进程重启均从waiting_phone开始，需当前连接的认证HTTPS检查；旧状态/历史记录不恢复ready。
- 普通停止录制保留连接。退出关闭代理并删除临时CA/config/profile，但保留Keychain身份。结束连接保留现有手机恢复确认，并撤销Keychain身份；再次创建才换证书。
- 旧版恢复标记没有新版身份，仍要求移除旧手机配置再结束连接；不能假称已复用已删除的旧CA。当前手机因此仍需一次迁移，之后才可复用。
- 手机VPN、原节点/订阅/DNS/FINAL不变；不在本轮发送、安装、信任证书或改手机路由。不实现小火箭无损导入，不宣称整体验收完成。

## 执行步骤与验收

1. 先在 `tests/test_ios_identity.py` 覆盖Keychain存储注入、365天真实证书、重复加载、拒绝/丢失/损坏/到期、退出后重建相同端点、原24小时边界不停止、旧版恢复阻断和占用端口保护。用现有内嵌Python运行并记录RED。
2. 新增 `ios_keychain.py` 限定服务的SecItem适配器；`ios_pairing_identity.py`管理身份生成、校验、元数据与撤销。修改setup/worker使用临时副本，不改变HTTP(S)采集范围。新profile不含私钥，使用绝对RemovalDate。
3. Swift测试覆盖 `can_resume` 兼容、重连按钮、重连不代表ready、不覆盖用户SSID、复用证书说明和旧版失败状态。更新Controller/View/集中Copy，不展示密码或底层原始错误。
4. `CAPTURE_TEST_IOS_PROXY=1`真实隔离代理连续3轮退出/重开，同一信任上下文与认证均HTTPS200；未经认证407，未检查不能录制，正常退出无worker/临时密钥残留；复核实际CA指纹和端口一致。
5. `CAPTURE_TEST_IOS_KEYCHAIN=1`仅写读删独立命名空间测试条目；无授权时明确失败，不访问其他Keychain条目。
6. 运行相关Python回归、`swift test --package-path macos-native`、构建和 `codesign --verify --deep --strict`；只在隔离运行目录查看新版重连UI。更新使用说明和证据，完成后本地任务提交，不推送。

原计划A2的24小时有限期由本任务最新需求覆盖，其下载票据、自动导入等内容仍未实施。实现无需等待A1，因为本任务只复用已有人工配置通道。

参考：[Apple profile top-level schema](https://github.com/apple/device-management/blob/release/mdm/profiles/TopLevel.yaml) 的RemovalDate是绝对移除时间；[Apple Keychain generic password](https://developer.apple.com/documentation/security/ksecclassgenericpassword)限定service/account，长期材料不落普通配置文件。

## 本地验收记录（2026-11-03）

- TDD：缺少身份模块/Swift复用字段、profile UUID不稳定先RED；进一步复现元数据中断临时文件阻塞重连、配置写入失败留下私钥副本、轮询覆盖SSID、操作失败被刷新抹去，修复后通过。
- `python3 -B -m unittest -q tests.test_ios_identity tests.test_ios_setup tests.test_ios_capture tests.test_ios_results tests.test_ios_lifecycle tests.test_console_core tests.test_console_api`：249项通过，9.251秒。使用应用内嵌Python；普通测试注入内存存储。
- `CAPTURE_TEST_IOS_PROXY=1 CAPTURE_TEST_IOS_KEYCHAIN=1 python3 -B -m unittest -v tests.test_ios_setup_integration tests.test_ios_keychain`：4项通过，8.567秒。跨两天身份、三轮真实代理进程重启保持同CA/凭据/端口，HTTPS200；未认证407，Mac自检不冒充手机ready，未ready禁止录制；正常退出删除运行材料。
- Keychain追加同一Python的独立子进程读取测试：1项通过，0.133秒。仅访问随机account的独立测试service，创建/重复拒绝/跨进程读取/删除及删除后不存在均通过。
- `swift test --package-path macos-native`：最终119项、17 suites通过，6.765秒。完整测试首次在既有NSWindow测试上崩溃；单独重现并用NSZombieEnabled确定close重复释放后，测试设置`isReleasedWhenClosed=false`，未跳过任何测试。
- `AI_CAPTURE_BUILD_ID=ios-c1-reuse-20261103 macos-native/scripts/build-app.sh`完成；内嵌新模块导入通过，最终`codesign --verify --deep --strict --verbose=2`通过。第一次手动启动Python视觉fixture未用`-B`而生成pycache使资源封印失效；重新完整构建并以`-B`验收后，运行后签名通过。产品RuntimeManager已有禁写bytecode设置，没有改动。
- 原生隔离窗口：暂停/重连入口、修改SSID后多轮刷新不覆盖、未验证禁止开始抓包、已复用默认折叠安装说明、展开补装说明、地址变化只提示更新测试路由、失败不展示原始JSON/凭据、退出保留证书但提醒恢复路由均检查。`tests/ios_native_ui_fixture.py`只监听loopback，无代理/真机/真实流量；合成验收不能替代手机证明。
- 使用说明已同步；本轮没有向手机发送或安装新配置、修改VPN、原节点、订阅、DNS、默认路由或证书信任。当前旧证书仍需一次人工迁移。没有推送或发布安装包，其他IOS-A/D任务保持原状态。

### 最终复核补充

独立只读审查提出四项重连/撤销风险，均在新增测试中实际RED复现后修正：

- 首次状态已到waiting_trust或ready时，prepare不能按超时关闭健康worker；仅接收本次worker的状态，验证门槛仍由认证HTTPS回调控制。
- 元数据缺失或写入失败不应让“结束连接”跳过Keychain撤销；显式结束始终删除本工具限定account，无须读取其他条目。
- 本机真实loopback对照复现TIME_WAIT导致原端口假占用；probe使用与listener一致的SO_REUSEADDR并执行listen检查，保留真实活动listener冲突保护，不启用SO_REUSEPORT、不结束进程。
- 地址改变后启动失败不能吞掉提醒；route_pending持久化，直到新连接实际ready才清除。

最终身份测试15项通过；相关Python扩展为253项通过（9.884秒）。最后追加真实活动listener保护断言后，15项身份测试再次通过（2.301秒）。Swift最终源码未再改变，复用119项已通过结果与原生视觉证据。

- 最终真实代理与Keychain合并验收4项通过（12.564秒），包括独立子进程读取同一测试Keychain条目；测试条目均清理。
- 最终全部代码已重新构建为`ios-c1-reuse-20261103`；从`/tmp`运行、以App内嵌backend优先的`PYTHONPATH`执行15项身份测试通过（2.000秒），确认打包内容而非工作树通过测试。
- 最终`codesign --verify --deep --strict --verbose=2 macos-native/build/抓包工具.app`与`git diff --check`通过。App为本地开发签名构建，不是公证发行包。
- 独立审查者复核四项修正，未发现遗留的具体问题；其结论为只读复审，实际测试和构建结果由主任务执行验证。
- 本轮只完成IOS-C1。本地隔离视觉fixture和窗口已退出，未发送手机配置或改变原VPN；旧手机证书迁移及真实手机重连不计入本次通过项，其他任务不因此标记完成。

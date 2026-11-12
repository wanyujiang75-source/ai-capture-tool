# Android 真机出网与连接状态实现计划

## 目标与约束

一个任务 ANDROID-NETWORK-READY：在已验证的单应用链路上补准入与生命周期证据。电脑 HTTP 代理负责外网访问；不声称两个 Android VPN 同时运行。原 VPN 节点/配置保持，其他应用不被抓取且不受原 VPN 保护。解密信任边界不变；不新增 CA、不改原包/Root。用户现用桌面和手机任务不因开发重启。

## 实现契约

1. 网络检查独立模块：手机只读检查 Wi-Fi；临时绑定 Mac 局域网地址的随机 TCP 监听，以每次随机值验证手机实际访问电脑，4 秒超时、有限输出、结束关闭。USB 仅传控制，不能把 USB 连接当局域网已通。
2. 真机出网需要电脑已启用的 HTTP(S) 代理。无代理/SOCKS-only/PAC-only 提示具体动作，不能自动切换直连。以 `/usr/bin/curl -q --proxy ... --noproxy ''` 做有界 HTTPS 检查（Google generate_204），保持 TLS 校验，禁用环境代理干扰，不跟随跳转、不读取正文、不提交账号数据。CONNECT 成功和最终 204 缺一不可；不把本地端口 connect 当联网成功。
3. 前置检查先于安装助手、写恢复日志、切换手机 VPN。准备和授权后仍复核，原代理端点锁定本轮；端点变更要求停止重试，不擅自跟随其他代理。
4. 助手 UP 仅为 connecting；通过 WireGuard getStatistics 的实际 handshake 才上报 connected。配置 keepalive，空闲时也能完成初始握手；旧握手超过 180 秒为断开，不用接口条数充当网络健康。手机状态写入单调采样序列，桌面发现采样停止不能继续报正在抓包。连接阶段上限 30 秒。
5. 桌面新增 checking_network / waiting_tunnel。未握手时归档保持 starting，不能显示抓包成功；手机授权后启动目标应用，使正常流量可建立握手，但不通过修改业务数据造流量。
6. 运行中每 10 秒复核手机局域网和锁定代理的 HTTPS。失败关闭本工具 worker、停止助手，再沿用原网络恢复；保存具体原因、错误码与网络摘要。不把停止等同于原 VPN 已恢复；原设备离线继续保留待恢复记录。主动取消优先，不重复启动或改手机。
7. 普通 UI 展示手机连接/电脑代理/外网检查摘要和明确动作，不展示 JSON。文档明确电脑代理需保持开启、手机同一可互通局域网、其他应用保护边界和退出恢复。

## 实施步骤（同一任务内顺序执行）

1. 新增 Python 准入/监测与服务生命周期回归、Java 握手状态、Swift 状态契约；先执行观察预期失败。
2. 实现独立网络检查、助手握手/采样、服务准入/监测/恢复；避免增长共享模拟器和 iPhone 网络模块。
3. 接入状态文案和说明；全部回归通过后完整构建并验证包内源码和签名。
4. 空闲后正常更新本机（先备份），在用户指定 StickerHub 选择第一个 Google 账号进行正常登录验收，不清数据、不退出其他账号。若有活动抓包则先等用户结束；密码/验证码/额外系统授权由用户完成。结果按网络接入、登录、Request/Response、原 VPN 恢复分别记录，不能互相代替。

## 验收命令与故障场景

- `.venv-console/bin/python -m unittest tests.test_android_physical_network tests.test_android_physical_service tests.test_android_physical_switch tests.test_android_physical_desktop tests.test_android_physical_api tests.test_android_physical_copy`（隔离 CAPTURE_RUNTIME_DIR）。
- `swift test --package-path macos-native`；`bash android-bridge/build.sh`。
- `AI_CAPTURE_BUILD_ID=network-ready-20261112 bash macos-native/scripts/build-app.sh`；严格 codesign 校验；本轮不推送、不发布 GitHub 包。
- 故障夹具：无 Wi-Fi/无 LAN 往返不得触发安装或写 marker；端口可连但 HTTPS 失败不得接管；代理端点变化不得继续转发或回退直连；无/过期握手不能显示 capturing；停止、取消、离线设备恢复记录不丢失。
- 网络自检使用自有临时监听或 mock，不断开真实用户 VPN 制造故障；实机正常链路与授权登录单独验收。

## 自审与证据

四项改造均有对应检查；只选择一个活动任务。新增状态保留旧 API 字段并兼容未知状态的禁用行为，禁止采集或展示代理凭据。180 秒握手有效期不是实时丢包证明；另用 10 秒局域网/HTTPS 检查缩短可观测断线时间。完整业务成功仍需真实请求响应，探针成功不能替代。

### 2026-11-12 实施与验收记录

- RED：网络模块缺失、Java 握手类缺失、Swift 不认识新状态均观察到失败；随后通过。扩大回归时曾误写两个不存在的测试模块名，纠正为仓库实际的 ios_capture/ios_results/ios_lifecycle 后重跑。
- 最终后端 134 项通过；Swift 202 项通过（另 1 opt-in 跳过）；Java 单元测试与 APK 构建通过。独立 worker 实际启动、仅目标应用配置、keepalive 及租约过期退出通过。
- 独立代码复核发现准备后需复查网络、取消竞态、启动后旧快照、租约预算、探针连接关闭与清理异常等问题，已逐项修复并增加回归；复核确认全部清除。探针有绝对截止时间和取消检查；网络阶段之间续约，启动的两次阻塞调用之间检查取消并续约；最终提升状态前重新读取助手状态。
- 完整构建及严格签名通过，最终构建标识 `network-ready-20261112-r3`。旧正式安装备份于 `CaptureToolBackups/20261112-before-network-readiness.EWylGU/抓包工具.app`，不清理运行目录或其他设备恢复记录。
- 本机 `/Applications/抓包工具.app` 已更新为 r3，安装后严格验签与构建标识核对通过；原生 UI 已打开 Android / 真机，后端为 idle，未重新启动抓包。r2 另存为同一备份目录下 `network-ready-r2.app`；重启后当前手机仍无活动 VPN、HTTP 代理为 `null`，旧 PHK110 恢复文件摘要不变。
- 真机 PKG110 / Android 16，StickerHub Play 版 `com.meta.inno.sticker` 3.18.14(195)：桌面开始 #101，手机到 Mac 往返及现有电脑代理 Google HTTPS 通过，助手实际握手 `connected / sequence=44`，桌面持续轮询正常；不是只凭 VPN UP 判断。
- 用户授权选择第一个 Google 账号，实际进入账号选择并选择首项后，应用提示“登录服务出现问题，请稍后重试”。本次结束为 0 请求、0 响应、39 次客户端 TLS 失败；有界应用日志至少一处显示 `Certificate blocklisted by public key`（CctTransportBackend）。这不能单独证明全部登录失败的根因，跨应用 Google 服务也未被本轮单应用范围采集。没有修改证书、原 APK 或扩大采集范围。
- 通过桌面停止，当前设备恢复到测试前无活动 VPN、系统 HTTP 代理 `null`；本轮 recovery.json/临时目录已清理。Mac 已有代理仍为原端点。旧 PHK110 待恢复文件 SHA-256 保持 `3a2bb229461addc57d3c15775ac9ccf5f40b94a56f53b326dbbce69259dacb27`，未冒充已恢复。
- **结论：网络准入、真实握手、出网检查、停止及保护代码完成；StickerHub Google 登录和完整业务正文验收未通过。任务保留 BLOCKED，不宣称真机兼容性全面通过。** 本轮不改 TLS 实现、不 Root、不改原包，不推送或发布 GitHub；后续需独立定位该版本的登录/HTTPS 兼容性。

# iPhone 真机统一桌面抓包 V1

## 已确定需求

- 四个导航不变：抓包、安装应用、接口、日志。抓包页增加 Android/iPhone 选择，默认 Android。
- iPhone 连接引导复用现有配置生成及系统共享；Wi-Fi 名称自动读或手填，密码只由用户在手机输入。
- 项目包含名称与目标域名，预设 PokeHub，支持用户添加/修改项目；按域名而非前台应用身份归属。
- 连接准备只解密检查域名，用户明确开始后才记录目标域名。停止记录后继续提供透传，保留同一次连接。
- 再次开始生成新抓包记录、复用证书/代理；结束连接要求手机删除配置，随后销毁代理认证与私钥。
- 接口统一展示、来源选择、URL 搜索、完整地址、Request/Response/cURL、清空显示不停止记录。
- 第一版一台 iPhone，可与 Android 并存；无 iOS 安装/日志/弱网/越狱/绑定绕过。安装与日志页面明确提示仅支持 Android。

## 实现契约

连接服务保留 `/api/ios-setup` 兼容入口，增加项目列表/保存与记录 start/stop 路由；原 `/stop` 仍代表结束连接。状态分别提供 `connection_state`、`recording_state`、`session_id`、`flow_count` 和可恢复错误。保留旧 `phase` 字段映射，旧客户端不能静默变成自动开始录制。

项目域名使用标准化 IDNA 主机名或明确 `*.example.com` 子域名规则；拒绝空范围、全局通配符、URL 路径、用户信息、控制字符和内置检查域名。主域与子域匹配边界明确，项目变更不影响已运行记录的快照。

控制平面由后端以原子文件下发有序版本命令，子进程确认已应用的版本。服务仅在确认后返回开始/停止成功，超时按失败处理并结束自有 worker，不能误报已停止。停止先禁止写入，关闭本代理持有的连接以重建透传；开始切换同理，旧请求不能串入新记录。

记录写入独立 iOS 抓包目录与 SQLite 索引，使用现有 capture_sessions 的整数 ID、`platform=ios`、`mode=ios-http-proxy`。iPhone 使用 `ios-<connection>` 标识，不伪装 Android AVD 或写入其设备池。后端按模式分发结果与停止，Android 启停、校验、安装互斥不受 iOS 记录影响。

每条元数据及正文有界：列表分页 200；正文内联 256 KiB、单段落盘最多 8 MiB；每轮最多 10,000 条或 500 MiB，达到上限停止记录并保留透传。请求与无响应也可显示。完整URL、方法、响应码、时间、耗时、Request/Response元数据按现有格式输出；大请求 cURL 使用本地文件引用，截断请求不生成伪完整 cURL。只存本地，日志不泄露正文或凭据。

连接状态：未连接/准备中/等待手机配置/等待 HTTPS 验证/已连接/需要恢复网络/失败。
记录状态：未开始/开始中/记录中/停止中/已停止/达到上限/失败。前端显示和按钮从状态生成。
记录与连接分别持有 generation/session ID；清空、切换来源、停启的过期响应不得恢复旧列表。

### D1 已实现接口契约

- `GET /api/ios-setup/projects` 返回 `{projects:[{id,name,domains}]}`；`POST /projects` 的可选 `id` 用于修改，缺省新增。最多100个项目，总配置不超过512KiB。
- `POST /api/ios-setup/recording/start` 接收 `{project_id}`，必须先有真实手机HTTPS检查证据；`POST /recording/stop` 无需删除手机配置。原 `/stop` 仍需 `phone_configuration_removed=true`，代表结束整个连接。
- 状态字段 `connection_state` 为 `idle/preparing/waiting_phone/waiting_trust/ready/needs_cleanup`；`recording_state` 为 `idle/recording/stopped/limit_reached/failed`。`phase` 保留旧客户端兼容，`flows` 始终为空，正文只能从共用结果API读取。
- `session_id`、`project` 为当前或最后一轮记录；`flow_count` 是该轮已入库请求数，尚无响应也计入。手机地址变化关闭当前记录并要求重新HTTPS检查，不自动恢复抓包。
- 共用 `/api/captures/{id}/flows?cursor=0&limit=200` 对iPhone返回 `{flows,total,cursor,next_cursor}`。`cursor` 是单调变更序号；有 `next_cursor` 时继续分页，无时保存 `cursor` 用于下次增量同步，同一flow的后续响应会以同一ID更新。Android旧返回不变。
- 每页最多200条且摘要约1MiB；单条完整元数据最多128KiB，超限停止记录并显示限额原因，不伪造截断后的完整URL。SQLite索引保留最多32MiB，正文预算预留索引和事务日志。
- 共用 detail/cURL 路由按mode分发。未完成或已截断的请求不能生成可重放cURL，大请求使用当前本地正文文件引用。二进制正文以文件信息展示，不按文本渲染。

停止后原有连接只透传不记录；WebSocket仅透传且不保留消息历史。上游 TLS 校验不得关闭。
正常退出提示手机恢复网络；允许明确继续退出。异常退出回收自有代理并保留恢复标记；不自动恢复录制。
地址或网络变化时重新检查并提示配置过期；不误报准备成功。临时配置最多24小时，同次连接可复用，结束后需重新安装新配置。

## 任务与验收

1. IOS-D1 后端：域名项目、连接/记录分离、命令确认、统一会话和有界结果、生命周期隔离。Python RED/GREEN；受控真实 HTTP(S) 启停/转发/隔离/限额验证；相关 Android 回归。
2. IOS-D2 原生桌面：平台选择与统一工作流、连接引导、来源与分页、安装/日志提示、退出恢复、精准文案。Swift RED/GREEN；构建与原生正常/空/加载/失败状态验收。
3. IOS-D3 最终验收交付：实际 iPhone 安装配置、信任、PokeHub目标业务Request/Response，第二个受控域名，Android共存，停止再开始、结束恢复；最终本地安装包、签名、新用户说明及可复现证据。仅本地提交，发布需另行请求。

每轮只领取一个任务，持续目标覆盖全部三项。允许保留真实手机外部条件缺口，禁止把本机自检当作手机成功。

## 验收命令

- 项目内嵌 Python：`-m unittest -q tests.test_ios_setup tests.test_ios_capture tests.test_ios_results tests.test_console_api tests.test_console_core tests.test_device_network`
- 真实隔离代理：`CAPTURE_TEST_IOS_PROXY=1 python3 -m unittest -v tests.test_ios_setup_integration`
- `swift test --package-path macos-native`
- `python3 -m unittest -q tests.test_native_app_packaging`
- `macos-native/scripts/build-app.sh`；最终 App 深度严格签名检查。
- 原生桌面及 iPhone 实测记录，不能仅用测试数量代替。

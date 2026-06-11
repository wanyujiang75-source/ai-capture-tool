# 项目发现记录

## 当前实现状态

- 项目根目录是 `/Users/wan/AI抓包`。
- 本机 Web 控制台入口是 `http://127.0.0.1:7001`，启动脚本是 `scripts/start_console.sh`。
- 后端已使用 FastAPI，核心入口是 `capture_console/app.py`。
- SQLite 存储文件是 `runtime/console.db`。
- 控制台已有应用库、抓包启动/停止、历史任务读取、接口详情、cURL 导出能力。
- 当前 Web 服务启动和关闭时会清空抓包任务记录，但保留应用库和 `runtime/captures/` 原始文件。
- 当前环境已有 `npm`，React/Vite 可以正常构建，Web 服务优先使用 `web/dist`。

## 抓包底层能力

- 底层统一入口是 `scripts/ai_capture.sh`。
- Android 支持 `system` 和 `flutter-socks` 两种模式。
- `flutter-socks` 模式会清空 Android global `http_proxy`，避免 HTTP 代理和 SOCKS5 冲突。
- mitmweb 默认端口是 `9091`，代理端口是 `9090`，token 是 `android-capture`。
- 保留登录态模拟器是 `Medium_Phone_API_36.1 / emulator-5554`。
- 抓包结果落在 `runtime/captures/<session>/`，包括 `candidates.tsv`、`*.meta.json`、`*.request.*`、`*.response.*`。

## 主要约束

- 非 root Google Play 模拟器可以保留 Google 账号和 App 登录态，但部分 App 仍可能因为证书绑定、Flutter/Dart TLS、native socket 等原因无法解密。
- V1 不应误开其他模拟器，默认只能使用保留登录态的 `Medium_Phone_API_36.1`。
- 用户需要长期使用，必须避免端口、pid、Frida、exporter 脏状态导致下一次启动失败。
- 用户明确希望关闭项目后清除页面里的抓取链接记录。
- 用户明确要求计划书当前先做 Android 端，iOS 只需要预留入口用于后续实现。

## 规划原则

- Web 控制台只编排流程，不直接重写底层 ADB/Frida/mitmproxy 逻辑。
- 原始抓包文件不迁移、不改名，SQLite 只做索引和当前运行态缓存。
- 页面默认只监听 `127.0.0.1`，不做公网部署。
- 需要清晰标注敏感信息风险，因为页面会展示 headers、token、request body、response body。
- 当前任何实现任务都不得因为 iOS 预留入口而影响 Android 主流程稳定性。

## 规划书评审发现

- 2026-05-12：规划书已明确 Android 先行，但 P0/P1/P2 的执行顺序仍有压缩风险。建议先完成 P0 稳定性闭环，再进入搜索、报告、历史导入。
- 2026-05-12：iOS 预留入口已写入目标，但数据模型当前没有 `platform` 字段。若确实要为 iOS 预留实现空间，建议在 V1 就把平台字段作为只读/默认 Android 的结构预留。
- 2026-05-12：测试规划没有明确保护保留登录态模拟器的边界。集成和端到端测试需要禁止 wipe、禁止新建/误选 AVD、禁止清空 App 数据。
- 2026-05-12：报告导出和敏感信息策略之间还缺少约束。既然要原样展示 token/header，就需要定义导出报告是否包含敏感字段、是否需要显式确认。
- 2026-05-12：已实现 `platform` 数据字段，默认 Android；iOS 应用可作为预留条目存在，但启动抓包会返回 501，且不会触碰 Runner/ADB/Frida。
- 2026-05-12：已在 Runner 层拒绝明显破坏登录态的命令，包括 emulator `-wipe-data`、`avdmanager delete`、`adb shell pm clear`、`adb uninstall`。
- 2026-05-12：已在健康检查前加入 retained emulator 守卫，非 `Medium_Phone_API_36.1 / emulator-5554` 直接失败，避免误用其他模拟器。
- 2026-05-12：页面已补齐应用添加与选择流程；抓包动作现在围绕“当前目标应用”执行，iOS 应用条目可以保存但不会启动抓包。
- 2026-05-28：Google 登录失败根因偏向网络出口而非 APK 实现。无抓包会话、Android 代理为 `null` 时，GMS 登录页卡在 `Checking info…`；服务器到 `accounts.google.com`、`oauth2.googleapis.com`、`www.googleapis.com`、`play.googleapis.com`、`android.clients.google.com` 的 HTTPS/TCP 443 超时，模拟器对这些域名 ping 也失败。`connectivitycheck.gstatic.com` 可达不足以证明 Google 登录链路可用。
- 2026-05-28：模拟器网络时间未成功同步，`dumpsys network_time_update_service` 显示 `mLastSuccessfulNtpServerUri=null`、`mTimeResult=null`，对应日志中大量 `No network time available`。Google 账号状态仍为 `Accounts: 0`。
- 2026-05-29：7890 代理能解决 Google 登录页加载问题。将 `device-1` 的 Android `http_proxy` 设置为 `10.0.2.2:7890` 后，GMS 登录从 `Checking info…` 成功进入 `Sign in - Google Accounts` 邮箱输入页。当前阻塞点变为模拟器没有 Google 账号，需要人工输入账号完成设备级登录。
- 2026-05-29：完成 Google 登录后，MelodyCraft 登录后首页可被抓包，session 19 捕获 78 条候选流量、60 条 200 响应、44 条 JSON 响应，详情接口和 cURL 导出可用。
- 2026-05-29：MelodyCraft 在 `flutter-socks` 抓包运行中出现系统 ANR 弹窗，界面仍能看到登录后首页并已产生接口流量。后续若要做长时间自动化遍历，需要单独排查 ANR 与 Frida hook、代理链路或 App 自身主线程阻塞的关系。
- 2026-05-29：模拟器预览页卡顿和画面过大主要来自预览服务自身配置：外层舞台原先最小高度 870px，1440x900 浏览器下页面总高度 993px；同时默认沿用 `smooth` 推流档 4Mbps/30fps/720x1600。已改为视口内自适应和默认低延迟档。
- 2026-05-29：预览页此前显示 10 个“可启动 AVD”的原因是 `/Users/jenkins/emulator-preview` 直接调用 `emulator -list-avds`，展示 Jenkins 账户下所有 AVD；AI 抓包工具项目实际启用设备只有 `Capture_AVD_01/02/03`。已将预览服务 API 收敛为读取项目设备配置并只返回启用 AVD。
- 2026-06-01：Google 登录完成后，`device-1 / Capture_AVD_01` 可以稳定复测 MelodyCraft 登录后业务流量；session 20 捕获 129 条候选流量、90 条 200 响应、93 条 JSON 响应，明显高于此前 session 19 的 78 条候选流量。
- 2026-06-01：抓包模式仍会按设计清空 Android `http_proxy`，停止后需要恢复维护代理 `10.0.2.2:7890`，否则后续 Google 相关页面可能再次受服务器直连网络限制影响。
- 2026-06-01：预览服务的 AVD 收敛结果保持有效，API 仍只返回项目启用的 `Capture_AVD_01/02/03`，没有重新暴露 Jenkins 账户下的其他历史 AVD。
- 2026-06-10：本机独立项目验收发现 React 入口 `web/index.html` 仍保留旧标题 `AI抓包工具`，会影响浏览器标签和 release 首屏识别；已改为 `TraceDeck`。
- 2026-06-10：本机旧 runtime 仍可能保留 MelodyCraft/PokeHub 等历史应用记录，但干净 release 默认不包含 `runtime/` 和 `config/local.json`，新用户启动仍是空设备/空历史状态。验收时应区分“当前开发库历史数据”和“发布包默认状态”。
- 2026-06-10：非 MelodyCraft 抓包通用性已用系统 Chrome 验证。临时 App 使用 `com.android.chrome/com.google.android.apps.chrome.Main` 和 `system` 模式，能启动抓包、产生 flows、查看详情、导出 cURL。
- 2026-06-10：`system` 模式停止抓包时存在 Android 系统代理残留风险。根因是普通 `/api/captures/stop` 和 `/api/captures/{session_id}/stop` 只停止进程，没有像 release/system sleep 一样调用 `clear_android_proxy()`；已修复并补回归测试。
- 2026-06-10：pip 首次安装受本机网络/代理环境影响明显。固定直接依赖版本可以避免回溯和 Frida 版本冲突；遇到 `127.0.0.1:<port>` 代理 502 时，可用 `PIP_PROXY=` 关闭 pip 代理或显式配置可用代理。
- 2026-06-10：Browser DOM 验收可用，但截图接口本轮对当前页面连续出现 CDP screenshot timeout。页面关键验收可以通过 DOM 指标覆盖；若需要最终视觉截图，可改用系统截图或独立 Playwright 环境补测。
- 2026-06-10：本机卸载重装验收通过。清理 `.venv-console`、`web/node_modules`、`web/dist`、`runtime`、`config/local.json` 后，重新执行 `./setup.sh` 和 `OPEN_WEB=0 ./start.sh` 可恢复可用控制台；页面和 API 均进入空项目状态。
- 2026-06-10：重装后的非 MelodyCraft 抓包复测继续通过。Chrome/system 模式 session 捕获 13 条 flow，详情与 cURL 可读；停止后 Android 代理恢复为 `null`，9090/9091 无残留监听。
- 2026-06-10：调试启动/停止接口时出现的 JSON 解析失败并非后端响应无效，而是 `zsh echo "$JSON"` 会解释 `\n` 转义导致测试管道生成非法 JSON；后续校验 API JSON 应使用 `printf '%s' "$JSON"`、`curl -o` 后读取文件，或直接用 Python/requests 读取响应体。
- 2026-06-10：真实模式矩阵证明不存在单一万能抓包模式。Chrome 在 `system` 下可捕获流量，MelodyCraft 在 `system` 下启动成功但无 flow；MelodyCraft 在 `flutter-socks` 下可捕获 `POST www.blockdance-test.xyz /aisong/portal/user/livestatus`。后续应实现 auto 模式和模式成功记忆，而不是把任一模式设为全局万能默认。
- 2026-06-10：页面轮询会影响抓包启动状态迁移。启动请求创建 `starting` session 后，页面轮询触发 `reconcile_active_session()`，曾导致 `sqlite3.IntegrityError: UNIQUE constraint failed: capture_sessions.device_id`，表现为 `flutter-socks` 500。已修复为 `starting` 状态不被 reconcile 改写，并补回归测试。
- 2026-06-11：auto 抓包策略已落地。`auto` 会优先使用 App 的 `last_success_mode`，否则依次尝试 `system`、`flutter-socks`；实际 session 仍只保存底层模式，避免 runtime 把 `auto` 当作抓包脚本模式。
- 2026-06-11：冒烟校验可以处理“启动成功但无可解析接口”的情况。真实 Melody Smoke 校验中，`system` 30 秒无 JSON 后自动清理并切到 `flutter-socks`；`flutter-socks` 在无人操作场景仍无 JSON，最终返回 warning 和完整 `mode_attempts`，未残留 Android 代理或 9090/9091 进程。
- 2026-06-11：非 Melody 通用抓包继续可用。Chrome Smoke 使用默认 `auto` 启动后实际选择 `system`，访问 `http://example.com/` 后 session 10 捕获候选 flow，详情接口和 cURL 导出可读；停止后 `last_success_mode=system`。

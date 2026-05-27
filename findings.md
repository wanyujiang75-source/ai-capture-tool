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

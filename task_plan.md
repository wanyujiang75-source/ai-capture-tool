# 长期安卓抓包平台规划任务

## 目标

基于当前 `<project-root>` 工作区已有能力，输出一份可执行、可追踪、适合后续迭代的长期安卓抓包平台规划书。

## 范围

- 当前重点是 Android 抓包平台，iOS 只保留扩展入口。
- 不重写底层抓包能力，继续复用 `ai_capture.sh`、mitmproxy、Frida、`runtime/captures`。
- 规划需要覆盖产品形态、架构、数据、流程、测试、风险、里程碑和后续迭代。

## 阶段

| 阶段 | 状态 | 说明 |
|------|------|------|
| 1. 读取当前项目状态 | complete | 已读取 README、FastAPI 入口、抓包脚本、核心测试 |
| 2. 提炼现状与问题 | complete | 已整理当前能力、边界、已知约束 |
| 3. 编写详细规划书 | complete | 已创建 `docs/长期安卓抓包平台规划书.md` |
| 4. 记录发现与进度 | complete | 已创建 `findings.md` 和 `progress.md` |
| 5. 调整 Android 先行边界 | complete | 已明确 iOS 只预留入口，不进入当前实现范围 |
| 6. 执行 P0 第一批稳定性改造 | complete | 已补 platform 字段、iOS 禁止执行、登录态模拟器守卫、破坏性命令拒绝 |
| 7. 页面支持应用添加与选择 | complete | 已在 React 页面和静态兜底页补齐平台选择、目标应用选择和 Android-only 启动保护 |
| 8. 独立可下载项目重构设计 | complete | 已输出并评审独立可下载项目重构计划 |
| 9. TraceDeck 本机项目化实现 | complete | 已落地 macOS 本机配置、空默认状态、设备发现、通用 App 添加、setup/start/release 入口和发布包验收 |
| 10. TraceDeck 自主收尾验收 | complete | 已完成页面/API/AVD/非 MelodyCraft App 抓包/release clean smoke 验收，并修复 system 停止代理残留问题 |
| 11. 本机卸载重装验收 | complete | 已清理本项目可再生产物后重新执行 setup/start，并完成页面、API、设备发现、Chrome/system 抓包和自动化回归验收 |
| 12. 抓包模式矩阵测试 | complete | 已真实测试 Chrome/MelodyCraft 的 system 与 flutter-socks，修复页面轮询导致 flutter-socks 启动 500 的 session race |
| 13. auto 抓包模式与真实验收 | complete | 已实现 auto 候选模式、上次成功模式记忆、冒烟校验 fallback 和 UI 提示，并完成 Chrome/Melody 真实验收 |

## 当前决策

- 规划书采用 V1.1/V1.2/V2/V3 分阶段方式，避免一次性过度建设。
- 短期优先解决长期使用稳定性、会话生命周期、接口检索、导出、错误提示。
- 当前执行范围只做 Android；iOS 只在页面、数据模型和路由层预留入口，暂不实现抓包流程。
- 中期可以做自动化操作录制和多设备能力；iOS 真正抓包实现需要作为独立后续阶段评审。
- P0 已开始执行，先落地 Android-only 执行边界和保留登录态模拟器保护。
- 页面已支持新增应用时选择 Android/iOS 预留平台，并在抓包前显式选择当前目标应用；iOS 条目只可保存，不可启动抓包。
- 2026-06-05：新重构方向修正为“独立可下载项目”。服务器/Mac mini 部署不再是主路径，后续设计应围绕别人下载项目后，在自己电脑上完成安装依赖、启动控制台、配置设备、添加任意 App、运行抓包。
- 2026-06-05：TraceDeck 已完成首轮本机项目化实现。默认不再种入 MelodyCraft 或固定 AVD；设备从 `adb devices` 发现；README、入口脚本和发布包改为 macOS 本机下载使用路径。
- 2026-06-10：TraceDeck 自主收尾验收已完成。最新 release 为 `release/TraceDeck-20260610-141015.tar.gz`；非 MelodyCraft App 通用抓包路径已通过 Chrome/system 模式验证；普通停止抓包入口已补 Android 代理清理。
- 2026-06-10：本机卸载重装验收已完成。清理 `.venv-console`、`web/node_modules`、`web/dist`、`runtime`、`config/local.json` 后，重新安装和启动成功，Chrome/system 抓包复测通过。
- 2026-06-10：抓包模式矩阵测试已完成。结论是不存在单一万能模式，应实现 auto 策略；同时已修复 `starting` session 被页面轮询 reconcile 改写导致 `flutter-socks` 启动 500 的问题。
- 2026-06-11：auto 策略已实现。新建 App 默认 `auto`，启动抓包会记录尝试模式，停止成功后记忆实际成功模式；冒烟校验会在无 JSON/失败时停止临时抓包、清理代理并尝试下一个候选模式。

## 完成标准

- 有一份独立 Markdown 规划书。
- 规划书能直接指导下一轮实现。
- 规划文件能支持后续 `/clear` 后恢复上下文。

## 2026-08-07 桌面端完整功能验收

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| 14. 验收范围与状态基线 | complete | 已对齐工作树、App 内嵌后端、设备、端口、Doctor 和发布边界 |
| 15. 自动化与构建验收 | complete | 整包签名、公证门禁、内嵌运行时和开发归档已验收 |
| 16. 桌面端运行时验收 | complete | App 自托管后端、受限 PATH HTTP smoke、AppKit 退出清理均通过 |
| 17. 环境与设备准入验收 | complete | Doctor、Google Play、网络、Google 登录策略与 Frida 均已实机验证 |
| 18. Jenkins 与 APK 安装验收 | complete | Jenkins 最新包、未就绪提示、真实安装与应用同步均已验证 |
| 19. 抓包闭环验收 | complete | App、session、实时 flow、request/response/cURL、Logcat 和停止清理均已验证 |
| 20. 分发包审计与最终复测 | complete | 隐私边界、内嵌运行时、签名门禁与全量回归已完成；正式公证仍需公司凭据 |

本轮详细验收约束见 `goal.md` 和 `specs/functional-acceptance.md`。

### 本轮错误记录

| 错误 | 尝试次数 | 当前处理 |
| --- | --- | --- |
| `GET /openapi.json` 首次返回 502 | 1 | 根因是 shell 设置 `ALL_PROXY/http_proxy/https_proxy=127.0.0.1:7897` 且没有 `NO_PROXY`；显式直连返回 200。产品的桌面端 APIClient 已禁用代理，不需改代码 |
| API 摘要 jq 结构假设错误 | 1 | `/api/apps`、`/api/captures`、Jenkins 响应不是验收命令假设的顶层数组；改为先读取实际 JSON 类型后再构造断言，不修改产品代码 |
| `.app` 整包签名校验失败 | 1 | 已调整资源打包与整包签名顺序；真实构建、`codesign --verify --deep --strict` 和回归测试均已通过，正式公开分发仍需公司 Developer ID 与公证凭据 |

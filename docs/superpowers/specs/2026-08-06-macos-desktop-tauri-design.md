# AI抓包工具 macOS 桌面端 Tauri 重构设计

## Summary

把当前本机 Web 控制台重构为 macOS 桌面端应用。桌面端使用 Tauri 承载现有 React 控制台，启动并管理本机 FastAPI 后端 sidecar；FastAPI 继续复用现有 `adb`、`emulator`、Frida、mitmproxy 和 `scripts/` 抓包链路。V1 的目标是形成可打开、可检查、可抓包、可退出清理、可打包分发的 macOS `.app/.dmg`，而不是重写抓包底层。

设计原则是“桌面壳接管生命周期，抓包核心保持稳定”。当前项目已经有可用的接口分析、设备发现、App 管理、Frida 准入、抓包启动、请求响应展示和 cURL 导出能力，桌面端只补齐用户入口、运行目录、进程归属、依赖检查和打包边界。

## Approved Direction

采用 `Tauri + 现有 React 前端 + FastAPI sidecar + 现有脚本复用`。

不采用 Electron，原因是 Electron 运行时和 Android 模拟器叠加后内存压力更高；不采用 Swift/AppKit 全量重写，原因是会重写已有 UI 和业务逻辑，风险大、周期长。Tauri 官方支持 macOS app bundle 构建，也支持 sidecar 外部二进制进程模型，符合当前“桌面壳 + 本机后端”的形态。

外部依据：

- [Tauri macOS app bundle 文档](https://v2.tauri.app/distribute/macos-application-bundle/)说明 `.app` 是 macOS 应用包格式，并可通过 Tauri CLI 在 Mac 上构建 app bundle。
- [Tauri sidecar 文档](https://v2.tauri.app/develop/sidecar/)说明外部二进制可以作为 sidecar 启动，并需要在 capability 中授权执行或 spawn。
- [Tauri 分发文档](https://v2.tauri.app/distribute/)说明 macOS 可通过 App Bundle 或 DMG 分发，正式外部分发涉及签名和 notarization。

## Current State

当前项目是本机 Web 工具：

- `web/` 是 React/Vite 前端。
- `capture_console/` 是 FastAPI 后端。
- `scripts/` 保存 adb、emulator、Frida、mitmproxy、抓包 exporter 和辅助脚本。
- `start.sh` 和 `scripts/start_web_services.sh` 负责命令行启动后端并打开浏览器。
- `release/package.sh` 生成源码 release 包，不生成 macOS `.app`。
- `runtime/` 保存本机运行数据，包括 SQLite、抓包结果、上传 APK、pid、日志和临时 launcher。

桌面端重构不能破坏这些能力。现有 Web 模式仍应保留为开发和排障入口，但普通用户主入口应从 `./start.sh + 浏览器` 变成双击 macOS App。

## Product Scope

V1 必须实现：

- 用户双击 `AI抓包工具.app` 后进入桌面控制台。
- 桌面端自动启动本机 FastAPI 后端。
- 桌面端加载现有 React 控制台。
- 后端只监听 `127.0.0.1`，默认不开放局域网。
- 抓包能力复用现有 Web 控制台功能。
- 桌面端提供后端启动失败、端口冲突、依赖缺失的可读错误。
- 用户数据写入 macOS Application Support 目录。
- App 退出时只关闭桌面端自己启动的后端 sidecar。
- 打包产物包含 macOS `.app`，可选生成 `.dmg`。

V1 不做：

- 不内置 Android Studio。
- 不内置 Android SDK。
- 不内置 Google Play AVD 镜像。
- 不托管 Google 账号密码。
- 不实现 iOS 抓包。
- 不重写 mitmproxy、Frida 或 adb 抓包逻辑。
- 不做多人远程模拟器画面控制。
- 不在普通退出时 wipe、uninstall、pm clear 或清除登录态。

## Architecture

```text
AI抓包工具.app
  ├─ Tauri native shell
  │   ├─ app lifecycle
  │   ├─ backend sidecar manager
  │   ├─ local runtime path resolver
  │   └─ main WebView window
  ├─ React/Vite built assets
  └─ Python backend bundle
      └─ FastAPI capture_console
          ├─ SQLite store
          ├─ device/app/capture APIs
          └─ scripts runner
              ├─ adb / emulator
              ├─ Frida server / hook
              ├─ mitmproxy / mitmweb
              └─ exporter / result indexer
```

Tauri 负责启动本机后端。后端启动成功后，WebView 加载 `http://127.0.0.1:<console_port>/`。React 页面仍走现有 HTTP API，不新增一套 Tauri IPC 业务接口。这样可以最大限度复用现有测试和 Web 调试能力。

## Component Design

### Desktop Shell

新增 `src-tauri/` 作为 Tauri 工程目录，职责只包含桌面能力：

- 应用窗口配置。
- 菜单和窗口标题。
- sidecar 启动与停止。
- 运行目录计算。
- 环境变量注入。
- 后端健康检查轮询。
- 后端失败页面或错误提示。

桌面壳不直接执行抓包命令。所有抓包动作继续通过 FastAPI API 调用，避免出现两套抓包入口。

### Backend Sidecar

FastAPI 后端作为 sidecar 运行。V1 采用“源码 + 本机 Python 环境/venv”的保守方案，后续如果需要更强自包含分发，再升级为 PyInstaller 或独立 Python runtime。

sidecar 启动脚本负责：

- 设置 `PYTHONPATH`。
- 设置 `CAPTURE_RUNTIME_DIR`。
- 设置 `TRACEDECK_CONFIG`。
- 设置 `CONSOLE_HOST=127.0.0.1`。
- 选择可用 `CONSOLE_PORT`。
- 启动 `uvicorn capture_console.app:app`。

桌面端必须记录 sidecar pid，并标记该 pid 是本次 App 启动创建的。退出时只停止这个 pid，不根据端口全局 kill。

### React Console

现有 `web/` 继续作为主 UI。桌面端构建流程先运行 Vite build，再让 FastAPI 服务 `web/dist`。这样 React 仍可以在普通浏览器和 Tauri WebView 两种环境下运行。

需要新增一个轻量环境识别能力：

- 浏览器模式：显示普通 Web 控制台。
- 桌面模式：显示桌面端状态，例如“后端由桌面应用管理”。

该环境识别只能影响 UI 提示，不能改变抓包业务语义。

### Runtime Directory

桌面端默认运行目录：

```text
~/Library/Application Support/AI抓包工具/
  config/
    local.json
  runtime/
    console.db
    captures/
    uploads/
    apks/
    capture_instances/
    logs/
```

开发模式仍可使用项目根目录的 `runtime/`，便于现有命令和测试继续工作。打包模式必须使用 Application Support，避免 App Bundle 内部被写入运行数据，也避免升级覆盖历史数据。

### Configuration

桌面端启动时生成或读取：

```text
~/Library/Application Support/AI抓包工具/config/local.json
```

配置继续兼容现有 `capture_console/local_config.py`：

```json
{
  "console": {
    "host": "127.0.0.1",
    "port": 7001
  },
  "android": {
    "sdk_root": ""
  },
  "capture": {
    "proxy_port_start": 9090,
    "web_port_start": 9091,
    "frida_port_start": 27042,
    "mitmweb_token": "android-capture"
  }
}
```

如果 `7001` 被占用，桌面端可以选择下一个可用端口，并把端口写入本次 sidecar 环境变量。React 不应硬编码 API 地址，加载同源后端即可。

## Lifecycle

### App Launch

1. Tauri App 启动。
2. 计算 Application Support 运行目录。
3. 检查已有后端是否由当前 App 管理。
4. 如果没有可复用后端，启动 FastAPI sidecar。
5. 轮询 `/api/status`，直到后端 ready 或超时。
6. WebView 加载控制台。
7. 页面执行现有环境检查和初始化向导。

### App Quit

1. Tauri 收到退出事件。
2. 通知后端执行安全 shutdown 钩子。
3. 停止当前 App 启动的 FastAPI sidecar。
4. 不停止 Android Studio。
5. 不停止用户手动启动的模拟器。
6. 不停止未知 pid 或未知端口进程。
7. 保留 `runtime/captures`、SQLite、上传包和设备登录态。

普通退出是否停止正在运行的抓包任务由后端现有 shutdown 逻辑决定。V1 的安全默认值是停止当前后端管理的抓包 exporter 和清理 Android proxy，但不关闭模拟器、不清除 App 数据。

## Error Handling

桌面端必须区分以下失败：

- 后端进程启动失败：显示日志路径和启动命令摘要。
- 后端端口占用：自动换端口或提示占用进程，不 kill 未知进程。
- Python 不可用：提示安装 Python 3.12+ 或运行项目提供的 setup。
- 依赖缺失：引导到现有环境检查页面。
- Android SDK 不可用：页面环境检查显示修复建议。
- Frida 不可用：沿用现有 Frida 准入提示。
- mitmproxy 不可用：沿用现有 preflight 和 readiness 提示。
- 抓包失败：保留现有接口详细诊断，不由桌面壳吞掉错误。

错误日志必须写入 Application Support 下的 `runtime/logs/`，并在页面或桌面错误页中提供路径。

## Security Boundaries

- 后端默认只监听 `127.0.0.1`。
- 桌面端不保存 Google 密码。
- 桌面端不展示或复制系统敏感信息，抓包页面仍按本机可信环境展示原始请求响应。
- Tauri shell 权限只允许启动受控 sidecar，不开放任意 shell 执行入口给前端。
- 所有 adb、Frida、mitmproxy 操作仍走 FastAPI 后端现有 runner 和安全拦截。
- 禁止新增 `wipe-data`、`pm clear`、`uninstall` 作为普通流程。

## Packaging

新增桌面构建入口：

```text
desktop/
  package-desktop.sh
src-tauri/
  Cargo.toml
  tauri.conf.json
  capabilities/
  src/
```

构建流程：

1. 安装前端依赖。
2. 构建 `web/dist`。
3. 准备后端 sidecar 启动脚本和资源清单。
4. 运行 Tauri build 生成 `.app`。
5. 可选生成 `.dmg`。

正式对外分发时，需要签名和 notarization。内部本机使用可以先生成未签名 `.app`，但文档必须说明 Gatekeeper 限制和解决方式。

## Migration Strategy

分阶段实现，避免一次性重写：

1. 新增桌面规格和实施计划。
2. 新增 Tauri 最小壳，能显示静态 React 构建产物。
3. 加入 FastAPI sidecar 启动和健康检查。
4. 接入 Application Support 运行目录。
5. 接入退出清理策略。
6. 更新 README 和 release 文档。
7. 增加桌面构建脚本和 smoke test。

Web 模式保留，`./start.sh` 继续可用。这样桌面端出现问题时，仍可用浏览器模式排查后端和抓包链路。

## Acceptance Criteria

桌面端 V1 完成后必须满足：

- 在 macOS 上可以构建出 `AI抓包工具.app`。
- 双击 App 能打开控制台，不要求用户先运行 `./start.sh`。
- App 自动启动 FastAPI 后端并加载 React 页面。
- `/api/status` 在桌面端内可正常访问。
- 运行数据写入 Application Support，不写入 App Bundle。
- 现有浏览器模式仍可通过 `./start.sh` 启动。
- 环境检查、设备发现、App 添加、启动抓包、接口分析、cURL 导出能力继续可用。
- 关闭 App 不会 kill 未知端口进程。
- 关闭 App 不会 wipe、uninstall、pm clear。
- Python 后端测试和前端 Node 测试仍通过。
- 桌面构建脚本能生成可运行的 `.app`。

## Verification Plan

实现阶段需要执行：

```bash
python -m unittest discover tests
npm --prefix web test
npm --prefix web run build
```

如果新增 Tauri 工程，补充执行：

```bash
npm run tauri build -- --bundles app
```

如果实际 package.json 脚本名称不同，实施计划必须先补齐可重复执行的桌面构建命令，再把该命令作为验收命令。

## Open Operational Decisions

以下决策已经在本设计中固定：

- 桌面端技术：Tauri。
- UI：复用 React。
- 后端：复用 FastAPI。
- 抓包：复用现有脚本。
- 运行目录：Application Support。
- 默认监听：127.0.0.1。
- V1 不内置 Android SDK 和模拟器镜像。

后续实施计划只需要拆任务，不再重新比较 Electron、Swift/AppKit 或全量重写路线。

# AI抓包工具 macOS 原生桌面端可分发版设计

## Summary

把 AI抓包工具从“Web/Tauri 桌面壳”升级为“macOS 原生 SwiftUI 桌面应用”。原生桌面端面向两类用户：你本机长期使用，以及公司同事下载到自己 Mac 后本机安装使用。App 必须隐藏 localhost、浏览器、WebView 概念，用原生窗口完成环境检查、设备管理、APK 上传、抓包启动、实时接口列表、Request/Response 详情和日志排查。

抓包底层不重写。现有 `capture_console` FastAPI、SQLite、ADB、emulator、Frida、mitmproxy、exporter、`runtime/captures` 仍是唯一抓包核心。SwiftUI App 负责原生 UI、运行时管理、首次引导、分发安装和本机环境准入。

## Product Direction

采用 `SwiftUI native app + existing FastAPI local runtime`。

不继续把 Tauri/WebView 作为最终桌面端。Tauri 版本可保留为过渡或内部调试，但原生桌面端必须在 `macos-native/` 独立实现。

## Distribution Goal

最终交付给其他用户的是 macOS `.app`，后续可升级为 `.dmg` 或 `.pkg`。

用户下载后应能：

1. 双击打开 App。
2. 在首次引导中检查本机依赖。
3. 按提示安装或配置 Android SDK / Android Studio / AVD。
4. 启动本机模拟器并登录 Google。
5. 上传自己的 APK。
6. 点击一键抓包。
7. 在原生界面查看接口、请求、响应和日志。

V1 不承诺完全离线自带 Android Studio/SDK/Google Play 镜像。Android SDK、Google Play AVD、Google 登录仍由用户本机准备或按向导安装配置。

## Architecture

```text
AI抓包工具.app (SwiftUI)
  ├─ Native UI
  │   ├─ SetupWizardView
  │   ├─ DevicePoolView
  │   ├─ AppLibraryView
  │   ├─ CaptureControlView
  │   ├─ FlowListView
  │   ├─ FlowDetailView
  │   └─ LogsView
  ├─ RuntimeManager
  │   ├─ starts/stops FastAPI backend
  │   ├─ resolves Application Support paths
  │   ├─ monitors backend health
  │   └─ opens logs/runtime dirs
  ├─ APIClient
  │   └─ calls existing local FastAPI APIs
  └─ Packaged Resources
      ├─ capture_console/
      ├─ scripts/
      ├─ requirements-console.txt
      ├─ tools/httptoolkit-frida/
      └─ config templates

Local FastAPI Runtime
  ├─ SQLite
  ├─ ADB / emulator
  ├─ Frida
  ├─ mitmproxy
  ├─ exporter
  └─ runtime/captures
```

## Runtime Directory

原生 App 所有可写数据必须放在：

```text
~/Library/Application Support/AI抓包工具/
  config/
  runtime/
    console.db
    captures/
    apks/
    logs/
    capture_instances/
    desktop-venv/
```

禁止把运行数据写入 `.app` bundle 或源码目录。禁止使用用户本机 `/Users/wan/...` 路径。

## Native UI Scope

V1 原生 UI 需要覆盖：

- 启动状态：内部后端启动中、就绪、失败。
- 环境检查：Python、adb、emulator、mitmproxy、frida-tools、Android SDK、端口。
- 设备池：设备在线/离线、启动、释放、Google 状态、Frida 状态。
- 应用库：生产包/测试包、本机 APK 上传、版本状态。
- 抓包控制：一键开始抓包、停止抓包、清理脏状态。
- 接口列表：实时刷新、按方法筛选、业务/其他/噪声分类、清空当前列表。
- 接口详情：Request/Response tab、headers、body、timing、files、cURL。
- 日志与诊断：打开后端日志、抓包日志、运行目录。

## API Reuse

原生 App 不直接执行 adb/Frida/mitmproxy 命令。所有业务动作通过现有后端 API：

- `GET /api/status`
- `GET /api/setup/state`
- `POST /api/setup/check`
- `GET /api/devices`
- `POST /api/devices/{device_id}/start`
- `POST /api/devices/{device_id}/release`
- `GET /api/apps`
- `POST /api/apps/install`
- `POST /api/apps/{app_id}/launch`
- `POST /api/captures/start`
- `POST /api/captures/stop`
- `GET /api/captures/{session_id}/flows`
- `GET /api/captures/{session_id}/flows/{flow_id}`
- `GET /api/captures/{session_id}/flows/{flow_id}/curl`

如果现有 API 缺少字段，优先做兼容性增强，不新增第二套抓包协议。

## Packaging Strategy

V1 分三层：

1. 开发版：`swift build` 或 Xcode 直接运行 `macos-native`。
2. 本机 `.app`：通过脚本组装 SwiftUI 可执行文件和后端资源。
3. 可分发 `.dmg/.pkg`：后续加入签名、公证、Gatekeeper 处理。

V1 允许用户首次打开时看到“缺少 Android SDK/mitmproxy/frida-tools”的引导，但不能直接崩溃。

## Security Boundaries

- 后端只监听 `127.0.0.1`。
- 不保存 Google 密码。
- 不自动 wipe、pm clear、uninstall。
- 不 kill 非本 App 启动的未知进程。
- 原始 token/header 只在本机可信环境展示。
- 退出 App 时可停止本 App 管理的后端和抓包进程，但不清除模拟器登录态。

## Acceptance Criteria

- `macos-native` 可以编译。
- 打开原生 App 后看到 SwiftUI 原生窗口，不是 WebView 页面。
- App 能启动或连接本地 FastAPI 后端，并显示后端状态。
- App 能通过 API 读取设备列表和应用列表。
- App 能执行一键抓包并实时显示接口列表。
- App 能展开接口详情查看 request/response。
- App 能上传 APK 到当前选中设备。
- App 可打包成 `.app`，别人拷贝到本机后进入首次引导。

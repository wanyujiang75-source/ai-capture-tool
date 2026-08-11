# AI抓包工具 macOS 一键分发闭环设计

## 目标

把当前“本机能打开的 SwiftUI App”升级为可明确区分开发包与正式分发包的 macOS 桌面产品，并让 Apple Silicon、macOS 14+ 的新用户在不预装 Python、Node、mitmproxy 或 Frida CLI 的情况下启动本机后端。Android SDK 与 Google Play system image 由首次准备流程复用或按需安装，Google 账号仍由用户手动登录。

## 已确认问题

- 当前 `.app` 在复制 Swift 可执行文件后又写入 Info.plist 和后端资源，但没有对完整 bundle 重签，`codesign --verify --deep --strict` 失败。
- 当前签名是 ad-hoc，未使用 Developer ID，也未经过 Apple 公证；Gatekeeper 不能把它当成正式分发包。
- 当前 App 只有 arm64 架构且最低 macOS 14，因此 V1 只支持 Apple Silicon、macOS 14+。
- 当前 RuntimeManager 调用 `start_console.sh` 创建 venv 并在线安装依赖，新 Mac 没有 Python 3.12 或 pip 网络不通时无法启动。
- 当前抓包脚本通过 PATH 查找 `python3`、`mitmweb`、`frida`、`frida-ps`，仅替换后端解释器不足以形成自包含运行时。
- 当前 RuntimeManager 不持有后端进程所有权，也没有正常退出清理，存在孤儿 uvicorn 风险。

## 方案分层

### A. 发布完整性

构建脚本必须先完成 Info.plist、可执行文件和 Resources 组装，再对整个 `.app` 签名。开发模式使用 ad-hoc 签名，仅供本机验证；正式分发模式必须使用 `Developer ID Application`、Hardened Runtime 和可信时间戳。

正式分发包必须执行：Developer ID 签名、`codesign --verify --deep --strict`、`notarytool submit --wait`、`stapler staple`、`spctl --assess`。任一环节失败都不生成“distribution”产物。公证凭据通过 Keychain profile 提供，不能写入仓库、脚本或归档。

### B. 自包含 Python 抓包运行时

发布构建机使用 `uv python install 3.12 --install-dir` 获取可重定位的 arm64 Python，并把 `requirements-console.txt` 的固定依赖安装到内嵌 runtime。App Resources 包含 Python、site-packages 和相对路径 wrapper；不直接复制开发机 venv，也不保留绝对 shebang。

RuntimeManager 优先选择 `Contents/Resources/runtime/bin/python3`，并设置：

- `CONSOLE_PYTHON` 指向内嵌 Python。
- `CONSOLE_SKIP_INSTALL=1`，禁止首次启动联网 pip install。
- `TRACEDECK_RUNTIME_BIN` 指向内嵌 wrapper 目录。
- PATH 把 runtime bin 放在 Android SDK 和系统 PATH 之前。
- `FRIDA_PYTHON_BIN` 指向内嵌 Python。
- `MITMWEB_BIN` 指向内嵌 mitmweb wrapper。

开发模式继续允许使用现有 `.venv-console`，便于本地迭代。

### C. Android 首次准备

桌面端只把 Android 工具链作为外部运行环境。优先复用 Android Studio SDK；缺少时由 Environment Doctor 给出官方 command-line tools 安装动作，并在用户接受 Android SDK license 后安装：platform-tools、emulator、cmdline-tools 和 `google_apis_playstore` arm64 system image。

创建的默认 AVD 固定为 `AI_Capture_AVD_01`，必须通过 Play Store 包、Google 账号、boot/unlock、网络、root/Frida 准入后才能安装 APK、打开 App 和抓包。Google 密码不由产品托管。

## 发布产物

开发产物：

```text
AI-Capture-Desktop-<version>-development-arm64.zip
```

它必须通过 bundle 完整性校验，但不会通过 Gatekeeper 公证校验，文件名和 manifest 必须明确标注 development。

正式产物：

```text
AI-Capture-Desktop-<version>-arm64.zip
AI-Capture-Desktop-<version>-arm64.zip.sha256
AI-Capture-Desktop-<version>-arm64.manifest.json
```

正式产物只有在 Developer ID、公证、staple 和 Gatekeeper 校验全部通过后才生成。

## 安全边界

- 后端只监听 `127.0.0.1`。
- 发布包不包含本机 runtime、SQLite、APK 缓存、抓包历史、Jenkins 密码、Google 账号或 Apple 公证凭据。
- 构建和退出清理只处理本 App 所有的 PID、端口和运行目录。
- 不执行 `wipe-data`、`pm clear`，不删除 Google/App 登录态。
- 正式发布凭据只保存在构建机 Keychain。

## 验收门禁

1. Python 全量测试、Web build、Swift build 通过。
2. `codesign --verify --deep --strict` 对开发和正式 App 均通过。
3. 开发包文件名包含 `development`，且不能被报告为已公证。
4. 正式模式缺少 Developer ID 或 Keychain profile 时在构建前失败，不生成误导性产物。
5. 正式包通过 `spctl --assess --type execute`，公证 ticket 已 staple。
6. 干净用户目录首次启动不调用 pip/npm，不依赖系统 Python。
7. 一键准备可启动 Google Play AVD；未登录 Google 时只允许进入登录流程。
8. Jenkins 安装、应用启动、真实抓包、Request/Response/cURL 和退出清理通过。

## 外部前置

当前构建机没有 `Developer ID Application` 身份，只有 Apple Development 身份。因此可以完成开发签名、发布脚本和失败门禁验证；正式 Developer ID 公证的最终通过需要公司导入有效证书，并预先执行 `xcrun notarytool store-credentials <profile>`。

# 抓包工具安装指南

本文是抓包工具的统一安装入口。Codex 辅助安装只是其中一条便捷路径；也可以手动安装、从源码构建或升级已有版本。

## 选择安装方式

| 场景 | 推荐路径 |
| --- | --- |
| 希望尽量自动完成检查、下载、安装和验收 | [路径 A：让 Codex 辅助安装](#路径-a让-codex-辅助安装推荐) |
| 只想下载桌面 App，不需要开发环境 | [路径 B：手动下载安装](#路径-b手动下载安装) |
| 需要修改代码或自行构建 | [路径 C：从源码构建](#路径-c从源码构建) |
| 已安装旧版，需要保留数据升级 | [路径 D：升级已有版本](#路径-d升级已有版本) |
| 新 Mac 没有 Android 环境 | [路径 E：新主机首次配置](#路径-e新主机首次配置) |

桌面端 V1 仅支持 **macOS 14 或更高版本、Apple Silicon（arm64）**。建议至少 16 GB 内存和 25 GB 可用磁盘空间。

## 路径 A：让 Codex 辅助安装（推荐）

把本文件交给 Codex，或者把下面这段话直接发送给 Codex：

```text
请阅读并严格按照下面的安装指南，在这台 Mac 上安装和验收抓包工具：
https://github.com/wanyujiang75-source/ai-capture-tool/blob/main/INSTALL.md

请优先从该仓库的 GitHub Releases 下载最新的 macOS Apple Silicon 桌面 ZIP，不要从第三方地址下载。先检查 macOS 版本、CPU 架构、磁盘空间、已有安装和 Android SDK；下载后校验 Release 提供的 SHA-256，再安装到 /Applications。若没有写入 /Applications 的权限，安装到当前用户的 ~/Applications。

如已安装旧版，必须保留 ~/Library/Application Support/AI抓包工具/ 和现有 Android AVD，不删除抓包历史、APK、账号或登录态。优先选择文件名不含 development 的正式包；如果目前只有 development 预发布包，要明确说明风险，并在真正打开该开发包前让我完成 macOS 必需的安全确认。

安装后启动桌面端，验证应用进程和 http://127.0.0.1:7001/api/status；随后检查 Android SDK、Google Play 模拟器、网络和 Frida 准入，并把自动完成项、需要我手动处理的步骤和最终验收结果汇总给我。

禁止关闭 Gatekeeper、禁止删除 quarantine 属性来绕过安全检查、禁止保存或代填管理员密码、禁止执行 wipe-data、pm clear、uninstall 或删除本机运行数据。遇到系统授权、Android SDK License、Google 登录、模拟器解锁或安全确认时，再明确告诉我需要接管哪一步。
```

Codex 可以自动完成：

- 检查 `sw_vers`、`uname -m`、磁盘空间和现有安装。
- 查询官方 GitHub Releases，选择匹配的 `arm64.zip`。
- 下载 ZIP 和校验文件，并验证 SHA-256。
- 保留旧数据，安装或升级 App。
- 启动 App，检查本机后端与环境诊断结果。

以下步骤必须由用户在需要时手动完成：

- 输入管理员密码或同意系统权限。
- 接受 Android SDK License。
- 在 macOS“隐私与安全性”中允许内部开发包首次运行。
- 解锁模拟器、登录 Google 账号或完成 App 内登录。

## 路径 B：手动下载安装

1. 打开 [GitHub Releases](https://github.com/wanyujiang75-source/ai-capture-tool/releases)。
2. 优先下载文件名不含 `development` 的 `AI-Capture-Desktop-<版本>-arm64.zip`，并同时下载对应的 `.zip.sha256`。
3. 如果 Release 只有 `development-arm64.zip`，它是内部预发布包，使用 ad-hoc 签名，不等同于已公证的正式分发包。
4. 在下载目录验证文件：

   ```bash
   cd ~/Downloads
   shasum -a 256 -c AI-Capture-Desktop-*.zip.sha256
   ```

5. 双击解压 ZIP，把 `抓包工具.app` 拖入“应用程序”。若安装过旧版 `AI抓包工具.app`，先保留旧版，待新版验收通过后再删除旧 App。
6. 双击启动。正式公证包应直接通过 Gatekeeper；内部开发包可能需要右键选择“打开”，或在“系统设置 -> 隐私与安全性”中手动允许。

不要直接在 ZIP 预览窗口内运行 App，也不要用命令关闭 Gatekeeper 或移除安全隔离属性。

## 路径 C：从源码构建

适合需要开发或调试的人。需要 Xcode Command Line Tools、Node.js、npm 和 `uv`：

```bash
xcode-select --install
brew install node uv
git clone https://github.com/wanyujiang75-source/ai-capture-tool.git
cd ai-capture-tool
npm --prefix web ci
npm --prefix web run build
macos-native/scripts/build-app.sh
open "macos-native/build/抓包工具.app"
```

本地构建默认使用 ad-hoc 签名，仅用于开发验证。给他人分发时必须使用 Developer ID 签名并完成 Apple notarization，详见 [桌面端开发与发布说明](macos-native/README.md)。

## 路径 D：升级已有版本

1. 在桌面端停止当前抓包并退出应用。
2. 按路径 A 或路径 B 下载并校验新版本。
3. 把 `/Applications/抓包工具.app` 更新为新版本；从旧名称升级时，新旧 App 可短暂并存，验收新版后再删除 `/Applications/AI抓包工具.app`。不要删除应用数据目录或 Android AVD。
4. 启动新版本，确认“环境”页显示内部服务已就绪。

升级 App 不会要求删除以下数据目录：

```text
~/Library/Application Support/AI抓包工具/
```

该目录可能包含数据库、APK 缓存、抓包文件和请求信息。备份或共享前应按敏感数据处理。

## 路径 E：新主机首次配置

下载的桌面 App 已包含 Python、FastAPI、mitmproxy 和 Frida 客户端，但不包含 Android SDK 和系统镜像。新 Mac 需要：

1. 从 [Android 官方网站](https://developer.android.com/studio) 安装 Android Studio。
2. 至少启动一次 Android Studio，完成 SDK 组件安装和 License 接受。
3. 打开抓包工具，在“环境”页确认内部服务已就绪。
4. 在“抓包”页执行“一键准备环境”。工具会定位 SDK、准备 Google Play 系统镜像、创建模拟器并检查网络和 Frida。
5. 模拟器启动后手动解锁；目标 App 需要 Google 登录时，再手动登录。

默认模拟器必须使用 `google_apis_playstore` 系统镜像。普通 AOSP 或仅 `google_apis` 的镜像不能作为默认抓包模拟器。

## 安装后验收

1. 启动 `抓包工具.app`。
2. “环境”页应显示内部服务已就绪。
3. 可选终端检查：

   ```bash
   curl -fsS http://127.0.0.1:7001/api/status
   ```

4. 进入“抓包”页，执行一键准备环境并启动模拟器。
5. 解锁模拟器，安装一个 Jenkins 测试包，打开应用并启动抓包。
6. 操作 App 后，“接口”页应实时出现请求；“日志”页应显示当前 App 的 Android Logcat。

安装后的产品操作、数据位置和故障处理见 [桌面端使用指南](docs/desktop-user-guide.md)。

## 安全边界

- 只从本仓库 GitHub Releases 或源码构建获取程序。
- 不关闭 Gatekeeper，不用 `xattr` 绕过安全检查。
- 不执行 `wipe-data`、`pm clear` 或无确认卸载。
- 不删除 `~/Library/Application Support/AI抓包工具/`，除非用户明确要求清空所有本机数据。
- 不把 Jenkins 密码、Google 密码、token 或抓包 headers 写入安装脚本、仓库或截图。

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

桌面端 V1 仅支持 **macOS 14 或更高版本、Apple Silicon（arm64）**。使用 Android 模拟器建议至少 16 GB 内存和 25 GB 可用磁盘空间。

iPhone 真机抓包已包含在新版预发布包中。仅使用 iPhone 可跳过 Android SDK 和模拟器准备，
按[iPhone 前置准备与完整操作](docs/desktop-user-guide.md#13-iphone-真机抓包)完成证书、节点和手机连接检查。
已在同一测试机验证 PokeHub、MelodyCraft、Wishly、StickerHub；不是所有设备/应用的兼容性保证。
手机安装、信任和转发切换必须本人完成；Mac 自检或界面可打开不代表已抓到手机接口。

## 路径 A：让 Codex 辅助安装（推荐）

把本文件交给 Codex，或者把下面这段话直接发送给 Codex：

```text
请阅读并严格按照下面的安装指南，在这台 Mac 上安装和验收抓包工具：
https://github.com/wanyujiang75-source/ai-capture-tool/blob/main/INSTALL.md

请优先从该仓库的 GitHub Releases 下载最新的 macOS Apple Silicon 桌面 ZIP，不要从第三方地址下载。先检查 macOS 版本、CPU 架构、磁盘空间和已有安装；仅在我要使用 Android 时检查 Android SDK。下载后校验 Release 提供的 SHA-256，再安装到 /Applications。若没有写入 /Applications 的权限，安装到当前用户的 ~/Applications。

如已安装旧版，必须保留 ~/Library/Application Support/AI抓包工具/ 和现有 Android AVD，不删除抓包历史、APK、账号或登录态。优先选择文件名不含 development 的正式包；如果目前只有 development 预发布包，要明确说明风险，并在真正打开该开发包前让我完成 macOS 必需的安全确认。

安装后启动桌面端，验证应用进程和 http://127.0.0.1:7001/api/status。Android 按指南检查 SDK、Google Play 模拟器、网络和抓包组件；iPhone 按仓库使用指南第13节准备本机连接，由我在手机安装和信任证书、临时切换专用节点并完成HTTPS检查。不要用Mac自检冒充手机验收。把自动完成项、手动步骤和真实验收结果汇总给我。

禁止关闭 Gatekeeper、禁止删除 quarantine 属性来绕过安全检查、禁止保存或代填管理员密码、禁止执行 wipe-data、pm clear、uninstall 或删除本机运行数据。iPhone VPN 保持开启，不编辑原节点、订阅、DNS或配置文件；临时转发前记录原选择，结束后恢复并检查联网。不得把节点密码/配置文件上传、写入仓库或聊天。遇到系统授权、证书信任、Android SDK License、Google登录或手机操作时，明确告诉我需要接管哪一步。
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
- 在 iPhone 安装和信任本机测试证书、首次设置专用节点，以及每次测试前后的转发选择与恢复。

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
6. 在 Finder 的“应用程序”目录中打开 `抓包工具`。正式公证包应直接通过 Gatekeeper。
7. 如果内部预览包显示“Apple 无法验证‘抓包工具’是否包含可能危害 Mac 安全或泄漏隐私的恶意软件”：

   1. 点击“完成”，不要点击“移到废纸篓”。
   2. 打开“Apple 菜单 -> 系统设置 -> 隐私与安全性”。
   3. 向下滚动到“安全性”，在 `抓包工具` 的拦截提示旁点击“仍要打开”。
   4. 使用 Touch ID 或 Mac 登录密码验证，再点击“打开”。
   5. 该按钮通常只在尝试启动 App 后约一小时内出现；如果未看到，重新尝试打开 App，然后立即回到此页检查。

   此操作会将该 App 保存为本机安全设置的例外，后续可正常双击打开。参考 [Apple 官方说明](https://support.apple.com/zh-cn/guide/mac-help/-mh40616/mac)。

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

1. 在桌面端停止当前抓包。若使用 iPhone，先恢复手机原节点/路由及曾手动设置的 Wi-Fi 代理，确认手机联网正常，再退出应用。
2. 按路径 A 或路径 B 下载并校验新版本。
3. 把 `/Applications/抓包工具.app` 更新为新版本；从旧名称升级时，新旧 App 可短暂并存，验收新版后再删除 `/Applications/AI抓包工具.app`。不要删除应用数据目录或 Android AVD。
4. 启动新版本，通过工具栏“运行检查”确认本机服务正常。iPhone 重新连接并完成手机检查，不会自动继续录制。

升级 App 不会要求删除以下数据目录：

```text
~/Library/Application Support/AI抓包工具/
```

该目录可能包含数据库、APK 缓存、抓包文件和请求信息。备份或共享前应按敏感数据处理。

## 路径 E：新主机首次配置

下载的桌面 App 已包含 Python、FastAPI、mitmproxy 和 Frida 客户端，但不包含 Android SDK 和系统镜像。使用 Android 的新 Mac 需要：

1. 从 [Android 官方网站](https://developer.android.com/studio) 安装 Android Studio。
2. 至少启动一次 Android Studio，完成 SDK 组件安装和 License 接受。
3. 打开抓包工具，在工具栏“运行检查”确认本机服务正常。
4. 在“抓包”页点击“启动模拟器”。工具会定位 SDK、安装或选择 Apple Silicon 原生 `arm64-v8a` Google Play 系统镜像、创建项目 AVD、应用自适应性能配置并完成启动准入。
5. 模拟器启动后手动解锁；目标 App 需要 Google 登录时，再手动登录。

默认模拟器必须使用 `google_apis_playstore` 系统镜像。普通 AOSP 或仅 `google_apis` 的镜像不能作为默认抓包模拟器。
16 GB 及以上内存且至少 8 个逻辑核心时使用 `4 核 / 4096 MB / GPU host` 高性能档；较低配置自动使用 `2 核 / 2048 MB` 均衡档。已经运行的 AVD 不会被热修改；现有同名但不合规的 AVD 会被原样保留，工具另行创建或复用带 `_GooglePlay` 后缀的合规替代设备。

## 安装后 Android 验收

1. 启动 `抓包工具.app`。
2. 工具栏“运行检查”应显示本机服务正常。
3. 可选终端检查：

   ```bash
   curl -fsS http://127.0.0.1:7001/api/status
   ```

4. 进入“抓包”页点击“启动模拟器”，等待设备启动；详细性能配置可在“运行检查”查看。
5. 解锁模拟器，安装一个 Jenkins 测试包，打开应用并启动抓包。
6. 操作 App 后，“接口”页应实时出现请求；“日志”页应显示当前 App 的 Android Logcat。

## 日常 Android 操作流程

1. 打开 `抓包工具.app`，等待本机服务启动。必要时通过工具栏“运行检查”查看状态。
2. 进入“抓包”页，选择 Android 并点击“启动模拟器”。新机首次使用时，这一步会自动准备合规 Google Play 模拟器，首次下载镜像可能需要较长时间。
3. 等待 Android 启动后手动解锁。目标 App 依赖 Google 登录时，先在 Play Store 中手动登录。
4. 从“安装应用”安装 Jenkins 测试包或本地 APK；已安装的应用可直接使用。
5. 在模拟器中打开目标应用，桌面端会自动识别。
6. 回到“抓包”页，点击“开始抓包”。页面显示正在抓取后，在应用中操作需要分析的功能。
7. 在“接口”页搜索并查看 Request、Response 和 cURL；需要排查 App 运行问题时进入“日志”页。
8. 完成后回到“抓包”页点击“停止抓包”，再正常关闭模拟器和桌面 App。

安装后的产品操作、数据位置和故障处理见 [桌面端使用指南](docs/desktop-user-guide.md)。

## iPhone 首次准备与日常使用

前置条件：测试 iPhone 已安装目标应用；Mac 与手机可在局域网互通；Mac 能访问目标服务。无需 Android SDK、Root、越狱或 iPhone 镜像。使用小火箭统一接入时，VPN 始终开启，但出口会使用 Mac 的网络路径，可能不同于原节点。

首次使用按[指南第13节](docs/desktop-user-guide.md#13-iphone-真机抓包)准备连接，运行本机命令读取参数并生成“仅证书＋检查入口”副本，隔空投送后安装/信任，再创建专用 `Capture-Mac` HTTP 节点。命令不修改网络/原文件/钥匙串，但会在下载目录创建副本；不是自动导入。不要安装含Wi-Fi代理的原文件或照抄他人IP、端口、密码。

日常顺序：打开桌面并重新连接 → 记录原选择 → 手机临时选择 Capture-Mac＋代理（VPN开启）→ 手机HTTPS检查通过 → 桌面开始抓包 → 操作应用 → 查看接口 → 停止抓包 → 恢复原选择并确认联网 → 退出桌面。

同一Mac和手机可复用一年有效期内的证书/节点，换应用无需配置业务域名；新手机须单独安装/信任和设置节点，换Mac或本机身份丢失需重新准备，地址变化需核对专用节点。不是每次抓包都重新装证书。

“停止抓包”只停止记录，不会自动恢复手机路由。iPhone暂不支持桌面安装应用、运行日志或弱网；证书绑定、自定义加密和非HTTP(S)协议不保证可读。下载ZIP内的两个安装说明也包含离线可用的完整步骤。

## 安全边界

- 只从本仓库 GitHub Releases 或源码构建获取程序。
- 不关闭 Gatekeeper，不用 `xattr` 绕过安全检查。
- 不执行 `wipe-data`、`pm clear` 或无确认卸载。
- 不删除 `~/Library/Application Support/AI抓包工具/`，除非用户明确要求清空所有本机数据。
- 不把 Jenkins 密码、Google 密码、token 或抓包 headers 写入安装脚本、仓库或截图。

# AI抓包工具

AI抓包工具是 macOS 优先的本机 Android 抓包工作台。桌面端是 SwiftUI 原生应用，会自动启动本机 FastAPI 后端，并复用已有 adb、Frida、mitmproxy 和抓包脚本。用户可以通过 macOS App 完成环境检查、设备发现、Jenkins 测试包安装、抓包启动、接口查看和 cURL 导出。

项目默认不包含历史抓包结果、上传 APK、本机数据库、cookie、token 或账号状态。新数据库会创建一台默认本机抓包设备 `device-1 / AI_Capture_AVD_01 / emulator-5554`；如果已有设备数据库或外部设备配置，不会覆盖。

## 下载使用

桌面端 V1 支持 **macOS 14+ / Apple Silicon**。普通用户应下载 Release 中的
`AI-Capture-Desktop-*-arm64.zip`，解压后把 `AI抓包工具.app` 移入“应用程序”目录，再双击打开。

文件名不含 `development` 的正式分发包必须经过 Developer ID 签名和 Apple 公证，可以直接打开。文件名包含
`development-arm64` 的内部开发包使用 ad-hoc 签名，首次打开时可能需要右键选择“打开”，
或在“系统设置 -> 隐私与安全性”中允许。

桌面 App 已内嵌 Python、FastAPI、mitmproxy 和 Frida 客户端运行时，不需要用户手动启动后端。
新 Mac 仍需具备 Android Studio 或 Android SDK；首次准备环境时，工具会检查 SDK、安装或定位
Google Play 系统镜像、创建模拟器并检查网络与 Frida。

完整操作和排错说明见 [桌面端使用指南](docs/desktop-user-guide.md)。

### 首次抓包

1. 打开桌面 App，等待“环境”页显示内部服务已就绪。
2. 进入“抓包”，选择设备后点击“打开模拟器”，等待 Android 启动并手动解锁。
3. 选择 Jenkins 测试包；首次使用该构建时，工具会自动下载并安装。
4. 点击“打开应用”，确认目标 App 已启动。
5. 点击“一键开始抓包”。该操作会自动执行环境、网络和 Frida 准入检查。
6. 在模拟器内操作目标功能，在“接口”页实时查看 Request、Response 和 cURL。
7. 完成后回到“抓包”页点击“停止抓包”。

### 从源码构建

开发者构建需要 Xcode Command Line Tools、SwiftPM 和 `uv`：

```bash
git clone https://github.com/wanyujiang75-source/ai-capture-tool.git
cd ai-capture-tool
brew install uv
xcode-select --install
macos-native/scripts/build-app.sh
```

生成后打开：

```text
macos-native/build/AI抓包工具.app
```

桌面端会自动启动 `.app` 内置的本机后端，不需要手动运行 `./start.sh`。如果是未签名的本地构建，macOS Gatekeeper 可能会阻止首次打开；内部使用时可以在系统设置的安全性页面允许打开，正式分发时需要进行签名和 notarization。

桌面端运行数据保存在：

```text
~/Library/Application Support/AI抓包工具/runtime-native/
```

包括 SQLite 数据库、抓包结果、上传 APK、日志和临时进程文件。升级 App 不应删除该目录。

首次执行环境准备时，桌面端会优先准备一台可 Google 登录的默认模拟器：

- 默认 AVD：`AI_Capture_AVD_01`
- 默认 serial：`emulator-5554`
- 必须使用 `google_apis_playstore` system image
- 普通 AOSP 或仅 `google_apis` 镜像不会作为默认抓包模拟器

如果缺少 Google Play system image，桌面端会尝试通过 `sdkmanager` 安装推荐镜像；如遇到 Android SDK license、网络或权限问题，界面会提示用户打开 Android Studio SDK Manager 手动处理。模拟器必须具备 Google Play 能力，但公司内部模式默认不强制设备预先登录 Google 账号；尚未登录时仍可安装 APK、打开 App 和启动抓包。需要严格准入时，可在启动桌面端前设置 `REQUIRE_GOOGLE_LOGIN=1`，此时未登录会阻止上述操作。

## 浏览器模式

```bash
git clone https://github.com/wanyujiang75-source/ai-capture-tool.git
cd ai-capture-tool
./setup.sh
./start.sh
```

打开：

```text
http://127.0.0.1:7001
```

首次抓包流程：

1. 点击 `一键准备环境`，让系统检查依赖、安装/定位 Google Play 镜像、创建并启动默认模拟器。
2. 解锁模拟器；如果目标 App 依赖 Google 登录，再按页面提示手动登录 Google 账号。
3. 从 Jenkins 包列表选择测试包并安装，或在应用库中选择已有 App。
4. 点击默认的 `auto` 自动抓包；需要排查时再手动切换 `system` 或 `flutter-socks`。
5. 手动操作 App，在接口列表查看请求、响应和 cURL。
6. 停止抓包后，结果保存在运行目录的 `captures/<session>/`。

## 浏览器模式与源码构建依赖

下载的桌面 App 已内嵌 Python、mitmproxy 和 Frida 客户端。以下依赖用于浏览器模式、源码开发
或重新构建桌面 App；普通桌面用户只需准备 Android SDK：

- Python 3.12+
- Node.js 和 npm
- Xcode Command Line Tools / SwiftPM，用于构建原生 macOS 桌面端
- Android Studio 或 Android SDK
- `adb`、`emulator`、`sdkmanager`、`avdmanager`
- `mitmproxy`，提供 `mitmweb`
- Frida 工具链，提供 `frida` 和 `frida-ps`
- `uv`，用于构建可重定位的桌面端内嵌 Python 运行时

常见安装方式：

```bash
brew install node mitmproxy uv
xcode-select --install
python3 -m pip install frida-tools
```

如果首次执行 `./setup.sh` 时 PyPI 或 npm 下载较慢，可以临时指定镜像或代理：

```bash
export PIP_INDEX_URL="https://pypi.org/simple"
export PIP_PROXY=
export npm_config_registry="https://registry.npmjs.org/"
./setup.sh
```

在公司网络或本机代理环境下，如果 pip 报 `127.0.0.1:<port>` 的 502/超时，先确认该代理是否可用；不需要代理时可用 `PIP_PROXY=` 覆盖。

Android SDK 默认从 `$ANDROID_SDK_ROOT` 或 `$HOME/Library/Android/sdk` 读取。也可以编辑 `config/local.json`：

```json
{
  "console": { "host": "127.0.0.1", "port": 7001 },
  "android": { "sdk_root": "/Users/you/Library/Android/sdk" },
  "capture": {
    "proxy_port_start": 9090,
    "web_port_start": 9091,
    "frida_port_start": 27042,
    "mitmweb_token": "android-capture"
  }
}
```

`config/local.json` 是本机文件，不会进入发布包。

## 抓包模式

- `auto`：默认模式。TraceDeck 会优先使用该 App 上次成功的抓包模式；没有历史结果时依次尝试 `system` 和 `flutter-socks`。App 冒烟校验会在无接口或启动失败时切换候选模式，并记住成功模式。
- `system`：通过 Android 系统代理配合 mitmproxy 抓包。
- `flutter-socks`：通过 Frida/Flutter hook 辅助抓包，适用于部分 Flutter App。

启动抓包前，后端会检查设备在线、App 可启动、端口可用，以及 `flutter-socks` 模式下 Frida 是否可连接。端口被其他项目占用时只报错，不会 kill 未知进程。自动校验过程中如果某个模式失败，会停止当前临时抓包并清理 Android 代理后再尝试下一个模式。

## 重要限制

- App 使用证书绑定、内置 CA、双向 TLS 或不信任用户 CA 时，HTTPS 响应可能无法解密。
- 默认抓包模拟器必须支持 Google Play；公司内部模式默认不强制 Google 登录。设置 `REQUIRE_GOOGLE_LOGIN=1` 后，未登录设备才会被禁止安装 APK、打开 App 或启动抓包。
- Google 登录、支付、风控等流程仍可能因为代理、证书或设备状态而失败。
- 真机抓包需要用户自行处理证书安装、USB 调试授权和系统代理限制。
- iOS 仅保留数据模型和 UI 扩展边界，当前版本不执行 iOS 抓包。

## 发布包

生成内部开发验证包：

```bash
TRACEDECK_RELEASE_KIND=development ./release/package.sh
```

输出的桌面包名包含 `development-arm64.zip`，使用 ad-hoc 签名，只用于本机/内部开发验收，不能当作已通过 Gatekeeper 的公开分发包。

生成他人可下载的正式包：

```bash
TRACEDECK_RELEASE_KIND=distribution \
MACOS_SIGN_IDENTITY="Developer ID Application: Company Name (TEAMID)" \
MACOS_NOTARY_PROFILE="ai-capture-notary" \
./release/package.sh
```

正式模式会在构建前校验 Developer ID 证书和 Keychain 中的 notary profile，然后依次执行整包签名校验、Apple 公证、staple 和 Gatekeeper 评估。任何一步失败都不会产生正式 ZIP。首次使用前需由证书管理员执行 `xcrun notarytool store-credentials ai-capture-notary ...`。

发布包包含 SwiftUI 原生 `.app`、后端代码、抓包脚本、`web/dist`、桌面打包脚本、配置模板、README、`setup.sh`、`start.sh`、`package.json` 和 `requirements-console.txt`。

发布包排除：

- `runtime/`
- `.venv*`
- `web/node_modules`
- `node_modules`
- `src-tauri/target`
- `src-tauri/gen`
- `macos-native/.build`
- `macos-native/.swiftpm`
- `config/local.json`
- 抓包结果、上传 APK、本机数据库、cookie、token 和账号状态

## Legacy

服务器、Mac mini、Jenkins、固定 AVD 和保留设备池相关能力仍保留在代码与脚本中，作为 legacy/advanced 场景使用。新用户主流程不需要这些内容。

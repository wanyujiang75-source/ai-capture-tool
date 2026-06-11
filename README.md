# TraceDeck

TraceDeck 是 macOS 优先的本机 Android 抓包工作台。下载源码或 release 包后，在自己的 Mac 上运行 `./setup.sh` 和 `./start.sh`，打开 `http://127.0.0.1:7001`，即可通过页面完成环境检查、设备发现、App 添加、抓包启动、接口查看和 cURL 导出。

项目默认是空状态：不预置 App、不预置设备池、不包含历史抓包结果，也不绑定 MelodyCraft、Jenkins、服务器或固定 AVD。

## 快速开始

```bash
git clone <your-tracedeck-repo-url>
cd TraceDeck
./setup.sh
./start.sh
```

打开：

```text
http://127.0.0.1:7001
```

首次抓包流程：

1. 在 Mac 上启动一个 Android 模拟器，或连接一台开启 USB 调试的 Android 真机。
2. 在页面执行环境检查和设备发现。
3. 添加目标 App：手动输入包名/Activity、从已安装 App 列表选择，或上传 APK 后解析。
4. 点击默认的 `auto` 自动抓包；需要排查时再手动切换 `system` 或 `flutter-socks`。
5. 手动操作 App，在接口列表查看请求、响应和 cURL。
6. 停止抓包后，结果保存在 `runtime/captures/<session>/`。

## 依赖

macOS 首版需要：

- Python 3.12+
- Node.js 和 npm
- Android Studio 或 Android SDK
- `adb`、`emulator`、`sdkmanager`、`avdmanager`
- `mitmproxy`，提供 `mitmweb`
- Frida 工具链，提供 `frida` 和 `frida-ps`

常见安装方式：

```bash
brew install node mitmproxy
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
- Google 登录、支付、风控等流程可能因为代理、证书或设备状态而失败。
- 真机抓包需要用户自行处理证书安装、USB 调试授权和系统代理限制。
- iOS 仅保留数据模型和 UI 扩展边界，当前版本不执行 iOS 抓包。

## 发布包

生成干净 release 包：

```bash
./release/package.sh
```

发布包包含后端代码、抓包脚本、`web/dist`、配置模板、README、`setup.sh`、`start.sh` 和 `requirements-console.txt`。

发布包排除：

- `runtime/`
- `.venv*`
- `web/node_modules`
- `config/local.json`
- 抓包结果、上传 APK、本机数据库、cookie、token 和账号状态

## Legacy

服务器、Mac mini、Jenkins、固定 AVD 和保留设备池相关能力仍保留在代码与脚本中，作为 legacy/advanced 场景使用。新用户主流程不需要这些内容。

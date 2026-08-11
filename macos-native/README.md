# AI抓包工具 macOS 原生桌面端

这是 SwiftUI 原生桌面端，不使用 React/WebView 作为主界面。普通用户请先阅读
[桌面端使用指南](../docs/desktop-user-guide.md)；本文件只说明开发、构建和发布。

V1 目标：

- 原生 macOS 窗口。
- 管理本机 FastAPI 抓包运行时。
- 调用现有后端 API 完成设备、应用、抓包和接口分析。
- 从 Jenkins REST API 读取最新企业构建 APK，并安装到当前模拟器。
- 打包成自包含 `.app/.zip`，供其他 Apple Silicon Mac 本机安装使用。

开发环境要求：

- macOS 14+
- Apple Silicon
- Xcode Command Line Tools / SwiftPM
- `uv`，用于构建可重定位的内嵌 Python 运行时

开发验证：

```bash
cd macos-native
swift test
swift build
./scripts/build-app.sh
open "build/AI抓包工具.app"
```

说明：SwiftPM 裸可执行文件只用于编译验证，实际桌面窗口通过 `.app` 包运行。

构建完整的内部开发包：

```bash
cd ..
TRACEDECK_RELEASE_KIND=development ./release/package.sh
```

开发 ZIP 使用 ad-hoc 签名，文件名会明确包含 `development-arm64`。正式分发必须使用 Apple Developer ID 并完成公证：

```bash
TRACEDECK_RELEASE_KIND=distribution \
MACOS_SIGN_IDENTITY="Developer ID Application: Company Name (TEAMID)" \
MACOS_NOTARY_PROFILE="ai-capture-notary" \
./release/package.sh
```

`release/notarize-app.sh` 只会在 `notarytool`、`stapler` 和 `spctl` 全部通过后生成最终 ZIP；不存在自动降级为未公证正式包的路径。

Jenkins 包源：

```bash
export JENKINS_BASE_URL="http://192.168.77.150:8080"
export JENKINS_USERNAME="jenkins"
export JENKINS_PASSWORD="..."
```

如果 Jenkins 当前允许内网匿名读取，用户名密码可以不配置。不要把真实密码写入仓库。源码运行时
可以使用已被 `.gitignore` 忽略的 `config/local.json`；下载版 App 不应修改签名包内部文件，需由
管理员通过受控启动环境注入配置。

完整回归：

```bash
cd ..
env -u CAPTURE_DEVICES_CONFIG -u CAPTURE_RUNTIME_DIR \
  python -m unittest discover -v tests
swift test --package-path macos-native
macos-native/scripts/build-app.sh
codesign --verify --deep --strict --verbose=2 \
  "macos-native/build/AI抓包工具.app"
```

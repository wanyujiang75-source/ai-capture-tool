# 抓包工具 macOS 原生桌面端

这是 SwiftUI 原生桌面端，不使用 React/WebView 作为主界面。普通用户请先阅读
[安装指南](../INSTALL.md) 和 [桌面端使用指南](../docs/desktop-user-guide.md)；本文件只说明开发、构建和发布。

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
open "build/抓包工具.app"
```

说明：SwiftPM 裸可执行文件只用于编译验证，实际桌面窗口通过 `.app` 包运行。

构建完整的内部开发包：

```bash
cd ..
TRACEDECK_RELEASE_KIND=development ./release/package.sh
```

开发 ZIP 使用 ad-hoc 签名，文件名含 `development-arm64`，通过 GitHub 预发布页手动分发。

## 通过 GitHub Actions 发布预览版

准备好新版本代码后，在同一次推送中新增一份 `release/desktop-previews/X.Y.Z-name.md`，写上要显示给同事的更新说明，再推送到 `main`。例如 `release/desktop-previews/1.0.1-update-notes.md`。每次发布使用新的、更高的三段版本号。小更新可从 1.0.0 升到 1.0.1，功能更新可升到 1.2.0。名称部分使用小写英文字母、数字或短横线。

「Desktop preview」工作流使用推送结束时的提交，在 GitHub 的 macOS arm64 runner 上构建并验证安装包。发布步骤创建预览 Release，上传桌面 ZIP 和 SHA-256，再公开两项文件。已装带「更新」按钮的同事可以从该入口读到新版说明并下载。同版本或更高版本显示「已是最新版」。

同一个推送新增一份说明即可。修改历史说明时，直接在已发布 Release 上更正。需要恢复中断的发布任务时，在 Actions 选择重新运行失败的任务，以继续使用原构建产物。

自动发版复用已发布且签名一致的 Android 连接助手。助手源码变更时，需要先用原签名构建发行基准，并在 `release/desktop-preview-ci.py` 更新基准包信息和源码树摘要。这样已有助手可原位升级。

## 发布支持应用内更新的正式版

首次发布准备 Apple Developer ID Application 签名身份及 `xcrun notarytool` 的钥匙串配置。
在发行 Mac 上生成 Sparkle 签名密钥并保管好私钥。后续版本继续使用相同的签名团队和更新公钥。

```bash
# 从仓库根目录执行
swift package --package-path macos-native resolve
sparkle_tools=macos-native/.build/artifacts/sparkle/Sparkle/bin
"$sparkle_tools/generate_keys" --account ai-capture-updates
export SPARKLE_PUBLIC_ED_KEY="$("$sparkle_tools/generate_keys" --account ai-capture-updates -p)"
```

为每次发布选取唯一的三段版本号和递增的整数构建号。下方的 `0.2.0` 和 `2` 仅作示例。
发下一版前，以最新正式 Release 的 `appcast.xml` 里的 `sparkle:version` 为准，确保新构建号更大。

```bash
TRACEDECK_RELEASE_KIND=distribution \
TRACEDECK_VERSION=0.2.0 \
TRACEDECK_BUILD_NUMBER=2 \
MACOS_SIGN_IDENTITY="Developer ID Application: Company Name (TEAMID)" \
MACOS_NOTARY_PROFILE="ai-capture-notary" \
./release/package.sh
```

可设置 `SPARKLE_RELEASE_NOTES` 为 Markdown 更新说明的文件路径，打包时会嵌入版本清单。
Sparkle 私钥默认从钥匙串读取。使用受保护的 CI 密钥文件时，将文件放在仓库目录外，再通过 `SPARKLE_PRIVATE_ED_KEY_FILE` 指定路径。
Apple 公证成功后，脚本生成并验证 Sparkle 签名。发布同一 tag 对应的四个文件：

| 文件 | 用途 |
| --- | --- |
| `release/AI-Capture-Desktop-0.2.0-arm64.zip` 和同名 `.sha256` | 首次安装和手动升级 |
| `release/.updates/0.2.0/AI-Capture-Update-0.2.0-arm64.zip` | Sparkle 安装 |
| `release/.updates/0.2.0/appcast.xml` | 已签名的版本清单 |

先以 `v0.2.0` 创建 GitHub Release 草稿，关联构建对应的提交，上传四个文件。把要在桌面「更新」窗口显示的版本说明写入 GitHub Release 正文。核对清单中的下载地址和资产名后一起发布，将该版设为最新正式 Release。App 使用固定的 `/releases/latest/download/appcast.xml`，清单使用带版本 tag 的包地址。签名后保留文件原样。首个正式版发布后，验证「检查更新…」能够读取清单并显示已是最新版。从第二个正式版开始，用上一版验证下载、安装、重启和原有数据。

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
  "macos-native/build/抓包工具.app"
```

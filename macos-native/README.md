# AI抓包工具 macOS 原生桌面端

这是新的 SwiftUI 原生桌面端，不使用 React/WebView 作为主界面。

V1 目标：

- 原生 macOS 窗口。
- 管理本机 FastAPI 抓包运行时。
- 调用现有后端 API 完成设备、应用、抓包和接口分析。
- 后续打包成 `.app/.dmg` 供其他 Mac 用户本机安装使用。

开发验证：

```bash
cd macos-native
swift build
./scripts/build-app.sh
open "build/AI抓包工具.app"
```

说明：SwiftPM 裸可执行文件只用于编译验证，实际桌面窗口通过 `.app` 包运行。

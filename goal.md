# 桌面端完整功能验收目标

验证当前 `codex/desktop-one-click-ready` 工作树可以交付为 macOS 本机桌面应用，并形成以下闭环：桌面端自启动本机后端、一键环境准备、Google Play 模拟器准入、网络与 Frida 检查、Jenkins/本地 APK 安装、应用启动、实时抓包、请求与响应查看、停止后的资源清理，以及可下载发行包完整性。

## 当前增量目标：Android 运行日志控制台

将桌面端左侧现有“日志”入口从占位页升级为实时 Android Logcat 控制台。用户选择设备和应用后，默认自动查看目标应用进程日志，并可切换系统日志与崩溃日志；页面支持暂停、继续、清空当前视图、关键字搜索、日志级别过滤和自动滚动。

日志功能必须按设备隔离，不依赖 Frida，不修改 Android 全局代理，不执行 `adb logcat -c`，不持久化可能包含账号或 Token 的原始日志。桌面端停止读取或设备释放后，后台 Logcat 进程必须自动退出。

## 边界

- 仅验收 macOS + Android。
- 不验证 Windows、Linux、iOS 或服务器多人模式。
- 不执行 `wipe-data`、`pm clear`，不删除 Google/App 登录态。
- 不停止或修改不属于本项目的模拟器、端口或进程。
- Google 密码和登录动作由用户自行完成；验收只检查准入状态。

## 验收命令与证据

- `python -m unittest discover tests`
- `npm --prefix web run build`
- `macos-native/scripts/build-app.sh`
- `release/package.sh`
- `python -m unittest -v tests.test_logcat_service tests.test_console_api`
- `swift test --package-path macos-native`
- 真实启动 `AI抓包工具.app`，检查 `127.0.0.1:7001`、Environment Doctor、Google Play 镜像、设备 Doctor、Frida、Jenkins、抓包 session、flow detail/cURL。
- 在真实模拟器中启动一个测试 App，确认“日志”页能显示应用日志、系统日志和崩溃缓冲区，切换设备或离开页面后无孤儿 `adb logcat` 进程。
- 检查发行包包含桌面 App 与内嵌后端，且不包含开发 runtime、数据库、账号和抓包历史。

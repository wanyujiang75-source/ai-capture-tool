# Android 真机日志支持实施计划

> **执行约束：** 本计划作为 `progress.md` 中单一任务 L5 执行，按 TDD 完成，不修改 Frida、抓包代理、Android 全局代理或其他项目进程。

**目标：** 优化桌面端日志模块，使模拟器与已授权的 USB/无线 Android 真机都能自动发现并读取应用、系统、崩溃日志，同时修复设备发现破坏模拟器配置、断连持续轮询和离页延迟释放的问题。

**架构：** 后端继续复用独立 `LogcatService`，增强 ADB 设备解析、稳定身份和结构化状态；桌面端新增日志专用设备发现与前台应用解析，不把真机强行纳入 Frida/抓包准入。设备日志生命周期由 `LogcatController` 显式拥有，页面离开即停止。

## 实施步骤

1. 先新增 Python 回归测试，覆盖 `device/unauthorized/offline` 解析、USB/无线分类、稳定且不冲突的真机 ID、重复发现复用记录，以及发现真机时保留既有 AVD。
2. 实现独立的后端日志设备发现与准入：只持久化已授权在线设备，返回阻塞设备摘要，不改变原抓包设备池接口及既有模拟器配置；日志启动错误按真机/模拟器给出精确恢复动作。
3. 先新增 Swift 回归测试，覆盖设备类型解码、发现 API、真机文案、断连停止轮询和离页主动停止。
4. 实现桌面日志页：进入/刷新时发现设备，展示连接类型，应用日志跟随所选设备前台应用，未授权和无设备时显示可操作引导，离页立即释放会话。
5. 完成 Python、Swift、App 构建/签名和真实 ADB 环境验收；无真实手机连接时明确记录该项为待真机补证，不用模拟器结果冒充真机实测。

## 验收

- `python3 -m unittest -v tests.test_console_core tests.test_console_api tests.test_logcat_service`
- `python3 -m unittest discover -q tests`
- `swift test --package-path macos-native`（若本机 Xcode Testing 工具链不可用，记录环境证据并以生产 Swift 构建及聚焦源码契约测试补证）
- `macos-native/scripts/build-app.sh`
- `codesign --verify --deep --strict macos-native/build/抓包工具.app`
- `adb devices -l` 与进程检查证明日志会话结束后无本项目 `adb logcat` 残留。

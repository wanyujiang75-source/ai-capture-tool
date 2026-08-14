# 抓包工具桌面端使用指南

本文面向在自己 Mac 上使用 `抓包工具.app` 的测试、产品和开发人员。当前版本仅支持
macOS + Android；iOS、Windows、Linux 和服务器多人共享不在桌面端 V1 范围内。

## 1. 使用前准备

### 1.1 Mac 要求

- macOS 14 或更高版本。
- Apple Silicon（M1/M2/M3/M4）。当前内嵌运行时不支持 Intel Mac。
- 建议至少 16 GB 内存、25 GB 可用磁盘空间。Android SDK、Google Play 系统镜像和
  模拟器数据占用主要磁盘空间，抓包工具自身约 256 MB。
- 能访问 Google Android 仓库；安装 Jenkins 测试包时还需连接公司内网或 VPN。

### 1.2 Android 要求

桌面 App 已包含抓包后端、mitmproxy 和 Frida 客户端，但不把 Android SDK 和系统镜像打进
安装包。新 Mac 需要先安装 Android Studio，或至少安装 Android command-line tools，并确保
以下命令可用：

```bash
adb version
emulator -version
sdkmanager --version
avdmanager list avd
```

Android SDK 默认从 `$ANDROID_SDK_ROOT` 或 `~/Library/Android/sdk` 查找。建议先打开一次
Android Studio，完成 SDK License 接受和基础组件下载。

## 2. 安装桌面 App

完整安装路径见 [安装指南](../INSTALL.md)，其中包括 Codex 辅助安装、手动下载、源码构建、升级和新主机配置。下面是手动安装的最短流程：

1. 下载 `AI-Capture-Desktop-*-arm64.zip`。
2. 校验下载页面提供的 `.sha256`（可选但推荐）：

   ```bash
   shasum -a 256 -c AI-Capture-Desktop-*.zip.sha256
   ```

3. 解压 ZIP，把 `抓包工具.app` 移入 `/Applications`。
4. 双击打开。正式公证包应直接通过 Gatekeeper。
5. 内部预览包如果显示“Apple 无法验证‘抓包工具’”，点击“完成”，不要点击“移到废纸篓”。打开
   “系统设置 -> 隐私与安全性”，向下找到该 App 的拦截提示，点击“仍要打开”，完成 Mac 登录验证后再确认“打开”。

“仍要打开”通常只在尝试启动 App 后约一小时内显示。参考 [Apple 官方操作说明](https://support.apple.com/zh-cn/guide/mac-help/-mh40616/mac)。

不要直接在 ZIP 预览窗口内运行 App，也不要移动或删除 App 内的 `Contents/Resources`。

## 3. 第一次准备环境

打开 App 后先查看左侧“环境”。出现“内部服务已就绪”表示本机 FastAPI 后端已由桌面 App
托管，无需再运行 `start.sh`，也无需打开 `127.0.0.1:7001`。

然后进入“抓包”：

1. 在“设备”中选择 `device-1`。
2. 点击“打开模拟器”。桌面端会自动检查并准备 `AI_Capture_AVD_01`：只选择 Apple Silicon
   原生 `arm64-v8a` 的 Google Play 镜像，检查 Hypervisor.Framework，并在缺少镜像时尝试安装。
   首次下载 Android 镜像可能需要数分钟。
3. 等待 Android 桌面出现并手动解锁。模拟器启动未完成或处于锁屏状态时，不允许安装 APK。
4. 打开目标 App 后点击“一键开始抓包”。工具会继续自动检查设备状态、网络、Android 代理、
   root/Magisk 和 Frida，不需要再逐项点击检测按钮。
5. 如果 App 依赖 Google 登录，在模拟器中打开 Play Store 并手动登录。公司内部模式默认不强制
   Google 登录；启动 App 前设置 `REQUIRE_GOOGLE_LOGIN=1` 可启用严格准入。

自动准备只操作本项目设备、端口和进程。发现端口被其他程序占用时只会报错，不会终止其他项目。

模拟器性能按宿主机自动选择：16 GB 及以上内存且至少 8 个逻辑核心时使用
`4 核 / 4096 MB / GPU host / 8 GB 数据分区`，资源较低时使用 `2 核 / 2048 MB` 均衡档。
如果同名 AVD 已存在但不是 Google Play 原生架构镜像，桌面端会保留原 AVD，自动创建或复用
带 `_GooglePlay` 后缀的合规替代设备并切换抓包设备绑定。它不会覆盖、wipe、删除原 AVD，也不会
随机调用用户的其他模拟器。

## 4. 安装 App

安装来源与抓包目标相互独立。Jenkins、本地 APK、Android Studio、ADB 或其他工具都只负责把 App
安装到设备；抓包目标始终由模拟器当前前台 App 决定。

### 4.1 本地 APK

在“设备与应用”页选择已启动、已解锁的设备，点击“选择本地 APK”。桌面端会把 `.apk` 安装到
当前设备并登记为生产包。安装完成后，在模拟器中手动打开该 App；不需要再到应用库选择一次。

### 4.2 Jenkins 测试包

“设备与应用”页会读取 Jenkins 企业构建任务的最新 APK：

1. 先选择已启动、已解锁的安装设备。
2. 找到目标构建，点击“安装”。
3. 页面显示“正在从 Jenkins 下载构建产物并执行 Android 包安装”时保持模拟器在线。
4. 安装完成后，包名、Activity 和版本信息会同步到本机应用库。
5. 在模拟器中打开刚安装的 App，抓包页会自动识别它。

Jenkins 只是测试包来源，不会自动成为当前抓包目标，也不会覆盖正在分析的 App。

当前本地入口支持单个 `.apk`。复杂 split APK、`.apks` 或 `.zip` 仍属于高级接口能力。

### 4.3 其他安装方式

通过 Android Studio、ADB 或其他安装工具预先安装的 App 无需导入应用库。只要包已安装且能在设备
前台打开，桌面端会自动读取包名、Activity 和版本；未登记的 App 会以 `production + auto` 幂等登记。

Launcher、System UI 和锁屏不会被误登记为业务 App。

### 4.4 Jenkins 无法加载

先确认 Mac 已连接公司内网或 VPN，并可访问页面显示的 Jenkins 地址。默认配置允许匿名读取；
需要账号时由管理员通过运行环境提供：

```bash
export JENKINS_BASE_URL="http://jenkins.example.internal:8080"
export JENKINS_USERNAME="jenkins-user"
export JENKINS_PASSWORD="<从安全存储读取>"
open -na "/Applications/抓包工具.app"
```

不要把真实密码写入仓库、截图、抓包说明或共享脚本。

## 5. 启动抓包

推荐顺序：

1. 在“抓包”页选择设备。
2. 点击“打开模拟器”，等待设备在线并解锁。
3. 在模拟器中打开目标 App；桌面端每 2 秒检查一次前台组件，包名变化时自动解析目标。
4. 状态显示“可开始”或“可自动准备”后点击“一键开始抓包”。即使 Frida 尚未运行，该按钮也会先自动准备 Frida 和网络环境，再创建 Session。
5. 状态显示“等待流量”后，在模拟器中操作需要分析的功能。
6. 捕获到至少一条接口后状态自动变为“可抓包”；进入“接口”页查看实时请求。
7. 完成后回到“抓包”页点击“停止抓包”。停止会清除旧的捕获状态，同一前台 App 可立即开始下一次 Session。

如果抓包运行期间切换到另一个 App，桌面端不会自动停止或切换当前 Session，而是提示先停止现有
抓包，避免历史丢失和误清理链路。

不要同时在同一设备启动第二个抓包任务。桌面端检测到已有 Session 时会自动接入该 Session；
需要重新开始时先点击“停止抓包”。

## 6. 查看接口

“接口”页每 2 秒刷新当前活动 Session，最新接口显示在列表中。点击一条记录后可切换：

- `Request`：请求 headers/body；GET 请求可能没有 body。
- `Response`：响应 headers/body。请求体为空但响应存在时，页面优先打开 Response。
- `cURL`：用于复现请求的命令，可能包含本机测试账号的 header 或 token，分享前必须脱敏。

`200` 只表示服务端返回成功状态，不保证响应一定有业务 body。`NO_RESPONSE` 表示当前抓包链路
没有捕获到响应，不能把它当作空 JSON 或伪造成功数据。

## 7. 查看 Android 日志

左侧“日志”页不依赖 Frida，可切换三种 Logcat 来源：

- `应用`：按当前 App PID 过滤。App 重启后会自动等待并连接新 PID。
- `系统`：查看设备主 Logcat 缓冲区。
- `崩溃`：查看 crash 缓冲区。

页面支持暂停/继续、清空当前内存视图、Tag/消息搜索、最低级别过滤和自动滚动。
“清空”不会执行 `adb logcat -c`，不会删除设备原始日志。日志最多保留 5,000 条或 2 MB，
只存于本机内存；离开日志页后约 30 秒会自动结束该设备的 Logcat 子进程。

## 8. 数据与退出

运行数据保存在：

```text
~/Library/Application Support/AI抓包工具/runtime-native/
```

该目录可能包含 SQLite 数据库、APK 缓存、抓包文件、请求 headers、token 和后端日志。不要上传到
Git，也不要直接共享整个目录。升级 App 时保留该目录可以继续查看本机历史；删除该目录会清除
桌面端运行状态，但不会自动卸载 Android 模拟器中的 App。

停止抓包会停止 exporter、Frida hook 和 mitmproxy，并清理 Android 抓包代理。退出桌面 App 会
停止它自己启动的后端，不会终止本机其他项目的服务。若模拟器窗口仍在运行，可从 Android Emulator
正常关闭；禁止使用 `wipe-data`、`pm clear` 或无确认卸载来处理普通故障。

## 9. 常见问题

### Apple 无法验证“抓包工具”

这表示当前下载的是未经 Apple 公证的内部预览包，不是 Android 环境或抓包后端故障。只有确认文件来自本项目 GitHub Releases 且 SHA-256 校验通过时才继续。点击“完成”后，到“系统设置 -> 隐私与安全性”点击“仍要打开”。不要关闭 Gatekeeper，不要执行删除 quarantine 属性的命令。

### 内部服务启动失败

确认 7001 端口未被占用，并查看：

```text
~/Library/Application Support/AI抓包工具/runtime-native/native-backend.log
```

工具不会自动杀死占用端口的其他进程。

### 找不到 Android SDK

安装 Android Studio，或设置正确的 `ANDROID_SDK_ROOT`。确认 `adb`、`emulator`、`sdkmanager`、
`avdmanager` 均来自同一个 SDK 根目录。

### 模拟器启动或安装失败

等待 `boot completed`，在模拟器窗口完成解锁后重试。页面提示“当前抓包任务运行中”时，先停止
抓包再安装。签名冲突或降级安装不会通过卸载方式自动修复，以免清除登录态。

### 模拟器没有网络

先确认 Mac 本身可联网，再执行“一键准备环境”。维护/登录阶段可使用宿主机代理；正式抓包前工具
会清空 Android 全局 `http_proxy`，避免 HTTP proxy 与 SOCKS 导流冲突。不要在抓包运行时手动设置
Android 全局代理。

### Frida 不可用

重新执行“一键准备环境”，确认使用的是工具准备的 Google Play AVD、设备已解锁且 Magisk/root
可用。Frida server 按设备端口隔离；不要手工启动另一个实例占用同一端口。

### 抓不到响应

先确认目标 App 在前台并实际触发了网络功能，再查看“接口”页和“日志”页。部分 App 使用证书绑定、
内置 CA、双向 TLS、QUIC 或自定义网络栈，可能只能捕获请求或完全无法解密。此时保留当前抓包代码和
Session 证据，再针对该 App 评估额外适配，不应把广告流量或 `200` 状态误判为目标业务响应。

状态长时间停留在“等待流量”表示链路已启动，但当前 App 尚未产生可导出的请求。先进入实际业务页
触发网络功能；不要仅凭首页静置 30 秒或自动滑动无结果就判定抓包失败。

## 10. 卸载

1. 先停止活动抓包并退出桌面 App。
2. 删除 `/Applications/抓包工具.app`。若仍保留升级前的 `/Applications/AI抓包工具.app`，也可一并删除。
3. 如确认不再需要历史数据，再手动删除：

   ```text
   ~/Library/Application Support/AI抓包工具/
   ```

Android SDK、AVD 和模拟器中的 App 是独立资源，不会随桌面 App 自动删除。

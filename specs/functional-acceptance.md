# 桌面端完整功能验收规格

## A. 自动化回归

1. Python 后端全量测试零失败。
2. React/Vite 构建成功。
3. Swift 桌面端构建成功。
4. 发行包构建成功且目录结构符合发布边界。

## B. 桌面运行时

1. 打开 `.app` 后自动托管本机 FastAPI，不依赖开发目录中的已启动服务。
2. 后端只监听 `127.0.0.1:7001`。
3. 桌面端可显示环境、设备、Jenkins、抓包与接口分析视图。
4. 关闭桌面端后本项目后端可被正确结束，不影响无关进程。

## C. 环境和设备准入

1. Environment Doctor 能检查 Python、Android SDK、adb、emulator、sdkmanager、mitmproxy、Frida 和项目端口。
2. 默认 AVD 必须使用 `google_apis_playstore` 镜像。
3. 设备启动后可检查 boot、unlock、网络、Android proxy、Google Play、Google 账号、root/Frida。
4. Google Play 镜像必须存在；公司内部默认模式允许设备未登录 Google。启用
   `REQUIRE_GOOGLE_LOGIN=1` 后，未登录设备必须阻止安装、打开 App 和抓包，并给出可执行提示。
5. 抓包模式前自动清空 Android global `http_proxy`。

## D. APK 与 Jenkins

1. Jenkins 列表能返回最新企业构建 APK。
2. 模拟器未就绪时安装返回专业、可执行的提示。
3. 模拟器就绪且当前 Google 准入策略通过时，APK 安装到所选设备并同步应用信息。
4. 本地上传 APK 与 Jenkins 安装均不能误操作其他设备。

## E. 抓包闭环

1. 启动应用、Frida 和抓包后形成 active session。
2. App 操作产生的新接口实时出现在列表顶部。
3. flow 详情同时展示请求 headers/body、响应 headers/body、状态、耗时和 cURL。
4. HTTP 200 且有响应体的 flow 必须能读取响应；无响应必须明确显示 `NO_RESPONSE`，不能伪造内容。
5. 停止抓包后 exporter、Frida hook、mitmproxy 和项目端口清理，Android proxy 恢复。

## F. 分发到新 Mac

1. 发行包不携带本机数据库、抓包历史、APK 缓存、Google 账号或 App 登录态。
2. 发行包内包含桌面 App、本机后端、脚本、前端构建和依赖清单。
3. 缺 Android SDK/Google Play system image 时 Doctor 能识别并给出一键准备或明确修复建议。
4. 本轮不宣称在真实第二台全新 Mac 上通过，只将可本机模拟的分发检查标记为通过；跨机器实装单列为残余验证。

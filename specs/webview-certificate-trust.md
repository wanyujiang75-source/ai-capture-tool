# 内嵌网页证书信任修复

## 证据与假设

- 2026-10-22 PokeHub“同步数据”页标题正常、网页内容空白。
- 抓包 #66 的 Java bridge 不存在，Android CA hook 被跳过，Flutter hook 正常。
- WebView 的 TLS -202 与代理日志的目标 Vercel 域名 certificate unknown 多次对应。
- Frida 17 不再内置 Java bridge；已打包的 frida-tools 14.8.2 提供 bridges/java.js。

## 修复约束

- 在同一个 Frida script realm 中先加载 bridge，再执行 Android 证书 hook。
- 从已安装 frida-tools 包资源读取，不依赖当前目录、Node、网络下载或开发机路径。
- 仅在启用 Android 证书 hook 时加载；保留其他抓包模式。
- 只信任配置的 CA，不使用无条件忽略证书错误，不改宿主机或全设备信任设置。
- bridge 缺失或运行失败必须可诊断，不把跳过注入视为成功。
- 保留现有抓包历史、应用与 Google 登录数据；允许必要的抓包重启，不执行卸载/清数据。
- 不顺手修复 Jenkins 性能、业务 RPC 404 或 exporter 的暂缺响应问题。
- 抓包脚本诊断输出必须使用桌面传入的 CAPTURE_RUNTIME_DIR，禁止写入签名后的应用包；这是构建后实际抓包验收暴露的同链路问题。

## 验收

1. 单元回归：bridge 在 hook 前执行；禁用 hook 不加载；包资源缺失时明确失败；模拟 Frida 消息失败不能误报成功。
2. 内嵌 Python 加载真实 bridge 资源，无开发环境依赖。
3. 真实 PokeHub 进程证书注入成功，验证系统 TLS 能访问目标 HTTPS，不接受未知 CA。
4. 桌面构建与签名通过，重启抓包后在“同步数据”页验证；无法操作时明确记录视觉验收缺口。

## 2026-10-22 验收证据

- TDD RED：旧脚本无 bridge/bootstrap 完成信号；初始化超时仍存活；诊断日志写进应用包。分别复现后修复。
- Python：`python3 -m unittest -q tests.test_console_core tests.test_console_api tests.test_device_network tests.test_flutter_proxy_unpin_capture`，最终 198 项通过。
- 打包：`tests.test_native_app_packaging` 的 8 项检查通过，包括移动 App 后加载真实 Java bridge；只生成本地验收产物，未发布。
- 真机链路（当前 Android 模拟器内的实际 PokeHub PID 3404）：`android-system-ca-ready`；Android HTTPS 请求目标网站 HTTP 200；临时生成的无关自签名证书被 `Trust anchor ... not found` 拒绝。
- 桌面实际点击开始抓包后任务 #67 捕获 `/zh-Hans/app/sync-data` HTTP 200、正文 11,078 字节，及 CSS、JavaScript、图片响应；用户随后明确反馈“可以了”。页面恢复为用户实测，不记为自动化截图验收。
- 构建后签名复核发现诊断脚本把日志写进 `.app`，另有本轮直接运行内嵌 Python 的 QA 产生字节码缓存。保留旧诊断日志到运行目录，再修复脚本遵循 `CAPTURE_RUNTIME_DIR` 并重新构建；后续 QA 使用 `PYTHONDONTWRITEBYTECODE=1`。
- 最终 `webview-ca-20261022-r2` 从桌面启动任务 #68，日志再次出现 `android-system-ca-ready`，诊断路径位于用户运行目录，`.app/Contents/Resources/backend/runtime` 不存在；运行后 `codesign --verify --deep --strict` 通过。
- 旧抓包 #66/#67 文件与登录数据保留。Jenkins 刷新性能问题、业务 RPC 404 和 exporter 暂缺响应未包含在本次修复。

参考：https://frida.re/news/2025/05/17/frida-17-0-0-released/

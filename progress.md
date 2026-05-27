# 进度记录

## 2026-05-12

- 读取了当前 README、FastAPI 后端入口、抓包脚本和核心测试。
- 确认当前项目已具备本机 Web 控制台、应用库、启动/停止抓包、接口详情和 cURL 导出能力。
- 确认当前 Web 服务重启后会清空页面里的抓包任务记录，保留应用库和原始文件。
- 创建 `task_plan.md`、`findings.md`、`progress.md`。
- 创建详细规划书：`docs/长期安卓抓包平台规划书.md`。
- 根据用户反馈调整规划边界：当前先做 Android，iOS 只预留入口，不进入本期实现。
- 对规划书进行了评审，发现 P0/P1 顺序、iOS 数据模型预留、测试保护登录态、敏感信息导出策略需要进一步收敛。
- 开始执行 P0 第一批稳定性改造。
- 新增 `capture_console/platforms.py`，统一 platform 校验、iOS 预留状态和 unsupported detail。
- 更新 `capture_console/store.py`，为 `apps` 和 `capture_sessions` 增加 `platform` 字段和迁移逻辑。
- 更新 `capture_console/app.py`，应用 payload 支持 platform，并在启动抓包前拒绝 iOS 预留应用。
- 更新 `capture_console/runner.py`，增加保留登录态模拟器检查和破坏性命令拒绝。
- 新增 `tests/test_console_api.py`，覆盖 iOS 预留应用不能启动抓包且不触碰 Runner。
- 扩展 `tests/test_console_core.py`，覆盖 platform 默认值、iOS 预留、破坏性命令拒绝、非保留模拟器配置失败。
- 更新 `web/src/main.jsx` 和 `web/src/styles.css`，新增“选择目标应用”区域，应用添加支持平台选择，启动抓包前明确选择目标 App。
- 更新 `capture_console/static/index.html`，让无 Vite 构建时的静态兜底页也支持平台添加、应用选择和 iOS 预留阻断。

## 验证

- 本次是规划文档输出，不涉及代码运行逻辑变更。
- 没有执行新的抓包任务。
- 已检查规划书章节并完成边界修订。
- `python3 -m unittest tests/test_console_core.py` 通过。
- `.venv-console/bin/python -m unittest tests/test_console_api.py` 通过。
- `PYTHONPATH=. .venv-console/bin/python -m py_compile capture_console/*.py` 通过。
- 已启动 `http://127.0.0.1:7001`，应用库中 MelodyCraft 已迁移出 `platform: android`。
- 已用临时 iOS 预留应用做 smoke test：`/api/captures/start` 返回 501，随后已删除临时条目。
- `npm run build` 通过，已生成新的 `web/dist`。
- 已在浏览器重新加载 `http://127.0.0.1:7001/`，确认页面包含“添加应用”“选择目标应用”、平台下拉和默认模式启动入口。
- 已执行页面验收：通过浏览器新增临时 Android 应用和 iOS 预留应用，验证应用库展示、目标应用选择、Android 启动按钮可用、iOS 启动按钮禁用。
- 验收结束后已删除临时应用记录，应用库恢复为 MelodyCraft。
- 将项目产品名统一为 `TraceDeck`，页面标题改为 `TraceDeck · Mobile Traffic Intelligence Console`，主视觉改为“移动端接口观测与取证工作台”。
- 同步更新 React 页面、静态兜底页、FastAPI 标题、README 和 Vite package 名称。
- 已在浏览器刷新 `http://127.0.0.1:7001/`，确认新品牌标题显示正确，旧的“长期安卓抓包控制台 / Android Capture Console”页面标题已移除。
- 尝试执行 TraceDeck + 保留模拟器端到端抓包验收，已启动 `Medium_Phone_API_36.1 / emulator-5554`。
- 修复后端健康检查：应用库已保存 Activity 时，不再因为 Android 自动 launcher 解析失败而误拦截抓包启动。
- 当前端到端验收暂停在模拟器锁屏：系统状态是 `RUNNING_LOCKED`，需要用户手动解锁后才能继续启动 App 和抓包。

## 2026-05-14

- 修复 `flutter-socks` 健康检查：Frida 不再依赖 `init.svc.frida_server`，改为检查 `frida-ps -H 127.0.0.1:27042`、adb forward 和进程权限。
- 修复 Frida 启动脚本：在 Google Play/rootAVD 这类 `adb root` 不可用的镜像上，自动使用 Magisk `su -c` 启动 root 权限的 `frida-server`。
- 修复多设备误连问题：`flutter_proxy_unpin_capture.py` 固定连接 `127.0.0.1:27042`，避免 `frida.get_usb_device()` 选到真实设备 `d265cb0a`。
- 已在 Magisk Superuser 中启用 `[SharedUID] Shell / com.android.shell` root 权限，解决 `frida.PermissionDeniedError`。
- 已重新启动 TraceDeck Web 服务和 MelodyCraft `flutter-socks` 抓包 session 21。
- 验证 session 21 正常：`exporter` 和 `frida hook` 均为 running，`runtime/captures/web-20260514-162532-MelodyCraft/candidates.tsv` 已产生业务接口。
- 已确认可抓到 `www.blockdance-test.xyz` 的 MelodyCraft 业务接口，包括 `song/featuresList`、`user/updateUserInfo`、`config/appLaunchActions`、`notification/hasUnreadNotifications` 等。
- 已验证接口详情和 cURL 导出可读；原始文件仍保留真实 headers/token，仅限本机可信环境使用。

## 2026-05-27

- 针对 Mac mini 服务器上模拟器 Google 登录和网络不可用问题，整理了网络链路修复计划。
- 新增计划文档：`docs/服务器模拟器网络修复计划.md`。
- 计划核心决策：区分 Maintenance Mode 和 Capture Mode，避免 Android `http_proxy` 与 `flutter-socks` 抓包链路冲突。
- 计划要求新增主机网络、代理网络、模拟器网络、Google 登录链路、抓包出口的分层准入检查。
- 根据“服务器上还有其他项目运行、端口可能已被占用”的约束，重写计划为 V2。
- V2 计划将 Server Isolation 作为 P0：先做端口/进程/launchd/代理/设备归属预检，再做网络模式切换。
- V2 明确禁止按端口无差别 kill，所有停止操作必须基于项目 pidfile、screen、launchd label 或设备池归属。

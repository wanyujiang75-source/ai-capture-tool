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

## 2026-05-28

- 开始对服务器部署地址 `http://192.168.77.150:7001` 做全量验证，范围限定为 AI 抓包工具。
- 浏览器打开服务器页面成功，首页显示 `AI抓包工具`，当前设备在线，常驻设备 `2/2` 在线。
- 页面初始化状态显示环境、设备、Frida 已通过，但仍停留在抓包冒烟测试阶段。
- 页面顶部 `mitmweb` 链接仍指向 `http://127.0.0.1:9091/?token=android-capture`，远程访问场景下不可直接打开。
- 只读 API 验证完成：首页、状态、环境检查、设备、应用、版本、已安装应用、历史会话、资源接口均返回 200。
- `/api/system/preflight` 返回 `ok=false`，阻塞项是 `19097/19098` 被 `emulator-preview/ws-scrcpy` 占用；按服务器隔离约束未处理这些进程。
- `/api/system/network-check` 返回 `ok=false`，失败目标是 `https://www.google.com/generate_204` 超时。
- 临时 iOS 预留应用 CRUD 验证通过：可保存，启动抓包返回 501，删除后应用库恢复为 MelodyCraft 单条记录。
- 页面“启动抓包测试”执行完成，新建 session 16，抓包链路能启动并自动停止，但结果为 warning：30 秒内未捕获可解析接口，`flow_count=0`。
- 普通抓包启动/停止 API 验证完成，新建 session 17；运行中 `health=running`、9090 代理开放、exporter 和 Frida hook 均为 running；停止后回到 `health=idle`。
- session 16 导出接口可返回产物列表，包含 `all-flows.tsv`、`candidates.tsv`、`exporter.log`、`frida.log`、`summary.md` 等，但 flows 为空。
- `/api/devices/device-1/preview` 返回的模拟器预览地址可访问，预览页标题为 `Emulator Preview`，能看到 `Capture_AVD_01 / emulator-5554` 在线。
- 本地自动化验证完成：`tests/test_console_core.py`、`tests/test_console_api.py`、`tests/test_readiness.py`、`tests/test_exporter_timing.py` 共 81 个 unittest 通过。
- 本地前端构建完成：`npm --prefix web run build` 通过。
- 按用户要求启动 MelodyCraft APK 做完整抓包测试，新建 session 18：`/Users/jenkins/ai-capture-tool/shared/runtime/captures/web-20260528-183809-MelodyCraft`。
- session 18 运行期间 `health=running`、9090 代理监听、exporter 和 Frida hook 均为 running；结束后已停止并恢复 `health=idle`。
- 通过 adb 操作了登录页：点击 `Sign in with Google`、`Privacy Policy`、`Terms of Service`；Google 登录被取消，Privacy/Terms 被系统交给 Chrome 首次使用页，无法进入 App 登录后的业务页。
- session 18 捕获到 2 条候选业务接口，均为 `POST https://www.blockdance-test.xyz/aisong/portal/user/livestatus`，状态 200，request/response JSON 均可解析。
- session 18 导出验证通过：18 个文件，详情接口和 cURL 导出接口可读。
- 排查 Google 登录失败：在无抓包代理干扰、Android `http_proxy=null` 的直连状态下复现，点击 `Sign in with Google` 后进入 `com.google.android.gms/.auth.uiflows.minutemaid.MinuteMaidActivity`，页面停留在 `Checking info…` 超过 30 秒。
- Google 登录日志显示 `Auth ... 5004`，系统日志反复出现 `No network time available`；设备账号状态仍为 `Accounts: 0`。
- 服务器和模拟器到 Google 登录核心域名不可达：`accounts.google.com`、`oauth2.googleapis.com`、`www.googleapis.com`、`play.googleapis.com`、`android.clients.google.com` 的 HTTPS/TCP 或 ping 均失败；`connectivitycheck.gstatic.com` 和部分 `mtalk.google.com` 可达。
- Android 网络时间服务 `time.android.com` 从未成功同步，`mLastSuccessfulNtpServerUri=null`、`mTimeResult=null`。

## 2026-05-29

- 按用户要求验证服务器上的 7890 代理，范围限定为 AI 抓包工具和 `device-1 / emulator-5554`。
- 服务器本机 `127.0.0.1:7890` 可连接，进程监听在本机回环地址；通过该代理访问 `accounts.google.com` 返回 200，访问 `www.google.com/generate_204` 返回 204。
- 通过 AI 抓包工具 API 将 `device-1` 切到维护代理模式，Android `http_proxy` 已设置为 `10.0.2.2:7890`。
- 模拟器内到宿主机 7890 端口连通，点击 MelodyCraft 的 `Sign in with Google` 后，Google 登录流程从 `Checking info…` 进入 `Sign in - Google Accounts` 邮箱输入页。
- 当前没有输入 Google 账号；设备仍显示 `Accounts: 0`，`/api/devices/device-1/google-state` 为 `not_logged_in`。
- AI 抓包工具当前没有活跃抓包任务，`/api/status` 显示 `health=idle`、`active_session=null`；维护代理仍保留为 `10.0.2.2:7890`，便于用户手动完成 Google 登录。
- 用户完成 Google 登录后，`/api/devices/device-1/google-state` 返回 `ok=true`、`google_account_present=true`。
- 启动 MelodyCraft `flutter-socks` 抓包 session 19，输出目录为 `/Users/jenkins/ai-capture-tool/shared/runtime/captures/web-20260529-114342-MelodyCraft`。
- session 19 运行期间 `health=running`、9090 代理监听、exporter 和 Frida hook 均为 running；抓包模式下 Android `http_proxy` 按预期清为 `null`。
- MelodyCraft 成功进入登录后首页并产生业务流量，但页面出现系统 ANR 弹窗 `MelodyCraft isn't responding`。
- session 19 已停止并恢复 `health=idle`、`active_session=null`；停止输出显示 exporter、Frida hook、mitmweb 代理和 Web 监听均已停止。
- session 19 捕获到 78 条候选流量，其中 60 条 HTTP 200，47 条包含 JSON 请求，44 条包含 JSON 响应；代表接口包括 `user/updateUserInfo`、`song/play`、`user/livestatus`、`notification/hasUnreadNotifications`、`music/get_running_tasks`。
- session 19 导出验证通过：`/api/captures/19/export` 返回 346 个文件；抽查 `POST /aisong/portal/user/updateUserInfo` 的详情接口和 cURL 导出均可读。
- 测试收尾后仅对目标包执行 `am force-stop com.meta.inno.monopoly_sticker` 关闭 ANR 状态，未清数据、未卸载、未操作服务器其他项目。
- 已将 `device-1` 恢复到维护代理 `10.0.2.2:7890`，当前 Google 账号仍为已登录状态。
- 按用户反馈优化服务器模拟器预览页 `/Users/jenkins/emulator-preview`：降低默认推流档位为极速，参数调整为 1Mbps、15fps、420x936；流畅/高清档位也整体降码率和帧率。
- 优化预览页布局：将模拟器舞台高度从固定大尺寸改为视口内自适应，1440x900 下页面级 `scrollHeight` 从 993 降到 900，预览画面无需整页上下滚动即可完整显示。
- 仅覆盖并构建 `/Users/jenkins/emulator-preview/frontend/src/App.tsx` 和 `styles.css`，构建通过；原文件已备份到服务器 `/Users/jenkins/emulator-preview/backups/codex-preview-fit-20260529121004`。
- 按用户要求收敛预览页 AVD 列表：服务器 `/Users/jenkins/emulator-preview/server.mjs` 现在读取 `/Users/jenkins/ai-capture-tool/shared/config/devices.macmini.json`，只返回 `enabled=1` 的项目 AVD。
- 预览服务已重启；`/api/devices` 当前只返回 `Capture_AVD_01`、`Capture_AVD_02`、`Capture_AVD_03`，不再展示 Jenkins 账户下历史遗留的 Pixel/Medium/Small/Tablet/Fold AVD。
- 浏览器验证通过：在线设备页只显示 `Capture_AVD_01`；切到“可启动 AVD”只显示 `Capture_AVD_02` 和 `Capture_AVD_03`。
- 服务器原 `server.mjs` 已备份到 `/Users/jenkins/emulator-preview/backups/codex-avd-filter-20260529174830/server.mjs`；未删除任何历史 AVD。

## 2026-06-01

- 按用户要求重新启动服务器上的 MelodyCraft `flutter-socks` 抓包测试，新建 session 20，输出目录为 `/Users/jenkins/ai-capture-tool/shared/runtime/captures/web-20260601-103407-MelodyCraft`。
- session 20 运行期间抓包链路正常：`health=running`、9090 代理监听、exporter 和 Frida hook 均为 running，前台应用为 `com.meta.inno.monopoly_sticker.MainActivity`。
- session 20 已停止并恢复 `health=idle`、`active_session=null`；9090 代理、exporter、Frida hook 均已停止。
- session 20 捕获 129 条候选流量，其中 90 条 HTTP 200、120 条包含 JSON 请求、93 条包含 JSON 响应。
- 代表接口 `POST https://www.blockdance-test.xyz/aisong/portal/config/upgrade` 的详情接口返回 200，cURL 导出返回 200 且内容以 `curl` 开头。
- session 20 导出接口验证通过：`/api/captures/20/export` 返回 610 个文件。
- 测试收尾后已将 `device-1` 恢复到维护代理 `10.0.2.2:7890`，Google Play 可用且 Google 账号仍为已登录状态。
- 复查预览服务 AVD 列表仍只返回 `Capture_AVD_01`、`Capture_AVD_02`、`Capture_AVD_03`。
- 按用户要求尝试抓取 MelodyCraft 流量表，新建 session 21，输出目录为 `/Users/jenkins/ai-capture-tool/shared/runtime/captures/web-20260601-113616-MelodyCraft`。
- session 21 中通过目标模拟器执行轻量滑动和点击触发；共捕获 49 条候选流量，其中 35 条 HTTP 200、40 条 JSON 请求、32 条 JSON 响应。
- session 21 导出接口验证通过：`/api/captures/21/export` 返回 228 个文件；抽查 `GET /aisong/portal/reward/bannerDetailV2` 的详情接口和 cURL 导出均可读。
- 已生成本地流量表文件 `output/melody_session21_traffic_table.md`；测试收尾后 `device-1` 已恢复维护代理 `10.0.2.2:7890`。
- 按用户反馈优化服务器模拟器预览页顶部：移除 header 中间的状态胶囊标签 `在线 / 启动中 / Jenkins APK / ADB`，保留标题和右侧操作按钮。
- 已重新构建 `/Users/jenkins/emulator-preview/frontend`；当前页面加载新产物 `/assets/index-BfBq_2Uj.js` 和 `/assets/index-tuhzHDm4.css`，验证产物中已无 `health-strip`。

## 2026-06-05

- 用户确认新的重构方向选择“本机开箱工具”：别人 clone 当前项目后在本机运行 `./start_capture.sh`，通过本机页面完成设备和 App 配置。
- 用户明确本轮不处理服务器上的部署和预览服务，修改范围只限当前本机项目。
- 后续设计应把服务器/Mac mini/Jenkins 相关路径从主流程中移除或降级为非默认能力，但本轮不需要连接或修改服务器文件。
- 用户进一步澄清目标不是只给当前本机使用，而是要做成“单独的项目，所有人都可以下载使用”。后续范围需要覆盖项目命名、安装脚本、默认配置、首次向导、README、发布包、敏感历史数据清理和服务器部署降级。
- 已创建计划书：`docs/独立可下载项目重构计划书.md`。计划覆盖目标形态、非目标、当前问题、推荐架构、配置模型、设备模型、App 模型、重构阶段、测试计划、风险和完成标准。
- 已按 V2 计划实现 TraceDeck 独立可下载项目化改造：
  - 新增 `setup.sh`、`start.sh`、`config/local.example.json`、`release/package.sh` 和 `docs/legacy/README.md`。
  - 后端新增本机配置读取 `capture_console/local_config.py`、ADB 设备发现/端口分配 `capture_console/device_discovery.py`。
  - `CaptureStore` 默认不再种入固定设备池；新增 `upsert_device`，设备改为运行期发现后写入。
  - 新增 `/api/devices/discover` 和 `/api/apps/installed`，并让 `/api/status` 在空设备状态下返回 idle。
  - React 页面和静态兜底页移除 MelodyCraft、固定 AVD、服务器默认语境，新增“发现设备”和“读取当前设备已安装 App”入口。
  - README 改为外部用户快速开始：`./setup.sh`、`./start.sh`、打开 `http://127.0.0.1:7001`。
- 验证完成：
  - `npm --prefix web run build` 通过。
  - `python -m unittest discover tests` 通过，95 个测试 OK。
  - `./release/package.sh` 通过，生成 `release/TraceDeck-20260605-184159.tar.gz`。
  - 发布包清单包含 `setup.sh`、`start.sh`、`web/index.html`、`web/src/main.jsx`、`web/dist/index.html`、`config/local.example.json`。
  - 发布包排除项检查通过：未包含 `runtime/`、`.venv*`、`web/node_modules`、`config/local.json`。
  - 干净目录 smoke 通过：解压最新 release 后运行 `./setup.sh`，再用独立端口执行 `./start.sh`，`/api/status` 可访问，测试服务已停止且端口无遗留监听。

## 2026-06-08

- 继续收尾本机 TraceDeck 项目化改造。
- 发现旧 `.venv-console` 使用 Python 3.9.6，无法安装 `mitmproxy>=12`；新增 `scripts/console_python.sh`，统一 `setup.sh`、`scripts/start_web_services.sh`、`scripts/start_console.sh` 的 Python 选择和 venv 检查逻辑。
- 新逻辑要求 Python 3.12+；默认项目 venv 不兼容时会重建，避免继续复用低版本 venv。
- 停止旧 session 60：已通过 `/api/captures/stop?device_id=device-1` 停止 exporter、Frida hook、mitmweb，并标记 session 为 stopped。
- 重启本机 `http://127.0.0.1:7001` 到新版本，当前 `.venv-console` 为 Python 3.12.5。
- 修复 discovery 后旧 runtime 仍显示历史固定设备的问题：`/api/devices/discover` 现在会禁用本次未发现且无活跃 session 的旧设备。
- 修复所有设备被禁用时 `/api/status` 返回 409 的问题；现在无在线设备时返回 idle 空状态和用户可读提示。
- 验证完成：
  - `npm --prefix web run build` 通过。
  - `python -m unittest discover tests` 通过，98 个测试 OK。
  - 最新 release：`release/TraceDeck-20260608-143750.tar.gz`。
  - 包内包含 `scripts/console_python.sh`、`setup.sh`、`start.sh`、`web/dist/index.html`、`config/local.example.json`。
  - 发布包排除项检查通过：未包含 `runtime/`、`.venv*`、`web/node_modules`、`config/local.json`。
  - 干净目录 smoke 通过：解压最新 release 后运行 `./setup.sh` 和独立端口 `./start.sh`，`/api/status` 可访问，测试服务已停止且端口无遗留监听。

## 2026-06-10

- 按用户要求继续做 TraceDeck 本机独立项目的自主收尾验收。
- 修正文档：README 依赖说明统一为 Python 3.12+，新增 PyPI/npm 镜像和 `PIP_PROXY=` 代理排错说明。
- 页面验收发现 `web/index.html` 标题仍为 `AI抓包工具`；已改为 `TraceDeck` 并重新构建。
- 本机服务验收：
  - `./start.sh` 可启动 `http://127.0.0.1:7001`。
  - `/api/status`、`/api/setup/state`、`/api/devices/discover`、`/api/devices` 均可返回。
  - 无在线设备时 `/api/devices` 返回空列表，不进入异常状态。
- 启动本机 `Capture_AVD_02 / emulator-5554` 做通用设备验收：
  - `/api/devices/discover` 成功发现并写入 `device-1`。
  - `/api/apps/installed?device_id=device-1` 可读取当前设备用户安装 App。
- 完成非 MelodyCraft App 抓包验收：
  - 临时添加 `Chrome 验收临时应用`，包名 `com.android.chrome`，Activity `com.android.chrome/com.google.android.apps.chrome.Main`，模式 `system`。
  - `/api/apps/11/readiness?device_id=device-1` 返回 App 已安装且 Activity 可启动。
  - `/api/captures/start` 新建 session 61，输出目录 `runtime/captures/web-20260610-140451-Chrome`。
  - 抓包运行中 `health=running`、9090 代理监听、exporter running、Chrome 前台、Android `http_proxy=10.0.2.2:9090`。
  - 通过 Chrome 打开 `http://neverssl.com/online` 后，`/api/captures/61/flows` 捕获到 17 条 flow。
  - 抽查 `POST http://update.googleapis.com/service/update2/json` 的详情接口和 cURL 导出接口可访问；`/api/captures/61/export` 返回 70 个文件并包含 `summary.md`。
- 验收发现并修复 system 模式停止后的代理残留问题：
  - 复现：停止 session 61 后 mitmproxy 已退出，但 Android `http_proxy` 仍为 `10.0.2.2:9090`。
  - 修复：`/api/captures/stop`、`/api/captures/{session_id}/stop`、`/api/cleanup` 统一调用 `clear_android_proxy()`。
  - 新增回归测试 `test_stop_capture_clears_android_proxy` 和 `test_stop_capture_session_clears_android_proxy`。
  - 复测 session 62：启动 system 抓包后代理为 `10.0.2.2:9090`，停止后代理恢复为 `null`。
- 页面 DOM 验收确认：
  - 页面标题为 `TraceDeck`。
  - 页面无 `preview token` 登录入口。
  - Browser 截图接口本轮出现 CDP screenshot timeout；已用 DOM 指标完成页面可视化关键检查。
- 自动化验证完成：
  - `python -m unittest discover tests` 通过，101 个测试 OK。
  - `npm --prefix web run build` 通过。
  - `./release/package.sh` 通过，生成 `release/TraceDeck-20260610-141015.tar.gz`。
  - 最新 release SHA256：`fd7a9c8c5f351d60c043a73e096fb81aeca656d60b39ec44d24b9ed105f21a58`。
  - 发布包必需文件检查通过：`README.md`、`setup.sh`、`start.sh`、`requirements-console.txt`、`scripts/console_python.sh`、`scripts/start_web_services.sh`、`web/dist/index.html`、`config/local.example.json` 均存在。
  - 发布包排除项检查通过：未包含 `runtime/`、`.venv*`、`web/node_modules`、`config/local.json`、抓包结果或上传文件。
  - 干净目录 smoke 通过：解压最新 release 后运行 `./setup.sh`，再用独立端口 `17071` 执行 `./start.sh`，`/api/status` 和 `/api/devices` 可访问，测试服务已停止。

### 本机卸载重装验收

- 按用户要求在本机执行“卸载已安装产物后重装”流程，仅清理当前项目可再生内容：`.venv-console`、`.venv-console312`、`web/node_modules`、`web/dist`、`runtime`、`config/local.json`，未删除源码、未操作服务器。
- 重新执行 `./setup.sh` 成功：
  - 重新生成 `config/local.json`。
  - 重建 `.venv-console` 并安装 `requirements-console.txt`。
  - 重新执行 `npm install` 和 `npm run build`，Vite 构建通过。
- 重新执行 `OPEN_WEB=0 ./start.sh` 成功，服务监听 `http://127.0.0.1:7001`。
- API 与页面验收：
  - `/api/status` 返回 idle 空设备状态。
  - `/api/setup/state` 返回环境检查通过、`app_count=0`。
  - 浏览器实际打开 `http://127.0.0.1:7001`，页面标题为 `TraceDeck`，无 token 登录入口。
- 启动本机 `Capture_AVD_02 / emulator-5554` 后，页面点击“发现设备”可显示 `device-1 · Android Emulator emulator-5554`。

## 2026-08-06

- 用户明确最终目标是“完整桌面端”，并补充要求：其他用户下载到自己 Mac 后也能本机安装和使用。
- 确认 Tauri/WebView 方案不作为最终桌面端方向；保留现有 Web/Tauri 能力作为过渡和调试入口。
- 新增原生 SwiftUI 可分发版设计文档：`docs/superpowers/specs/2026-08-06-macos-native-distributable-design.md`。
- 新增原生 SwiftUI 可分发版实施计划：`docs/superpowers/plans/2026-08-06-macos-native-distributable.md`。
- 创建 `macos-native/` SwiftUI 原生桌面端骨架：
  - `Package.swift`
  - `AICaptureNativeApp.swift`
  - `AppState.swift`
  - `ContentView.swift`
  - `README.md`
- 第一阶段只实现原生窗口、原生侧边栏和运行时状态占位，不接抓包业务逻辑。
- 第二阶段接入本机后端运行时检测：
  - 新增 `RuntimeManager.swift`，解析 `~/Library/Application Support/AI抓包工具/runtime-native/` 并检测 `http://127.0.0.1:7001/api/status`。
  - `AppState` 增加运行目录、最近检测时间和 `refreshRuntimeStatus()`。
  - 原生 App 启动和点击“重新检测后端”时会自动刷新后端状态。
  - 后端检测使用禁用代理的 `URLSessionConfiguration.ephemeral`，避免本机 `http_proxy/ALL_PROXY` 把 `127.0.0.1:7001` 错误转发到代理。
  - 新增 `macos-native/scripts/build-app.sh` 生成最小 `.app`，解决 SwiftPM 裸可执行文件无法稳定打开 SwiftUI 窗口的问题。

## 验证

- 本机环境确认：Xcode 26.2，Swift 6.2.3。
- `cd macos-native && swift build` 通过，生成原生可执行目标 `AI抓包工具`。
- `cd macos-native && ./scripts/build-app.sh` 通过，生成 `macos-native/build/AI抓包工具.app`。
- 实际打开 `.app` 通过：进程保持运行，原生窗口显示“内部服务已就绪：http://127.0.0.1:7001”。
- 发现并规避本机代理干扰：普通 `curl` 因 `ALL_PROXY/http_proxy=http://127.0.0.1:7897` 返回 502；`curl --noproxy '*' http://127.0.0.1:7001/api/status` 返回 200，原生检测已按直连处理。
- 通用 App 抓包复测：
  - 临时添加 `Chrome reinstall QA`，包名 `com.android.chrome`，Activity `com.android.chrome/com.google.android.apps.chrome.Main`，模式 `system`。
  - readiness 显示模拟器在线、App 已安装、Activity 可启动、Chrome 在前台。
  - 启动抓包后 `health=running`、9090/9091 监听、Android `http_proxy=10.0.2.2:9090`。
  - Chrome 访问 `http://neverssl.com/online` 后，session 1 捕获 13 条 flow；抽查 `GET http://edgedl.me.gvt1.com/...crx3` 的详情和 cURL 导出成功。
  - 停止抓包后 session 标记 stopped，9090/9091 关闭，Android 代理恢复为 `null`。
- 收尾清理：
  - 删除临时 Chrome App 记录，`/api/apps` 回到空列表。
  - 关闭测试模拟器，`adb devices` 为空，无 `Capture_AVD_02` 相关 emulator/qemu 进程残留。
  - 本机 TraceDeck 服务保留运行在 `127.0.0.1:7001`，抓包端口无监听。
- 回归验证：
  - `./.venv-console/bin/python -m unittest discover tests` 通过，101 个测试 OK。
  - `npm --prefix web run build` 通过。

### 抓包模式真实矩阵测试

- 按用户要求继续真实测试“是否存在通用抓包模式”和“不可用时如何切换”。
- 测试环境：
  - 本机 TraceDeck：`http://127.0.0.1:7001`。
  - 模拟器：`Capture_AVD_02 / emulator-5554`。
  - Frida 准入：`/api/devices/device-1/prepare-frida` 返回 ok，`frida-ps reachable on 127.0.0.1:27042`。
- 矩阵结果：
  - `Chrome/system`：启动成功，捕获 4 条 flow，包含 `neverssl.com /online`；停止后 Android 代理恢复为 `null`。
  - `MelodyCraft/system`：启动成功但 15 秒内捕获 0 条 flow，说明“启动成功”不能等同于“模式适配”。
  - 页面轮询开启时，`Chrome/flutter-socks` 和 `MelodyCraft/flutter-socks` 初次均返回 500。
- 500 根因：
  - 后端日志显示 `sqlite3.IntegrityError: UNIQUE constraint failed: capture_sessions.device_id`。
  - 根因是启动抓包创建 `starting` session 后，页面轮询 `/api/status`、`/api/devices` 会触发 `reconcile_active_session()`，把启动中的 session 改写为 stopped 或恢复其它运行态，和启动请求自身的 `starting -> running` 状态迁移竞争。
- 修复：
  - `reconcile_active_session()` 遇到 `status == "starting"` 的 active session 时不再改写，交给启动请求或显式停止/清理收尾。
  - 新增回归测试 `test_reconcile_leaves_starting_session_untouched_during_capture_start`，先复现失败，再修复通过。
  - 额外补充 Store 层状态迁移测试 `test_store_promotes_starting_session_to_running_without_unique_conflict`。
- 修复后真实复测：
  - 浏览器重新打开 TraceDeck 页面并保持轮询。
  - `MelodyCraft/flutter-socks` 启动成功，session 9 running。
  - 操作 App 后捕获 1 条 200 接口：`POST www.blockdance-test.xyz /aisong/portal/user/livestatus`。
  - 停止后 Android 代理恢复为 `null`。
  - 停止页面轮询后，`Chrome/flutter-socks` 也可启动并捕获 `GET neverssl.com /online`。
- 当前结论：
  - 没有单一模式适配所有 App。
  - `system` 对 Chrome 这类遵守系统代理的应用有效。
  - `flutter-socks` 对 MelodyCraft 这类 system 无流量的应用有效。
  - 后续应实现 `auto` 策略：优先推荐最近成功模式，否则先 system，再 fallback 到 flutter-socks，并把“启动成功但无流量”标记为需要切换模式的 warning。
- 回归验证：
  - `./.venv-console/bin/python -m unittest discover tests` 通过，103 个测试 OK。
  - `npm --prefix web run build` 通过。
- 收尾：
  - 临时 Matrix/Retry App 记录已删除，`/api/apps` 为空。
  - 测试模拟器已关闭，`adb devices` 为空。
  - 9090/9091 无监听，7001 主服务保留运行。

### auto 抓包模式实现与验收

- 已实现通用 `auto` 抓包策略：
  - 新建 App 默认 `default_mode=auto`。
  - Store 允许 App 默认模式为 `auto/system/flutter-socks`，session 仍只允许真实底层模式 `system/flutter-socks`。
  - App 新增 `last_success_mode`，停止成功后记录真实成功模式。
  - `auto` 候选顺序为：上次成功模式 -> App 默认底层模式 -> `system` -> `flutter-socks`，自动去重。
- 启动抓包接口：
  - `/api/captures/start` 支持 `mode=auto`。
  - 返回 `requested_mode` 和 `mode_attempts`，UI 可展示 `auto -> system/flutter-socks`。
  - 若某个候选模式健康检查、网络切换或启动失败，会停止临时状态、清理 Android 代理后继续尝试下一个候选。
- 冒烟校验接口：
  - `/api/apps/{app_id}/validate-capture` 支持 auto fallback。
  - 某个候选模式 30 秒内无 JSON 请求/响应时，标记 `reason=no_json`，停止临时抓包、清理代理，再尝试下一个模式。
  - 所有模式都无 JSON 时返回 warning，不误标成功。
- 前端更新：
  - 主按钮改为“自动抓包”。
  - 应用表单和静态兜底页新增 `auto（自动选择）`。
  - 接口分析区新增模式尝试摘要，显示 auto 实际落到哪个模式及每个候选的状态。
- 文档更新：
  - README 首次抓包流程改为默认使用 `auto`。
  - README 补充 auto 策略、成功模式记忆和自动清理说明。
- 自动化验证：
  - 目标测试通过：`test_start_capture_auto_falls_back_to_flutter_socks_when_system_is_not_ready`、`test_validate_capture_auto_falls_back_to_flutter_socks`、`test_store_allows_auto_default_mode_and_records_last_success_mode`。
  - 全量 Python 测试通过：`./.venv-console/bin/python -m unittest discover tests`，106 个测试 OK。
  - 前端构建通过：`npm --prefix web run build`。
- 页面与 API 验收：
  - 重启本地服务，入口为 `http://127.0.0.1:7001`。
  - Browser 实际打开页面，首屏为 `TraceDeck` 通用入口，空设备状态正常，无固定 Melody/Jenkins/服务器语境。
  - 启动 `Capture_AVD_02 / emulator-5554` 后，页面点击“发现设备”可显示 `device-1 · Android Emulator emulator-5554`。
- 真实 App 验收：
  - 非 Melody：临时添加 `Chrome Smoke`，默认 `auto`，启动后实际选择 `system`；Chrome 访问 `http://example.com/` 后 session 10 捕获候选 flow，详情接口和 cURL 导出成功；停止后 Android 代理恢复为 `null`，9090/9091 无监听，App 记录 `last_success_mode=system`。
  - Melody：临时添加 `Melody Smoke`，默认 `auto`，执行冒烟校验；`system` 30 秒无 JSON 后自动切换 `flutter-socks`，第二轮无人操作仍无 JSON，最终返回 warning 和完整 `mode_attempts`；校验结束后 Android 代理为 `null`，9090/9091 无监听，抓包进程无残留。
- 发布包验收：
  - `./release/package.sh` 通过，生成 `release/TraceDeck-20260611-162421.tar.gz`。
  - tar 内容抽查通过：包含 `README.md`、`setup.sh`、`start.sh`、`requirements-console.txt`、`web/dist/index.html`、`config/local.example.json`。
  - tar 排除项抽查通过：未发现 `runtime/`、`.venv*`、`web/node_modules`、`config/local.json`、抓包结果或本机数据库。
- 收尾：
  - 临时 `Chrome Smoke` / `Melody Smoke` App 记录已删除，`/api/apps` 回到空列表。
  - 测试模拟器已关闭，`adb devices` 为空。
  - `127.0.0.1:7001` 本地服务保留运行。

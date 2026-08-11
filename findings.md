# 项目发现记录

## 当前实现状态

- 项目根目录在文档中统一记为 `<project-root>`。
- 本机 Web 控制台入口是 `http://127.0.0.1:7001`，启动脚本是 `scripts/start_console.sh`。
- 后端已使用 FastAPI，核心入口是 `capture_console/app.py`。
- SQLite 存储文件是 `runtime/console.db`。
- 控制台已有应用库、抓包启动/停止、历史任务读取、接口详情、cURL 导出能力。
- 当前 Web 服务启动和关闭时会清空抓包任务记录，但保留应用库和 `runtime/captures/` 原始文件。
- 当前环境已有 `npm`，React/Vite 可以正常构建，Web 服务优先使用 `web/dist`。

## 抓包底层能力

- 底层统一入口是 `scripts/ai_capture.sh`。
- Android 支持 `system` 和 `flutter-socks` 两种模式。
- `flutter-socks` 模式会清空 Android global `http_proxy`，避免 HTTP 代理和 SOCKS5 冲突。
- mitmweb 默认端口是 `9091`，代理端口是 `9090`，token 是 `android-capture`。
- 保留登录态模拟器是 `Medium_Phone_API_36.1 / emulator-5554`。
- 抓包结果落在 `runtime/captures/<session>/`，包括 `candidates.tsv`、`*.meta.json`、`*.request.*`、`*.response.*`。

## 主要约束

- 非 root Google Play 模拟器可以保留 Google 账号和 App 登录态，但部分 App 仍可能因为证书绑定、Flutter/Dart TLS、native socket 等原因无法解密。
- V1 不应误开其他模拟器，默认只能使用保留登录态的 `Medium_Phone_API_36.1`。
- 用户需要长期使用，必须避免端口、pid、Frida、exporter 脏状态导致下一次启动失败。
- 用户明确希望关闭项目后清除页面里的抓取链接记录。
- 用户明确要求计划书当前先做 Android 端，iOS 只需要预留入口用于后续实现。

## 规划原则

- Web 控制台只编排流程，不直接重写底层 ADB/Frida/mitmproxy 逻辑。
- 原始抓包文件不迁移、不改名，SQLite 只做索引和当前运行态缓存。
- 页面默认只监听 `127.0.0.1`，不做公网部署。
- 需要清晰标注敏感信息风险，因为页面会展示 headers、token、request body、response body。
- 当前任何实现任务都不得因为 iOS 预留入口而影响 Android 主流程稳定性。

## 规划书评审发现

- 2026-05-12：规划书已明确 Android 先行，但 P0/P1/P2 的执行顺序仍有压缩风险。建议先完成 P0 稳定性闭环，再进入搜索、报告、历史导入。
- 2026-05-12：iOS 预留入口已写入目标，但数据模型当前没有 `platform` 字段。若确实要为 iOS 预留实现空间，建议在 V1 就把平台字段作为只读/默认 Android 的结构预留。
- 2026-05-12：测试规划没有明确保护保留登录态模拟器的边界。集成和端到端测试需要禁止 wipe、禁止新建/误选 AVD、禁止清空 App 数据。
- 2026-05-12：报告导出和敏感信息策略之间还缺少约束。既然要原样展示 token/header，就需要定义导出报告是否包含敏感字段、是否需要显式确认。
- 2026-05-12：已实现 `platform` 数据字段，默认 Android；iOS 应用可作为预留条目存在，但启动抓包会返回 501，且不会触碰 Runner/ADB/Frida。
- 2026-05-12：已在 Runner 层拒绝明显破坏登录态的命令，包括 emulator `-wipe-data`、`avdmanager delete`、`adb shell pm clear`、`adb uninstall`。
- 2026-05-12：已在健康检查前加入 retained emulator 守卫，非 `Medium_Phone_API_36.1 / emulator-5554` 直接失败，避免误用其他模拟器。
- 2026-05-12：页面已补齐应用添加与选择流程；抓包动作现在围绕“当前目标应用”执行，iOS 应用条目可以保存但不会启动抓包。
- 2026-05-28：Google 登录失败根因偏向网络出口而非 APK 实现。无抓包会话、Android 代理为 `null` 时，GMS 登录页卡在 `Checking info…`；服务器到 `accounts.google.com`、`oauth2.googleapis.com`、`www.googleapis.com`、`play.googleapis.com`、`android.clients.google.com` 的 HTTPS/TCP 443 超时，模拟器对这些域名 ping 也失败。`connectivitycheck.gstatic.com` 可达不足以证明 Google 登录链路可用。
- 2026-05-28：模拟器网络时间未成功同步，`dumpsys network_time_update_service` 显示 `mLastSuccessfulNtpServerUri=null`、`mTimeResult=null`，对应日志中大量 `No network time available`。Google 账号状态仍为 `Accounts: 0`。
- 2026-05-29：7890 代理能解决 Google 登录页加载问题。将 `device-1` 的 Android `http_proxy` 设置为 `10.0.2.2:7890` 后，GMS 登录从 `Checking info…` 成功进入 `Sign in - Google Accounts` 邮箱输入页。当前阻塞点变为模拟器没有 Google 账号，需要人工输入账号完成设备级登录。
- 2026-05-29：完成 Google 登录后，MelodyCraft 登录后首页可被抓包，session 19 捕获 78 条候选流量、60 条 200 响应、44 条 JSON 响应，详情接口和 cURL 导出可用。
- 2026-05-29：MelodyCraft 在 `flutter-socks` 抓包运行中出现系统 ANR 弹窗，界面仍能看到登录后首页并已产生接口流量。后续若要做长时间自动化遍历，需要单独排查 ANR 与 Frida hook、代理链路或 App 自身主线程阻塞的关系。
- 2026-05-29：模拟器预览页卡顿和画面过大主要来自预览服务自身配置：外层舞台原先最小高度 870px，1440x900 浏览器下页面总高度 993px；同时默认沿用 `smooth` 推流档 4Mbps/30fps/720x1600。已改为视口内自适应和默认低延迟档。
- 2026-05-29：预览页此前显示 10 个“可启动 AVD”的原因是 `/Users/jenkins/emulator-preview` 直接调用 `emulator -list-avds`，展示 Jenkins 账户下所有 AVD；AI 抓包工具项目实际启用设备只有 `Capture_AVD_01/02/03`。已将预览服务 API 收敛为读取项目设备配置并只返回启用 AVD。
- 2026-06-01：Google 登录完成后，`device-1 / Capture_AVD_01` 可以稳定复测 MelodyCraft 登录后业务流量；session 20 捕获 129 条候选流量、90 条 200 响应、93 条 JSON 响应，明显高于此前 session 19 的 78 条候选流量。
- 2026-06-01：抓包模式仍会按设计清空 Android `http_proxy`，停止后需要恢复维护代理 `10.0.2.2:7890`，否则后续 Google 相关页面可能再次受服务器直连网络限制影响。
- 2026-06-01：预览服务的 AVD 收敛结果保持有效，API 仍只返回项目启用的 `Capture_AVD_01/02/03`，没有重新暴露 Jenkins 账户下的其他历史 AVD。
- 2026-06-10：本机独立项目验收发现 React 入口 `web/index.html` 仍保留旧标题 `AI抓包工具`，会影响浏览器标签和 release 首屏识别；已改为 `TraceDeck`。
- 2026-06-10：本机旧 runtime 仍可能保留 MelodyCraft/PokeHub 等历史应用记录，但干净 release 默认不包含 `runtime/` 和 `config/local.json`，新用户启动仍是空设备/空历史状态。验收时应区分“当前开发库历史数据”和“发布包默认状态”。
- 2026-06-10：非 MelodyCraft 抓包通用性已用系统 Chrome 验证。临时 App 使用 `com.android.chrome/com.google.android.apps.chrome.Main` 和 `system` 模式，能启动抓包、产生 flows、查看详情、导出 cURL。
- 2026-06-10：`system` 模式停止抓包时存在 Android 系统代理残留风险。根因是普通 `/api/captures/stop` 和 `/api/captures/{session_id}/stop` 只停止进程，没有像 release/system sleep 一样调用 `clear_android_proxy()`；已修复并补回归测试。
- 2026-06-10：pip 首次安装受本机网络/代理环境影响明显。固定直接依赖版本可以避免回溯和 Frida 版本冲突；遇到 `127.0.0.1:<port>` 代理 502 时，可用 `PIP_PROXY=` 关闭 pip 代理或显式配置可用代理。
- 2026-06-10：Browser DOM 验收可用，但截图接口本轮对当前页面连续出现 CDP screenshot timeout。页面关键验收可以通过 DOM 指标覆盖；若需要最终视觉截图，可改用系统截图或独立 Playwright 环境补测。
- 2026-06-10：本机卸载重装验收通过。清理 `.venv-console`、`web/node_modules`、`web/dist`、`runtime`、`config/local.json` 后，重新执行 `./setup.sh` 和 `OPEN_WEB=0 ./start.sh` 可恢复可用控制台；页面和 API 均进入空项目状态。
- 2026-06-10：重装后的非 MelodyCraft 抓包复测继续通过。Chrome/system 模式 session 捕获 13 条 flow，详情与 cURL 可读；停止后 Android 代理恢复为 `null`，9090/9091 无残留监听。
- 2026-06-10：调试启动/停止接口时出现的 JSON 解析失败并非后端响应无效，而是 `zsh echo "$JSON"` 会解释 `\n` 转义导致测试管道生成非法 JSON；后续校验 API JSON 应使用 `printf '%s' "$JSON"`、`curl -o` 后读取文件，或直接用 Python/requests 读取响应体。
- 2026-06-10：真实模式矩阵证明不存在单一万能抓包模式。Chrome 在 `system` 下可捕获流量，MelodyCraft 在 `system` 下启动成功但无 flow；MelodyCraft 在 `flutter-socks` 下可捕获 `POST www.blockdance-test.xyz /aisong/portal/user/livestatus`。后续应实现 auto 模式和模式成功记忆，而不是把任一模式设为全局万能默认。
- 2026-06-10：页面轮询会影响抓包启动状态迁移。启动请求创建 `starting` session 后，页面轮询触发 `reconcile_active_session()`，曾导致 `sqlite3.IntegrityError: UNIQUE constraint failed: capture_sessions.device_id`，表现为 `flutter-socks` 500。已修复为 `starting` 状态不被 reconcile 改写，并补回归测试。
- 2026-06-11：auto 抓包策略已落地。`auto` 会优先使用 App 的 `last_success_mode`，否则依次尝试 `system`、`flutter-socks`；实际 session 仍只保存底层模式，避免 runtime 把 `auto` 当作抓包脚本模式。
- 2026-06-11：冒烟校验可以处理“启动成功但无可解析接口”的情况。真实 Melody Smoke 校验中，`system` 30 秒无 JSON 后自动清理并切到 `flutter-socks`；`flutter-socks` 在无人操作场景仍无 JSON，最终返回 warning 和完整 `mode_attempts`，未残留 Android 代理或 9090/9091 进程。
- 2026-06-11：非 Melody 通用抓包继续可用。Chrome Smoke 使用默认 `auto` 启动后实际选择 `system`，访问 `http://example.com/` 后 session 10 捕获候选 flow，详情接口和 cURL 导出可读；停止后 `last_success_mode=system`。

## 2026-08-07 桌面端完整功能验收

- 验收分支为 `codex/desktop-one-click-ready`；验收开始时产品改动涉及 17 个文件，覆盖桌面端自托管、一键准备、Google Play 准入、响应读取与发行打包。
- 主工作区还存在一组较早的抓包响应改动，本轮不合并、不覆盖。
- 验收开始时 `127.0.0.1:7001` 由桌面端内嵌后端监听；9090、9091、27042 均无监听，说明没有 active capture 或残留 Frida forward 监听。
- 本轮不操作不属于项目的模拟器或进程，不执行 `wipe-data`、`pm clear`，不清理 Google/App 登录态。
- 桌面端内嵌后端 PID 85262 的 cwd 是构建产物 `AI抓包工具.app/Contents/Resources/backend`，不是源码目录，证明当前运行的是打包资源。
- `adb devices -l` 发现现有 `emulator-5558`；本轮目标设备默认是 `device-1 / emulator-5554`，因此不会对 5558 执行停止或清理。
- 交互式 shell 的 PATH 中没有裸命令 `emulator`。验收需通过 Environment Doctor 确认桌面端能从 Android SDK 路径自行定位 emulator；若 Doctor 也失败，才是新机分发缺陷。
- 首次使用普通 `curl` 请求 `/openapi.json` 返回 HTTP 502。当前只记录现象，尚未确认是 shell 代理环境还是后端；后续使用显式 `--noproxy '*'`、直连 socket 和桌面端日志分层定位。
- 502 已定位为验收 shell 的代理环境：`ALL_PROXY/http_proxy/https_proxy` 均指向 `127.0.0.1:7897`，但没有 `NO_PROXY`。使用 `curl --noproxy '*'` 后 `/openapi.json` 与 `/api/status` 均返回 200；桌面端 RuntimeManager/APIClient 使用禁用代理的 ephemeral session，因此不是产品故障。
- Environment Doctor 能从 `$HOME/Library/Android/sdk` 定位 `adb`、`emulator`、`sdkmanager` 和 `avdmanager`，同时检测到 Python、Node/npm、mitmweb、Frida、screen、xz，依赖层全部通过。
- Doctor 将 7001 判定为 `owned_by_project`，7002/9090/9091/19097/19098/27042 均为空闲；未杀掉或占用其他项目端口。
- Google Play 镜像准入通过：选中 `system-images;android-36.1;google_apis_playstore;arm64-v8a`，普通 `google_apis` 镜像不会被选为默认抓包 AVD。
- `device-1` 已绑定 `AI_Capture_AVD_01 / emulator-5554`，当前是按需关闭状态；Doctor 因目标模拟器离线而返回整体 `ok=false`，提示先启动模拟器，属于正确阻塞而非环境依赖失败。
- `/api/apps`、`/api/captures` 和 Jenkins 摘要命令的首个 jq 过滤器假设了错误的顶层 JSON 结构，导致验收命令报错；后续先读取实际类型，不能将其记为产品缺陷。
- 自动化回归：`./.venv-console/bin/python -m unittest discover tests` fresh run 通过，127 项测试、0 失败，耗时 12.919 秒。
- Web 生产构建：`npm --prefix web run build` 通过，Vite 转换 41 个模块，生成约 253 KB 的主 JS 和 22 KB 的 CSS。
- 原生桌面构建：`macos-native/scripts/build-app.sh` 通过，生成 `macos-native/build/AI抓包工具.app`。
- 发行打包：`release/package.sh` 通过，生成 `release/TraceDeck-20260807-113601.tar.gz` 及 SHA-256 文件。
- `npm install` 报告 4 个依赖漏洞（2 low、2 high）。这不会让本次构建失败，但属于分发前必须单独审计的供应链残余风险，不能直接执行可能升级主版本的 `npm audit fix`。
- 通过向 App PID 发送 SIGTERM 结束桌面进程时，内嵌 uvicorn 子进程没有同步退出，需要单独终止。本现象可能是测试终止方式绕过 AppKit 生命周期，也可能是 RuntimeManager 清理不足；后续必须使用真实“退出应用”UI 再判定是否为产品缺陷。
- 发行包 SHA-256 校验通过，大小约 1.3 MB；`.app` 约 3.2 MB。压缩包包含桌面 App、内嵌后端、Web dist 和依赖清单，未发现 runtime、数据库、抓包历史、node_modules、venv 或本地配置。
- 桌面可执行文件目前只有 `arm64`，最低 macOS 14；V1 应明确限定 Apple Silicon，不能宣称支持 Intel Mac。
- 当前签名是 Swift 可执行文件的 ad-hoc 签名，整个 `.app` 的 Info.plist 和 Resources 未被封装签名。`spctl --assess` 失败，错误为 `code has no resources but signature indicates they must be present`。
- 新增 `tests/test_native_app_packaging.py` 后，真实调用构建脚本并执行 `codesign --verify --deep --strict`，测试按预期失败，证明该测试能捕获分发缺陷。尚未修改生产构建脚本。
- 旧版原生桌面设计明确把签名、公证和 `.dmg/.pkg` 放在“后续”，并允许首次启动依赖用户预装 Python/mitmproxy/Frida；这与当前“一键下载使用”要求冲突，新方案必须显式覆盖旧假设。
- 当前 `RuntimeManager` 通过 `scripts/start_console.sh` 启动后端；该脚本会创建 venv、在线执行 pip install，并把 Node/npm 当作可选 Web 构建依赖。新 Mac 没有 Python 3.12 或 pip 网络不可用时无法启动，因此 3.2 MB 的 `.app` 不是自包含运行时。
- Environment Doctor 当前把 Node/npm、Python、mitmweb、frida/frida-ps 全部作为必需项；桌面包已经内嵌 Web dist，Node/npm 不应再成为桌面运行时阻塞项。
- 原生 App 当前没有显式的应用退出生命周期处理；`RuntimeManager` 只启动后端、不持有或停止子进程。这与 SIGTERM 后 uvicorn 残留现象一致，后续需增加项目后端 PID 所有权和正常退出测试。
- 当前 Keychain 只有 Apple Development 身份，没有 `Developer ID Application` 身份；本机可以验证开发签名完整性，但无法完成正式分发签名和 Apple 公证。
- 本机工具链具备 Xcode 26.2、Swift 6.2.3、`xcrun notarytool` 和 Apple Silicon arm64，能够实现并测试发布流水线除真实 Developer ID 公证之外的所有步骤。
- `uv 0.10.7` 可通过 `uv python install --install-dir` 下载 relocatable managed Python；当前 uv 管理的 Python 3.11 约 63 MB。可用该机制在构建机生成 arm64 Python 3.12 runtime，再把固定依赖安装到该 runtime，避免新 Mac 依赖系统 Python/Homebrew。
- 抓包脚本大量通过 `python3`、`mitmweb`、`frida`、`frida-ps` 命令发现运行时，因此自包含方案必须在桌面后端环境中把内嵌 runtime 的 `bin` 放到 PATH 首位，并设置 `CONSOLE_PYTHON`；仅让 Swift 后端启动使用内嵌 Python还不够。
- 完整 bundle 签名修复完成：`build-app.sh` 在所有资源和 Info.plist 写入后对整个 App 签名并严格校验。原失败测试转绿，`codesign` 输出 `valid on disk` 和 `satisfies its Designated Requirement`。
- 开发/正式发布边界已建立：开发包明确命名为 `development-arm64.zip`；正式模式若缺少 Developer ID 或 notary profile，会在 npm/Swift 构建前失败，不会生成误标为可分发的产物。
- macOS `ditto` 生成的中文 App ZIP 在 Python `zipfile` 中会因 UTF-8 flag 缺失显示乱码，但 macOS `ditto -x` 和系统 `unzip` 均能正确解压。验收已改为真实解压后检查 App 可执行文件及整包签名，避免只验证 ZIP 目录字符串。
- 正式发布已独立为 `release/notarize-app.sh` 硬边界：依次校验 Developer ID 签名、提交 `notarytool`、执行并校验 staple、运行 Gatekeeper `spctl` 评估，最后才原子移动正式 ZIP 和 SHA-256 到 release 目录。
- 内嵌运行时已用 `uv` managed CPython 3.12 构建，安装固定的 FastAPI/mitmproxy/Frida 直接依赖，并以相对路径 wrapper 暴露 `python3/uvicorn/mitmweb/frida/frida-ps`。实际复制 App 后重新导入通过。
- `uv python install` 会创建一个指向构建临时目录的绝对别名软链，会使整包 `codesign --verify --deep --strict` 失败。构建脚本现在删除该冗余别名，并对任何剩余绝对软链直接拒绝打包。
- 完整运行时当前约 248 MB，整个 App 约 253 MB；这是不依赖新 Mac 系统 Python/mitmproxy/Frida 的交换。源码 TAR 已排除 `macos-native/build`，不会重复携带运行时。
- 内嵌后端已在限制 PATH 下通过真实 HTTP smoke：系统仅提供 `/usr/bin:/bin`，Python/uvicorn 来自复制后的 App Resources，`/api/status` 返回 200，且指定的禁止 venv 目录没有被创建。
- 桌面 Doctor 现在把 Python/mitmweb/Frida 解析到 App 内嵌 runtime，不再要求 Node/npm/xz。Frida server `.xz` 在 Homebrew xz 缺失时由内嵌 Python `lzma` 解压；Android SDK 四个命令仍保持强制准入。
- RuntimeManager 现在只保存它自己启动的 Process 和 PID 记录。Swift 测试验证 shutdown 会终止自有进程但不会终止外部进程；AppDelegate 已在正常 AppKit 退出事件中调用该清理。

## 2026-08-11 六应用桌面端抓包兼容性复测

- 验证设备：`AI_Capture_Clean_QA3_20260810 / emulator-5564`，仅通过原生桌面端执行环境准备、Jenkins 安装、应用启动、抓包启动和停止。
- StickerHub：Jenkins `Stickerhub #618 / Stickerhub_618.apk` 安装成功，解析包名 `com.meta.inno.monopoly_sticker`，Session #5 以 `flutter-socks` 启动成功。Frida 日志确认 native TCP 重定向和 Flutter 证书绕过均已加载，但启动阶段接口列表为 0，暂记为“抓包链路可启动，未捕获业务接口”。
- GLP：Jenkins `glp-1-tracker #158 / glp-1-tracker_158.apk` 安装并解析为 `com.example.glp1_tracker`，Session #6 使用 `flutter-socks` 捕获 4 条 `POST 200` 业务接口，包括 `/shottrack/user/info`、`/shottrack/user/profile/update` 和 `/shottrack/user/reminder/medication/update`；桌面端可展开 Response JSON。报告不记录响应中的认证字段。
- BiteCal：Jenkins `BiteCal #124 / BiteCal_124.apk` 安装并解析为 `com.niubi.testapp`，Session #7 使用 `flutter-socks` 捕获 51 条启动业务接口，列表均为 `POST 200`；覆盖设备登录、用户资料、Paywall、日历、饮水、体重与趋势等接口，桌面端 Response JSON 可完整展开。报告不记录响应中的认证字段。
- WakeQuest：Jenkins `wayk #80 / wayk_80.apk` 安装并解析为 `com.niubi.wayk`，Session #8 使用 `flutter-socks` 捕获 102 条启动及轮询接口；已确认 `/wayk/config/common`、`/wayk/user/device-login`、`/wayk/alarm/list`、`/wayk/user/profile/update` 均返回 `POST 200`，桌面端可展开完整 Response JSON。报告不记录响应中的认证字段。
- Melody：选择 Jenkins `Melody #481 / Melody_481.apk` 后，桌面端在安装阶段返回 `downgrade install is not supported`；目标模拟器内同包名 `com.meta.inno.monopoly_sticker` 已由 StickerHub #618 安装为 `versionCode=129 / versionName=3.1.1`。因桌面端保护登录态、不允许降级且本轮不卸载/清数据，Melody 未进入抓包阶段；该结果属于同包名版本冲突，不是抓包链路失败。
- PokeHub：Jenkins `PokeHub #530 / PokeHub_530.apk` 安装并解析为 `com.test.tcgp`，Session #9 以 `flutter-socks` 启动成功；两次通过桌面端打开应用后接口列表仍为 0。Frida 日志确认 hook、Flutter 证书绕过和 native TCP 重定向均已加载，但出现多次 `SOCKS: Server returned error code 4`，exporter 统计 `total flows seen: 0`。暂记为“抓包链路可启动，但当前构建启动流量未成功导出”。

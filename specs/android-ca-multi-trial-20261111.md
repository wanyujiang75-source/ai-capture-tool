# Android 三应用原版隔离抓包验收

## 范围

2026-11-11 ANDROID-CA-MULTI，承接 PokeHub 的新链路验证，仅操作一加 PHK110 / d5f39352。

| 应用 | 原版包名 |
| --- | --- |
| MelodyCraft | com.mi.ai.music |
| Wishly | com.shapley.wishly |
| StickerHub | com.meta.inno.sticker |

- 不 Root、不改源码/包、不注入、不降级、不关闭更新、不读取应用或 VPN 私有数据。无需新安装 CA。
- 临时 WireGuard 每轮只包含该应用；原 Clash 节点、配置与 Mac 现有代理不改，每轮结束恢复 Clash。
- 使用独立 mitmproxy 12.3.1 运行时，保留真实上游证书校验，只解密目标业务主机。发现新主机先根据本轮限定应用的 SNI 等只读证据确认，不抓取无关应用。
- 仅启动/只读页面切换；不点击创作、支付、交易、提交、发帖、编辑、删除等业务操作。登录由本人处理；登录条件阻塞需如实记录。
- 单正文 8 MiB，单轮归档 100 条/30 MiB/900 秒上限；敏感原文仅在 0700 临时目录中，报告仅含路径、长度、状态、结构及哈希。

## 验收

1. 当前手机与三原版包名/版本/安装来源、全部 APK 哈希以及代理、VPN、USB 映射基线。
2. 各应用至少一条真实业务关联 Request/Response，包含头与完整正文，按长度/哈希/结束时间/JSON 解析检查，不以广告、图片、TLS 成功或其他应用代替。
3. 无正文、HTTP 业务错误、仅密文、TLS 拒绝、未触发请求、登录阻塞等单独说明；TLS 解密不保证可解业务层另行加密的正文。
4. 结束恢复原 Clash 运行/规则模式/自动配置/美国节点，系统代理与原 APK 摘要一致；删除本轮隧道/手机下载文件、私钥/正文及新增 USB 映射，仅停止本轮进程。
5. 更新脱敏证据并通过 git diff --check。未全部恢复不标完成；每应用技术结论独立，不扩大为所有版本通用。

## 继承依据

受损链机制、官方安全公告、PokeHub fake-IP 修正及非通用性边界见 android-emudhra-trial-20261111.md。原版三应用之前的普通用户 CA 失败或只读诊断记录仍保留，不代替本轮实测。

## 前轮 USB 断开记录

- 起始 ADB 能识别 d5f39352 / PHK110；逐个 pm list packages -i 确认三包 installer=com.android.vending，没有使用 StickerDev 或其他副本。
- 准备基线时设备掉线，第一条 dumpsys package 返回 device not found，未写出 before.json。连续多次 adb devices -l 仅见 emulator-5554，未改用模拟器，未启动任何本轮手机转发。
- 三包当前版本/完整 APK 哈希、业务流量与正文均尚未验收；历史版本表不代替本轮身份记录。已通过异步问题提示用户重新连接及授权。
- 私有目录 /private/tmp/android-ca-multi-20261111.aBrakV 保留独立 mitmproxy 12.3.1 运行时和 baseline.py、trial.py、verify.py、test_trial.py，便于恢复执行；没有运行代理、生成隧道密钥、安装 CA 或改变手机 VPN/原节点/配置。本轮新增 USB 映射为零。
- py_compile 退出码 0。4 项离线单元检查最终通过：三应用路由修正不改变 HTTP 请求字节、无关 SNI 不改写/归档、Host 与 SNI 不一致拒绝、超过归档上限不停止转发。首次合成夹具漏填 Host，被正常的严格校验拒绝；修正夹具后通过，没有放宽校验。
- 阻塞原因仅为实机 USB 连接缺失，不是三应用 TLS 失败。连接恢复后先重新完成基线，再逐项真实验证，不使用离线模拟结果冒充手机抓包成功。

## 连接恢复后的实际验收

2026-11-11 18:06 至 18:35，用户确认重新连接后，重新识别 PHK110 / d5f39352、transport28，未使用模拟器。手机为 Android 16 user 构建、ro.debuggable=0。重新建立 before.json，不沿用断线前未完成的基线。

### 原版身份与隔离方式

| 应用 | Play 原版版本 | APK/split 数量 | 临时隧道 |
| --- | --- | --- | --- |
| MelodyCraft | 1.20.0 (76) | 12 | CA-Melody-1111 |
| Wishly | 1.3.0 (17) | 12 | CA-Wishly-1111 |
| StickerHub | 3.18.15 (196) | 12 | CA-Sticker-1111 |

- 三包均由 com.android.vending 安装；StickerHub 已不同于早期试验的 3.18.14，结论以本轮实际版本为准。结束时全部 36 个 APK/split SHA-256 与本轮基线一致。
- 独立 Python 3.12.5 / mitmproxy 12.3.1，未升级桌面现用后端。继承已验证的 eMudhra 路径，ssl_insecure=false；不是关闭真实上游 TLS 校验，也不是依赖新安装的用户 CA。
- 每轮 WireGuard IncludedApplications 仅含表中对应包。原 Clash 在试验期间被临时替换、每轮后恢复，并非原 Clash 与 WireGuard 同时运行。手机原节点/配置、Mac 系统代理均不编辑。
- 每应用只解密预先确认的业务主机，经 Mac 原有 127.0.0.1:7897 出网。严格比对 SNI 与 Host，再在独立代理内修正旧 fake-IP 的路由目标；请求头、authority 和业务正文不修改，不重放合成请求。
- 第一次较长隧道名 Capture-Melody-1111 导入后未出现隧道；缩短为 CA-Melody-1111 后导入成功。没有读取到明确的客户端异常堆栈，不把名称长度推断写成已证实根因；后两轮采用短名。

### 实际请求和响应

| 应用 | 关联 HTTP 记录 | 目标 TLS 成功 | 代表性请求 | HTTP | 请求体 / 响应体字节 | 可读结构 |
| --- | --- | --- | --- | --- | --- | --- |
| MelodyCraft | 24 | 17 | POST /aisong/portal/song/feedList | 200 | 25 / 14744 | 请求含 page、page_size；响应 data 为 15 个对象的数组 |
| Wishly | 1 | 1 | POST /manifest/config/common | 200 | 33 / 267 | 请求含 configCode；响应 data 为 3 字段对象 |
| StickerHub | 39 | 20 | POST /rest/v1/rpc/get_albums_v2 | 200 | 25 / 4427 | 请求含 language_code；响应 albums 为 24 个对象的数组 |
| StickerHub（同轮） | 已计入上行 | 已计入上行 | GET /rest/v1/user_sticker | 200 | 0 / 48261 | 请求本身无正文，响应为 JSON 数组 |

- 三轮共 64 组关联 HTTP 记录，不等于 64 个不同业务接口。Melody 24 条和 Wishly 1 条均为 200；StickerHub 为 28 条 200、2 条 204、8 条 304、1 条 101，含静态资源、缓存和 WebSocket 升级。
- 三轮均未记录 target_tls_failed_client、target_tls_failed_server、target_http_error 或归档限额触发。38 次目标 TLS 成功不单独用作正文验收依据。
- 对代表响应继续检查内层 data/albums 结构，确认是可读 JSON 对象/数组，不只是一个带密文字符串的外层 JSON 包装。报告不保存参数值、个人数据、Authorization、Cookie 或 Token。
- 每条记录含 Request/Response 头与未截断正文。代表 POST 的请求头/响应头数量分别为 Melody 16/17、Wishly 14/18、StickerHub 10/23。

代表正文 SHA-256（请求 / 响应）：

| 应用 | 请求 | 响应 |
| --- | --- | --- |
| MelodyCraft feedList | 6d9250de6f4949ba990e75a9fafc4753b5b4c604e3fd9d0020263d767f3859e2 | 8ddfbfa8343b624aa33ddf27ea022f6c1a04bf307f87189250ea114c828e4eba |
| Wishly common | 7d0a4459d261ea37de080de208e9400999f24380479235d35771d8d0ace22bb0 | 1bcde52438d936874cffa9b5780de0b3b89cc508c0b867c19a4852c44a5e484e |
| StickerHub albums | 99ddee533e8a47ac415d71b9f6481298dad591a7cd0afd9cbd905c3fdbe1faa5 | 3c804115e58c2e67b3046caaabce7cbeb36e40fe9806028a00fd24bd676421dc |

### 页面覆盖与限制

- Melody 显示创作首页，启动触发上述音乐列表等接口。尝试通过 Flutter 语义定位“发现”后，截图仍是创作页且键盘展开，描述输入框可见一个字符；无法确认是否原有草稿，因此只收起键盘，未清空或提交内容。不能将该次点击记为发现页已验收。
- Wishly 停留“创造你向往的生活”欢迎页；未点击接受条款、注册或登录。已证明启动配置请求的完整正文可抓，登录后业务接口尚未覆盖。
- StickerHub 已登录，能看到画册内容和活动弹窗；未点击兑换、创作、交易、发帖等操作。只验证本轮实际触发的请求，不宣称所有功能或 WebSocket 后续消息帧通过。
- 应用启动会自动发送更新用户信息、活跃状态等请求。未手工提交业务表单、改写请求或重放请求，但不能声称启动过程中完全没有服务端写入；已将这些记录与只读代表接口区分。

### 验收与恢复证据

- 最终文件上重跑 `python -m unittest -v test_trial.py`：4/4 通过、退出码 0。
- `python verify.py Melody`、`python verify.py Wishly`、`python verify.py Sticker` 分别退出 0、integrity=PASS。独立 FlowReader 检查全部 64 条：ID 一一对应、无 flow.error、客户端及上游 TLS 存在、结束时间存在、正文非流式且 raw_content 非空缺、字节数/SHA-256/头数量相符；适用消息 Content-Length 一致。代表业务 JSON 全量解析成功，不以屏幕预览片段冒充完整正文。
- 最终 trial.py SHA-256：3d1c6fa39bfcec42988a8d6373e1fc4216d34f7e85679a6a936f497fefdea0d7；verify.py：6ede41f188cec637d7d846b0ff09687e446054a2858f124cdafcb20000363930；baseline.py：203cef9f4646f949c425bfd08635bb4c4ca5a86d3afabeda78ef961c6dbe7a4f。
- 三轮试验代理已停止，PID 3524、6870、7895 均不存在；UDP 60513、63652、50286 均无监听。未停止其他服务。
- WireGuard UI 确认三条自有隧道均关闭后删除，显示“成功删除了 3 项”和空列表。仅删除本轮四个 Download 配置文件（含首次长文件名）；逐一 ls 确认不存在，没有卸载工具或清理其他用户文件。
- 最后 UI 确认 Clash 运行中、规则模式、“自动”配置已激活；代理页仍选中 US / “日用 专线 美国[0.2]”。这是 UI/行为核对，不冒充对 VPN 私有配置文件的逐字节读取。
- `baseline.py final` 退出码 0、RESTORATION PASS：三包版本/来源/全部 36 个 APK 摘要、设备身份、user/debuggable 标志、Android http_proxy=null、Mac scutil --proxy、原 VPN 所有者、forward/reverse 均与开始一致；VPN CONNECTED/VALIDATED。
- 原 tcp:23761→10156、tcp:36166→10157 映射保留；仅回收本轮工具新增 tcp:62152→mobilecli-server。最后基线检查之后不再调用会重建映射的手机操作工具。
- 原始归档、密钥及独立运行时统一在脱敏记录完成后删除；最终目录删除及差异检查结果见 progress.md。

### 结论

本轮三款 Play 原版均取得真实 HTTPS 请求/响应及可读正文；Wishly 仅覆盖未登录启动配置。此前普通用户 CA 路径失败不再等于这些具体构建无法抓包。

该结果依赖当前构建的证书信任漏洞，是受限隔离验证，不是所有 Android 设备/应用或未来版本通用的免 Root 方案。修复后的 SDK 或证书固定可能拒绝此链，应通知项目维护者修复，不能为了持续抓包而保留漏洞或阻止更新。未将新链路集成到桌面产品，未执行产品构建、发布或推送。

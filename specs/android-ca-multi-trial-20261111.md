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

## 本轮证据

- 起始 ADB 能识别 d5f39352 / PHK110；逐个 pm list packages -i 确认三包 installer=com.android.vending，没有使用 StickerDev 或其他副本。
- 准备基线时设备掉线，第一条 dumpsys package 返回 device not found，未写出 before.json。连续多次 adb devices -l 仅见 emulator-5554，未改用模拟器，未启动任何本轮手机转发。
- 三包当前版本/完整 APK 哈希、业务流量与正文均尚未验收；历史版本表不代替本轮身份记录。已通过异步问题提示用户重新连接及授权。
- 私有目录 /private/tmp/android-ca-multi-20261111.aBrakV 保留独立 mitmproxy 12.3.1 运行时和 baseline.py、trial.py、verify.py、test_trial.py，便于恢复执行；没有运行代理、生成隧道密钥、安装 CA 或改变手机 VPN/原节点/配置。本轮新增 USB 映射为零。
- py_compile 退出码 0。4 项离线单元检查最终通过：三应用路由修正不改变 HTTP 请求字节、无关 SNI 不改写/归档、Host 与 SNI 不一致拒绝、超过归档上限不停止转发。首次合成夹具漏填 Host，被正常的严格校验拒绝；修正夹具后通过，没有放宽校验。
- 阻塞原因仅为实机 USB 连接缺失，不是三应用 TLS 失败。连接恢复后先重新完成基线，再逐项真实验证，不使用离线模拟结果冒充手机抓包成功。

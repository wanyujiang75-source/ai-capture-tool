# Android 原版免 Root 抓包可行性核查

日期：2026-11-10。目标是未 Root 真机上既有原版应用的完整业务 Request/Response，不是日志、域名或加密包统计。

## 边界与通过条件

- 不改源码、APK、签名、应用数据、系统信任库或启动安全设置。
- 不 Root，不开启第二个 VPN，不改变现有 VPN 节点、规则或配置。
- 本轮只读检查；不重新安装证书、启动证书中间人或扩大手机流量采集范围。
- 实现通过必须证明原版业务请求的方法、URL、请求头/正文、响应状态、响应头/正文可关联展示；无正文请求按协议标记，不要求虚构正文。敏感凭据不进入公开记录。
- 其他应用、浏览器或隔离夹具的成功只作对照，不替代目标应用验收。

## 新的实机证据

ADB 确认唯一 Android 真机为 PHK110；Android 16、系统构建类型 user、ro.debuggable=0、ADB 身份 uid=2000(shell)。这些信息说明当前调试权限，不单独作为绝对未 Root 的证明；未执行 adb root、su 或任何提权操作。

| 原版应用 | 包名 | 当前版本 | 调试条件 |
| --- | --- | --- | --- |
| PokeHub | com.mi.poketrade | 2.1.1 (98) | 无 DEBUGGABLE；run-as 被系统拒绝 |
| StickerHub | com.meta.inno.sticker | 3.18.14 (195) | 无 DEBUGGABLE；run-as 被系统拒绝 |
| MelodyCraft | com.mi.ai.music | 1.20.0 (76) | 无 DEBUGGABLE；run-as 被系统拒绝 |
| Wishly | com.shapley.wishly | 1.3.0 (17) | 无 DEBUGGABLE；run-as 被系统拒绝 |

上一轮从当前安装包拉取的本地副本检查：三个应用的 arm64 split 均含 libflutter.so/libapp.so；引擎中有系统 CA 目录字符串。未在三个应用的 manifest 中发现 debuggable/profileable 入口；StickerHub/Wishly 未声明 networkSecurityConfig，MelodyCraft 的配置仅放行 127.0.0.1 明文访问，没有 user CA trust-anchors。另一个 com.meta.inno.monopoly_sticker 标签为 StickerDev，不能当作正式 StickerHub 的结果。

限制：静态配置和字符串不能证明所有请求都使用同一网络栈，也不能证明存在证书锁定。MelodyCraft/Wishly 尚未在本轮完成新的代理解密实测，不能报成功或断言永远无法抓取。

既有 PokeHub 真机试验（specs/android-original-proxy-trial.md）：在当时获准的临时代理和用户 CA 下，浏览器 HTTPS 对照通过；原版业务 33 次 ClientHello、33 次客户端 TLS 失败、0 业务 HTTP 响应，应用日志为 CERTIFICATE_VERIFY_FAILED / unable to get local issuer certificate。该结果支持证书链不被接受，不足以判定 pinning。此前恢复记录保留，不重复更改手机配置。

本轮只读复核 /Users/wan/test/TCGPFlutter/lib 与 android：StatisticalClient 继承 IOClient，默认构造；未找到 keyLog、SSLKEYLOGFILE、HttpOverrides、SecurityContext 或 badCertificateCallback 配置。该目录是测试源码，不保证与四个线上 APK 一致，未修改或构建。

## 技术选型

| 路径 | 能解决什么 | 当前限制与结论 |
| --- | --- | --- |
| Charles / mitmproxy / HTTP Toolkit | HTTP 代理和受信任 HTTPS 中间人 | 不能令应用自动信任被拒绝的 CA；换工具不等于解决信任问题 |
| Reqable 增强模式 | 接入不遵循系统代理的 Flutter 流量 | 官方仍要求处理 Flutter 系统 CA 信任；不是免 Root 解密证明 |
| PCAPdroid / VpnService / WireGuard | 接入 IP 数据包或转发应用流量 | 同用户第二个 VPN 会替换既有 VPN；解密仍需 CA 或目标 TLS 密钥，当前不启用 |
| 现有 VPN 本地代理 / USB reverse / 路由器采集 | 改善接入或采集密文 | 不能仅凭 CONNECT、IP、SNI 或 VPN 外层密钥解密应用内层 TLS；历史接入已成功但 TLS 被拒绝 |
| Shizuku / 无线 ADB | 向兼容工具提供 ADB 或 Root 启动身份的 API 权限 | 本机 ADB 是 shell，不会因此取得 Root 或任意进程读取权限；不安装来重复已知权限限制 |
| Frida 调试器注入 / JVMTI | 在满足调试条件时观察应用进程 | 当前四个原版包均不可调试；Gadget 需要应用加载，重新打包不符合边界 |
| Android Studio / profileable | 支持的网络栈调试或性能追踪 | Network Inspector 主要支持 HttpsURLConnection/OkHttp；profileable 不提供任意堆内存读取，不是 Dart TLS 正文出口 |
| PCAP + NSS TLS key log | 保持原 TLS 时离线解密 | 需目标 TLS 端点实际导出会话密钥；Dart keyLog 是应用回调，不是电脑端勾选开关；当前未找到可用导出证据 |
| MDM / 工作资料 CA 安装 | 管理用户 CA | DevicePolicyManager.installCaCert 安装的仍为用户 CA，不强制原版 Flutter 引擎信任；不引入设备管理配置 |
| 服务端或已授权网关的 TLS 终止日志 | 不改手机时从服务端采集 | 需相应端点权限与正文采集能力；已知无管理权限，不绕过权限；普通服务日志未必含完整正文 |
| 虚拟容器 / 改包 / 系统漏洞 | 改变运行环境或权限 | 不属于当前已安装原版真机条件；不作为无损通用功能引入，不尝试提权或降低系统安全 |

## 官方依据

1. HTTP Toolkit Android：https://httptoolkit.com/docs/guides/android/ 。非 Root 原版若不信任用户 CA，需要应用配合或系统级条件。
2. Reqable Flutter：https://reqable.com/en-US/blog/2024/06/27/post/ 。增强接入与证书信任是分开的条件。
3. mitmproxy 模式：https://docs.mitmproxy.org/stable/concepts/modes/ 。WireGuard 是流量接入模式，并非无需 TLS 信任。
4. PCAPdroid 解密：https://emanuele-f.github.io/PCAPdroid/tls_decryption.html 。解密插件使用 mitmproxy，仍有证书信任限制。
5. Android VPN：https://developer.android.com/develop/connectivity/vpn 。每用户或工作资料只能有一个活动 VPN 服务。
6. Frida：https://frida.re/docs/android/ 。非 Root 的调试器和 Gadget 路径各有前置条件。
7. Network Inspector：https://developer.android.com/studio/debug/network-profiler 。网络库支持范围有限。
8. Profileable：https://developer.android.com/guide/topics/manifest/profileable-element 。性能分析不提供任意内存数据读取。
9. Shizuku：https://shizuku.rikka.app/introduction/ 。权限来自启动它的 ADB 或 Root 身份。
10. 设备管理 CA：https://developer.android.com/reference/android/app/admin/DevicePolicyManager#installCaCert(android.content.ComponentName,%20byte[]) 。安装用户 CA，不自动使 Android 7+ 应用信任。
11. Dart keyLog：https://api.dart.dev/dart-io/HttpClient/keyLog.html 。需要应用设置回调导出 TLS 会话密钥。
12. 对应本地测试 SDK 的实现：https://github.com/dart-lang/sdk/blob/3.10.7/runtime/bin/security_context_linux.cc 。Android 默认加载系统 CA 目录；不据此假设所有线上包的引擎版本相同。

## 实施门槛及状态

目前没有验证到符合全部边界的完整解密路径，产品实现受阻。不能把报告完成标为免 Root 功能完成，不能增加声称支持这些原版包的成功状态或下载包。

继续实现至少需要一项新的实际条件：原版自身已提供且可授权开启的正文/会话密钥诊断入口；用户可管理的服务端 TLS 终止点及采集权限；或重新明确允许使用由发布方提供、保持正确签名和登录能力的诊断构建。前两项可保留原版手机包；后一项是另一种构建，不能替代原版验收。当前均未具备，不擅自执行。

只读复核后 VPN transport 仍存在，全局 http_proxy=null，USB reverse 映射为 0。本轮没有修改节点、路由、证书或手机数据；只能确认这些可读状态，不能将其扩大为读取或验证了 VPN 私有配置内容。

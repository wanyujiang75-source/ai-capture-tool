# PokeTrade 原版代理对照

2026-11-10 ANDROID-POKETRADE1。用户指定桌面PokeTrade；只读应用清单确认手机包me.poketrade.app、版本1.42.6(195)、Play来源、target36、未声明debuggable。不等同之前PokeHub的com.mi.poketrade。

边界：不Root、不改原APK/重签、不注入、不复制登录态、不清数据。不改VPN原配置、订阅、节点、DNS或Mac现有代理；只允许本轮独立临时转发与测试CA，VPN保持开启。安全确认和登录由用户完成，不操作购买/交易/消息发送或服务端权限。若只读静态证据已提示信任限制，明确告知，但不把静态判断冒充实测。

验收：原APK集合SHA256前后核对；读取Manifest网络安全配置和库类型，仅提取所需信息，不输出包内密钥；核对用户当前页面、配置模式/节点及USB基线。代理只回环经USB接入，上游复用7897，HTTP正文限1MiB、记录数量50，私有目录700，无关HTTPS透传。先本机/浏览器对照，再业务读取请求；业务响应必须有真实正文才算解密成功。证书失败需原始错误层佐证。

结束后恢复原VPN选择、检查同一VPN实例、原应用联网及原APK摘要；仅删本轮配置/CA/转发/服务/私钥与敏感正文。未恢复不报完成，无正文不报抓包成功。当前产品源码/构建/安装包/远端发布均不在范围。原有android-copy-capture-trial.md修改不动。

## 预检与等待安全确认

- 已确认PokeTrade首页可用。通知提示选择“先不要”，未授予新通知权限或执行业务写操作。
- 原13个APK摘要存于私有/tmp/poketrade-original-ORCLkV/hashes.json。包内有Compose、Ktor及OkHttp类；业务URL线索https://api.pockettrade.app。类库存在不等于已确认每个实际网络调用实现；未把OkHttp CertificatePinner类名当作实际固定证书证据。
- Manifest声明network_security_config，但内容仅允许10.0.2.2明文通信，没有用户CA信任声明；仍须实际TLS对照。
- 独立有界代理复用先前原型，目标仅example.com与api.pockettrade.app，其余HTTPS透传；3项原型测试通过。本机无认证407、指定本轮CA的认证HTTPS200/TLS验证0。服务PID82030，回环50787/50788，上游7897未修改，最长30分钟自动退出。尚未导入或启用手机临时VPN配置、尚未建立本轮reverse；若用户等待超过期限需先复核服务再继续。
- 唯一公有CA文件已放入Download/Capture-PokeTrade-Trial-ORCLkV.crt，CA名称Capture PokeTrade Trial ORCLkV，一天有效。本轮等待用户在CA警告页自行确认及输入锁屏密码；不读取密码。原凭据四项（Charles CA、Capture Oneplus Temporary 1105、charles WLAN、reqable WLAN）已只读核对，不动。
- 本轮UI工具新增forward50119待收尾移除；原23761/36166保留。VPN仍原实例189、系统http_proxy=null，尚未切换原节点或配置。

## 11:41–11:45 实测结果

用户确认安装后服务仍存活，新增本轮reverse50787/50788，导入并启用独立Capture-PokeTrade-ORCLkV配置。原“自动”和“新配置”保留；VPN显示运行中/规则模式。Chrome打开带本轮标记的example.com，没有证书警告，代理记录手机GET及正文；包含本机对照，共3条HTTP200响应归档。浏览器结果仅作为证书/代理对照，不代表业务成功。

冷启动me.poketrade.app原版（不清数据），PID4267；关闭“浮动窗口”介绍的“了解”提示，没有启用悬浮窗权限。目标api.pockettrade.app实际记录6次ClientHello、6次客户端TLS失败，均为`tls alert certificate unknown`，业务HTTP响应记录0。应用首页显示“PokeTrade伺服器目前無法連線”。因此用户CA安装有效、浏览器可解密，但当前正式版业务连接拒绝该抓包证书。不能从这个错误单独断言存在显式证书固定。

应用Logcat另有UnityAds的`CertPathValidatorException: Trust anchor for certification path not found`；该错误在恢复后PID6882仍出现3次，因此不作为业务域名失败证据，也不宣称全应用无错误。业务结论依靠目标域名的TLS事件及页面对照。未读取或修改服务器数据、未操作购买/交易/聊天。

ANDROID-POKETRADE1完整请求响应目标BLOCKED；诊断和恢复已经完成，不重复换CA或扩大到Root/改包/注入。

## 恢复及清理

- 切回原“自动”配置，规则模式；截图确认PROXIES仍US、下级仍“日用 专线 美国[0.2]”。只删除本轮临时配置，列表仅原来的两个配置。
- 本轮CA在用户凭据确认名称Capture PokeTrade Trial ORCLkV、alias user:6a4e0e39.0，然后仅卸载该项。最终原四项凭据保留，本轮项消失。此前只读进入ACCV系统证书详情，未停用或修改任何系统证书。
- 删除手机Download中本轮crt。恢复手机路由后停止PID82030，进程及exec会话退出0。删除本轮私钥、ca/mitmproxy-ca.pem、认证state.json、trial.yaml及3条对照正文归档，只留诊断代码、公有CA、无正文事件日志与原APK摘要。
- 本轮reverse50787/50788已删除，reverse为空；forward50119移除，原23761/36166保留。VPN仍同一实例189、创建时间2026-11-09T03:51:20.059Z，http_proxy=null。Mac上游未修改。
- 13个APK的SHA256与测试前完全一致。恢复后原版新PID6882首页重新显示在线用户、已列出卡牌及卡片列表，服务器无法连接提示消失。此项只证明观察页面恢复，广告SDK残余错误另记，不宣称全部业务功能通过。
- 复用原型的3项测试通过；产品代码未改，不运行无关构建；文档diff检查通过后仅提交本轮goal/progress/spec，不包含原有android-copy-capture-trial.md修改，不推送远端。

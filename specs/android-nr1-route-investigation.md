# NR-1 原版业务正文出口核查

2026-11-10。目标：PokeHub优先，其余三个原版独立记录；满足不Root、不改源码/包、VPN保持开启且原节点/配置不变的完整业务Request/Response入口。

版本说明：以下至“本轮结果与后续条件”为首次只读核查历史；用户随后明确授权打开MelodyCraft/Wishly，新增运行时证据及当前结论见文末“追加：两应用运行时补验”。旧记录中的“未运行”不再代表当前覆盖状态。

## 本轮范围

复用此前CA被拒绝、AP-0及安装身份证据。不重建代理、不安装CA、不转发端口、不改VPN、不提权、不启动或重启应用。只读设备检查与公开官方资料核实，测试源码仅作线索而非线上构建证明。

## 新假设及通过标准

| 假设 | 最小安全检查 | 合格候选必须具备 | 停止条件 |
| --- | --- | --- | --- |
| 原版是profile或已有可用Flutter VM Service | 当前进程/有界诊断日志、官方构建模式说明、原包公开配置 | 目标原版真实可用诊断服务，能证明业务请求与响应正文出口，并有访问授权 | 没有实际入口；仅发现库字符串、调试符号或timeline统计 |
| 原版/系统可导出目标TLS会话密钥 | 查官方keyLog机制、原版公开可读配置及已给测试源码 | 原版当前TLS端点生成且可合法读取的对应会话密钥，具备匹配内层报文来源 | 需要改包、注入、提权、读取私有凭据或仅拿到VPN外层密钥 |
| 现有工具可在原VPN不变时输出业务正文 | 查官方网络日志、抓包/代理与解密能力的差异 | 明确目标归属、协议层与正文完整度，不替换原VPN、不改原配置 | 只有IP/域名/SNI/连接时间/加密PCAP；仍依赖被拒CA |

每个候选除通过标准外必须有具体接入、权限、业务验证方法、失败/清理方式。公开资料说“支持抓包”不足以启动NR-2。查不到入口不等于数学证明永远不可能，但不能生成已验证候选。

## 新证据及应用覆盖

设备仍为PHK110，ADB传输代次为21；本轮没有启动应用。只读包信息均仍显示Play安装来源和不含DEBUGGABLE的flags。安装来源不是签名/原版真实性证明，本轮没有生成完整身份或任何成功准入证据。

| 应用 | 当前版本 | 当前运行检查 | 本轮正文/诊断证据 |
| --- | --- | --- | --- |
| PokeHub | 2.1.1 (98) | 主进程存在 | 选定PID的有限日志窗口未匹配VM服务或结构化HTTP正文标记；未读到该PID对应WebView调试套接字 |
| StickerHub | 3.18.14 (195) | 主进程存在 | 同样未匹配上述日志标记或WebView套接字；缓存包存在WebView调试方法标识，但不能证明调用过或已经启用 |
| MelodyCraft | 1.20.0 (76) | pidof退出1、无PID和错误输出 | 本轮未运行验证；仅检查已有包副本和公开构建机制，不报告实际解密失败 |
| Wishly | 1.3.0 (17) | pidof退出1、无PID和错误输出 | 本轮未运行验证；仅检查已有包副本和公开构建机制，不报告实际解密失败 |

运行检查局限：每次logcat只读最多2000条有限缓冲区记录，限定目标PID及flutter/DartVM标签，再在设备侧过滤诊断标记，返回内容受8秒/64KiB执行器上限控制。只输出匹配数量和是否存在回环服务URL，不输出VM服务认证URL、业务日志或凭据。没有清日志、转发端口、开放新监听、重启进程或修改日志级别。零匹配不证明应用永远不可能提供诊断能力，也不排除其他进程、历史日志被覆盖或入口未开启。

WebView检查仅按当前目标PID匹配/proc/net/unix中webview_devtools_remote名称；没有扫描端口或连接其他应用。未匹配不能证明所有子进程都没有WebView；即使某网页可以调试，也只能覆盖该WebView内的请求，不能替代Dart业务请求验证。

三个已有原包副本的manifest均未匹配debuggable/profileable/VM诊断配置，未找到kernel_blob.bin等调试快照资产。对应arm64引擎副本均未匹配本轮搜索的VM服务启动提示、enable-vm-service、getHttpProfile、SSLKEYLOGFILE字符串。静态缺失不是构建模式的绝对证明；缓存副本本轮未重新取得全量签名/摘要来绑定当前安装，不扩大为当前原包完整性验证。

尝试只读查找本地Flutter SDK内现成libflutter.so用于profile/release精确摘要对照，未找到可直接对照的该路径产物。因此没有报告“引擎摘要证明是Release”，也没有下载、构建或安装其他引擎。

## 候选逐项判定

### H1：Flutter VM Service直接读取正文

机制确实存在：Flutter DevTools Network View能查看受支持Dart请求的头和正文。官方移动端构建模式说明Release关闭调试与service extensions，profile保留部分服务能力。因此Android的DEBUGGABLE=false不能单独排除profile服务，需要实际入口证据。

本轮PokeHub/StickerHub没有观察到实际VM服务URL，另两款未运行验证。没有具体可连接的目标服务，不能启动flutter attach来冒充只读核查，更不能重建profile包。候选状态为未成立，非“技术上所有非Root设备都不支持”。

若后续原版公开提供诊断地址且用户授权访问：先核对设备/包/进程归属及只读服务权限，再在NR-2用原版业务请求检验Network View可取得的实际字段。若仅timeline或无正文，立即停止该候选；仅创建的本机自有诊断通道可以清理，不改手机VPN。

### H2：TLS会话密钥导出

本地测试SDK的HttpClient.keyLog是可空回调：_http/http_impl.dart:2793声明_keyLog，2824处setter写入，2697处传给安全连接。io/secure_socket.dart:663只有回调非空时才建立密钥回传处理。该机制是应用显式提供的，不是电脑设置SSLKEYLOGFILE就能强制为Android原版启用。

针对用户给出的TCGPFlutter测试源码，未找到keyLog、SSLKEYLOGFILE、HttpOverrides、SecurityContext、VM服务注册或已知网络调试插件的有效配置。一次宽松alice搜索命中了西班牙语翻译字符串，已排除这个假阳性；未将全文字符串扫描当作诊断功能证据。

测试源码不是线上构建的等价证明，本轮也没有在手机私有目录搜索密钥或凭据。目前没有可合法读取、能匹配原版当前TLS会话的密钥来源，也没有匹配内层PCAP，因此候选未成立。没有运行环境变量注入、wrap脚本、内存导出或任何提权。

若后续原版本来就能由用户授权导出本次会话密钥，才能进入NR-2核对NSS key log和对应内层报文；不匹配即停止，不会使用其他应用或VPN外层密钥替代。密钥按凭据处理，仅本机受控存储，试验后删除本轮副本。

### H3：原版日志或性能平台已有正文

新发现：TCGPFlutter/lib/util/network/statistical_client.dart:42只构造host+path的reportUrl；48–51记录响应码、请求/响应长度和content-type；55–66的日志为路径/成功失败/状态码。它没有记录请求headers/body，也没有读取响应流导出response body。Firebase Performance官方列出的网络trace指标也是时间、请求/响应字节大小和成功率，而不是原始正文。

即使这些记录可读，不能恢复未记录的正文。选定PokeHub/StickerHub当前PID的有限日志没有匹配本轮HTTP正文标记，只能记“本窗口未观察到”，不推断所有日志或业务都无正文。没有擅自开启日志开关或进入性能平台获取管理权限。

只有原版本来提供、得到授权且包含完整业务字段的诊断导出，才是NR-2候选。当前没有该导出或服务端管理权限，故未成立；不请求用户重复提供已经明确没有的后台权限。

### H4：WebView远程调试

Chrome官方说明WebView调试必须由应用启用，而且其开关独立于manifest的DEBUGGABLE。StickerHub/MelodyCraft副本的DEX中存在setWebContentsDebuggingEnabled方法名，是新增线索，不是开启证据；未发现可匹配当前目标PID的已启用WebView调试套接字。

若用户原版本来有公开可用WebView诊断入口，后续只能验证该WebView内的业务请求，不能把网页广告/登录SDK请求等同于原生Dart业务。需要注入、重新打包或设置全局系统调试开关时停止。当前候选未成立，MelodyCraft因未运行仍属于未覆盖项。

### H5：现有VPN的嗅探能力或Android Studio监视器

Mihomo官方sniffer是域名嗅探，支持HTTP/TLS/QUIC分类和目标域名识别；这些说明不能证明其导出HTTPS业务正文。仅连接统计或SNI不满足NR-2。没有连接其管理接口、读取订阅/原节点凭据或改变嗅探设置；不假设当前VPN客户端的具体内核与版本。

Android Studio Network Inspector官方范围为HttpsURLConnection/OkHttp。不能据此推断可直接读取这里的Dart IOClient业务；即便看见原生SDK流量，也必须独立证明目标业务归属和完整性。未安装新的监视代理或调试构建。

本轮没有发现现有工具绕过目标CA信任或提供目标会话密钥的新机制，不重复旧Charles/mitmproxy/用户CA试验。若未来原VPN自带已授权正文导出，仍需确认是否真实完成应用TLS终止以及覆盖范围，不能只看“嗅探已开启”字样。

## 来源与本地证据

- Flutter Network View：https://docs.flutter.dev/tools/devtools/network 。说明可展示请求响应头/正文，但不提供对任意Release强行启用VM服务的方法。
- Flutter构建模式：https://docs.flutter.dev/testing/build-modes 。移动Release关闭调试和service extensions，profile保留部分服务。
- Flutter服务扩展：https://api.flutter.dev/flutter/semantics/SemanticsBinding/initServiceExtensions.html 。VM服务需包含在构建中，二进制内残存字符串也不能证明服务可用。
- Dart keyLog：https://api.dart.dev/dart-io/HttpClient/keyLog.html 。由应用设置回调输出NSS会话密钥。
- Chrome WebView：https://developer.chrome.com/docs/devtools/remote-debugging/webviews 。应用显式启用，独立于manifest debuggable。
- Firebase网络trace：https://firebase.google.com/docs/perf-mon/network-traces?platform=flutter 。网络性能指标不等同正文归档。
- Mihomo域名嗅探：https://wiki.metacubex.one/config/sniff/ 。文档定义域名/协议嗅探，不作正文出口证据。
- Android Network Inspector：https://developer.android.com/studio/debug/network-profiler 。目前列明支持HttpsURLConnection和OkHttp。
- 本地只读SDK：/Users/wan/fvm/versions/3.38.6/bin/cache/dart-sdk/lib/_http/http_impl.dart、lib/io/secure_socket.dart；该SDK版本不能自动套用到全部线上包。
- 本地测试源码：/Users/wan/test/TCGPFlutter/lib/util/network/statistical_client.dart、lib/util/network/api.dart；没有修改或构建。既有ios/Podfile.lock、pubspec.lock脏文件保留。
- 既有副本：/tmp/android-app-trust-lpeJQe下三个base和对应arm64 split；只读检查，没有生成或安装改包。

资料获取限制：一个猜测的Mihomo源码路径返回404，Dart GitHub页面查找超时、另一gitiles链接不可用，未使用这些失败页面作为实现证据；对应结论只依赖成功读取的官方文档和本地SDK。未通过安装未知工具或网络绕行来补齐来源。

## 本轮结果与后续条件

NR-1技术状态：BLOCKED。本轮已核查5个出口假设，未形成同时具备新机制、原版具体入口、授权及验证/恢复方法的可执行候选；不进入NR-2，不生成Candidate(mechanism_verified=True)，不改变NR-0默认不准入策略。

未运行中的MelodyCraft/Wishly没有新的动态验证，不能记为已解密失败，也不能要求用户为已经验证失败的旧证书路线重复操作。未来仅当出现原版本来可用的诊断入口或会话密钥导出、已授权的服务端正文采集，或其他符合约束的新机制时恢复本任务。必要的用户手动打开目标页面属于补充观察，不会单凭该动作解除技术阻塞。

网络复核：本轮可读状态为全局http_proxy=null、VPN transport存在、USB reverse映射0；没有任何写配置或创建/删除映射操作。仅确认可观察状态，不声称读取或逐项验证了原VPN的私有节点配置。未关闭当前桌面端，也没有需要用户恢复的本轮临时改动。

## 追加：两应用运行时补验

### 授权、身份与操作

用户明确要求打开MelodyCraft和Wishly，补齐运行时出口验证。不Root、不改源码/安装包、VPN开启及原节点/配置不变的限制继续有效。复用当前一加PHK110、ADB目标d5f39352与传输代次21，未接触另一台连接的iPhone。

通过本机手机操作工具正常启动已安装的com.mi.ai.music和com.shapley.wishly，没有force-stop、重装、清数据或以调试参数重启。首次前台查询失败，随后识别到USB用途选择弹窗；仅按返回键关闭弹窗，未更改USB用途。之后工具明确返回了对应前台应用，应用主进程分别为21218、22745。

| 应用 | 已观察页面和操作 | 页面结果 | 运行时出口结果 |
| --- | --- | --- | --- |
| MelodyCraft 1.20.0 (76) | 主界面、发现、最新发布、音乐库、设置；只读切换，不点击创作/分享/播放/删除 | 最新发布先加载，之后可见内容列表；音乐库可见；设置仅观察公开选项 | 当前应用进程及包名匹配进程检查未找到VM服务、正文/密钥导出标记或对应WebView调试套接字 |
| Wishly 1.3.0 (17) | 首页、肯定语、我的、设置；不发送输入、不签到、不购买、不编辑、不登录 | 首页和肯定语内容可见；设置有Google登录入口，未尝试登录 | 当前应用进程及包名匹配进程检查未找到上述出口或对应WebView调试套接字 |

已查看的设置项没有提供可识别的网络日志、TLS密钥导出或诊断服务入口。没有尝试版本连点、隐藏开发菜单、调试开关或任何修改型操作；不能据此证明应用所有页面均无相关功能。记录不包含账号、用户ID、个人内容或具体歌曲/卡片数据。

### 日志与套接字检查

为两款应用分别记录设备侧启动前epoch作为logcat起点：1794304918、1794305033；不修改系统时间。按包名识别主进程及同包命名子进程，本轮每款各观察到1个匹配进程。Flutter标签定向扫描后，追加了不限标签的目标PID有界日志，避免仅检查flutter标签漏掉原生诊断输出。

- MelodyCraft一次起始窗口达到49152字节/468行上限；随后最新窗口17309字节/174行。不能将被截断起始窗口当作完整启动日志。
- Wishly一次最新窗口约49151字节/437行，达到窗口边界；只按有限窗口描述，不宣称全部日志被检查。
- 最后对每款从各自起点到检查时的可用缓冲区，在设备侧过滤诊断标记，再以16384字节限制输出。两款匹配行数均0：没有观察到Dart VM服务/Observatory提示、request/response body标签、NSS key log标签或所查TLS/网络异常标记。
- 按实际目标PID读取/proc/net/unix并过滤对应webview_devtools_remote；本轮均未匹配。没有连接调试端口，没有启动flutter attach或DevTools，没有读取手机私有目录。

诊断数据只在本机内存中处理并输出计数/布尔结果，未保存原始应用日志、认证服务URL、正文或密钥。截图仅用于核对当前页面与设置图标，没有将用户界面截图加入仓库或新建公开证据文件。

局限：日志缓冲区可能覆盖，正文可能不带所查标签，WebView可能存在不按包名命名的隔离进程，页面数据也可能来自缓存。页面内容和零TLS错误都不能证明取得了线上业务Request/Response；本轮更没有证据证明所有HTTPS都已通过或永远无法抓取。

### USB工具资源与网络恢复

起始可读基线：全局http_proxy=null、VPN transport存在、reverse为0，已有forward为2。保留摘要在本机内存，不读取原节点密码或订阅。

手机操作工具自动新增了`d5f39352 tcp:51309 localabstract:mobilecli-server`映射，用于UI操作，不是抓包代理。该增量与本轮最初“不创建转发”的意图不同，故单独记录。通过移除该单行后其余列表SHA-256与基线完全一致，确认其为精确增量；且目标为工具的mobilecli-server。全部UI操作结束后仅删除该映射，命令返回0，原2条forward列表摘要恢复一致。没有remove-all、清空映射或终止未知进程。

最终复核：proxy_unchanged=true、vpn_present=true、vpn_summary_unchanged=true、reverse_unchanged=true、forward_unchanged=true。没有手工配置抓包代理或证书，没有操作VPN客户端或节点，也没有改变系统代理。可读摘要一致不等于读取了VPN私有配置；本轮没有需要用户恢复的网络变更。最后前台停在MelodyCraft“发现”页面，未关闭或重启用户桌面端。

### 当前结论

补齐了这两款应用在本轮指定页面的运行时观察，不再标为“未启动”；但没有形成可用的原版业务正文出口，NR-1仍为BLOCKED，不进入NR-2，不生成已验证候选。

本次是运行时入口核查，不是对这两款执行了新的代理/证书解密试验。结论是“已观察的原版页面及进程未发现满足约束的现成出口”，不是“新CA试验再次失败”或“已证明所有免Root方式不可能”。下一步仍需原版确实提供诊断/密钥出口、授权服务端正文来源或其他符合约束的新机制；再次重复启动或换证书不能自动解除这一阻塞。

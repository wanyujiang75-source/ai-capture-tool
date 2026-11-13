# Android 真机广告兼容计划与 AD-0 验收

## 目标与边界

### 11-13用户切换PokeHub验证目标

#### 15:31 本轮最终验收：未通过视频标准

- 原Clash冷启动后15:03:10观察到interstitial loaded，点卡片后显示真实视频，前台为Google AdActivity；截图poke-vpn-google-video.png。视频内容未点击，没有交易、清数据或登录态变更。
- 桌面#122仅两个入口，#123四个精确入口/渲染主机，#124六个精确主机；每轮在抓包建立后重启目标进程，打开只读卡片。三轮均未复现视频，#124卡片触发15:27:47开始interstitial加载、15:28:14报错误0。并非单凭缺少Banner判失败。
- #124新增的googleads4.g.doubleclick.net及s0.2mdn.net均经原上游CONNECT收到源站数据；另出现lh3.googleadsserving.cn、pagead2.googleadservices.com等target/capture TLS失败。没有继续扩大范围，也没有将这些错误直接认定为同一个插屏的唯一根因。固定几项主机不能覆盖动态素材/中介依赖，缺少具体加载尝试与适配器/素材的关联证据。
- 三轮分别50（43x200/4x204/3x101）、49（42x200/4x204/3x101）、58（51x200/4x204/3x101）条归档。所有已归档/rest/v1/rpc/请求及响应complete=true；get_app_config各4/3/4条，80B请求/2621B响应，无截断。#124桌面Request/Response切换实际检查通过；101仅握手，不宣称WebSocket后续正文完整，也不宣称所有SDK请求均捕获。
- 两次依赖边界扩充均先RED再GREEN；最终Android回归131项、130通过/1可选跳过，日志/tmp/ad1-poke-final-tests.log；27项路由/原TLS/无HTTP归档/无直连回退专项通过。诊断私有App验签通过；未作最终发布构建，因为真实视频标准未通过。
- 三轮均通过桌面停止，打开原Clash启动后点击检查网络恢复并确认成功；当前VPN为com.github.metacubex.clash.meta，系统http_proxy=null，原19387/46619 ADB映射保留，临时worker通道清理。原APK SHA256仍为255614ea1252bd69a8cc7f8cd9b6af6af646af7744c8cfc426915773ecf83e39；历史PHK110恢复记录SHA256仍为3a2bb229461addc57d3c15775ac9ccf5f40b94a56f53b326dbbce69259dacb27。没有编辑节点/订阅/配置或修改原包。
- /Applications/抓包工具.app已由reconnected-original.app稳定备份恢复并启动，严格签名校验通过；最后诊断版移存poke-final-probe.app，原始证据仅存/tmp/capture-ad1-gms-20261113.lzL0nf。未推送或发布；仓库普通worker未强制开启探针。
- AD-1为BLOCKED而非DONE：三次限定修订均未满足完整视频验收，停止当前固定主机试错。后续先设计有界的广告尝试/适配器关联诊断或可明确区分业务与广告的策略，再恢复真机验证；不以自动扩大所有TLS失败主机、关闭校验或修改原包代替定位。

15:22第二轮修订后两个渲染主机均原TLS返回数据，jsLoaded出现，但卡片触发的新interstitial仍报加载错误0；有界诊断新增googleads4.g.doubleclick.net五次及s0.2mdn.net两次target/capture TLS失败。这暴露入口轮换/独立素材域而非上游拒绝。最后一次精确对照仅加入这两个观察到的主机，不使用整个doubleclick/2mdn通配，不增加其余中介。此修订替代上方“一项依赖修订”的试验停止条件：第三轮仍失败就停止扩域、恢复稳定桌面与原Clash并记录未通过，不默认启用或发布。测试前原Clash基线再次恢复。

15:16第二阶段对照：两入口透传下点击卡片无视频，目标WebView证书公钥拒绝/-202，static.googleadsserving.cn两次、www.googletagservices.com一次target/capture TLS失败。下一次唯一依赖修订仅这两个精确Google渲染主机，不扩域、不透传其他SDK或业务。新边界测试先RED（缺少CONNECT），再修订；仍私有探针，默认关闭。首次两入口对照业务50请求/50响应，尚不计广告成功。

15:06最小对照假设：原Clash冷启动后目标日志commonInterstitial loaded，点击卡片出现真实视频，前台为com.google.android.gms.ads.AdActivity；#121同应用pagead2.googlesyndication.com目标连接两次TLS失败。先只对PokeHub精确googleads.g.doubleclick.net/pagead2.googlesyndication.com保留原始TLS CONNECT，独立于StickerHub清单；仍显式probe才启用，其他包/业务/子域/未知角色保持原行为。先路由和真实TLS回归，再桌面实测；最多依据新证据扩一项明确渲染依赖，不做全部SDK兜底。不把Error3无填充误当证书根因。

14:40用户明确修订广告验收：不要求底部Banner，点击卡片后视频广告正常出现即可。原Clash下已点击只读卡片并观察到视频广告，作为基线；后续需在桌面抓包开启时复现相同视频广告并验证业务正文，不能因无Banner判失败。只关闭视频广告，不点击落地内容。

14:50对照结果：桌面#121仅PokeHub原版2.2.0(99)，冷启动和卡片只读操作后132条归档（117个200、5个204、7个304、3个101握手）。get_app_config五次均请求80B/响应2621B，双向complete=true/truncated=false，桌面Request/Response实际显示格式化JSON。广告配置enable=true、trigger_interval=240；本轮未复现视频，目标日志三次Ad failed to load : 3，同时多个广告中介连接TLS失败。不能将错误3、投放间隔或全部中介TLS失败直接归为视频根因；尚未满足抓包与视频同时成功。没有套用StickerHub透传域或关闭证书校验。

停止前出现连接中断自动停止，#121最终stopped；ADB随后仍在线，具体中断来源未确认，不虚报手动停止按钮成功。打开原Clash点启动，桌面“检查网络恢复”确认原网络已恢复，旧PHK110提醒保留。原包SHA-256 255614ea1252bd69a8cc7f8cd9b6af6af646af7744c8cfc426915773ecf83e39前后一致。未编辑VPN节点/配置、未改包/Root/清数据。私有截图poke-original-vpn-video.png与poke-capture-card-no-video.png存于既有临时证据目录；原始身份/正文不提交。下一步必须定位实际视频中介及失败阶段，不能按所有TLS错误扩域；AD-1未完成。

当前子轮仅PKG110上的com.mi.poketrade正式版2.2.0(99)。原Clash保持原节点和规则配置，先观察Banner与只读卡片触发的广告，再临时通过桌面助手进行相同操作及业务正文对照，结束恢复Clash。无广告不能直接归因TLS；不套用StickerHub专用透传范围。不得点击广告落地内容、购买、交易或改变账号数据；允许打开卡片详情及关闭广告。证据需区分Banner、开屏与插屏，不以一种广告代替另一种。验收沿既有AD-1，不新增任务；StickerHub既有未完成结论保留为历史。

抓包开启时保留 StickerHub 的 Google 登录、业务完整请求/响应及广告联网能力。广告出现是附加证据，不等于网络健康，也不能保证投放。仅 PKG110 上原版 StickerHub；不 Root、不改源码/原 APK、不清账号或数据、不点击广告或高频刷新。原节点/订阅/配置/系统代理不编辑。测试临时切换原 VPN 与本工具助手，结束恢复实际起始状态。敏感日志和截图仅存私有临时目录，仓库只记脱敏计数/状态。不得归档 Google 依赖的认证正文。

## 分阶段设计

- AD-0：记录设备/包/网络/VPN/USB 基线；原 VPN 与现有桌面抓包各进行一次低频页面观察及有界日志；核对业务和广告差异；恢复基线。只有证据充分才进入后续修复，不以无广告直接判断证书错误。
- AD-1：依据 AD-0 证据定位进程、DNS、TLS、TCP/QUIC 或广告无填充。归属与主机名可观察性不足时明确限制，不声称已经定位。
- AD-2：最小化补齐确认必要的依赖加密转发；目标业务保留现有采集，可靠识别的广告连接保持原始 TLS，不归档正文。混合主机/未知身份不得静默扩大旁路或整机采集，不重放写入请求，不回落直连。UDP 不默认能走 HTTP CONNECT。
- AD-3：桌面自动诊断/恢复，用户只做必要系统授权；清楚区分流量转发、TLS、业务响应与广告实际投放，技术细节折叠。
- AD-4：真机对照及相关后端/助手/Swift回归、构建验签、停止/退出/断线/换机恢复、有界缓存/超时验证；已知兼容缺口如实保留。远端发布不在此授权内。

AD-0历史轮只处理基线。2026-11-12用户新授权从AD-1继续定位并做最小修复、自验收：当前只领取AD-1，将已明确要求的最小修复纳入本任务；不并行领取其他任务，不额外实现AD-3全套UI改造。

## AD-1 实施契约

14:15 #119仍无Banner，Google target/login CONNECT均接受且无拒绝，GMS仍报Software caused connection abort，不能将上游接受等同于TLS成功。下一步仅在既有opaque路径记录有界收发字节总数、收到服务端数据的连接数、首个关闭方向；不读取/持久化TLS正文，不新增主机/降级验证/改变转发。范围新增android_physical_opaque_probe.py及对应测试，先验证真实TLS仍原样、无HTTP flow，随后一次手机对照。#119已桌面停止并确认原Clash恢复。

#120显示完整开屏广告，但底部Banner未出现；Google login四个连接均返回数据，汇总148886B，观察到首关方向均为client，不等同于四个错误。业务39请求/响应。额外核对固定target/login/unknown归属计数，排除查询失败拒绝的隐蔽路径；只在显式探针统计，不开放未知身份或写原始UID/IP。不再添加广告域名。

重连续做：确认同一PKG110/d265cb0a，21个原APK摘要cmp一致，系统HTTP代理null、原19387/46619映射保留。Clash显示已停止，connectivity无活动VPN，已完成上轮初始无VPN状态恢复。继续既有CONNECT诊断候选，仅查看是否上游接受/拒绝，不增加域名；测试结束恢复本轮相同基线。

### 11-13续查：先排除跨进程转发时序

#118单变量观察仍无Banner，未产生新的supply主机连接，不能据此证明新增端点有效。补充有界CONNECT接受/拒绝计数，仅在现有主机条目内累计，不保留HTTP头、错误文本、正文或凭据；接受不等于端到端TLS成功。真实loopback的200/403对照先RED（缺少计数字段），再GREEN。沿已有Google广告中断定位上游层，不继续新增主机。

11:36普通构建#117复测未显示Banner，空首包计数target/login均为0；不得把#116的单次成功归因于该修复。撤回默认启用，继续显式诊断探针。原APK只读反编译确认InMobi适配器11.4.0.0；Ads的首页Banner广告位末尾2327864214包含accountid/placementid。安装包的AdConfig明确supply.inmobicdn.net承载MRAID脚本和OMSDK资源，#117该精确主机target/capture两次TLS失败。下一次唯一扩充是此渲染主机，不放行unif-id身份、et-eus统计、i.l或整个inmobi/inmobicdn域；不能把其他SDK错误算成该Banner根因。新增精确主机/其他包/子域/身份统计保持采集回归先RED。手机APK不修改，测试副本只存私有目录。

11:26候选#116首次显示完整Banner，桌面业务get_app_config请求null/响应200完整JSON已核对。随后尝试默认启用同一依赖边界并增加固定target/login空首包等待计数；#117复测失败，已撤销默认启用，保留原ad_compatibility_probe显式开关。单次出现广告不证明空首包就是根因；新增范围为既有ad_routing聚合及对应测试，其他功能不改。

### 11-13 本轮收尾与待恢复事项

- #116共40组请求/响应且有Banner；#117冷启动再次无Banner，排除“已稳定修复”的结论。#118仅新增精确InMobi渲染资源主机后仍无Banner，且本轮没有该主机的新连接，无法给这一修订记成功。该原APK的适配器版本11.4.0.0与本地测试依赖不一致；不能从测试源码直接认定全部生产行为。
- #118保留36组请求/响应（30个200、4个204、2个101握手）。get_app_config为200，请求4B、响应405B，双向complete=true、truncated=false。其他中介、身份、统计、客服等仍有TLS失败，不能声称所有流量完整；业务代表接口未回归。
- 新CONNECT分层诊断不新增透传范围，真实loopback200/403 RED-GREEN通过；只累计现有64条主机项的接受/拒绝，不读正文/凭据，不把CONNECT成功说成端到端TLS成功。最终Android回归123项（122通过、1可选worker跳过）；显式开启worker验收另1项通过，日志/tmp/ad1-final-tests.log及/tmp/ad1-final-worker-test.log。构建ad1-connect-probe-20261113退出0，签名通过；git diff --check通过。
- Mac原HTTP代理127.0.0.1:7897对Google广告根路径返回301、InMobi mraid.js返回200，均CONNECT200/证书校验0；只证明电脑侧当前可达，不代表手机SDK的实际连接已正常。
- #116/#117/#118均桌面停止并确认原Clash恢复，未编辑节点/订阅/规则配置。最后一轮CONNECT实机诊断尚未启动时USB断开（adb devices为空），因此不能补齐实机CONNECT结果和最终APK复核。本轮初始无VPN，目前最后确认Clash已恢复；尚未撤销本轮临时启用以回到初始无VPN。待重连后完成，不虚报完整恢复。
- 候选桌面已退出并恢复本轮原版备份google-routing-auth-20261112；未发布。无本轮worker/logcat残留，历史PHK110恢复记录SHA-256仍为3a2bb229461addc57d3c15775ac9ccf5f40b94a56f53b326dbbce69259dacb27。原APK只读提取用于SDK端点核对，没有重装、改包、Root或清数据。USB断开前没有任何APK写入操作，最终21个摘要一致性仍待重连检查。
- 私有证据/tmp/capture-ad1-gms-20261113.lzL0nf包括三个状态、Banner/失败截图、有界日志、原APK只读副本、原/诊断桌面备份；不提交含标识符的原始证据。AD-1因USB不可用暂标BLOCKED，不进入AD-2，不盲目追加全部广告SDK或发布。

继续已有AD-1 DOING，文件范围沿用routing/worker/对应测试。旧#115日志显示Google广告请求在GMS进程报Software caused connection abort，目标进程随后Ad failed to load : 0；不能直接归因AppLovin等中介。先检验login角色在空首包时过早按IP CONNECT的时序缺口：完整ClientHello/SNI到达前不发起上游连接；分片仍等待，原TLS不解密、无直接回退、不新增透传域。隔离测试再做桌面实机单变量对照。若仍失败，依据新连接证据定位，不用主机清单盲试。当前同一PKG110已连接且解锁、无活动VPN，用户原节点/配置不变；测试后恢复该实际基线。

- 加入每任务最多64项的聚合诊断，只记录规范化SNI、owner角色、capture/opaque/reject路由和TLS失败计数；不存IP、URL参数、正文/账号、连接原始字节。溢出合并计数，不无界存储；活动连接映射沿用1024上限并断开释放。
- 先在现有解密路由下确认目标UID广告连接及失败主机。最初仅精确主机；11-13发现广告节点轮换后修订为四个广告服务域名边界及少量已观察精确依赖（详见下文），仅限定StickerHub的target角色。不得使用Google/共享CDN全域通配，不因一次错误动态放行所有主机。TLS透传意味着对应主机所有路径均不归档，并非按URL区分广告。
- 未通过真实Banner验收的策略默认关闭。仅worker私有配置显式布尔`ad_compatibility_probe=true`才能启用，构造器也默认关闭；普通API/桌面流程不提供或写入该标志。默认抓包路径维持原逻辑，诊断聚合不包含正文。不能将探针开关视为已交付兼容功能。
- 目标业务继续采集，未知身份拒绝。混合业务域名、缺失SNI、畸形/过大ClientHello、分片和并发上限均有回归；透传不生成HTTP flow，不做断点修改、不重放失败请求，不回落直连。
- 原始TLS保留客户端到源站验证，不降低TLS/证书检查。不修改已有Google服务转发和UDP规则；诊断不证明Google全部连接可用。
- 验收命令：physical-runtime python unittest目标routing/ads/worker及test_android_physical*.py；真实loopback原证书/零HTTP钩子；Swift回归（如修改文案）；build-app.sh与codesign严格验签；桌面真机抓包中冷启动观察Banner、归档业务完整Request/Response；停止恢复与APK/USB/代理比对；git diff --check。广告未出现或外部条件不满足不能标DONE。

### AD-1 中间证据与范围修订

诊断版#108确认googleads.g.doubleclick.net和pagead2.googlesyndication.com属于target且进入capture，每次握手失败；业务Supabase零TLS失败，32条响应中26条200、3条204、3条101。首次#107电脑外网预检失败，独立HTTPS204后重试成功，未修改代理。

第一版只透传上述两个入口：#109广告脚本已输出jsLoaded，但冷启动无Banner，目标Ads日志进一步明确rr1---sn-i3belnls.gvt1.com证书公钥拒绝；lh3.googleadsserving.cn也有target/capture失败。当前最小兼容范围增加这两个精确依赖地址。GVT节点不是全局广告专用，故这是明确的取舍：仅StickerHub到这个节点的所有TLS连接不归档，不能声称按URL区分广告。不会扩大*.gvt1.com、所有Google、动态失败放行或其他包；未知/混合业务主机默认仍采集。依赖节点迁移可能再次不兼容，后续需重新验证，不能将本轮结果推广所有网络与广告供应商。

RED已记录缺少diagnostics、package策略及新增依赖测试；真实loopback曾发现TLS层构造时提前设置client.tls，改为timestamp_tls_setup判断完成握手后23项路由测试通过。第一版116项Android回归115通过/1跳过；Banner未通过时仍DOING，不算已完成。

## AD-1 实机复验与未完成结论（2026-11-13）

### 本轮结果

| 抓包记录 | 候选范围 | 结果 |
| --- | --- | --- |
| #112 | 追加已观察渲染脚本/字体精确主机 | 出现空白广告位，没有素材；新增轮换广告主机TLS失败；停止前26请求/26响应 |
| #113 | 四个广告服务域名边界及子域 | 无Banner；发现www.gstatic.com仍在capture失败；停止前34请求/34响应 |
| #114 | 追加精确www.gstatic.com | 无Banner；发现static.googleadsserving.cn仍在capture失败；停止前35请求/35响应 |
| #115 | 追加精确static.googleadsserving.cn | 冷启动后观察约2分钟仍无Banner；40请求/40响应，最终本地TLS失败181次（不是181个主机，也不是181次Banner错误） |

#115的目标Supabase连接23条、TLS失败0，归档34条200/4条204/2条101；桌面Request/Response核对`get_app_config`：请求4B、响应405B，双方complete=true、truncated=false。101仅表示WebSocket握手，不证明消息内容完整。只证明已检查的业务请求完整，不声称所有第三方SDK或广告正文都采集成功。

剩余失败涉及AppLovin、Unity、Moloco、Pangle等广告中介服务，也混有客服、统计和Facebook业务；不能将这些错误一概归因于Banner或全部转为透传。Google广告脚本jsLoaded及opaque计数也不等于广告加载成功。当前最小修复候选不足，AD-1保持DOING。下一轮应先将Banner广告格式/加载错误与具体中介连接关联，重新审查可保留业务的最小原TLS边界；不继续仅凭TLS失败堆叠主机。

### 验证与保护现有行为

- 候选相关边界测试先RED后GREEN；最后新增“默认不启用未验收广告策略”测试先失败，再增加双层显式诊断开关。最终`macos-native/build/physical-runtime/bin/python3 -m unittest discover -s tests -p 'test_android_physical*.py'`：120项，119通过、1跳过。包含真实TLS证书相同、零HTTP正文钩子、上游失败无直连、未知角色失败关闭、域名边界和业务保留；未改Swift页面。
- 四轮实机候选均完成构建/严格验签；最终默认关闭版本`ad1-disabled-20261113`单独重建退出0，严格验签通过，日志`/tmp/capture-ad1-20261113-guard-build.log`。最终`git diff --check`通过。未验收候选不安装为日常使用版、不推送、不发包。
- 本轮从无活动VPN开始。原Clash对照时10:28出现Banner；#115停止后使用原Clash启动按钮恢复，桌面确认stopped，再冷启动StickerHub于10:57出现铃声广告Banner。未点击广告、清缓存/数据或更改应用；磁盘广告缓存未清，故截图与TLS证据共同支持路径差异，不独立证明每张素材均为网络新下载。
- 测试结束撤销本轮临时启用的Clash：VPN type=-1、HTTP proxy=null，恢复起始无VPN基线。原Clash规则模式/新配置未编辑；21个原APK摘要cmp一致；原ADB tcp19387->10156、tcp46619->10157保持，只有移动工具自己的localabstract映射；capture-owner映射已清理。自有logcat子进程已显式停止，旧PHK110待恢复记录SHA-256仍为`3a2bb229461addc57d3c15775ac9ccf5f40b94a56f53b326dbbce69259dacb27`。
- `/Applications/抓包工具.app`已恢复测试前`google-routing-auth-20261112`，严格验签通过且退出；不保留失败候选给用户误用。没有Root、改包、修改手机原节点/配置或电脑代理。
- 独立缺口仍存在：停止后原Clash未自动重连（本轮手动恢复后桌面确认）；网络摘要在业务已有响应时仍可能显示“没有新的HTTPS响应”。未将这两项混进本轮TLS修复，也不声称全流程自动恢复通过。
- 私有证据`/tmp/capture-ad1-20261113.pu6ZdZ`：各轮state聚合、有界Ads/Chromium日志、前后APK摘要、原/候选桌面备份、baseline/restored-banner/static-result截图；日志可能有广告标识，不提交。#115业务归档`web-physical-c26ed65d2d60470c9d5bffc197afe702`保留本机。最终回归日志`/tmp/capture-ad1-20261113-guard-tests.log`。

## AD-1 历史暂停交接（2026-11-12，已于11-13恢复）

### 2026-11-13恢复

#114审查：Google广告主体和s0.2mdn已透传，业务32条响应；仍无Banner。可直接核实遗漏static.googleadsserving.cn（target/capture/TLS失败），属于已确认广告素材服务且Google官方RTB域名清单列明；补该精确主机而非继续扩大服务分类。该修订仅纠正素材链具体遗漏，不采用更多中介SDK/整个静态CDN放行。未取得Banner前所有候选仍未完成验收。

#113继续暴露www.gstatic.com目标UID静态资源TLS失败，业务Supabase正常；加入该精确共享静态资源例外，明确其所有路径不归档。仍不使用*.gstatic.com，保留other.gstatic.com及子域伪装回归。此次为今日第三个有界候选，若Banner仍未通过，不继续用新增主机堆叠声称修复。

架构复核（#112）：新增渲染依赖后出现空白广告位，素材未完成；target新增googleads4.g.doubleclick.net、www.googleadservices.com、s0.2mdn.net均TLS失败。固定单主机无法覆盖轮换广告节点。因此限定策略修订为四个广告服务域名边界（doubleclick.net、googlesyndication.com、googleadservices.com、2mdn.net）及其子域，而非逐节点补丁；仍只针对StickerHub、可靠target归属、现有上游CONNECT。保留精确字体等例外，不扩到gvt1.com/gstatic.com/googleapis.com通配或第三方混合业务。域名边界、伪装后缀、其他包/未知身份、业务保留均回归。此规则使这些广告服务内容不归档，不能声称抓取全部广告正文。Google广告域名来源另见 https://developers.google.com/authorized-buyers/rtb/relnotes ，不是依此放行其整张Google域名表。

同一PKG110已连接，初始active VPN type=-1、http_proxy=null。继续现有DOING，不领取AD-2。修正昨日逐个入口思路：按广告渲染依赖链检验，而非把所有失败连接认作广告。#111已观测target的www.googletagservices.com、tpc.googlesyndication.com、fonts.googleapis.com、fonts.gstatic.com全部TLS失败；前两者为广告脚本/素材，后两者为共享字体资源，明确这些精确字体主机上的流量不归档，不能称全部目标流量均解密。不扩大*.gstatic.com、GVT通配、Facebook混合API、应用统计或所有中介SDK域名；其他包保持原逻辑。

验证：新增精确主机、后缀伪装/子域、其他包及业务保留用例先RED后GREEN；复用真实CONNECT证书/零HTTP钩子测试；桌面限定一次冷启动观察，再依据实际证据决定下一步，不连续盲试。证据来源：本地fix3-state及Google官方 https://support.google.com/admanager/answer/10358597 与 https://support.google.com/google-ads/answer/6335679 。抓包中Banner出现、业务正文完整、停止恢复同时满足才完成。

用户要求保存进度，明天继续。AD-1未通过Banner验收，保持DOING，仅表示未完成；当前暂停执行，不进入AD-2、不发布候选包。

- 三轮候选#109/#110/#111均未显示Banner。第二轮新增pagead2.googleadservices.com和fundingchoicesmessages.google.com的精确透传后，第三轮仍存在目标UID下googletagservices、tpc.googlesyndication、字体和动态GVT依赖的TLS失败。不能通过无限补地址或全域旁路宣称解决；下一轮先重新审查依赖分类和混合业务主机边界。
- 业务采集未失效：#111共33条响应（27条200、4条204、2条101），桌面已核对get_app_config的Request及完整JSON Response；complete=true、truncated=false。101仅表示握手，不能算完整WebSocket消息验收。透传连接的零本地TLS失败也不等于远端握手成功。
- 最终Android相关回归117项，116通过、1跳过；真实loopback验证源站证书保持、零HTTP正文钩子及上游失败不直连。桌面构建和严格签名通过。候选实现仍是未验收修复，不替代真实Banner证据。
- #111已通过桌面停止；原Clash经其启动按钮恢复并由桌面确认stopped，原节点/规则/配置未编辑。21个原APK摘要前后一致，系统HTTP代理null，原3条ADB映射保留，旧设备待恢复记录摘要不变。没有Root、改包、清数据或点击广告。
- 本机应用已恢复至测试前备份，严格签名验证通过；候选版保存在私有临时目录。最后只读检查显示原Clash仍活动；随后USB断开，无法撤销本轮临时启用以回到最初“无活动VPN”基线。保留该恢复差异，不声称完全恢复，也不远程改动其他设备。
- 已观察到独立问题：应用网络摘要曾显示零响应/失败，但实际归档已有完整200；停止后Clash仍需人工启动。留待独立修复，不混入本轮TLS结论。
- 私有证据目录：/tmp/capture-ad1-20261112.wr8rQm，包含fix1/fix2/fix3状态、截图、有界日志及原版/候选桌面备份；测试日志/tmp/capture-ad1-tests-final3.log。原始日志/截图/敏感归档不提交仓库。业务#111保存在本机现有归档web-physical-0191a9d0830a43b8a4d81f60978950b1。
- 恢复工作时先核对手机连接、实际VPN与用户当前状态，再读取本节和候选代码；不自动重放旧任务，不沿用临时连接凭据，不重复已有测试除非代码/环境有变化。

## AD-0 操作与验收

1. 只读确认序列号、StickerHub版本/包路径/摘要、VPN实际活动状态、系统HTTP代理、原ADB映射、桌面空闲状态。若有用户新启动任务先不打断。
2. 原 Clash 只使用既有启动按钮，记录已有模式/配置，不打开或导出节点凭据。StickerHub 已登录则保留；只观察首页/画册，不点广告，不清数据。记录有限时间窗口内广告相关错误、可见 Banner，避免把旧缓存误认新加载。
3. 通过桌面真机页面启动现有抓包，观察同页与有界目标日志，统计业务完整响应/连接错误，不读取认证正文；若系统确认需要用户则停在该步。
4. 桌面停止并核对恢复原 Clash；再撤销本轮临时启用，恢复开始时无VPN（若实际基线不同则以记录为准）。核对原APK、系统代理、已有ADB映射，旧设备待恢复记录不动。
5. 记录能与不能证明的结论、定位建议；无法完成时标 BLOCKED 并恢复已改变状态；`git diff --check`。基线完成不代表广告修复或AD-1至AD-4完成。

## 起始证据

- 2026-11-12：唯一 USB 真机 PKG110 / Android16，序列号末尾 cb0a。
- active vpn type=-1；系统 http_proxy=null；原ADB tcp19387->10156、tcp46619->10157、tcp63683->localabstract:mobilecli-server。
- 既有 Google 登录验收见 sticker-login-network-20261112.md；当前本机版本 google-routing-auth-20261112。不能以该历史验收替代本轮广告结果。

## AD-0 实际结果（2026-11-12 18:00 至 18:05）

### 实机 A-B-A

- A：只点原 Clash 的启动按钮，规则模式/新配置保持不变；StickerHub 正式版3.18.14(195)冷启动，保留已有登录态。18:00首页底部出现横幅广告，截图已保存；没有点击广告或启用系统弹出的游戏增强权限。
- B：从 /Applications/抓包工具.app 的 Android 真机入口启动 #106，桌面记录原VPN为Clash，系统实际由助手接管。未改产品、未重装证书、未修改APK。冷启动目标应用清除进程内已加载广告的影响，不清磁盘缓存或数据；18:01:37起观察约75秒，首页正常但底部没有Banner。切换瞬间曾展示旧广告，不算新加载成功。
- #106：29请求/29响应，均为业务Supabase主机（25条200、2条204、2条101；101仅握手）。get_app_config POST200请求4B/响应405B，complete=true、truncated=false。未读取或复制认证正文。
- B的120654字节有界目标UID日志：22条Certificate blocklisted by public key，49条WebView net_error -202，1条Unity初始化失败（请求超时）；广告日志同时有3次错误3和2次错误0，无法将其全部绑定到Banner。重启后的目标PID仍有googleads.g.doubleclick.net公钥拒绝；切换前后同一UID的events.ads.vungle.com也出现公钥拒绝，不能断言它单独导致Banner缺失。最终worker累计340次TLS失败不是340个不同域名，也不全部等于广告失败。
- A回切：桌面停止后进入recovery_required，原Clash未自动重连。通过原Clash启动按钮恢复，再点桌面检查网络恢复，状态stopped。冷启动StickerHub后18:04首页底部再次出现不同横幅；2650字节限定标签日志中未见公钥拒绝/WebView -202，不推导所有进程均无错误。

### 结论与限制

对照支持“抓包路径影响广告TLS兼容”，而不是“手机原VPN开启状态是不可替代条件”。现有代码对target角色保留解密、仅login角色原TLS CONNECT，广告SDK在目标UID下的连接可能进入解密分支；必须在AD-1用逐连接元数据/隔离对照确认，不能直接把所有广告域名加入旁路。

Google官方定义AdRequest错误3为NO_FILL（请求完成但无广告库存），不是网络错误2。因此原VPN时出现过错误3仍能显示其他Banner并不矛盾。来源：https://developers.google.com/admob/android/reference/com/google/android/gms/ads/AdRequest 。目前不知道日志中每条错误对应的广告格式；不把错误3当作Banner根因。

冷启动不删除磁盘广告缓存，A回切出现Banner不能单独证明所有素材刚从网络下载；与新进程日志和B的明确TLS失败共同作为定位证据。本轮未使用无损透传修复、未声称广告已修好；AD-1至AD-4尚未执行。停止后Clash自动重连缺口保留，不伪称自动恢复全通过。

### 恢复与证据保管

- 本轮起始没有活动VPN。确认Clash回切可用后，仅关闭本轮临时启动的Clash，最终active vpn type=-1、HTTP proxy=null、助手进程已退出。原节点/订阅/配置文件未编辑；Clash仍是原规则模式/新配置。
- 21个原APK摘要前后cmp一致；原3条ADB映射完全保留，无capture-owner映射；两个自有有界Logcat进程已停止。历史PHK110待恢复记录SHA-256仍为3a2bb229461addc57d3c15775ac9ccf5f40b94a56f53b326dbbce69259dacb27。
- 桌面保持停止状态，实验授权勾选恢复为未勾选。没有Root、改包、清数据、点击广告或修改电脑代理。
- 私有临时目录 /tmp/capture-ad0-20261112.H8OXft：三张对照截图、两个APK摘要列表及有界日志；不提交原始日志/截图/归档，日志可能含广告标识。最初两次历史Logcat抽取不完整，不作为无错误证据；后续使用有界实时流。完整业务结果保留在用户本地#106既有归档。
- 验收为上述实机对照、SQLite仅元数据核验、恢复检查和git diff --check；仅规划与证据变更，不跑无关构建，不发布新版。

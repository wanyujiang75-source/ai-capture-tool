# Android 真机广告兼容计划与 AD-0 验收

## 11-15 公开播放器诊断可用性

### 15:17 StickerHub 3.18.15 对照与恢复结果

- 用户改用StickerHub原版3.18.15(196)，包com.meta.inno.sticker、UID11071、21个APK。未重装已缺失的PokeHub，不使用旧UID或改包副本。只操作原应用首页/相册、返回和关闭广告/稍后提示，没有点击广告落地页或奖励/转盘。
- 原Clash暖进程开始没有Banner且贴纸有占位图；恢复Clash并冷启动后出现Banner。因此占位图或暂时无广告不能单独归因于抓包。公开media.player有界输出主要是编解码能力，media.metrics仅见目标UID音视频编解码计数，没有URL、连接错误或本次广告标识，不构成视频播放/TLS关联证明。
- 稳定桌面#130先通过准入，后因Google HTTPS出网检查失败自动停止。恢复原Clash后，用同一curl参数检查电脑现有127.0.0.1:7897代理三次均为CONNECT200/HTTP204，耗时0.150/0.113/0.104秒。未明确短暂失败根因，不修改上游、VPN或健康检查阈值。该失败保留，不能报告所有轮次成功。
- 稳定#131先见静态插屏（可能缓存，不是视频证明），冷启动后没有Banner；最终32归档：24个200、3个204、4个304、1个101。22组业务RPC的请求和响应complete=true、truncated=false、实际长度匹配；42个非空JSON、18个gzip有界解压解析通过，2个零长度正文按约定无文件。101仅升级握手，不宣称WebSocket帧完整。冷启动固定日志有8次TLSHandshake和21次WebView -202，不能把所有SDK失败都当广告根因。
- 使用已存在、严格验签的私有poke-final-probe.app，仅开启已有诊断开关；当前包实际选择StickerHub自己的既有策略，未套用PokeHub域名表。路由模块与源码核对一致/等价，没有新增主机、生产修改或构建。#132冷启动目标进程后Banner实际显示并轮换两份创意，进入相册再返回未观察到视频。截图仅本地保存于/tmp/capture-ad1-gms-20261113.lzL0nf/sticker-196-probe-banner-20261115.png。
- #132最终62归档：53个200、6个204、3个101；47组业务RPC双向正文完整性检查全部通过，90个非空JSON、39个gzip、4个约定零长度无文件。检查以落盘字节数、complete/truncated及1MiB有界解压解析为准，不输出用户正文/请求头。连接统计仍有TLS失败532次、未知身份0、诊断overflow0，Banner可见不等于全部广告依赖已修复。
- 官方广告调试短时打开并于测试后关闭。脚本qa_ad_network_trace.py在目标UID11071/PID11639采集120秒，338条身份匹配输入、69事件（30请求/33响应/6正文可用性），scope_mismatch丢弃1、invalid_json丢弃3、0未闭合；正文3个digest_only/3个inline，仅记可用性，不解码或保留正文。窗口覆盖一次相册动作，没有视频resource提示或素材错误关联。rr4---sn-i3b7kn6k.gvt1.com一次TLS失败只是候选，Banner后来仍成功，未加入透传。不得把时间重叠升级为视频素材根因。
- #131归档目录web-physical-efa2f98831114089a0e97ed54b11ca75，#132为web-physical-bfdbd6eff8fc4dd1b86e59f24c1176c1，均在本机runtime-native/captures；诊断JSON位于同一私有tmp目录的sticker-196-probe-20261115.json。原始广告/账户信息不写入仓库。
- 已通过桌面停止#132，手机原Clash显示运行中/规则模式/新配置已激活，桌面点击检查后明确显示原网络连接已恢复。广告调试开关关闭、log.tag.Ads为空、Android http_proxy=null；连接目录和当前recovery.json已清理，旧PHK110待恢复提醒保留。私有探针退出，/Applications/抓包工具.app稳定版已重新打开，没有替换包。Mac HTTP/HTTPS仍为127.0.0.1:7897，原节点/订阅/配置未编辑。
- 收尾21个APK联合SHA256为a7809813798530f42def1bc439171ab08a2f6e5ff02f303aed39bb33833645c4，与开场一致；旧恢复提醒SHA256仍为3a2bb229461addc57d3c15775ac9ccf5f40b94a56f53b326dbbce69259dacb27。自有mobilecli转发60461移除，原19387/46619保留。仅更新规划证据，未重复声称运行上轮14项诊断/130通过回归；本轮验收为实际归档、UI恢复及git diff --check。
- 结论：新版Banner有单轮正向证据，业务完整性通过；视频播放与具体素材/TLS关联仍BLOCKED。没有足够证据收敛到必要且可复现的最小生产策略，因此保持探针默认关闭，不发布“已修复”，不继续扩域猜测。后续需明确视频展示触发和可关联的素材失败证据，而非重复同条件采样。

14:38再次核对前台：Clash已运行、规则模式/新配置已激活，助手未执行启动或切换动作，属于外部状态变化。本次正式对照以此最新运行状态为恢复基线，覆盖此前起始停止状态，不在收尾关闭用户已启用的VPN。

用户确认PokeHub已卸载并指定继续StickerHub：当前包com.meta.inno.sticker为3.18.15(196)，不同于此前3.18.14，不沿用旧版本成功/失败结论。恢复同一AD-1；使用原Clash建立广告基线，先检查公开播放器证据，再桌面对照当前应用及业务双向正文。仅原有已授权只读页面/广告关闭，不点广告落地内容；不改包、不退出账号、不清数据、不扩大透传。Clash初始已停止，正式测试前以14:38新观察到的运行状态为恢复基线，原配置/节点不动。若新版本出现信任差异，单独记录，不自动换证书或降级。

本轮设备前置检查阻塞：ADB确认d265cb0a/PKG110，当前用户0；`dumpsys package com.mi.poketrade`明确Unable to find package，`pm path`退出1，`pm list packages -u -U`与用户999查询均无目标。没有启动原版进程，不能沿用旧UID11077作为当前身份。Clash首页显示已停止/新配置已激活，http_proxy=null；本轮没有切换VPN、编辑配置、开启广告调试、安装或删除应用。仅启动Clash查看状态。`media.metrics --help`确认有--since时间过滤；有限只读媒体诊断无旧目标UID或URL，不展示其他应用记录，不能用作PokeHub失败证据。待确认重新安装上轮原版或核对新包身份后继续，禁止误用试验副本；视频验收未通过。

继续AD-1，先核对media.player等公开诊断是否提供原版目标UID/PID的播放器状态、错误码及素材主机；不读取私有目录或强开调试。输出按目标身份限定，不保存其他应用媒体内容、完整URL、参数或凭据。没有目标身份则只记录入口是否可用，不展示记录正文。验收为记录已确认的观测能力/缺失字段，再决定是否存在信息增益足够的单次卡片对照；没有强关联不改透传。若修改独立诊断脚本则先补边界测试，生产抓包保持不变。本轮不发布、不改包或VPN原配置。

## 11-13 广告尝试关联诊断

### 18:55 原包日志出口及第129轮结果

- 从已校验PokeHub原APK的classes5.dex只读追踪：`uj0.onError`拼接`Video Load Error URL:`，`c70.onReceivedSslError`拼接主错误码与URL；二者均经`bm.b -> a60.a -> y50`进入SDK内部JSON缓冲。`a60.a(String)`经`es.a`写文件，`cs.a(Context, long)`定位到`context.getFilesDir()/logging`，并非Logcat。`ud0`为空类。仅存在这些字串不能证明正式包会在ADB日志中输出；未读取应用私有目录、强开SDK门控或注入。c70整体反编译有1处错误，SSL回调为已生成部分，不把未恢复方法当证据；y50使用工具附带的指令级输出核对。早先目录中的InMobiMediationAdapter.java未与当前包建立来源对应，本轮不据它判断版本或行为。
- classes4.dex的`com.chartboost.sdk.impl.bl.a(PlaybackException)`中“Codec error during video playback: url=”仅在4001至4005分支记录，其余分支返回AssetUnavailable。因此不能将该固定字符串未出现解释为无TLS/素材错误。原包启动后、首页及卡片动作后多次未见webview_devtools_remote套接字；只说明这些观察时点没有可用入口，不强行开启调试。
- 诊断采集盲区：实际PID11985的ps为UID11077，UID过滤0字节，而PID过滤返回3424字节；随后15秒同窗对照UID0字节，PID2964字节/22行，其中21行有数字UID11077。只报告实测差异，不推断Android系统具体实现原因。过去零匹配不能据此排除错误。独立脚本增加显式PID备用模式，启动ps和逐行UID/PID双重校验，未自动扩大范围。2项新测试（5个断言失败/子例）先RED，最终14项GREEN（4.211秒）；生产worker不引用该脚本。
- 原Clash短时对照保持网络不变。PID模式60秒取得8条GMA事件（4请求/4响应），24条已校验行，1个scope_mismatch为非目标格式行被拒绝；同时固定事件计数器读到264条身份合格日志。只读卡片操作后观察到有进度/倒计时的视频。域名仅Google入口及Vungle事件上报，不含视频素材路径，不能把上报域名当视频源或据此扩大透传。
- 桌面既有六主机私有探针启动#129，原包冷启动PID687，未更改探针清单。120秒采集覆盖第一次卡片动作（手机1794566952秒）：37条事件，14请求/17响应/6正文可用性事件，244条已校验行，4丢弃（scope_mismatch1、restarted_block1、invalid_json2），无视频路径提示。独立同PID有界计数器2671行，30次SSLHandshakeException、81次WebView -202、3次loaded；没有含素材主机的播放器错误，不能将loaded直接视为插屏加载或播放完成。
- 为排除点击过早，在上述loaded事件之后又进行一次只读卡片操作，60秒窗口13事件（5请求/6响应/2正文事件），72条已校验行，2丢弃（scope_mismatch1、invalid_json1）。观察到全屏静态广告画面，随后回到卡片详情；没有取得连续视频帧、播放器播放状态或具体视频素材URL，不将其计为视频成功。没有点击“Visit & Close”或广告落地内容。该次尝试仍未建立具体素材与TLS连接的强关联，故不修订生产透传策略、不关闭TLS验证。
- #129最终stopped，67条归档（48x200、5x204、2x101、12x304），42组RPC双向complete=true且无截断。独立核验79个正文文件长度，37份gzip有界解压、非空JSON均可解析，5份零长度正文按约定无文件。101仅握手，不宣称WebSocket帧完整。Android回归131项130通过/1可选跳过（10.539秒），git diff --check通过；普通生产代码没有更改，不需要重建或发布。
- 通过桌面停止，启动原Clash后已确认运行中/规则模式/新配置，parse_vpn为com.github.metacubex.clash.meta；首次恢复操作短暂进入配置列表但未选择、编辑或删除配置，随后在首页正确启动。桌面检查确认原网络恢复，广告调试开关恢复关闭，http_proxy=null、log.tag.Ads为空。当前recovery.json不存在，旧PHK110提醒摘要仍3a2bb229…b27，原APK摘要仍255614ea…3e39。退出私有探针、重新打开/Applications稳定版；移除本工具mobilecli64535映射，原19387/46619保留。未推送或更新安装包。
- 独立诊断盲区修复完成，AD-1视频修复仍BLOCKED：原包现成GMA/ADB出口未暴露可关联的视频素材，SDK内部日志不属于可访问的系统日志。没有因果证据前不新增透传，也不将本次静态展示作为完成。后续必须先取得同一播放尝试的可验证素材/连接关联；不得继续重复同条件主机试错。

### 原包中介播放器诊断续做

本轮补充独立采集器PID模式（仍在既有脚本/单测范围）：PKG110实测同一进程11985、UID11077，UID日志过滤返回0字节，PID过滤返回带11077身份的记录。显式`--pid`仅在启动时`ps`核对UID/PID成功后启用，每条日志再核对数字UID/PID，错误身份不进入解析器；默认UID模式保持兼容，不自动扩大为全设备日志。验收为错误身份拒绝、跨UID分片丢弃、无敏感原文、进程结束和原12项回归RED-GREEN，以及手机短时只读对照。该修复只纠正诊断盲区，不等于广告修复；原VPN及生产路由不变。

停止同条件GMA重采，转为只读核对已校验原APK中的播放器错误日志：具体类/调用者、日志级别及门控、是否含素材主机、能否在既有生产构建输出。APK解包/反编译仅在私有临时目录，不改已安装包或应用数据。仅保留固定错误类型与脱敏主机，不输出广告正文/完整URL/设备或用户标识。先确认入口再决定是否做目标UID短时复现；没有可用入口不强开SDK私有标志或注入。主机时间重叠不升级为因果；只有现成同请求错误或等价证据才能提出最小修复，不增猜测透传。
### 18:20 暂停后续验与第128轮证据收尾

- 诊断字段补充先取得3项RED，再12项GREEN；恢复后同一代码重跑 `macos-native/build/physical-runtime/bin/python3 -m unittest discover -s tests -p 'test_ad_network_trace.py'`，12项通过（1.522秒）。既有Android回归131项130通过/1可选跳过，生产源码与该次回归一致；本轮不新增生产路由或透传主机。
- #128既有六主机探针的150秒目标UID窗口覆盖卡片点击。记录时间范围1794562398519至1794562539750，卡片动作前手机时间1794562444秒；点击后有25请求、12响应、4正文可用性事件。总计127记录：73请求、44响应、10正文事件；39个同network请求/响应配对。5个invalid_json、0未闭合，输入676082字节；不能将丢失记录解释为不存在请求，也未保存畸形原文。
- 公共gma_js_loader同network:9d794bde33eb3714在1794562400165发请求、1794562400862收到200，相差697ms。没有video_file_hint/video_manifest_hint；这只表示当前SDK入口没有输出匹配的路径，不能证明所有中介没有视频请求。正文事件6条digest_only、4条inline，均未保存/解码正文。另一100秒固定状态采集输出0匹配，不能用它排除播放错误。
- 卡片操作后观察到PokeHub卡片详情页，未观察到视频播放；未点击广告素材或落地页面。不能用上轮静态插屏或本轮脚本200当视频成功。此前诊断的失败主机仅为候选，没有新的逐请求素材/TLS因果证据，不扩大范围。
- #128为stopped，51条归档，其中42条业务RPC请求与响应均complete=true、truncated=false。独立读取42组落盘文件，全部长度匹配；38个gzip正文有界解压、所有非空正文JSON解析通过，4个零长度正文按约定无文件。101记录仅是升级握手，不宣称后续帧已完整采集。
- 暂停时已停止并启动原Clash；恢复后实际发现Clash停止、广告调试开关已关闭。没有据此推断用户做过何种操作；重新启动既有Clash，确认规则模式/新配置、系统parse_vpn为com.github.metacubex.clash.meta，桌面检查显示原网络已恢复。未改原节点或配置；广告调试既已关闭，不再触碰。log.tag.Ads为空、http_proxy=null、recovery.json不存在；原APK和旧PHK110恢复提醒SHA256与17:18一致。连接目录随停止清理，首次读取旧state.json不存在，改以只读归档和恢复检查核验，不重建或修改运行状态。
- 补查系统media.metrics仅有界读取，不落盘；当前匹配规则未找到目标UID11077行，不能将其解释为没有播放器或TLS错误。没有获取其他应用的正文、URL或媒体信息。此入口暂不能补齐所需素材关联。
- 私有探针正常退出，旧PHK110提醒保留；/Applications/抓包工具.app稳定版已重新打开，未替换安装包。临时mobilecli转发收尾移除，原19387/46619转发保留。未推送或发布。
- 诊断增强已通过；AD-1视频修复仍BLOCKED：当前可用GMA事件和系统播放器摘要不足以把某个具体视频素材绑定到失败连接。下一步须先找到原包现成的播放器/中介错误与连接关联出口，或取得可重复且明确的视频素材失败证据；不重复同条件采集、不把时间相邻作强关联、不放行全部广告域名。没有此证据前不实施新的TLS策略，也不宣称已满足视频验收。

### 视频素材关联续做契约

继续同一AD-1 DOING，仅修改scripts/qa_ad_network_trace.py、tests/test_ad_network_trace.py及规划证据。原包zzl.zzf明确bodylength<10000才输出base64正文，否则bodydigest；上一轮63KB至88KB正文无法从该日志恢复素材URL，不尝试绕过门控或解码摘要。Google官方network-tracing说明同样将正文与摘要分开；InMobi官方CreativeID获取方式依赖应用回调，不在本轮改包约束下强行注入。

新增诊断字段仅为固定枚举：请求路径以.mp4/.webm结束标video_file_hint，以.m3u8/.mpd结束标video_manifest_hint；仅合法HTTP(S)、无userinfo、正常端口的URI，不因查询参数出现.mp4误判。扩展名不是内容格式或视频成功证明。响应正文仅报告inline/digest_only/absent，仍不保留或解码正文与摘要。固定丢弃原因计数区分block_limit/buffer_limit/invalid_json/unsupported_event/record_limit及输入行截断；总量上限不变。单测覆盖秘密字段、假后缀、格式错误、容量及子进程收尾，先RED再GREEN。

真机仅复用既有六主机私有探针，采集必须覆盖一次只读卡片动作；先记录手机时钟与窗口，点击后再结束。禁止广告创意/评分/落地页点击。结果分为请求类型线索、TLS主机重叠、实际视频三个层级，不能由前两者自动新增透传或宣告第三者成功。结束恢复原Clash、调试开关、稳定桌面及自有转发；保留原包和原配置。若SDK未输出视频请求则如实记为观察入口不足，不继续重复同条件采集。

参考：https://developers.google.com/admob/android/network-tracing ；https://support.inmobi.com/monetize/sdk-documentation/android-guidelines/android-testing-and-troubleshooting 。

### 17:18 同范围对照结果：脚本已响应，视频未通过

- USB恢复后仅运行已验签的既有六主机私有探针，桌面启动#127，再冷启动原版PokeHub；没有新增主机、改SDK开关或修改生产路由。广告调试短时开启，log.tag.Ads保持原空值。
- 180秒GMA采集77条：31请求、36响应、10正文长度事件、5条丢弃、0未闭合。精确gma_js_loader的匿名network:4ec6db42640f502a请求与HTTP200响应配对，时间戳1794561097212/1794561097464，相差252ms。区别于#126同资源只有请求；这是脚本网络响应恢复，不等于视频已播放。记录有丢弃且响应多于请求，不能声称完整广告网络追踪。
- 固定类型UID日志出现jsLoaded和AdsLoadState.loaded，同时有大量WebView net_error -202；采集达到100条上限，后续卡片操作不在该180秒日志窗口内，不能用其loaded事件绑定后来的展示。点击首卡后实际进入com.inmobi.ads.rendering.InMobiAdActivity；页面显示静态插屏图片和破损资源图标，没有观察到视频播放。只关闭广告反馈面板和返回，没有提交评分或点击落地内容。截图poke-existing-probe-interstitial.png仅为静态展示证据。
- 同轮连接诊断中supply.inmobicdn.net、i.l.inmobicdn.net、videoassets41.blob.core.windows.net等仍为target/capture/TLS失败；这些是待关联线索，不足以认定某一连接就是本次视频素材，也不据此新增透传。未知归属计数1仍按原逻辑拒绝，未扩大采集。
- #127共46条归档，39条/rest/v1/rpc/全部request_complete/response_complete=true，且双方truncated=false。广告原TLS连接不归档正文，不能宣称全部请求都已解密。一次误将state.json定位到归档目录的只读检查失败，随后按实际connection-8__tipd0目录核对，不影响任务或归档。
- 收尾独立核验39组RPC落盘正文：首次直接JSON解码遇到gzip失败，按gzip解压后又发现零长度正文不生成文件；依现有归档约定处理后，39组双向实际长度全部匹配，35个gzip正文有界解压，所有非空正文JSON解析通过，4个缺文件项元数据长度均为0。只读验证修正，不改归档数据，也不把初次脚本假设错误隐去。
- 桌面停止后原Clash仍需通过其启动按钮恢复；规则模式/新配置保持不变，桌面检查确认原网络已恢复，#127为stopped。系统http_proxy=null、Ads日志级别为空、Google广告调试开关已关闭。APK及历史PHK110待恢复记录SHA256均与前轮一致，当前recovery.json不存在。原19387/46619映射保留，移动工具临时56742映射随后清理；两个有界采集进程均正常退出。
- 已退出私有探针并重新打开/Applications/抓包工具.app，未替换稳定包。只有规划/证据更新，没有新生产代码、构建或发布。诊断9项及Android130通过/1跳过沿用未变代码的上一轮结果，不虚报新跑。
- AD-1继续DOING，仍未完成视频标准。下一步应先补具体展示尝试与素材TLS失败的强关联，区分静态广告投放、素材加载失败和视频播放失败；不得以静态插屏或HTTP200冒充视频成功，也不继续固定主机扩充试错。后续采集窗口须覆盖单次卡片动作，并明确计数截断，避免把启动期日志当成点击后证据。

### 16:35 同范围诊断对照

用户确认重新连接后已核对PKG110/d265cb0a transport16，USB阻塞解除，恢复同一AD-1 DOING。先复查实际网络/转发基线；本次仍只比较已存在六主机探针，不扩大域名或修改正式包。

16:40准备检查：原包zzblu.a的gads:log:verbose_enabled默认false，与zze.zzc的双门控一致；因此上轮设置log.tag.Ads VERBOSE但没有内部引擎失败栈，不能据此排除引擎错误，也不尝试改私有SDK标志。既有poke-final-probe.app严格签名验证通过，ad_routing摘要与当前源码一致；routing差异仅等价格式/条件写法，worker仅把既有探针设为true，无新主机。

新对照尚未启动：ADB连续三次无设备，最新抓包#126/#125均stopped。未运行私有App、未切VPN、未重新开启手机广告调试，已请求重连。AD-1实机环节因USB缺席BLOCKED；设备恢复后继续这一个同范围对照，不重复默认路径失败或扩大清单。

沿AD-1 DOING，不再加域。重新使用既有六主机私有探针，与#126默认路径比较公共加载脚本的同一network_request请求/响应配对及后续失败阶段；不是第四次扩域修复。先验证探针与仓库对应文件/严格签名，确认无活动抓包后仅临时运行该私有App，结束重开原/Applications稳定版。短时广告调试、目标UID采集及停止恢复边界不变。原包SDK zze.zzc还受内部zzblu开关控制，设置Ads VERBOSE并不能保证内部失败栈可见，禁止修改原包或私有SDK标志来强行取栈。通过标准为真实脚本请求/响应配对和视频加载结果分开记录，不把HTTP成功当广告成功。

### 原包SDK契约核对与诊断修订

16:32复验结果：新增2项测试先失败（错误事件被丢弃、缺少固定资源分类），修复后共9项通过；现有Android回归131项130通过/1可选跳过，diff检查通过。SDK实际错误事件已补收，原错误正文仍不落盘；没有修改生产worker或透传范围。

用户解锁后短时开启广告调试与Ads VERBOSE，通过稳定桌面开启#126。120秒目标UID采集6条onNetworkRequest，0响应/错误事件，0丢弃、0未闭合；其中2条精确公共gma_js_loader请求，分别在冷启动和卡片操作后出现。固定日志类型观察到16:28:10.985 interstitial，16:28:19.544错误0；点击首卡后16:29:22.197 interstitial、16:29:23.403公共加载脚本请求、16:29:30.760错误0，期间WebView -202。没有出现视频，也未取得插屏ID/中介响应信息；这是重复的初始化资源阻塞线索，不是唯一中介根因证明，不再重复以ad_request为采集目标。

本次47条归档，其中40条业务RPC全部双向complete=true且无截断；3条get_app_config均200，请求80B、响应2621B。桌面停止后原Clash规则模式/新配置恢复，桌面检查确认原网络已恢复；广告调试Switch无checked，log.tag.Ads空，http_proxy=null，原ADB映射及既有mobilecli映射保留。活动recovery.json不存在，历史PHK110提醒摘要及原版APK摘要均未变。两个采集进程已退出。未改原节点、配置、APK或广告ID，未发布。

AD-1仍DOING。已排除诊断解析遗漏解释本轮全部无响应；仍缺SDK加载失败到具体视频适配器的强关联。后续应从连接级TLS失败证据及SDK调用链建立因果对照，不能把固定主机扩充、时间相邻或HTTP CONNECT接受当作广告修复成功。

只读原版2.2.0(99)的classes5.dex中com.google.android.gms.ads.internal.util.client.zzl：构造器只产生network_request UUID，没有ad_request。错误事件实际为onNetworkRequestError，params.error_description仅在非2xx响应分支输出；因此修正事件名只能补齐HTTP错误关联，不能宣称捕获所有TLS异常。原异常文本继续丢弃。SDK静态加载地址由classes6.dex的zzbmc声明，与上轮运行时观察一致。

独立采集脚本增加固定resource=gma_js_loader，仅精确https、googleads.g.doubleclick.net、默认443及/mads/static/mad/sdk/native/sdk-core-v40-loader.html匹配时输出；不保存其他路径或任何查询参数，不改变采集或透传路由。先验证真实事件与匿名network ID关联、秘密字段不泄露、近似域名/路径不匹配。仍不能用网络ID代替插屏ID，避免重复索取本SDK根本不输出的关联字段。

### 16:09 对照结果：定位缩小，仍未修复

- 手机原开关关闭；用户明确同意短时开启。PokeHub UID11077，正式版APK不变。新脚本独立运行，不导入worker，不改路由策略/透传主机；生产桌面仍原稳定包。
- 原Clash下冷启动后点击首张卡片，真实视频播放（poke-gma-baseline-video.png）；120秒日志解析64条：26请求、30响应、8正文长度事件、2条丢弃、0未闭合。会话内匿名network_request可以配对，但没有ad_request ID；不能宣称已取得视频位/中介对应关系。响应比请求多，存在缺口，不能将此次日志当完整网络归档。
- 桌面原默认抓包#125建立后冷启动：120秒得到5条googleads.g.doubleclick.net GET事件，0响应，0丢弃/未闭合；只有network_request标识。静态SDK资源单独只读核查发现/mads/static/mad/sdk/native/sdk-core-v40-loader.html请求；未保存原始URL参数/headers/body。该公共JavaScript加载资源是具体阻塞线索，尚不等于某个视频广告的唯一根因。
- 为提取SDK失败栈，将log.tag.Ads从空临时设VERBOSE；75秒目标UID过滤输出16条固定类型事件。16:03:16.761出现interstitial加载，前后WebView net_error=-202；16:03:25.135-.147三次错误0，25.152为loadFailed。没有得到nonagon适配器堆栈，时间邻近不作强关联。参考工程admob_ad失败回调丢弃LoadAdError信息，但其与生产版本对应未证实，不修改源工程或原包。
- #125最终84条归档，74条/rest/v1/rpc/均请求/响应complete=true且无截断。桌面停止并检查恢复成功；原Clash已连接、HTTP proxy=null、自有recovery.json不存在，原19387/46619 ADB映射及mobilecli映射保留。APK与历史PHK110恢复记录SHA256均与15:31一致。Google广告调试开关已关闭，log.tag.Ads恢复空值；两个120秒采集及75秒过滤进程均结束。未清系统日志（避免删除他人诊断资料），未修改原VPN节点/配置，未发布。
- 新脚本7项测试通过，含Unicode字节上限RED-GREEN、秘密字段过滤、线程分片、格式错误、容量、UID限定、0600私有输出与超时终止；原Android回归131项130通过/1可选跳过。私有脱敏JSON保存在既有临时目录poke-gma-{baseline,capture}.json。AD-1保持DOING，不标广告修复完成；下一步需获取可靠的插屏尝试/SDK资源关联，或设计无需扩域的连接分类诊断，不能把这次公共资源失败直接扩展为新主机策略。

暂停固定主机试错，沿同一AD-1。官方入口：https://developers.google.com/admob/android/network-tracing 。手机Google服务/广告中“启用广告调试日志记录功能”当前关闭。仅临时开启，按PokeHub UID和短时间窗口采集；恢复原关闭状态。不重置广告ID，不改变任何VPN节点/配置、应用/账号数据。

新增独立诊断脚本与单元测试（scripts/qa_ad_network_trace.py、tests/test_ad_network_trace.py），不导入生产worker。解析GMA BEGIN/CONTENT/FINISH，按线程隔离分片；每块最多256KiB、最多8个并发缓冲、512条记录、输入最多32MiB、最长180秒。只输出会话内匿名关联编号、时间、事件、主机、方法、状态码及长度；忽略原始headers/body/URL参数、异常文本、广告/用户标识。默认拒绝无法解析或超限记录，明确丢弃计数；不得使用时间邻近伪称同一请求关联。UID过滤由logcat负责，退出必须终止自身子进程。

验收：synthetic secret/分片并发/超限/畸形/缺边界测试RED-GREEN，真实目标日志是否提供关联记录分开报告；短时原VPN与抓包对照，仅点击只读卡片、不点击广告落地内容，全部临时状态恢复。若只得到网络关联、未得到插屏格式或适配器，明确保留该缺口，不加域名也不声称根因。普通业务完整正文仍以桌面归档为证。

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

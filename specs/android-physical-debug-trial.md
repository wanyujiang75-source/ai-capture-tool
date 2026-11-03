# 一加真机PokeHub免Root试验

## 范围

2026-11-03用户授权查询Jenkins是否存在PokeHub Debug包，存在时安装到已连接一加并尝试抓取接口。复用当前工作树，仅处理ANDROID-D1；iOS自动导入与桌面产品改造不在本轮范围。

## 不可变边界

- 仅操作当前已授权的一加PHK110，不选择其他设备。
- 不Root、不解锁bootloader、不调用adb root、不修改VPN、全局代理、系统信任或证书。
- Jenkins仅GET任务、构建及产物，不触发构建或修改配置。
- 不卸载、清除数据、降级或自动重签APK。共享测试包名必须先核对现有应用身份；不替换其他项目。
- 不读取或发布第三方VPN账号、节点、订阅或凭据。只验证网络状态，不更改路由。
- APK和原始抓包信息仅留本机临时目录，仓库只记录必要元数据，不提交敏感请求正文。

## Release安装追加授权

用户在得知没有Debug产物后，明确要求安装已下载的#588 Release并试验。该要求替代原先“无Debug不安装”的条件，先前Jenkins检查结果保留为历史。安装目标为`com.test.tcgp`，不是Google Play的`com.mi.poketrade`或通用`com.niubi.testapp`。安装前检查同包名是否已有应用；若存在，核验版本与签名，不自动卸载或降级。

安装后检查现有可用调试服务及有界目标进程日志，操作已观察到的只读页面以触发业务请求。不修改VPN、系统代理/证书，不启用会替代现有VPN的抓包应用，不调用root、不注入Gadget或重签APK。只看到日志/请求URL/埋点不能算HTTP请求与响应采集成功。需要登录或系统安全确认时交由用户操作。安装成功和抓取成功分别验收，能力受限时记录BLOCKED及已完成的安装部分。

## 流程和判定

1. 查询PokeHub相关任务和已有构建，检查产物名称、构建参数及必要的过滤日志。名称中的test/debug不是可调试证据。
2. 下载候选APK，用SDK工具读取包名、版本、application debuggable及签名，结合Flutter产物判断是否存在可连接调试服务；无合适包则记录检查范围与缺口。
3. 安装前核对既有同包名应用和签名，版本不降级、身份不冲突时才能保留数据安装；任何冲突都不自动卸载。
4. 若为可调试Flutter包，启动后通过USB的独立loopback端口连接其VM服务，验证HTTP网络分析能力。此路线不改变应用的网络出口，不等同于抓取所有原生插件流量。
5. 触发实际PokeHub请求，只有取得目标请求与响应证据才记录成功。需要登录时由用户操作，不索取密码。
6. 完成后移除本轮创建的USB转发，不关闭原VPN、不清除系统日志、不删除原应用。留存安装版本与结果。

## 验收

- Jenkins返回结果、产物实际可用性、下载摘要和APK检查结果。
- Debug路径存在时：安装成功、目标包运行、USB调试服务连接、至少一条真实请求和响应、转发清理。
- 不具备前提时：明确BLOCKED的具体原因和所需产物，不以其他项目或Release包代替。
- 文档差异检查通过；无产品代码变化不运行无关构建或把既有测试当作实机验收。

## 当前证据

- 一加PHK110，Android16/API36，arm64-v8a，USB已授权、系统已启动。
- 当前ADB为shell权限，bootloader报告locked、verified boot为green，PATH未找到su；仅据此按未Root处理。
- 已安装`com.mi.poketrade` 2.1.0(96)，来源Google Play，未开启DEBUGGABLE。
- 已安装共享测试包名`com.niubi.testapp` 1.3.0(1)，未开启DEBUGGABLE；尚未确认应用身份，不允许直接覆盖。
- Logcat缓冲区信息可读取；这不是HTTPS接口抓取通过证明。

## Jenkins与APK实测结果（2026-11-03）

检查范围为当前可见Jenkins任务及PokeHub保留构建，不包含已删除构建或不可见任务。根索引包含39个任务，无嵌套任务文件夹；与PokeHub名称匹配的是应用构建`PokeHub`和接口测试任务`pokehub-api-test`，未发现独立的PokeHub Debug任务。API中返回的任务URL使用另一地址，本轮沿用已验证可访问的原Jenkins基址，不跟随该旧地址。

`PokeHub`的`allBuilds`与最近构建列表一致，仅保留#583至#588共6个SUCCESS构建，每个只有一个`PokeHub_<编号>.apk`。逐个读取构建日志并只输出构建模式标记，6个均出现`flutter build apk`、`--release`、`assembleRelease`和`app-release.apk`。最新#588参数明确为`BUILD_ANDROID=true`、`BUILD_MODE=release`。任务存在`BUILD_MODE`与`FLUTTER_BUILD_APK_ARGS`参数，但未触发新构建，也不能认定debug参数分支已经验证。

仅下载最新#588并检查实物，其余5个构建以已有产物列表与日志为证，不声称已逐个下载核验：

| 项目 | 结果 |
| --- | --- |
| Jenkins产物 | `build_588/PokeHub_588.apk` |
| 文件大小 | 209557795字节 |
| SHA-256 | `23b602f915ff93b31b6152686498933b085e12a0a0b50526a5a4186b37c6355b` |
| 应用名称与包名 | PokeHub；`com.test.tcgp` |
| 版本 | 1.0.0，versionCode=1 |
| Android支持 | minSdk=24，targetSdk=36，包含arm64-v8a |
| `apkanalyzer manifest debuggable` | false，退出0 |
| `aapt dump badging` | 未出现application-debuggable标记 |
| Flutter产物 | 各ABI包含libapp.so/libflutter.so；匹配检查未发现kernel_blob.bin/vm_snapshot_data/isolate_snapshot_data |
| APK签名 | apksigner验证通过，v2；证书名Android Debug，不等于应用为Debug运行模式 |

最终结论：在当前检查范围内未找到可用的PokeHub Flutter Debug APK，免Root调试服务路线的前置条件不满足，ANDROID-D1记录BLOCKED。仅改debuggable标记或重签Release不能替代正确的Flutter Debug构建，本轮不做这种修改，也不把Release包安装到用户手机试错。

未执行任何adb install/uninstall、启动目标应用、清数据、Root、USB转发、代理/证书/VPN修改；没有新建需要清理的设备转发。iOS当前连接、证书及VPN配置未操作。下载APK仅留本机临时目录，不提交仓库；不保存完整构建日志或请求正文。

后续需要由项目构建流程产出真正的Flutter Debug APK（保留正确应用环境，采用不覆盖无关应用的包名/签名），再继续安装和真实请求响应验收。不能用“测试环境”或“Debug签名”代替调试运行模式。本轮仅记录检查结果，不修改Jenkins任务、不触发构建、不构建桌面、不推送或发布。

## Release安装与启动试验（2026-11-03 16:31后）

本节记录追加授权后的操作，前节“未安装”是上一轮结果，不再代表当前状态。

- 目标仍为已授权的一加PHK110/Android16。发现手机已安装`com.test.tcgp`，读取原APK确认名称PokeHub、版本1.0.0(1)；原签名SHA-256与#588一致，未覆盖其他项目。原APK保存在本机临时目录，仅含安装包而非应用数据备份。
- 下载文件摘要复核与前节相同。执行指定设备的`adb install -r`，输出`Success`；原生安装器也显示PokeHub安装完成。未使用卸载、清数据、降级、自动重签或授权所有权限的选项。
- 从新安装路径读取APK的SHA-256，仍为`23b602f915ff93b31b6152686498933b085e12a0a0b50526a5a4186b37c6355b`，确认实际安装的是#588，而非仅版本号相同的旧包。更新时间为16:31:28。
- 安装采用保留数据替换命令，但设备报告的firstInstallTime也变为此次时间；登录态与应用数据是否完整保留尚未通过UI核对，不能只凭`-r`宣称已验收数据保留。未检测到或执行任何清数据命令，不据此推断已丢数据或擅自回退APK。
- 通过设备工具启动目标包。出现可选通知权限弹窗后选择“不允许”，不为接口试验授予无关通知权限。进程启动成功；随后手机自动锁屏，已请求用户解锁并保持测试版PokeHub前台，尚待页面验证。
- `run-as com.test.tcgp id`返回`package not debuggable`。Release中调试/服务扩展禁用的限制参见[Flutter构建模式](https://docs.flutter.dev/testing/build-modes)；没有通过Root或重新打包绕过。
- 只读取本轮启动时间之后、目标进程的Logcat快照，685行/81818字节，保存在私有临时目录。脱敏检查见到Adjust统计SDK请求和响应提示、Flutter初始化/认证状态日志及部分域名；未取得可对应的PokeHub业务Request/Response正文，也未发现VM服务启动标记。日志不是代理抓包证据，不声称不存在任何其他诊断能力。
- 安装前后全局HTTP代理均为null，默认网络编号相同且VPN transport仍存在；未修改VPN应用或设置、系统代理/证书。没有启动替代VPN的采集器，也没有变更iOS抓包连接。
- UI工具新增一项`localabstract:mobilecli-server`的USB转发，结束本轮检查时仅移除此项；前后已有两项USB转发完全一致，未动原转发或其他设备。

当前结果：安装与启动通过；完整业务接口抓取仍未通过。ANDROID-D1保持BLOCKED，剩余是解锁后的页面/登录态核对，以及在当前Release、未Root、不改网络约束下取得真实请求响应。所有只读检查和安装命令均已结束，无持续Logcat采集或自建代理；已安装PokeHub保留供用户使用。只修改验收文档，不构建产品或发布。

## 解锁后续验（2026-11-03 16:54）

- 用户确认已解锁后，设备工具确认前台为`com.test.tcgp`，页面仍是电子邮件/密码登录表单，尚未进入业务首页。未读取密码、代填或提交登录；不把安装采用`-r`当成原登录态保留的证据。已请求用户自行登录，不留存账号字段。
- 只读取PID5891的有界Logcat快照，文件36行/4738字节（34条记录，16:51:15.892至16:54:27.597）。脱敏关键词检查没有匹配VM服务、请求/响应正文或状态码标记；没有获得完整业务Request/Response，也未操作登录后的业务页面。该结果只覆盖此快照，不证明应用不存在其他诊断能力。
- 全局HTTP代理仍为`null`，默认网络184，VPN transport仍存在。未Root、修改VPN/系统代理/证书、安装采集VPN或重新安装应用；没有持续日志采集器。
- 仅移除本轮UI工具新增的`tcp:64291 -> localabstract:mobilecli-server`转发，复核原`tcp:23761 -> tcp:10156`、`tcp:36166 -> tcp:10157`均保留。PokeHub未关闭。
- ANDROID-D1再次记录BLOCKED：等待用户自行进入业务首页，同时Release无已验证的免Root诊断通道。安装成功与抓包成功分别报告；只有实际取得业务请求响应后才可验收通过。

## 登录后只读业务试验（2026-11-03 16:58至16:59）

- 用户自行登录后，USB前台和元素检查确认测试包`com.test.tcgp`显示卡牌列表。进入SP1-027卡牌详情，切换“谁在寻找”和卡牌的“训练家”，返回后查看市场的“训练家”并做一次下拉手势，最后返回卡牌列表。页面显示卡牌与无匹配帖子/训练家的空状态；仅凭页面可打开不推断业务请求已成功返回。
- 未点击发布、交换提交、购买、同步数据或账号设置。返回卡牌页时出现新手引导，用返回键退出；应用留在卡牌列表，没有退出账号或关闭应用。不再次安装，也不宣称覆盖安装已保留原登录态。
- 目标PID5891从16:58:28起的Logcat快照为136行/13764字节（135条记录，首条16:58:28.985、末条16:59:46.482）。检查了请求/响应/状态码/异常/VM服务标记和日志标签，取得Firebase日志上报与Adjust广告收入上报的URL、Adjust的成功响应文字，但没有可对应的PokeHub业务URL、方法、状态码和Request/Response正文。统计SDK日志不计为业务抓包；原始快照只留本机临时目录，不提交凭据或正文。
- 结合已验证的Release构建、`debuggable=false`和`run-as`拒绝，当前没有可用的Flutter调试采集证据。只读核对`scripts/start_frida_server.sh:74`附近逻辑：现有启动路径要求uid=0或su；未执行该脚本、Root检测命令或自动环境准备流程，不以试验名义修改设备。
- 后续免Root候选路径是正确的Flutter Debug包和USB调试连接，再验证其实际业务流量是否被DevTools Network记录；不是保证任意Release/原生SDK流量都可读取。[Flutter构建模式](https://docs.flutter.dev/testing/build-modes)明确Debug启用调试/服务扩展而Release禁用；[Network视图](https://docs.flutter.dev/tools/devtools/network)覆盖`dart:io`及接入`http_profile`的流量。本轮没有触发新构建或改动Jenkins。
- 收尾验证：系统HTTP代理`null`、默认网络184、VPN transport存在，均与基线一致；没有Root、证书/代理/VPN修改，没有替代VPN采集器或持续Logcat。仅移除本轮工具新增`tcp:65282 -> localabstract:mobilecli-server`，原两项转发保留，未操作iOS连接。

结论：安装、启动和登录后的只读页面验证完成，完整业务接口抓取未通过。原登录阻塞已解除，ANDROID-D1仍为BLOCKED，原因改为当前Release在已授权限制内没有已验证的采集通道；下一步需要Debug构建或应用内诊断支持，不再让用户反复调整手机网络。

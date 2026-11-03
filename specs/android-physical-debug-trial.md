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

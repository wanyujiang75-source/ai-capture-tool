# AP-0 一加与PokeHub只读准入验收

日期：2026-11-05，约18:10至18:16（Asia/Shanghai）。任务：AP-0。

## 结论

AP-0检查模块和只读验收完成；当前设备的业务HTTPS抓包准入为blocked，不能据此进入AP-1实机接入或宣称真机抓包可用。本轮没有发送业务请求、启动应用或代理，没有进行TLS解密试验。

已区分当前Google Play来源的原版候选与历史Jenkins测试包。来源与签名证据充分支持本次选择，但没有独立的官方发布签名基准进行外部比对，不声称完成应用商店供应链认证。

## 实机证据

| 检查项 | 结果 |
| --- | --- |
| 指定设备 | 唯一在线USB设备为一加PHK110，序列号尾号9352，已授权；每次shell均使用精确serial |
| 系统 | Android16/API36，arm64-v8a，用户0，boot completed=1 |
| 锁屏 | window policy显示showing=false、inputRestricted=false；未操作锁屏 |
| Root相关只读证据 | shell uid=2000、flash.locked=1、verifiedbootstate=green。按无已验证Root能力处理；未调用su、adb root，也不以这些字段绝对证明不存在隐藏Root |
| 原版候选 | com.mi.poketrade，2.1.0(96)，targetSdk36，installer=com.android.vending |
| 测试包 | com.test.tcgp，1.0.0(1)，installer=com.android.packageinstaller；未替代为原版验收 |
| 调试 | 系统包flags无DEBUGGABLE，base Manifest未设置debuggable；arm64 split含libapp.so/libflutter.so，base未找到Debug快照文件；未主动连接调试服务 |
| APK集合 | base加11个split；12个apksigner verify均退出0，应用签名一致；结束时设备sha256sum与本机提取的12个文件全部一致 |
| 网络信任 | base Manifest没有networkSecurityConfig声明，未找到同名资源；这不代表已审计全部自带TLS栈或证明证书绑定 |
| VPN | 前后均观察到connectivity的VPN transport；always_on_vpn_app和always_on_vpn_lockdown前后均为null。null不是VPN关闭 |
| 代理 | 全局http_proxy前后均为null；不据此推断Wi-Fi、VPN内部或应用代理均为空 |
| 客户端线索 | 已安装两个Clash相关包；不凭已安装包判断哪个正在管理VPN，未读取其配置、节点、订阅、日志或密钥 |
| 本地端口 | ss观察到127.0.0.1:7890/7891/7892/7893等监听；同时出现netlink权限不足，只能视为不完整监听信息。未连接这些端口，协议、归属、认证和可作为上游的能力均未知 |
| 企业限制 | 过滤的device_policy未显示所检查的三个限制；空输出不等于证明无企业策略 |
| 日志 | logcat -g可读取缓冲区元数据；未读取用户业务日志，也不算Request/Response |

APK应用签名SHA-256：`546afb7a484cc2ad4269c143565db5e232dcf510a69e303896b22587521efc46`。

| APK | SHA-256 |
| --- | --- |
| base.apk | d29ff6da7ae6df38acf933a9941de01fead011869fbdd08b2e2fe3d9b8ee1144 |
| split_config.arm64_v8a.apk | 0cf04880f794d2ad5ada0840ab34ab3de1b7c52f510030dea8c87813e9ba5e3a |
| split_config.de.apk | 0e5bab72aff7c6eda461970ddc66e1a544a195aa579bc867cc0684cf53265917 |
| split_config.en.apk | ea00e68523e370db3fd493e740f78b5cb2b29e602f2e4df53e1b8a095450b29f |
| split_config.fr.apk | 80d66145fac381fe3bf3687b17e19174320d2eb93169878f9ef78a7823583f08 |
| split_config.ja.apk | e1bba999f28a9e323836966aa4e6a6f26c8f239be629e8d92e8a297d0750bb35 |
| split_config.ko.apk | 35a552a364e6d615ee1e80f6c609a055e4e0dce2c035caa51a14b4dcec9389f2 |
| split_config.pt.apk | 92a2ed19a8571513402c35ebb3d3c1869b6238be9c17faac82b69b6347e9a4dc |
| split_config.ru.apk | cbab4dfa36d7cfa3248d57f7caa2ed81b4bf47420a2c4dc15408914ebb7d5df5 |
| split_config.tl.apk | 5511d0e7a73f31664687b41c3e01d7558ff4f503d7b90d546877a0d2d31f5faf |
| split_config.xxxhdpi.apk | ac6ae9489f6ee3642c3cbaffae07782bcf2af7ea050d737abc6a4f64c67d61e9 |
| split_config.zh.apk | 39193551022d8214813002d1035f72e18bf3205267934256e64d125a17f0a72d |

APK只从设备pull至本机临时目录ap0-pokehub-pc57q1ek，未提交安装包。没有拉取应用私有数据。

## 路径判断

1. USB连接只证明ADB可用。现有转发为tcp:23761到tcp:10156及tcp:36166到tcp:10157，前后相同；reverse为空。未创建、移除或接管任何转发。
2. 免Root普通代理：缺少已验证的目标应用接入与TLS信任。该targetSdk36应用未声明自定义网络安全配置，Android平台默认不信任用户添加CA；Flutter/native自带信任实现仍未知，不把平台默认当作所有连接的实测失败。[Android网络安全配置](https://developer.android.com/privacy-and-security/security-config)
3. 原版包不是可调试构建，不能把USB授权等同于获得Flutter调试采集服务；本轮也未通过重签、Gadget或改包尝试。
4. Root辅助：没有已授权且已验证的Root能力，本轮不执行提升权限。Frida文档中的常见root-server路线或重打包路线均不满足当前全部约束。[Frida Android](https://frida.re/docs/android/)
5. 现有VPN本地端口是后续候选线索，而非可行通道证明。即使以后验证可作为上游，也只解决出网的一部分，不能自动解决应用TLS解密。本轮不连接端口、不改节点/默认路由、不启动第二VPN。

因此当前返回capture_ready=false，TLS、应用HTTP与断点状态保持unknown，recommended_mode为空。不是“已证实永远无法抓包”，而是“当前授权条件下没有经过验证的完整路径”。不要求用户再试装证书或反复调整VPN。

## 实现与自动化验收

新增独立模块capture_console/android_physical_capabilities.py，暂未注册API、接入UI或替换已安装桌面。使用固定只读命令、参数格式校验和精确serial；单进程8秒/64KiB限额；命令错误不暴露原始内容。未知保留，uid=0或DEBUGGABLE也不自动判定抓包成功。

非用户0设备先阻塞包身份读取，防止把主用户应用误当成当前工作资料中的应用。没有修改既有模拟器、iPhone或抓包生命周期。

测试过程：新模块未实现时入口测试出现预期ImportError；补充多用户防串包测试出现1项断言失败，随后加入用户边界，复测通过。不存在未处理的验收失败。

```bash
env PYTHONDONTWRITEBYTECODE=1 /Applications/抓包工具.app/Contents/Resources/runtime/bin/python3 -B -m unittest tests.test_android_physical_capabilities -v
# 13项通过，8.056秒
env PYTHONDONTWRITEBYTECODE=1 /Applications/抓包工具.app/Contents/Resources/runtime/bin/python3 -B -m unittest tests.test_android_physical_capabilities tests.test_logcat_service tests.test_device_network -q
# 33项通过，8.263秒
```

覆盖无设备、离线、未授权、误选模拟器、多设备精确选择、非主用户、非调试包、root线索、限制提示、命令失败/超时/输出超限及输入注入。实机补充APK身份、签名、摘要与前后有限网络基线对照。未执行完整桌面构建、UI验收、API集成或真实HTTP解密测试，不复用其他平台通过记录充当真机通过。

## 不变边界与交付

本轮只执行设备清单、getprop/id、am get-current-user、包/路径查询、只读settings get、经过滤的dumpsys、ss、转发列表、pidof、logcat -g、APK pull及sha256sum。Mac端仅解析/验签/测试和文档修改。未Root、安装/卸载/启动应用、改证书、代理、VPN或配置，未触发Jenkins。

没有读取完整VPN配置，因此“配置未改”的证据是命令审计及有限基线，不是假称做过全配置摘要比较；VPN节点和实际出口未核验。无自建代理或持续日志进程需要回收。

AP-0 DONE；AP-1至AP-4未启动。当前仅本地提交，不推送、不更新安装包。后续必须先解决经授权的流量接入及应用TLS能力，不能自动把研究候选升级为实机操作。

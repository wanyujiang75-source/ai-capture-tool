# iOS 使用说明与预发布包交付

## Scope

IOS-R1只交付当前已完成的产品代码、说明和可下载预览包。沿用现有工作树；用户授权推送源码及发布资产。
不实施未完成的模块导入、自动手机控制、原出口多级代理或新设备适配。不修改测试手机网络。

## Documentation Contract

- README提供下载入口和iPhone简要流程；INSTALL区分Android与iPhone前置条件。
- 完整指南和ZIP根目录说明均写清：Mac/网络/本人手机授权、首次准备、证书安装与信任、首次Capture-Mac节点参数取得、临时统一转发、手机HTTPS验证、开始/停止、恢复原路由与节点、重连/换设备/换网络/撤销、排错。
- 参数来源是当前Mac生成的mobileconfig，不写入任何真实IP/端口/密码或测试账号。当前UI不直接显示节点凭据，提供本机plutil读取和证书副本生成步骤，不声称全自动。原文件不变，副本仅root证书/WebClip，不能带Wi-Fi/VPN载荷、代理密码或私钥；与实测派生配置路径一致。
- 小火箭VPN保持开启，修改的是临时选择，不改原节点、订阅、配置文件、DNS或FINAL；出口可能变为Mac路径。
- 停止记录不恢复路由；Mac退出/断网前须先恢复。首次安装/信任不必每次重复。
- 产品通用接入不等于所有应用/协议可解密；记录可能混入后台流量。新Mac/新iPhone未实测不标记通过。
- ZIP内INSTALL.md与安装说明.md内容一致；发布说明标注Apple Silicon/macOS14+、ad-hoc未公证及必需手动步骤。

## Verification And Delivery

1. git diff --check；文档链接/过时流程/敏感值扫描；本机参数读取命令用合成mobileconfig验证。
2. 相关iOS/console/Jenkins/证书Python回归；Swift全测试；CAPTURE_TEST_IOS_PROXY=1真实隔离代理；现有打包测试。
3. 从最终源码提交构建development-arm64 ZIP，记录build ID和SHA-256。包内资源不得包含运行数据、CA私钥、描述文件、APK、真实配置或抓包正文。
4. 解压到独立目录验证签名/架构/运行时；CAPTURE_TEST_IOS_APP_PATH运行三轮隔离后端归档测试；隔离原生窗口验收，不改手机或旧运行数据。
5. 仅快进更新远端源码，无强推；基于明确源码提交创建新的预发布Release，不覆盖旧包。上传ZIP与校验文件，回读资产digest并下载校验；主工作区无关文件保持原样。
6. 证据写回本规格与progress；交付下载链接和iPhone指南，区分源码/包版本与验收记录提交。

## Evidence

- 说明已同步README、INSTALL、完整使用指南、ZIP安装说明；桌面旧的逐域名提示改为与指南一致。发现默认profile包含Wi-Fi载荷，因此按此前真实手机成功路径生成证书/WebClip副本，不宣称原始分享等同于不改网络。
- 最终说明命令用make_profile合成数据验证：两处脚本逐字一致，字段读取正确，副本只含原证书和WebClip，源文件不变，文件0600/目录0700；缺少连接与不符载荷会失败退出，没有读取真实凭据。
- Python全量 `env -u CAPTURE_DEVICES_CONFIG -u CAPTURE_RUNTIME_DIR ... -m unittest discover -s tests`：356项/67.007秒，351通过、5项opt-in跳过（代理3、Keychain1、包生命周期1）；其中包含8项打包回归。先前相关284项也通过。
- 单独启用真实隔离代理3项/9.076秒通过；独立测试namespace的真实Keychain1项/0.075秒通过并清理。Swift最终121项/17 suites/7.722秒通过。
- 基础凭据模式扫描未推送历史未发现私钥材料、GitHub/AWS/Bearer凭据；跟踪文件无profile/pem/key/db/apk/pcap/har/local.json。该模式扫描不是所有秘密类型的完整证明。
- 当前无Developer ID分发身份，沿用明确标注的ad-hoc development预发布，不绕过Gatekeeper。主工作区未跟踪用户文档保留，基线SHA-256为3273ffb68135fb7c2bc633f667fc9cb3a2d4e0aea67bbe501e7bee0016a97a25。
- 从源码提交`d2795fe4c20c733e841c1c948c4965151f514b72`构建development包，内嵌build ID为`d2795fe4c20c`。ZIP共99,695,714字节，SHA-256为`4b4b37cd04fa705ff015476617a8e16038c7a61047d406e0b52a7f9ea449ee81`。
- 独立解包确认arm64可执行文件、两份安装说明与最终源码一致、内嵌后端源码一致；运行前后`codesign --verify --deep --strict --verbose=2`均通过。未包含用户描述文件、抓包记录、真实配置、APK或本工具CA私钥。
- 验收脚本首次误将预期build ID写成13位，修正为从Git取得实际12位后通过，包本身无需修复。私钥标记扫描曾命中Python依赖中的`tornado/test/test.key`；核对为与独立安装Tornado逐字节一致的公开测试fixture，不是用户密钥；没有把该项当作产品秘密或直接略过失败。
- 最终ZIP中的App执行`CAPTURE_TEST_IOS_APP_PATH=... -m unittest tests.test_ios_packaged_lifecycle`：1项/5.623秒通过，覆盖三轮正常/异常后端重启及归档恢复。至此全量套件的5项opt-in均另行启用并通过。
- 独立新运行目录实际启动最终App，原生四导航、Android空状态、iPhone入口、初次准备弹层和未准备时按钮禁用通过；未点击准备、未生成手机配置、未连接手机或重新录制。正常退出并再次核对签名。
- GitHub main和功能分支以原子快进推送至源码提交，无强推。新预发布`desktop-preview-20261104-d2795fe`已公开，tag指向上述源码提交，旧Release未覆盖。资产只有ZIP和SHA-256文件，GitHub返回的ZIP digest与本地一致。
- 使用不带GitHub认证的curl从公开Release地址重新下载ZIP及校验文件，`shasum -a 256 -c`通过，`cmp`与本地ZIP完全一致；公开main使用指南与本地最终指南也逐字节一致。发布后的验收记录是独立文档提交，不改变此包源码版本。
- IOS-R1完成。仍未覆盖第二台Mac/全新iPhone的整套人工安装验收，不宣称所有设备/应用可抓取；手机安装及信任、临时转发选择与结束恢复仍需手动操作。

## Published Links

- [安装包与校验文件](https://github.com/wanyujiang75-source/ai-capture-tool/releases/tag/desktop-preview-20261104-d2795fe)
- [完整使用指南](https://github.com/wanyujiang75-source/ai-capture-tool/blob/main/docs/desktop-user-guide.md)
- [下载与前置条件](https://github.com/wanyujiang75-source/ai-capture-tool/blob/main/INSTALL.md)

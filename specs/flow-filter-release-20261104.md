# 接口过滤发布验收

## Scope

FLOW-R1只发布已经完成的FLOW-F1源码和预览安装包，沿用当前功能工作树。用户明确授权GitHub推送和安装包更新；不修改手机/VPN、不启动实际录制、不实施断点计划、不覆盖旧Release、不收集或上传本机运行数据。

## Delivery

- README、包内安装说明和独立Release说明描述“仅看接口”：默认关闭、可恢复全部、可叠加搜索、清空后增量、失败与未知保留；不是按进程精确归属。
- 从记录的最终源码提交构建，build ID为该提交前12位；新标签`desktop-preview-20261104-<short-sha>`，新ZIP`AI-Capture-Desktop-20261104-<short-sha>-development-arm64.zip`及同名`.sha256`。
- 当前沿用ad-hoc未公证预览版，macOS14+/Apple Silicon；不冒充Developer ID正式发行，不关闭Gatekeeper。
- 远端main及功能分支仅快进，历史不改写；保留所有旧资产。既有断点调研文档不等于安装包包含断点功能。

## Acceptance

1. 核对git差异、远端和主工作区无关文件；git diff --check；检查发布说明无真实凭据。
2. 对未变化产品复用FLOW-F1绑定的Python199、Swift126、iOS回归及3项真实隔离代理证据；新包必须重新执行打包回归、签名、架构、build ID、包内源码与说明一致性检查。
3. 独立解包、不依赖开发目录或本机Python；使用包内运行时执行摘要回归与`CAPTURE_TEST_IOS_APP_PATH=... -m unittest tests.test_ios_packaged_lifecycle`三轮归档重启，保持手机和VPN不变。
4. 最终App使用合成夹具、独立运行目录验收原生筛选开关/计数/恢复；不使用真实设备作为夹具。完成回收自有进程，再次校验签名。
5. 包内无用户profile/私钥/抓包结果/APK/本机配置；依赖公开测试fixture需明确区分而非误判为用户秘密。
6. 发布后读取GitHub tag/资产digest，匿名下载两资产，校验SHA-256与本地字节一致；记录验收提交与包源码提交的区别。

## Evidence

- 发布前远端main=77aed99，工作树HEAD=ef7fef3，干净。当前产品文件相对3f1284f无变化；先前原生UI完整证据见`flow-interface-filter.md`。主工作区无关未跟踪文档保留。
- 重新执行Python全量`env -u CAPTURE_DEVICES_CONFIG -u CAPTURE_RUNTIME_DIR ... -m unittest discover -s tests`：358项/66.095秒，353通过、5项opt-in跳过，包含打包回归；Swift全量126项/18 suites/7.695秒通过。独立启用`CAPTURE_TEST_IOS_PROXY=1 CAPTURE_TEST_IOS_KEYCHAIN=1`的4项/9.148秒通过；Keychain使用测试独立身份，不动用户抓包身份。剩余1项包生命周期将在最终解包App上启用。
- 文档差异/链接锚点检查、基础凭据模式扫描通过；当前无Developer ID分发身份，继续标注ad-hoc开发预览版。包内筛选说明已加入，README链接到已有“6. 查看接口”。
- 尚未构建或发布本次安装包；完成后补齐精确版本、摘要、命令和URL。

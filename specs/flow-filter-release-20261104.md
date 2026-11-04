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
- 最终源码`be6d0543b498dc5de2af319a5e4acd574fa79cde`，build ID=`be6d0543b498`；`AI_CAPTURE_BUILD_ID=be6d0543b498 TRACEDECK_VERSION=20261104-be6d054 TRACEDECK_RELEASE_KIND=development MACOS_SIGN_IDENTITY=- release/package.sh`成功。ZIP为99,719,780字节，SHA-256为`0e1582835b7425be313092e2a12545881a0a16b1e4d248c221d13203a1ab5f33`。
- 独立解包到新临时目录，arm64、最低macOS14、bundle ID/build ID正确，28个后端Python源文件与源码一致，两份包内安装说明逐字节一致；运行时requirements摘要匹配，符号链接均相对且不逃出Resources。后端无用户profile/pem/key/db/APK/HAR/pcap/local.json；私钥标记扫描只命中依赖解析器中的边界字符串与Tornado公开test.key，后者与独立安装的依赖fixture字节一致，不是用户密钥。
- 最终包内Python/后端直接执行13项摘要/归档测试通过（0.446秒），已断言模块来自解包目录而非源码树。`CAPTURE_TEST_IOS_APP_PATH=<解包App> ... -m unittest tests.test_ios_packaged_lifecycle`1项/5.485秒通过，覆盖三轮正常/异常重启及请求响应归档。全量套件跳过的5项opt-in至此均另行启用通过。
- 直接运行最终解包App，使用独立合成夹具与runtime：默认6/6、筛选3/6、搜索401为1/6、Request详情可读、关闭搜索与筛选恢复6/6；未访问手机、VPN或真实抓包。App退出码0，自有夹具已关闭，7001无监听；运行前后严格深度签名均通过。控制台有一条NSTableView重入兼容性警告，当前未出现崩溃或功能失败；不宣称此警告已修复。
- 源码已原子快进推送main及codex/ios-device-trial至上述提交，无强推。Release先以草稿上传，只有完整上传并核对摘要后公开；公开下载结果随后补齐。
- 首次ZIP上传被GitHub返回HTTP408（upload body inactivity timeout），校验文件上传成功但版本仍保持草稿，没有公开不完整资产。该失败属于发布链路，任务保持DOING，重试相同校验过的ZIP；不修改VPN/系统代理或覆盖旧Release。
- 使用仅对上传进程生效的`GODEBUG=http2client=0 gh release upload ...`重试成功，不据此断言原失败根因。GitHub两资产均uploaded，ZIP大小/digest与本地一致后才公开草稿。Release公开时间2026-11-04T05:58:17Z；新标签精确指向be6d054，旧d2795fe标签和两项旧资产仍保留。
- `curl -q --fail --location ...`不带GitHub认证匿名重新下载ZIP及校验文件，两个下载均退出0；`shasum -a 256 -c ...zip.sha256`为OK，两个`cmp`与本地原件逐字节一致。公开主分支已含筛选代码与说明，后续验收记录是独立文档提交，不移动Release标签或替换已验证ZIP。
- FLOW-R1完成；未改手机/VPN，也未把合成桌面测试视为新手机/新主机整体验收。主工作区无关未跟踪文档SHA-256保持`3273ffb68135fb7c2bc633f667fc9cb3a2d4e0aea67bbe501e7bee0016a97a25`。

## Published Links

- [接口过滤版安装包与SHA-256](https://github.com/wanyujiang75-source/ai-capture-tool/releases/tag/desktop-preview-20261104-be6d054)
- [安装与前置条件](https://github.com/wanyujiang75-source/ai-capture-tool/blob/main/INSTALL.md)
- [接口使用说明](https://github.com/wanyujiang75-source/ai-capture-tool/blob/main/docs/desktop-user-guide.md#6-查看接口)

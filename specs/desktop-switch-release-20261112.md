# 换机修复发布与本机更新

## 授权和范围

用户明确要求合并主分支、更新远程包和本机桌面。发布已完成的 d4d7c6c、c5aad1e、a5aa0fa 及本发布记录，不扩大功能。保持 main 快进，不强推；旧 Release 和工作区无关变更保留。iPhone USB 配置安装已取消，不纳入版本。

Android 真机仍使用单应用临时 VPN 接管，不声称与原手机 VPN 同时连接、通用解密或全自动网络恢复。iPhone 流程保持隔空投送。当前 PHK110 待恢复记录不因更新删除或标已恢复。

## 交付

1. 运行 Android 真机、换机、API、文案、既有 iOS/接口链路 Python 回归与 Swift 全套。测试仅模拟设备或隔离后端，不修改手机。
2. 提交本发布规划/说明，固定提交构建完整 release App 与 development-arm64 ZIP，带独立运行时、连接助手、INSTALL/USER_GUIDE/BREAKPOINTS 和 SHA-256。
3. 最终 ZIP 解压后严格签名、内嵌源码/指南与提交一致；使用解压 Python 跑隔离后端生命周期和关键回归。未签 Developer ID/公证的事实在说明中保留。
4. 快进 main，推送 main/开发分支/独立预发布标签；不覆盖已有资产。检查 Release 目标提交、资产和匿名下载摘要。
5. 本机录制空闲后正常退出旧桌面；iPhone 连接监听会随旧后端退出暂停，但不操作手机 VPN/节点。备份旧 App，安装已验收 ZIP 的同一 App，启动验证 build ID、新按钮/入口、后端可用及待恢复记录不丢失。禁止自动开始抓包或恢复手机网络。
6. 更新证据、仅本地任务文件提交并推送；产品包所对应的固定提交单独标明，避免把后续纯证据提交误报为包体代码落后。

## 验收证据

### 构建和回归

- 固定产品提交：`48a2b81e20e679c5bb80d2d8a41aff88c96d42a6`；主分支与开发分支快进推送成功。
- Python 118 项通过；Swift 201 项、26 个套件通过（另 1 项 opt-in 跳过）；解压包 Python 的隔离后端/归档生命周期与关键回归 77 项通过。
- `CONFIGURATION=release AI_CAPTURE_BUILD_ID=48a2b81e20e6 TRACEDECK_VERSION=20261112-48a2b81 TRACEDECK_RELEASE_KIND=development bash release/package.sh` 退出 0。
- ZIP 的 93 个后端源码文件与固定提交逐文件一致；INSTALL.md、USER_GUIDE.md、BREAKPOINTS.md 与提交一致，包含两个 Python 运行时及 android-bridge.apk。
- 最终 ZIP 解压签名通过。直接运行测试曾在临时验收副本的 backend/runtime 中产生 console.db，导致该副本严格验签失败；未用于安装。重新从原始 ZIP 解压，严格验签通过后安装，本机首次启动后再验签也通过。后续包内测试应始终显式指定隔离 CAPTURE_RUNTIME_DIR。
- npm 安装报告 8 项已有开发依赖告警；`npm --prefix web audit --omit=dev --json` 为 0 项生产依赖漏洞。本轮不调整依赖。

### 发布和本机

- 已发布独立预发布 `desktop-preview-20261112-48a2b81`，目标为固定产品提交；旧 Release 保留。后续证据提交仅改文档，不改变包体代码。
- 公开下载：https://github.com/wanyujiang75-source/ai-capture-tool/releases/tag/desktop-preview-20261112-48a2b81
- ZIP 为 249893759 字节；SHA-256：`2c2485427fa8c3b0c47367fa8834bc97a755d7c44d53e6d40c4fa658df736cce`。GitHub 资产摘要、本地 ZIP、无登录 curl 下载 ZIP 三者一致，完整 cmp 退出 0；公开下载的 SHA 文件也与本地一致。
- 用户确认结束后，API 再确认 #96 等任务已停止。正常退出旧桌面并备份到 `~/Library/Application Support/CaptureToolBackups/20261112-before-switch-release.CICMuY/抓包工具.app`，安装最终 ZIP 的干净副本到 `/Applications/抓包工具.app`。
- 新版桌面已启动，API build_id=`48a2b81e20e6`，原生 UI 确认“模拟器 / 真机”；用户开始 #97 后不再操作窗口，不为验收中断其任务。终止按钮沿用本轮 Swift 和上一轮原生隔离验收，不在用户活动任务中点击验证。
- PHK110 待恢复记录前后 SHA-256 均为 `3a2bb229461addc57d3c15775ac9ccf5f40b94a56f53b326dbbce69259dacb27`，未删除或标记已恢复。不修改手机 VPN、节点、原配置或数据。

### 发布后的现场反馈

用户反馈“抓包中但接口为空”。只读检查 #98 得到请求/响应/TLS 失败均为 0；手机 Wi-Fi 关闭、仅有移动网络，连接助手反复报告 WireGuard 握手失败，无法访问 Mac 的局域网地址。用户自行连接同一 Wi-Fi 并重开 #99 后恢复：API 24 条，包含 10 条 HTTP 200、3 条 204、10 条 304 和 1 条 101；用户两次确认可用。未操作其 VPN 或节点。

该结果仅确认当前设备和构建恢复，不代表所有应用兼容。另确认产品状态提示缺口：当前将 VPN 服务 connected 当作 capturing，没有先验证隧道握手；尚未修复，不计为本次发布修复项。真实新轮手机抓包不由本次发版主动发起，既有硬件边界不因发版解除。

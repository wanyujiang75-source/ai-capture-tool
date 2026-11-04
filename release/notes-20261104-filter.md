# 抓包工具 Desktop Preview 2026-11-04 · 接口过滤

macOS 14+ / Apple Silicon（arm64）预发布版，ad-hoc签名，未经Apple公证。首次启动可能需要在macOS“隐私与安全性”中本人确认“仍要打开”，不要关闭Gatekeeper。

## 本版更新

- “接口”列表上方新增“仅看接口”，隐藏可识别的静态资源、普通网页及统计/系统检查请求，并显示过滤数量。
- 默认显示全部，关闭筛选即可恢复；可与搜索叠加，新接口继续实时出现，不停止抓包、不删除记录。
- 失败、暂无响应及类型未知的可能业务请求保留，避免过滤掉排错线索。筛选是启发式判断，不等于按应用进程精确归属。
- 被过滤的选中项自动清除详情，避免展示旧请求；保留之前已发布的Android/iPhone抓包能力和完整使用说明。本版不包含断点修改功能。

## 下载与升级

1. 在Assets下载`AI-Capture-Desktop-…-development-arm64.zip`及同名`.zip.sha256`，无需下载Source code。
2. 使用`shasum -a 256 -c <下载的校验文件>`校验，解压后将“抓包工具.app”移入“应用程序”。ZIP内附“安装说明.md”和同内容的“INSTALL.md”。
3. 升级前停止记录；iPhone用户先恢复原节点和路由、确认联网，再退出旧桌面端替换App。保留本机运行目录、钥匙串身份、模拟器和已有结果，无需为本次筛选升级重新安装证书。
4. 打开新版后进入“接口”，点击“仅看接口”；找不到预期请求时关闭筛选并清空搜索。

- [安装与前置条件](https://github.com/wanyujiang75-source/ai-capture-tool/blob/main/INSTALL.md)
- [完整操作指南](https://github.com/wanyujiang75-source/ai-capture-tool/blob/main/docs/desktop-user-guide.md)

## 验证范围

接口分类、Android/iPhone摘要、搜索、计数、清空后的增量、详情切换及失败恢复已通过测试和原生桌面合成场景验收。安装包发布另执行独立解包、签名、包内运行时和归档重启验证；发布证据见仓库`specs/flow-filter-release-20261104.md`。

不保证所有第三方应用或全新设备均可抓取；iPhone证书信任、转发切换与网络恢复仍需本人完成。停止录制不等于恢复手机网络，具体边界见使用指南。

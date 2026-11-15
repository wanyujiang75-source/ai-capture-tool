# 2026-11-15 桌面发布

## 范围

交付当前已提交Android网络准入、Google登录加密转发、StickerHub限定Banner兼容及诊断改动。main为当前分支祖先，使用快进，不强推。其他任务的未提交goal/progress片段及未跟踪文档不纳入提交或安装ZIP。只发布桌面ZIP及校验文件、使用指南，不上传工作区源码打包。

## 边界

- Apple Silicon、macOS14+开发签名预览版，未公证，不假称正式签名。
- StickerHub3.18.15(196)/PKG110 Banner和完整业务正文已验；视频不作为完成承诺，其他SDK仍可能TLS失败。
- 不启动手机抓包、不改VPN节点或配置、不清除运行目录和手机数据。保留旧PHK110恢复提醒。
- 本机Applications旧版先移动到私有备份目录，新版校验通过再启动；失败恢复备份。不清理其他桌面副本。

## 验收

1. 复用70ac90d对应134项Android通过及#134真机证据；最终构建严格codesign校验，包内源码核对。
2. main快进并推送，核对远端SHA；发布tag绑定构建提交。
3. ZIP包含app、INSTALL.md、USER_GUIDE.md、BREAKPOINTS.md及安装说明；不含私有配置、运行数据或其他任务草稿。
4. 发布GitHub预览版并重新下载资产核对SHA256。
5. 本机新版从/Applications启动，构建ID与发布包一致，后端健康、未自动抓包；记录交付链接。

## 交付证据

- 2026-11-15 main快进至f383aa963eb7da9a257226235fb3429ad71d7594，origin/main与发布tag均核对一致。旧分支和其他工作区保留；goal/progress其他任务未提交片段及未跟踪文档未纳入提交。
- `AI_CAPTURE_BUILD_ID=f383aa9 bash macos-native/scripts/build-app.sh`退出0，codesign深度严格校验通过；连接助手Gradle9项无失败。`swift test --package-path macos-native`205项通过，诊断14项通过；134项Android沿最终相同产品源码的上一轮通过证据。
- 发布页：https://github.com/wanyujiang75-source/ai-capture-tool/releases/tag/desktop-preview-20261115-f383aa9 ，公开预览版非草稿。ZIP250916837B，SHA256为bb60107fc2c5e0a3688d5fffa5b65605b78daa6a50911f03557ae23f3d46eb0a。CRC/指南/构建ID检查通过，不含运行数据或未提交草稿；GitHub资产digest与本地一致，gh重新下载并shasum -c通过，匿名HEAD跟随跳转HTTP200。
- /Applications/抓包工具.app已替换为同一构建，旧版备份在用户Library/Application Support/AI抓包工具/app-backups/20261115-f383aa9/抓包工具.app。主二进制摘要与构建目录一致，包内路由源码cmp一致，严格签名通过。
- 实际启动进程来自/Applications，UI停在Android真机页并识别PKG110，未勾选授权或启动抓包。/api/status返回health=idle、active_session=null、desktop.build_id=f383aa9。没有删除数据、修改手机VPN或旧PHK110恢复提醒。
- 收尾提交只补发布证据，不改变安装包产品源码，因此发布tag和安装包继续对应f383aa9。

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

# 2026-11-10 main 合并与预览包

仅RELEASE-1110。先确认main为当前分支祖先，正常快进合并并推送，不强推；保留主工作树未跟踪中文文档及功能树Android副本规格脏文件。无实质产品新增，复用同源码191项Swift、88项后端和3项实链路结果；固定合并SHA重新release构建。

使用已有build-app.sh及ditto/zip组装桌面ZIP，避免package.sh的npm install和额外源码归档。ZIP附INSTALL.md、安装说明.md、BREAKPOINTS.md及USER_GUIDE.md；不包含本机运行数据、CA或APK。独立目录解包，以包内Python和后端、独立CAPTURE_RUNTIME_DIR运行节点/iOS/生命周期测试，防止生成pyc污染签名。检查build ID、源码摘要、架构、严格签名。

新建draft prerelease，上传ZIP及SHA256，核验资产大小/服务端digest后公开；匿名下载ZIP及SHA，逐字节及SHA一致才交付。不覆盖旧版本或本机应用，不改VPN，不将发布等同于所有新主机已实测。Apple Silicon/macOS14+开发签名，尚未Apple公证。

## 结果

main由c4a7d6c快进至b628992972d8724538381094c170f7990f401f8b并推送/ls-remote一致。完整release构建build ID b628992972d8，arm64/macOS14，最终解包154项22.032秒通过（含节点、iOS归档/三轮生命周期、历史清理、断点引擎/API及Android准入）。47个后端源码文件与固定提交逐字节一致，无APK/用户DB/私钥/描述文件/pyc，严格签名在测试后复验通过。

发现便携安装说明仍有旧终端步骤，停止首次草稿上传，修正release/安装说明.md并以6dec74b合并推送main；产品代码未变，包内APP仍固定b628992。更新ZIP中的INSTALL.md与中文安装说明，和USER_GUIDE.md/BREAKPOINTS.md共同交付。中文条目因zip历史编码导致Python直取名称失败，按CP437字节转UTF8核对后与源文件一致，ZIP完整性通过；未将工具编码差异当文件丢失。

公开预发布desktop-preview-20261110-b628992，两资产uploaded，ZIP99,511,551字节，SHA256 a87f065d6422673bc7cc817ff70321a77444a3bacc89fa2ede0c007be2daba29，与服务端digest一致。初次下载在发布完成前请求得到404并被缓存，公开后加独立验证查询参数匿名下载成功；ZIP及124字节SHA文件均与本地cmp一致，shasum -c通过。仓库PUBLIC。保留旧版本，不改本机在用应用/VPN，两个工作树无关未提交文件未纳入。

发布页：https://github.com/wanyujiang75-source/ai-capture-tool/releases/tag/desktop-preview-20261110-b628992

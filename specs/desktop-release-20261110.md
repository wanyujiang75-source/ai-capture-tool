# 2026-11-10 main 合并与预览包

仅RELEASE-1110。先确认main为当前分支祖先，正常快进合并并推送，不强推；保留主工作树未跟踪中文文档及功能树Android副本规格脏文件。无实质产品新增，复用同源码191项Swift、88项后端和3项实链路结果；固定合并SHA重新release构建。

使用已有build-app.sh及ditto/zip组装桌面ZIP，避免package.sh的npm install和额外源码归档。ZIP附INSTALL.md、安装说明.md、BREAKPOINTS.md及USER_GUIDE.md；不包含本机运行数据、CA或APK。独立目录解包，以包内Python和后端、独立CAPTURE_RUNTIME_DIR运行节点/iOS/生命周期测试，防止生成pyc污染签名。检查build ID、源码摘要、架构、严格签名。

新建draft prerelease，上传ZIP及SHA256，核验资产大小/服务端digest后公开；匿名下载ZIP及SHA，逐字节及SHA一致才交付。不覆盖旧版本或本机应用，不改VPN，不将发布等同于所有新主机已实测。Apple Silicon/macOS14+开发签名，尚未Apple公证。

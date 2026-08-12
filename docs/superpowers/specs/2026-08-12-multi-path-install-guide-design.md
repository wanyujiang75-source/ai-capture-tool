# 多路径安装说明设计

## 目标

为 AI抓包工具提供一份统一的安装入口，覆盖 Codex 辅助安装、手动下载安装、源码构建、已有版本升级和新主机首次配置。Codex 是便捷路径之一，不把文档设计成某个工具专用协议。

## 结构

- 根目录新增 `INSTALL.md`，作为所有安装方式的权威说明。
- `README.md` 只保留安装方式摘要、适用场景和指南入口。
- `docs/desktop-user-guide.md` 继续负责安装后的产品操作，并链接回安装指南。
- 源码发布包必须包含 `INSTALL.md`，确保离线解压后仍可阅读。

## Codex 辅助安装

文档提供一段可直接复制的提示词。Codex 应检查 macOS 版本、CPU 架构、磁盘、现有安装和 Android SDK，再从官方 GitHub Releases 选择 Apple Silicon 桌面包、校验 SHA-256、安装并验证本机后端。Codex 不得关闭 Gatekeeper、删除用户数据、自动接受协议、保存管理员密码或清除模拟器登录态。

## 发行包选择

- 优先选择不含 `development` 的 `arm64.zip` 正式包。
- 只有预发布包时，必须明确其为内部开发包；首次运行可能需要用户在 macOS 安全界面手动允许。
- 不从第三方镜像下载 App，不以源码归档代替桌面 ZIP。

## 验收

- 所有 Markdown 相对链接均可解析。
- 源码发布包包含 `INSTALL.md`。
- 安装命令不包含关闭 Gatekeeper、清除隔离属性、wipe、`pm clear` 或删除运行数据等破坏性动作。

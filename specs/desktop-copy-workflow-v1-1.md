# 桌面端交互与精准文案 V1.1 规格

## 用户主流程

1. 默认进入“抓包”。
2. 用户点击“开始抓包”。
3. 工具按顺序处理模拟器启动、Android 启动、解锁等待、前台应用识别、环境准备和抓包启动。
4. 抓包运行时展示应用名称、接口数量和“停止抓包”。
5. 用户在“接口”页实时查看 Request、Response 与 cURL；“清空列表”只建立新的显示基线。

## 导航与页面边界

- 主导航固定为 `抓包`、`安装应用`、`接口`、`日志`。
- “运行检查”位于工具栏或弹窗，只展示本机环境、模拟器、网络、抓包组件四项摘要。
- 单设备隐藏设备选择器；多设备才显示“使用设备”。
- Jenkins 仅作为安装包来源；前台应用是抓包目标来源。

## 状态模型

`CaptureWorkflowState` 至少覆盖：初始、启动模拟器、启动 Android、等待解锁、等待应用、已识别应用、准备环境、启动抓包、抓包中、停止、恢复旧任务、应用冲突和失败。

每个状态必须提供标题、说明、主按钮和可选次按钮。视图不能自行拼接流程文案。

## 错误模型

`UserFacingIssue` 包含：

- `code`
- `title`
- `message`
- `recoveryAction`
- `technicalDetail`

普通页面只显示 title、message 和 recoveryAction。技术详情仅在“运行检查”展开区显示。后端可附加 `code`、`recovery_action`、`technical_detail`，同时保留已有 `detail/message/user_message/fix` 兼容字段。

## 文案约束

- 业务文案集中在 `AppCopy`，SwiftUI 页面不散落状态文案。
- 进行中统一使用“正在……”和中文省略号 `…`。
- 普通页面禁用：`Session`、`active session`、`执行中`、`未就绪`、`HTTP 409`、`Frida`、`AVD`、端口号。
- Request、Response、cURL、APK、Jenkins 保留英文。
- 应用名称统一使用中文引号：`“{应用名}”`。

## 验收

- Swift 状态/文案单元测试覆盖每个 `CaptureWorkflowState`。
- 自动抓包流程测试覆盖离线、启动中、锁定、等待应用、运行和冲突。
- 安装、接口、日志错误不显示原始后端 JSON 或实现术语。
- Python 错误响应兼容测试通过。
- Swift/Python 全量测试、App 构建、深度签名和四页面视觉检查通过。

# 超大接口响应稳定展示

## 问题证据

- `2026-09-15 16:34` 与 `16:37` 的两份 macOS hang report 均显示桌面端主线程在 SwiftUI/CoreText 文本测量中分别阻塞约 44 秒和 39 秒。
- 两次阻塞前分别产生了约 2 MB 的 JSON 响应文件；当前详情链路会完整 JSON 解码、递归格式化，并将整段字符串交给 SwiftUI `Text` 排版。
- 选择接口时还会自动请求 cURL，而 cURL 后端复用完整详情读取，导致同一份 Response 被无意义地再次加载。

## 约束

- 请求、响应原始文件不得删除或改写。
- 小于内联上限的 JSON 和文本继续完整展示。
- 超过内联上限的正文只返回 UTF-8 安全预览，并明确显示原始大小与截断状态。
- 桌面端必须提供“在 Finder 中显示完整文件”，但不得自动用其他应用打开超大文件。
- 二进制正文继续只展示类型与大小，不转成文本。
- cURL 必须继续包含完整 Request，但不得加载 Response。

## 接口与展示

- 内联正文上限为 256 KiB。
- `request_body` 与 `response_body` 增加 `truncated: Bool`；`path` 指向完整原始正文文件。
- 大 JSON 的 `request_json` / `response_json` 置空，预览放入对应的 `*_text`，`*_body_kind` 仍标记为 `json`。
- 桌面端使用原生只读 `NSTextView` 承载正文，关闭自动换行并允许横向滚动，避免 SwiftUI 对全文做同步 CoreText 布局。
- 截断正文上方显示预览说明、完整字节数和“在 Finder 中显示完整文件”按钮。

## 验收

- Python 回归验证 256 KiB 边界、UTF-8 截断、完整文件留存和 cURL 不读取 Response。
- Swift 回归验证正文元数据解码、截断提示与文件路径选择。
- 使用本机真实约 2 MB JSON 响应打开 Request、Response 和 cURL，桌面端保持可交互且不再产生 hang report。
- 运行 Python、Swift 全量测试，构建 `.app` 并通过严格签名检查。

# Request / Response 数据展示

## 范围

- 使用现有 FlowDetail 和 meta_json.summary，不改后端、录制、断点或归档。
- Request 显示 URL 查询参数、请求头、正文；Response 显示状态、响应头、正文。统一只读文本支持跨区域选择、Cmd+A/C 和查找，不增加新的详情页签。
- 查询参数和表单按字段换行，保留重复、空值及原次序；只对 application/x-www-form-urlencoded 使用加号转空格。
- Headers 来自已保存的 name/value 数组，重复项不合并。未保存的内容明确说明，不伪造。
- JSON 对象、数组递进两个空格，键值对逐行。文本 JSON 只修改字符串外的空白，保留转义、重复键、数字字面值。结构化 JSON 使用标准字符串编码，并保留 Int64/UInt64 整数精度。
- 旧 Android 的 JSON `null` 与缺失正文通过已归档的正文类型区分，不能将 `null` 显示成“没有请求体”。旧二进制记录回退到顶层 `*_body_kind`。
- 普通文本保留原内容，二进制使用明确提示及已归档正文路径；无响应不当作空成功响应。

## 资源与兼容约束

- 格式化输入最多 256 KiB；输出最多 512 KiB、8000 行、64 层嵌套。超限、不完整或非法 JSON 保留有界原始预览，不尝试补全结构。
- 不扩大后端正文读取上限，不从正文文件读全量数据，不改变 cURL。
- 查询参数和 Headers 在转换前限制输入为 32 KiB，并限制转换后输出，保留可展示的前缀及截断说明；不全量展开超长元数据。
- 旧记录缺少 headers/body info 时仍可查看。截断提示仅表示预览不完整，不宣称归档一定完整或正文一定超过 256 KiB。
- 保持既有列表过滤、当前/历史切换、详情请求竞态保护及原生文本跨行选择。

## 验收

- Swift：iOS 文本 JSON、Android 结构化 JSON、嵌套数组/转义/大整数/重复键；查询和表单、重复 Headers、旧归档；空正文/暂无响应/二进制；格式化膨胀、层级、行数和截断边界。
- `swift test --package-path macos-native`；`swift build --package-path macos-native -c release`。
- 独立 loopback 合成 fixture + 独立原生 app/runtime：切换 Request/Response/cURL，核对参数/头/正文和跨行复制，非法/大包预览仍可操作。禁止连接真实手机或录制实际流量。
- 不覆盖已运行 bundle、不更改 VPN 或原配置；验收结束关闭自有 fixture/app，记录证据后本地提交。

## 验收证据（2026-11-05）

- 首轮 3 项 RED 复现 iOS JSON 单行、嵌套缩进/转义错误、大整数 ID 舍入、普通文本前后空白丢失；实现后 GREEN。
- 扩展边界测试发现 Foundation 接受尾逗号，已显式拒绝格式化，保留原始不完整文本。
- 独立审查发现超长元数据转换前无限制、旧二进制类型回退缺失；已补 RED/GREEN。40 KB Header 保留有界前缀；十万个查询参数的测试由全量转换约 0.408 秒降至有界转换约 0.048 秒（单机测试观察，非性能保证）。
- JSON `null` 双向误报空正文另有 RED/GREEN，限定独立复核通过。新增 14 项详情回归，最终 `swift test --package-path macos-native` 报告 179 项、24 suites 通过；1 项既有条件实链路测试跳过，未冒充实际设备验收。最终耗时 7.119 秒；日志 `/tmp/capture-detail-ux-20261105/swift-tests.log`。
- Release 构建 14.11 秒通过；独立 `/tmp/capture-detail-ux-20261105/抓包详情验收.app` 严格签名通过。没有覆盖运行中的 bundle。
- 隔离只读 loopback fixture（53671）与原生窗口已验证 Request 参数/重复 Headers/嵌套 Body、Response 状态/重复 Cookie/嵌套数组/数字、表单分行、cURL、4 MB 声明正文的受限预览、二进制、暂无响应及 204 空正文。Cmd+A/C 后粘贴到合成搜索框，核对参数、头和完整正文全部保留；最终构建复核 Request/Response 和二进制无重复提示。
- 自有 app 与 fixture 已退出，53671 无监听。原 7001 PID45594、build541e878-bp4、idle/active_session=null 不变，原应用严格签名仍通过。未操作手机、VPN、原节点或配置。
- 使用说明已同步；仅本地修改和任务提交，未推送或更新 GitHub 安装包。

# 前台应用驱动抓包流程规格

## 1. 目标

把桌面端主流程改为：

```text
选择设备 -> 安装 App（可选）-> 用户打开 App -> 自动识别前台目标 -> 自动准入检查 -> 开始抓包 -> 实时确认流量
```

APK 来源与抓包目标完全解耦：

- Jenkins 负责列出、下载并安装测试构建。
- 本地 APK 入口负责把用户选择的 APK 安装到当前设备。
- 用户通过其他工具预先安装的 App 也必须可用。
- 抓包目标始终以当前设备实际处于前台的 App 为准，而不是以 Jenkins 选项或历史应用库选项为准。

## 2. 方案评审

### 方案 A：继续要求用户从应用库选择

改动最小，但手动安装的 App 仍需先添加记录，无法满足“打开即可检测”，不采用。

### 方案 B：前台 App 自动识别并幂等登记（采用）

桌面端轻量轮询当前前台组件；包名变化后调用解析接口。后端校验包已安装、解析可启动 Activity、复用或创建应用记录，并返回 readiness。该方案复用现有 `app_id` Session 模型和 `auto` 模式，改动边界清晰。

### 方案 C：完全移除应用记录，Session 直接接收包名

短期看更直接，但会破坏版本、历史、最近成功模式、Logcat 和设备应用状态关联，需要大规模迁移，不采用。

## 3. 后端设计

新增独立前台目标解析模块，避免继续扩大 `capture_console/app.py`：

- 从 `dumpsys activity activities` 或现有窗口状态中解析当前 resumed component。
- 校验包名确实安装在指定设备上。
- 使用 `cmd package resolve-activity --brief` 补全 Activity。
- 读取版本和 installer 信息；无法可靠获取应用名称时使用包名，不伪造名称。
- Launcher、System UI、锁屏等系统界面返回 `no_target`，不自动登记为业务 App。
- 已存在包名时复用应用记录，并保留其 `environment`、最近成功模式和备注。
- 未知包名按 `environment=production`、`default_mode=auto` 幂等创建，并标记来源为前台自动发现。

新增接口：

- `GET /api/devices/{device_id}/foreground-app`：轻量读取当前前台组件，不产生数据库写入。
- `POST /api/devices/{device_id}/foreground-target/resolve`：解析、登记或复用当前 App，并返回应用、设备版本和 readiness。

错误状态使用稳定枚举：

- `device_offline`
- `device_locked`
- `no_target`
- `package_missing`
- `ready`

响应中的捕获状态分为：

- `detected`：已识别 App，但尚未启动抓包。
- `ready`：环境和抓包链路准入通过。
- `waiting_traffic`：Session 已运行，尚未捕获目标流量。
- `capturable`：当前 Session 已捕获至少一条目标接口。
- `blocked`：Frida、网络、端口、解锁或包状态阻止抓包。

## 4. 桌面端设计

“抓包”页移除 Jenkins 包作为目标应用的 Picker，改为“当前前台应用”状态卡：

- 每 2 秒轻量检查所选设备的前台组件。
- 包名发生变化时才调用 resolve，避免重复执行完整健康检查。
- 显示应用名或包名、Activity、版本、识别状态和抓包状态。
- 没有目标时提示“请在设备中打开需要分析的 App”。
- 已识别且准入通过时启用“开始抓包”。
- 抓包运行后继续轮询 readiness；捕获到接口时显示绿色“已验证可抓包”。
- App 未产生请求时显示橙色“抓包运行中，请操作 App 触发网络请求”。
- 活动 Session 与新前台 App 不一致时不自动停止或切换，提示先停止当前 Session，避免丢失历史和误清理链路。

“设备与应用”页保留 Jenkins 安装列表，并增加“选择本地 APK”入口：

- Jenkins 安装完成只提示安装结果，不自动成为抓包目标。
- 本地 APK 默认登记为生产包；测试包继续优先从 Jenkins 获取。
- 用户在 Android Studio、ADB 或其他工具中安装的 APK 无需导入桌面端，只需打开即可识别。

## 5. 状态与数据边界

- 应用库继续作为包名、版本、历史模式和 Session 关联的内部索引，不再要求用户手动维护。
- 自动发现不得覆盖已有应用的人类名称、环境、备注或最近成功模式；只补齐缺失 Activity/版本。
- Session 启动仍使用现有 `app_id + device_id + mode=auto` API。
- 同一设备仍只允许一个 active Session。
- 前台轮询不得启动 Frida、修改代理或创建 Session；这些动作只在用户点击“开始抓包”后执行。
- 不修改抓包底层脚本，不执行 `uninstall`、`pm clear`、`wipe-data`。

## 6. 验收

### 后端自动化

- 能解析常见 `topResumedActivity`、`mResumedActivity` 和窗口组件格式。
- Launcher、System UI、锁屏返回 `no_target`。
- 未登记但已安装的 App 会创建 `default_mode=auto` 记录。
- 已登记 App 被识别时保留名称、环境和最近成功模式。
- 设备离线、锁屏、包不存在返回明确 4xx/状态，不创建错误记录。
- 当前 Session 有流量时返回 `capturable`，无流量时返回 `waiting_traffic`。

### Swift 自动化

- 前台组件未变化时不重复 resolve。
- 前台 App 变化时更新当前目标和按钮状态。
- active Session 与当前前台包不一致时阻止自动切换并显示提示。
- 本地 APK 选择、上传状态和失败文案可测试。

### 真实验收

- 使用外部 ADB 安装一个未登记 APK，打开后桌面端 5 秒内识别包名和 Activity。
- 从 Jenkins 安装一个 APK，打开后无需再次从列表选择即可开始抓包。
- 启动抓包后，未操作 App 时显示等待状态；触发网络请求后显示可抓包并在接口页出现 flow。
- 停止 Session 后代理、Frida hook、exporter 和端口按现有规则清理。

## 7. 明确不做

- 不声称 readiness 通过就代表所有接口一定可解密。
- 不自动停止当前 App 的 Session 并切换到另一个前台 App。
- 不自动 Root 真机或模拟器。
- 不支持本轮 iOS、Windows、Linux 和 split APK 本地选择器。

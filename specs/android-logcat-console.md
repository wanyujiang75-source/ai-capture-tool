# Android Logcat 桌面控制台规格

## 目标

在原生 macOS 桌面端左侧现有“日志”Tab 中提供接近 Xcode Console 的 Android 运行日志体验。用户无需打开 Android Studio 或终端；选择设备和应用后，页面自动开始读取 Logcat，并可在“应用 / 系统 / 崩溃”三种来源之间切换。

## 用户界面

- 左侧栏继续使用现有“日志”入口，不新增重复导航项。
- 页面顶部展示设备选择、应用选择、连接状态和当前日志来源。
- 使用三段式切换：
  - `应用`：只读取当前目标应用 PID 的日志。
  - `系统`：读取当前设备主 Logcat 缓冲区。
  - `崩溃`：读取当前设备 `crash` 缓冲区。
- 工具栏提供：暂停/继续、清空当前视图、关键字搜索、最低日志级别、自动滚动。
- 每条日志展示精确到毫秒的时间、级别、PID/TID、Tag 和消息。级别使用克制的颜色区分：Verbose/Debug 灰色、Info 默认色、Warn 橙色、Error/Fatal 红色。
- 默认进入“应用”来源。设备在线且应用已选择时自动启动；应用尚未运行时显示“等待应用启动”，应用进程出现后自动接入，无需重复点击。
- 页面明确提示“日志仅保存在本机内存，可能包含敏感调试信息”。

## 后端架构

新增独立 `LogcatService`，不把长生命周期进程管理继续塞入 `capture_console/app.py` 或 `ConsoleRunner`。

- 每个 `device_id` 最多保留一个活动 Logcat 会话。
- 切换来源、包名或设备时，只停止对应设备的旧会话，不影响其他设备。
- 应用来源先执行 `pidof -s <package>`，成功后启动：
  - `adb -s <serial> logcat --pid <pid> -v threadtime`
- 系统来源启动：
  - `adb -s <serial> logcat -v threadtime`
- 崩溃来源启动：
  - `adb -s <serial> logcat -b crash -v threadtime`
- 应用进程不存在时会话进入 `waiting_app`，每秒重新解析 PID；应用重启导致 PID 改变时自动重新接入。
- Reader 线程将输出解析为结构化 `LogcatEntry`，原始无法解析的行仍作为 `raw` 消息保留。
- 每台设备使用单调递增 cursor；缓冲区最多保留 5,000 条或 2 MiB，先到上限者生效。
- 客户端超过 30 秒没有轮询时自动停止对应 `adb logcat` 子进程。
- 后端退出、设备释放、系统休眠时停止相关 Logcat 会话。
- V1 不把日志写入 SQLite、抓包目录或普通文件。

## API

### 启动或切换日志

`POST /api/devices/{device_id}/logcat/start`

```json
{
  "source": "app",
  "package_name": "com.example.app"
}
```

`source` 只允许 `app`、`system`、`crash`。`app` 必须提供符合 Android 包名格式的 `package_name`；另外两种来源忽略该字段。

### 增量读取

`GET /api/devices/{device_id}/logcat?after=120&limit=500`

```json
{
  "device_id": "device-1",
  "source": "app",
  "state": "streaming",
  "package_name": "com.example.app",
  "next_cursor": 124,
  "truncated": false,
  "entries": [
    {
      "cursor": 121,
      "timestamp": "08-11 15:24:01.337",
      "pid": 2468,
      "tid": 2501,
      "level": "E",
      "tag": "flutter",
      "message": "example message",
      "raw": ""
    }
  ]
}
```

如果 `after` 已早于当前缓冲区最小 cursor，返回 `truncated=true`，桌面端提示较早日志已因内存限制丢弃。

### 控制接口

- `POST /api/devices/{device_id}/logcat/clear`：只丢弃本工具内存缓冲，cursor 保持单调递增。
- `POST /api/devices/{device_id}/logcat/stop`：停止该设备日志进程并释放资源。

设备不存在返回 `404`；设备未在线返回 `409`；参数错误返回 `422`。命令全部使用参数数组执行，不拼接 Shell 字符串。

## 桌面端数据流

- 新增 `LogcatController`，独立维护日志状态，避免继续扩大通用 `AppState`。
- `LogsView` 从 `AppState` 读取当前设备和应用选择，并把变化传给 `LogcatController`。
- 启动成功后每 750 毫秒按 cursor 增量读取一次。
- 暂停时界面冻结，但每 5 秒继续轮询作为会话心跳，并把增量放入有界 `pendingEntries`；继续时一次性合并暂存日志。这样长时间暂停不会触发 30 秒孤儿回收，也不会丢失暂停期间的日志。
- 切换设备、应用或来源时取消旧轮询任务，调用旧设备 stop，然后启动新配置。
- 离开“日志”页时停止轮询；后端 30 秒 TTL 负责兜底释放。
- 搜索和级别过滤在 Swift 客户端对当前有界缓冲执行，不额外请求后端。

## 安全与资源边界

- 日志可能包含 Token、账号标识和业务数据，仅在本机内存展示。
- 不提供日志上传、云同步或默认导出。
- “清空”不执行 `adb logcat -c`，避免影响 Android Studio 或其他调试工具。
- 不依赖 Frida，因此 Frida 不可用时仍能查看 Logcat。
- 不启动、停止或修改不属于当前 `device_id` 的模拟器和进程。

## 验收标准

- 左侧“日志”Tab 不再显示占位文案。
- 目标 App 已运行时，应用日志在 2 秒内出现；App 重启后自动重新接入新 PID。
- 系统与崩溃来源使用正确 Logcat 缓冲区，切换时无重复后台进程。
- 暂停、继续、清空、搜索、级别过滤和自动滚动行为符合界面文案；暂停超过 30 秒后继续仍能恢复该会话。
- 5,000 条/2 MiB 边界和 `truncated` 提示有自动化测试。
- 设备离线、应用未运行、ADB 断开都有明确状态，不展示原始 JSON 错误。
- 离开页面 30 秒、释放设备或退出后端后，无该设备残留 `adb logcat` 进程。
- Python、Swift 和最终 `.app` 构建测试通过。

## 非目标

- 不实现 Windows/Linux/iOS 日志。
- 不实现日志文件持久化、云端检索或团队共享。
- 不解析 Flutter DevTools Timeline、性能火焰图或 Android Perfetto。
- 不在 V1 增加正则表达式、高亮规则编辑器或日志导出格式配置。

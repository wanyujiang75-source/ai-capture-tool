# BP-1 引擎与控制契约

基线27f5c6a，2026-11-04。只实施既定计划BP-1，不接真实传输，不修改运行中的桌面、手机或VPN。

## 设计

- Engine绑定一个capture/device/epoch，在所属事件循环串行处理无await的状态变更；只有等待决策是异步。默认关闭，5秒租约过期关闭，不因恢复心跳自动启用。使用可注入单调时钟及独立定时任务，不依赖UI轮询触发过期。
- 规则最多100、当前规则表JSON编码总量512KiB，避免状态响应越过控制帧上限；超限创建/更新均不修改原表。按顺序分别选择请求/响应阶段第一条可用规则；同flow预留单次规则，进入暂停才消耗。更新规则创建新revision，在途保留旧快照。精确origin规范化，路径不含query；匹配不修改任何路由。可信adapter标记recording/system，未录制或内部请求直接旁路。
- 20个flow名额覆盖收集、暂停、应用决策及等待响应。预算16MiB，编码/解码各256KiB，adapter必须先申请再分配。头200项/64KiB、URL8KiB；编辑副本也记预算。大包、二进制、流式和未支持协议旁路，BP-0适配本阶段不装载。
- 独立阶段ID、revision、事件和不可变原始/有效消息。resolve仅选择决策，状态applying；adapter取决策后ack才结算，不能把接受编辑称为送达。applying最长3秒，未确认回收并标记disconnected；已断连等待者不能获取旧编辑。操作去重记录最多256条/300秒，包含指令指纹；operation_id必须为`{pending_id}.{随机后缀}`，总长不超过128，限定ASCII字母/数字/点/下划线/减号。复用ID换内容拒绝；缓存淘汰后也不能将旧ID绑定新阶段。
- 请求决定后仍为双阶段保留名额；响应匹配使用原请求快照。等待响应最长60秒，避免无回调永久占用。禁用/失联释放已完成正文的暂停，收集中保留截止或完成后原样继续；停止/所属进程退出最多3秒有限排空，之后显式断连，不假称全部透传。
- 本地API不直接持有Flow。API工厂只接受loopback、无浏览器Origin和Bearer桌面令牌；每次请求必须提供device/epoch。仅已注册的capture路由到固定UDS客户端，不接受文件路径或任意命令。每个worker独立令牌，不能以桌面令牌越过worker认证。
- UDS位于新建0700私有目录、socket0600；长度前缀JSON，每帧1MiB，读写/连接3秒、关闭缓冲最多1秒，超时abort自有transport，最多8并发连接，单连接单命令。白名单命令、version=1、目标一致；错误无原始payload/正文/凭据。关闭先禁止接受连接、停止引擎有限排空，再取消控制任务和等待server退出；不把wait_closed放在排空前。仅回收inode匹配的自有资源。Windows不创建UDS，明确不支持（产品V1是macOS）。
- API与IPC共享control分派和严格schema。GET列表最多50条有界摘要，不包含query、认证头或正文；选中项才能获取正文。JSON/UTF-8/form校验，同源URL、重复Header顺序、受管运输头不可改、HEAD/204/304语义；正文修改清除失效完整性字段。无效patch不改变revision/期限/预算。

## 接线契约（BP-2）

- `create_control_app({capture_id: WorkerClient(...)}, desktop_token)`仅创建独立FastAPI应用，未挂载产品。由后续监督器在loopback托管，禁止开放到LAN；每次桌面生命周期生成独立随机令牌，不使用worker令牌或URL参数承载认证。
- HTTP请求头为`Authorization: Bearer <desktop_token>`、`X-Device-ID`、`X-Breakpoint-Epoch`。目标注册表固定、不可由客户端选择socket路径。返回`transport_attached=false`，enabled仅为引擎状态，不表示实际抓包已启用断点。
- UDS信封为`version/token/capture_id/device_id/epoch/command/payload`，4字节大端长度后接UTF-8 JSON。rule命令对应`id/expected_revision/rule`；resolve对应`id/operation_id/expected_revision/action/patch`。action仅apply/original/abort；其他schema字段禁止附加。stop仅供监督器IPC调用，不添加未经设计的HTTP路由。
- adapter须在实际转发前以元数据调用admit/response；按编码/解码累计字节先reserve，再分配/收集；失败立即走原链路旁路，不交付截断正文。大包/二进制/流式/不支持协议本阶段不支持头暂停；可编辑性由可信adapter确定。原文不变的编辑必须复用同一bytes引用。
- 正文完整后pause并等待wait；拿到决策后，在所属事件循环**不插入await**地应用到实际流并ack（错误则disconnect或失败ack）。ack只确认传输层接收了动作，不是源站或客户端已收到；后续归档仍须使用真实传输结果。暂停或收集中等待者收到abort/410必须回收实际流，不能继续发送旧编辑。网络取消/背压依赖BP-2适配，不由本阶段状态回收冒充完成。
- 列表cursor是进入可见状态的单调序号，删除前页项不挪动后页位置。release-all关闭未来命中，逐flow返回collecting/applying/ended；collecting仍等完成或原收集截止，不伪称已放行。等待者取消不自动撤销UI暂停，仍由暂停/租约/停止期限兜底。
- 16MiB为正文及编辑元数据预留预算，不是整个Python进程RSS上限。当前规则表单独512KiB，20个在途流还最多引用40个旧规则对象；控制输入并发8、每帧1MiB，终态缓存只保留无正文的结果。真实传输和整体RSS须在BP-2继续组合验收。

## 验收

1. 引擎：origin、顺序、单次占用/归还、双阶段路径修改仍命中、版本快照；预算、慢正文/空数据、租约、停止、断连及同时resolve唯一决策；原始消息不可变、无效编辑与重试。
2. 控制：真实UDS认证/世代/设备/版本/未知命令/过大帧/慢客户端/并发上限/回收；独立loopback API贯穿UDS到引擎，未授权/跨Origin/目标错误不能读正文或决策，错误无秘密。
3. 既有37项回归、BP-0严格36项；产品源码和运行服务前后只读状态一致。不开启真实抓包，不构建或发布。

## 证据

过程记录：新模块缺失的初始RED后，基础23项通过。补边界测试明确复现5项失败：未确认决策永久占用、断连旧编辑仍被取走、失败ack记成已继续、分页删项漏项、端口0被当默认端口。修复后29项通过。增加UDS慢客户端/8连接上限/旧身份拒绝/自有资源清理，10项中1项复现启动失败遗留私有目录，补所有权清理后通过。测试夹具曾因过长Pydantic参数、插入位置语法错误和过大HTTP请求的连接重置失败，已修正，未作为产品缺陷或通过证据。

后续RED/GREEN：实际UDS不读详情客户端令旧close超过5秒；非法form被接受；等值正文未复用；二进制误暂停；未领取即可ack；淘汰操作ID跨阶段复用，均补失败测试后修复。再复现大规则表状态frame_too_large、release-all漏报告非paused流、清空JSON正文转换204被误拒绝，已修复。测试曾引用未安装httpx，改为直接ASGI边界测试，未新增依赖。

最终结果：BP-1 DONE，53项11.691秒通过；包括真实loopback HTTP→UDS→engine、单独Python worker进程及退出、慢发送/不读取/分块输入/认证/世代/容量/幂等/资源回收。既有37项回归0.861秒通过，只有既有FastAPI on_event弃用警告。BP-0严格36项47.367秒通过：100MiB额外RSS约2.6–4.5MiB、20路20.7MiB，保持64MiB门槛和字节哈希；压缩扩张8.3MiB。不是三套集成到生产后的验收。两组独立静态复核未发现已修复范围残余P1/P2；53项通过后仅更新文档，未修改实现与依赖。

验收命令（Python为本机既有`.venv-console/bin/python`，不新增依赖）：

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest tests.test_breakpoint_engine tests.test_breakpoint_ipc tests.test_breakpoint_api -q
env -u CAPTURE_DEVICES_CONFIG -u TRACEDECK_CONFIG CAPTURE_RUNTIME_DIR=<新临时目录> PYTHONDONTWRITEBYTECODE=1 python -m unittest tests.test_ios_capture tests.test_ios_results tests.test_ios_lifecycle tests.test_exporter_timing tests.test_flow_summary_types -q
CAPTURE_TEST_BREAKPOINT_TRANSPORT=1 CAPTURE_REQUIRE_BP0_SAFE=1 PYTHONDONTWRITEBYTECODE=1 python -m unittest tests.test_breakpoint_guard -q
```

只读复核7001前后均`be6d0543b498 / running / idle / active_session=null`。既有产品入口/runner/iOS代理/exporter没有breakpoints导入或路由，自有测试worker进程枚举为空；回归临时数据库及目录已回收。初次静态扫描误用了不存在的`mitm_exporter.py`路径，改为实际`ai_capture_export.py`重查无匹配。未改依赖、手机、VPN、原配置或实际运行数据，未构建/推送/发包。后续BP-2仍需真实传输接入、归档/全局配额和退出组合验收，不把本次合成控制验收当作真机或桌面UI验证。

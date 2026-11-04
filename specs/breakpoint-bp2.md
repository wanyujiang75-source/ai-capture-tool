# BP-2 真实转发与归档

## 范围与隔离

- 显式 `CAPTURE_BREAKPOINTS=1` 才装载适配；引擎仍须认证 enable，默认为关闭。关闭功能开关时保持原抓包路径。
- 仅本机独立测试进程、临时 CA 和 loopback 端口；不操作实际设备、VPN、系统网络、原配置和运行服务。
- BP-3 桌面交互、远端发布、安装包更新不属于本轮。

## 接入约束

- Android regular/SOCKS 和 iOS 使用相同 addon/engine；生产代码不导入 tests。
- 已验证的 BP-0 传输保护提升为产品实例级实现，固定依赖版本准入，保持原严格矩阵作为回归。
- 正文进入暂停前完成 encoded/decoded 配额；不可编辑、大包、流式内容原样通过。收集、暂停、应用及退出均有期限。
- 控制目标绑定本次 capture/device/epoch；私有 UDS、令牌和描述文件；不通过公共状态暴露凭据。
- 停止先禁新命中并收敛等待，再关闭归档/连接；iOS 停止记录与断开代理继续分离。

## 归档约束

- 保存原始与实际采用的版本；effective 不代表送达或业务成功。
- 原正文与有效正文相同则引用共享；空正文、仅 URL/header/status 改写也保留原信息。
- 存储受限；iOS 不重复追加，Android 不导出尚待决策的快照。老记录无新字段仍可读取。
- cURL 使用有效版本；终止不得伪造成功响应。同一 flow 不生成两条可见记录。

## 验收

1. 新 `tests.test_breakpoint_adapters`、`tests.test_breakpoint_archive` 与生命周期用例先 RED 后 GREEN。
2. 真实 regular/SOCKS/iOS 认证链路的请求/响应修改，对照 origin/client/磁盘/cURL；默认关闭、原样、取消和停止。
3. BP-1 引擎/IPC/API 和 BP-0 严格传输矩阵；已有 iOS capture/results/lifecycle、exporter timing、flow summary 回归。
4. 检查 diff、独立复核、自有进程与文件清理、原服务状态只读对照。本地提交，不发布。

## 过程证据

首批 4 项预期 RED（模块未实现）后 GREEN；连同 BP-1 共57项11.690秒通过。

真实链路首轮12项47.139秒失败：未知长度越界时在父层直接驱动stream产生未注册的连接命令；改为实例 GuardStream 在自身 check_body_size 内切换流式并保留归档回调。另双阶段夹具重复Content-Type造成候选被排除，纠正夹具而非放宽生产判定。修正后 regular/SOCKS/iOS 共12项18.716秒通过。既有37项0.894秒通过。

本轮保守边界：Brotli 不开放正文断点，原字节流式通过；其output_buffer_limit不能严格约束分配，不能以BP-0可解码实验冒充生产准入。gzip/deflate与identity继续有界验收。所有临时端口/证书均仅测试使用。

## 接线实现与读取兼容

- Android 显式启用时，每轮生成私有 launch 配置，使用已有 owned-process 重启路径，不复用没有对应 worker 的旧代理；启动等待 worker 描述文件。停止脚本使用后端同一 Python，发出认证 stop 后最多等待4.2秒，超时仍只进入既有自有进程停止路径。
- iOS 保留手机认证、连接检查、录制范围及停止后透传机制；仅 opt-in recording 子类使用断点运行时，每次录制重新生成 epoch，不继承规则。没有改变证书、VPN、上游或手机配置生成逻辑。
- 两端 opt-in 使用同一受限 SQLite/正文归档，Android exporter 不再提前冻结尚待决策的 mitmweb 快照。带 `breakpoint-archive.json` 标记的 Android 记录走新读取器，旧 TSV/JSON 与 iOS 旧记录继续可读。
- 新归档保留每个阶段 original/effective 元数据、正文摘要与文件引用；`adopted` 只表示代理采用的版本，`delivered=false` 不声称手机/源站已收到。正常详情/cURL 使用有效内容；正文不完整或终止返回409，不生成误导性重放。
- 发送停止时，先关闭新命中、释放等待，再等待真实 flow 及 H2 DATA/END_STREAM、writer 缓冲排空；3秒宽限结束后关闭所属传输。不同调用者等待同一个 shield 关闭任务，不因重复停止提前返回。
- 控制 API 仅在功能开关开启时挂载；桌面 token、worker 描述文件0600且不进入公开导出清单。可信 store 解析 capture，UDS进一步校验 capture/device/epoch。无有效录制目标或 worker 已退出时明确拒绝。

## 复核修复记录

首轮完整27项真实链路39.394秒及249项原有回归7.303秒通过，但不作为最终完成证据。两个只读复核分别发现：停止只看决策ACK、H2 RST单流取消、并发关闭、regular代理复用、迟到trailer；以及短写哈希文件、配额后其他等待未收敛、动态分页重复、Android cURL异常状态。新增边界11项中8失败1错误后修复，11项3.511秒通过。迟到trailer原样通过，不带着旧校验值改正文；归档正文使用临时文件原子发布，现有文件校验类型/长度/摘要。

停止慢响应夹具最初将gate放在H1正文之后，Content-Length满足时HTTP实际已结束，不能当作慢响应证据；改为源站发headers之前等待。真实链路扩为33项102.004秒通过，regular/SOCKS使用实际AndroidBreakpoints启动钩子；100MiB H1/H2归档透传额外峰值内存分别约6.19/5.65/4.88 MB，哈希完整。

第二轮复核进一步发现flow_done时H2发送队列可能未空，以及stop回执异常会漏调cleanup。真实H2小窗口与UDS回执注入两项RED后修复，2项1.173秒通过。归档与生命周期最终限定只读复核无剩余P1/P2；不把静态复核替代真实链路验收。

另补压缩响应改为204的RED：gzip空正文仍有20字节，改为无正文语义清理原始字节及传输编码；单测与真实传输、H2客户端到H1源站混合协议3项1.878秒通过。

## 可复现命令

所有命令在本工作树执行，Python使用项目`.venv-console/bin/python`，设置`PYTHONDONTWRITEBYTECODE=1`。

```sh
python -m unittest tests.test_breakpoint_engine tests.test_breakpoint_ipc tests.test_breakpoint_api tests.test_breakpoint_adapters tests.test_breakpoint_archive tests.test_breakpoint_lifecycle tests.test_breakpoint_boundaries -q
CAPTURE_TEST_BREAKPOINT_TRANSPORT=1 python -m unittest tests.test_breakpoint_integration -q
CAPTURE_TEST_BREAKPOINT_TRANSPORT=1 python -m unittest tests.test_breakpoint_guard -q
# 必须指定新建的独立临时目录；不指向已有运行数据。
env -u CAPTURE_DEVICES_CONFIG -u TRACEDECK_CONFIG CAPTURE_RUNTIME_DIR=/tmp/<isolated-bp2-runtime> python -m unittest tests.test_console_api tests.test_console_core tests.test_ios_setup tests.test_ios_capture tests.test_ios_results tests.test_ios_lifecycle tests.test_exporter_timing tests.test_flow_summary_types -q
```

真实集成套件包含：regular/SOCKS/iOS认证模式、双阶段改写、HTTP后端→动态目标→UDS→真实代理→源站/客户端/归档、默认关闭、原样放行、终止、RST、客户端断开、慢正文取消、停止收集中/等待响应/H2发送缓冲、gzip/deflate、压缩膨胀/Brotli降级、204无正文、H2到H1、100MiB响应与配额截断。脚本加载和owner失效清理使用独立mitmdump进程，不使用用户设备。

## 当前限制

- 本阶段不是桌面可点击断点功能，仍须BP-3接入编辑与待处理队列。开关默认关闭，没有升级正在运行的桌面端或安装包。
- 未操作真实Android/iPhone，本轮证据是产品适配器的隔离网络验收；不能声称所有真实应用/证书绑定均支持。
- 不支持H3、二进制、SSE/无限流或大包正文编辑；Brotli与有trailers的消息降级为原样通过。H1/H2适配固定依赖版本，版本不符拒绝开启，不修改已安装依赖。
- 3秒排空不是无限慢网络的送达保证；超时明确结束所属连接，不承诺停止后仍完成所有请求。完整录制正文保存上限沿用8MiB，断点可编辑正文上限256KiB。

## 最终验收结果（2026-11-04）

- 引擎/UDS/API/adapter/archive/lifecycle/boundaries：73项，16.451秒，通过。
- 产品真实链路：45项，108.923秒，通过。100MiB响应H1/H2，额外峰值RSS：iOS 5,701,632 bytes、regular 6,111,232 bytes、SOCKS 5,177,344 bytes，均小于64MiB；哈希与源正文一致。
- 生产guard的BP-0严格回归：36项，49.087秒，通过。20并发慢消费者额外RSS22,282,240 bytes；未命中p95关闭19.35ms、开启18.32ms；包含100MiB上传/下载、TLS等待、GOAWAY/信用与RST、慢正文绝对/空闲取消。
- 原有backend/core/iOS/exporter/summary：249项，8.632秒，通过；后续只改opt-in addon/guard/IPC和新测试，对该默认关闭证据无影响。总计403项，全部完成且无跳过。
- 4个修改的shell脚本`bash -n`通过，29个修改Python文件AST解析通过，`git diff --check`通过。
- 两组限定独立复核无剩余P1/P2；检查发现及RED过程均在上文保留，不隐藏失败。
- 现有7001服务前后均为`be6d0543b498 / running / idle / active_session=null`；无服务重启或设备操作。测试自有代理正常退出并验证socket/描述文件移除，未发现遗留测试worker；主工作区的用户未跟踪文档保持原样。

交付仅BP-2本地源码与验收记录；BP-3未领取，未合并、推送或打包发布。

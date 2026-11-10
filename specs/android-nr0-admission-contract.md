# NR-0 准入契约实施范围

本轮仅实现无I/O的进程内模型；不调用ADB、不读私有数据、不创建代理、不接入生产API。不把模型测试或模拟证据作为真机解密成功。真实哈希/签名收集、可信适配器业务证明、并发控制、资源所有权持久日志及桌面接入留给后续阶段。

## 输入与可信边界

- CaptureIdentity：设备、Android用户、包名/版本、当前签名SHA-256、签名轮换链、全部APK名称/摘要、系统指纹、引擎版本、路线、ADB连接代次、端点/CA或密钥来源的公有身份、VPN可观测连接代次。
- 使用不可变对象；必填缺失、非法标识、非SHA-256、重复APK名称、缺base.apk等拒绝。签名/APK集合规范排序，轮换链保留顺序。端点采用摘要，不接受带凭据的URL。身份只是已收集证据的合同，不通过语法校验宣称原版真实性。
- Candidate：已验证机制标识、路线、对应授权及资源有界条件。默认不成立；没有原版正文不阻止其成为候选，但仅ADB在线或已装CA不能产生候选。
- AP-0 inspection：检查精确serial、physical、连接状态、VPN transport可观测、boot、Android用户、包名/版本/APK清单和问题列表。VPN不可确认时不准入；不将transport存在视为已经核对了原VPN私有节点。既有no_verified_capture_path不是阻止首次试验的错误，其余采集缺失、用户不支持等问题必须阻断。AP-0不会自动构造完整CaptureIdentity。
- 真实采集适配器后续提供本probe_id下已关联的业务请求与响应完整度。此接口仅供可信本机代码使用，不接受网络请求中的布尔值来伪造通过；业务完整度不要求请求一定有正文，合法无正文也可完整。NR-0不实现采集或自行证明这些输入真实。

## 状态及时间

AdmissionGate.check根据新快照返回probe_available/verified/needs_action/blocked/recovery_required等决策，绝不执行外部动作。begin_probe在合格候选上生成本实例唯一probe_id。observe仅接受当前正在验证的probe_id；默认120秒/20事务内允许不完整证据继续等待，完整业务证据到达后先进入stopping，不立即启用采集。

stop(cleanup_confirmed=True)确认本轮清理后才使待通过证据成为verified；失败进入recovery_required并废弃待通过证据。取消、失败、超时、预算用尽均不得产生成功证据。重复停止幂等；NR-0只记录恢复状态，不实现清理动作或把外部清理当已执行。

start_recording必须重新提交AP-0快照、完整身份及候选，内部重新检查后才允许进入recording。完整身份或候选变化、连接丢失、TLS/链路显式失败使活动状态进入stopping；完成清理后才能重试。当前实例不保存成功证据到文件，另一个Gate实例不能复用旧probe_id或结果。

使用注入的单调时钟。证明在观测完整业务时计时，10分钟内允许首次启动；清理不能刷新有效期。正在recording不因单纯时间到期中断。时间回退/非有限值拒绝并使证据失效；适配器需在运行时定期调用检查，NR-0不创建定时线程。长时间休眠、断线和并发资源互斥的真实实现/验证在NR-2/NR-3完成。

## 验收

```bash
python3 -m unittest -v tests.test_android_physical_capabilities tests.test_android_capture_admission
git diff --check
```

测试用模拟AP-0和假时钟，外部命令边界仅运行自有Python夹具；不运行真机ADB。覆盖新设备、无候选、未授权、多设备定向、缺包/身份、同版本重签、split变化、端点/CA/连接变化、证据过期、重启实例、旧probe_id、取消/超时、20事务、恢复失败和重复停止。没有新增API、GUI或打包变化，不执行桌面构建/替换。

## 本轮验证记录

- 初次RED：24项因准入模块尚不存在而按断言失败。
- 追加边界用例先复现：清理期间身份变化仍保留待通过证据、异常时钟丢失恢复状态、重复清理确认丢失有效证据、畸形嵌套输入异常、VPN未知仍获准入。修复后复验，无忽略失败。
- 最终命令：`python3 -m unittest -v tests.test_android_physical_capabilities tests.test_android_capture_admission tests.test_logcat_service`，61项通过，8.287秒；其中准入29项、AP-0 16项、日志16项。
- `python3 -m py_compile capture_console/android_capture_admission.py tests/test_android_capture_admission.py tests/test_android_physical_capabilities.py` 与 `git diff --check` 通过。
- 未运行全仓测试、Swift构建或真机抓包；模块未接入既有产品启动链路，无真机业务解密成功结论。没有运行ADB实机命令、改动VPN、证书、原包或当前桌面服务。

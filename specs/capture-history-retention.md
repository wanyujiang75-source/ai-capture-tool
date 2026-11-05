# 抓包历史自动保留七次

## 规则

- Android/iPhone 共用最近7次已结束(stopped)/失败(failed)记录，按全局递增编号倒序。启动中、抓包中、停止中及未知状态不自动删除。
- 终态写入后、后端启动状态恢复后执行清理。启动不再清空所有Android索引，改为标记遗留活动任务中断，统一执行保留策略。正常停止仍先停止写入，再标记终态。
- 数据库删除与文件清理用同一SQLite写事务串行化；先删文件再删索引。删除中断时索引仍在，下次可重试；文件已不存在时允许删除过期索引。失败记录保留并记录warning，不伪装成功，也不令已完成的停止操作失败。
- 只删除console.db同级captures下，由会话登记的web-/ios-独立直接子目录。不跟随符号链接，不清空根目录、不扫描删除未登记目录、不触碰APK/证书/身份/设备/应用/VPN配置。与其他记录路径重叠或别名冲突的目录拒绝删除。
- 当前展示记录若在成功刷新时已从后端消失，清空其列表和详情、返回当前任务，显示说明；刷新失败保留原内容。不再把已删除的历史附加回来源列表。
- 面板说明明确“仅保留最近7次已结束的抓包，较早记录及文件将自动删除”。运行任务不计入七次。

## 验收

1. 临时数据库和真实临时文件验证10条变7条、跨平台合计、活动保护、零到7条、启动恢复、缺文件、路径越界/根/符号链接/共享目录防护、删除失败重试、并发停止/清理。
2. Swift成功刷新移除已删历史、失败不清空和已有竞态/展示测试；后端现有核心/iOS/断点归档相关回归；全套Swift及release构建。
3. 本机清理前只读取候选与活动状态，核对目录确在受管captures内；按用户授权执行同一清理器，核对保留七条及文件摘要、旧目录消失，配置/证书不变。不中断活动抓包，不改VPN；本地版本更新不覆盖运行中的bundle。
4. 记录结果、本地提交；不推送远端或更新下载包。历史FLOW-HISTORY7证据保留，本规则替代其“不删除文件”范围。

## 2026-11-05 验收结果

- TDD：数量、终态和启动保留三项先失败；Swift已删记录复活四个断言、启动/停止中分组两个断言先失败。最终新增11项Python回归覆盖活动保护、并发、重试与删除边界。
- 后端：嵌入Python 3.12.12执行 `-m unittest tests.test_capture_retention tests.test_console_core tests.test_console_api tests.test_ios_lifecycle tests.test_ios_capture tests.test_ios_results tests.test_breakpoint_archive tests.test_breakpoint_lifecycle -q`，238项通过，7.830秒。
- 桌面：`swift test --package-path macos-native`，报告184项/24 suites通过，6.971秒；既有opt-in真实链路测试1项跳过，本次未改断点传输。
- 构建：`CONFIGURATION=release AI_CAPTURE_BUILD_ID=retention7-20261105 macos-native/scripts/build-app.sh` 成功。最终包以 `PYTHONDONTWRITEBYTECODE=1` 和Python `-B` 执行 `tests.test_ios_packaged_lifecycle`，1项包含三轮正常/异常重启通过，4.015秒；启动后 `codesign --verify --deep --strict` 仍通过。
- 验收过程问题：初次用内嵌Python运行测试写入stdlib pyc导致严格签名失败。重新完整构建，禁止测试写pyc后重新执行包装测试及签名检查通过，没有将失败结果算作通过。
- 真实数据：确认无活动抓包后调用同一清理器，数据库11条变7条，删除#80、#79、#78、#77及对应4个独立目录，错误0。保留#87至#81；重启前后275个归档文件和3个身份文件SHA-256全部匹配，应用表dump摘要一致。未登记的旧目录不在自动删除范围，不宣称已清空全部历史磁盘占用。
- 原生验收：正常退出旧版后启动新版，7001返回build_id=retention7-20261105、health=idle、active_session=null；历史页显示最近7次与自动删除说明，刷新仍为7条，搜索#80无结果，清除搜索后#87至#81完整显示，打开#87加载75条请求。
- 本机证据目录：`/tmp/capture-retention7-20261105`，包括python-tests.log、swift-tests.log、packaged-tests.log、keep-before.sha256、identity-before.sha256、apps-before.sha256及expired-paths.txt。日志/抓包内容不入库，不推送远端。本轮未操作手机、VPN、节点、证书信任或原配置。

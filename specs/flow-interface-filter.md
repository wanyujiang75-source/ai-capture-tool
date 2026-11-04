# 接口列表过滤实现与验收

## Goal And Boundary

FLOW-F1在列表搜索框附近提供带筛选图标的“仅看接口”开关，初始关闭。显示过滤数量并提供说明，关闭即恢复全部未清空的记录。Android与iPhone共用，不按项目域名白名单、不改变录制/路由、不删除原始数据，不获取每条正文。不承诺从共享代理准确归属应用，也不能完美区分业务和第三方API；未知请求优先保留。

## Classification Contract

- 只用摘要中的URL/Host/Path/Method/JSON标记及可选request_content_type、response_content_type。
- 精确/子域边界匹配少量专用统计、崩溃、广告服务域名与系统检查地址；不使用Google/Apple/CDN大域名或URL子串匹配，也不直接使用既有过宽kind=noise。
- 隐藏CONNECT、OPTIONS辅助请求；已知统计/探测请求隐藏。
- 保留JSON/XML/表单/GraphQL/gRPC/SSE、非GET/HEAD业务动作及API路径，避免上传返回图片、错误返回HTML被误隐藏；HTTP错误/无响应不是过滤条件。
- 其他GET/HEAD中明确图片/音视频/字体/JS/CSS/HTML或常见静态文件扩展名隐藏；URL查询中的文件名不能误判，JSON文件仍保留；无法判定保留。
- iOS新摘要在headers/finish后更新MIME；旧归档不修改/迁移，缺字段走URL启发式。Android从已有meta summary取得MIME；均规范化并限制长度，不携带完整头或凭据。

## UI And State

筛选和搜索取交集，过滤数基于未清空列表而非搜索结果。无匹配时提示可关闭筛选；列表为空时保留原等待态。筛选/搜索/增量变化使选中项不可见时，清除详情并使进行中的旧详情失效；保留仍可见项。切换不停止轮询，不复活清空记录。所有新增文案集中AppCopy，按钮可键盘操作且有状态可读性。

## Execution

1. 先添加摘要Python测试与分类/状态Swift测试，记录预期失败；不先写实现。
2. 增加纯Swift分类器并扩展filtered的可选模式；两个后端摘要补Content-Type；Swift兼容解码。接入开关、计数、说明、空态及详情失效。
3. 回归`/Users/wan/AI抓包/.venv-console/bin/python -m unittest tests.test_flow_summary_types tests.test_ios_results tests.test_console_core tests.test_console_api`和`swift test --package-path macos-native`。
4. 扩展loopback合成UI夹具提供JSON/API失败/图片/HTML/统计混合记录，构建App，验证全部/过滤/搜索/恢复/无结果/详情更新。只对隔离运行目录操作，不连接真实手机。合成UI不作为真实手机采集证据。
5. 更新使用说明与本记录，diff检查，本地单任务提交；不推送和发包。

## Self Review

保留未知请求比“只认/api/或JSON”少误杀；用户要按钮而非永久删除，故默认关闭且可恢复。规则仍是启发式，说明中明确不是精准业务归属。不会沿用Android的Google/登录相关noise标记，避免过滤认证接口。历史iOS无MIME时存在过滤精度差异但不读取全量正文或更改归档。

## Evidence

- RED：摘要Python测试2项预期失败（缺MIME）；Swift新接口声明补齐后，14项中分类/选择失效共20处预期断言失败。初次Swift编译仅因新增接口尚不存在，未当作行为RED；随后空实现验证真实断言失败。
- GREEN：分类与列表14项（含32组参数化分类边界）通过；Python摘要/iOS/console/core/API共199项通过，另一次iOS相关75项通过（有重叠，不相加计算独立覆盖）；真实隔离HTTPS3项通过。最终Swift全量126项/18 suites/6.869秒通过。
- `AI_CAPTURE_BUILD_ID=77aed99-flow-f1 macos-native/scripts/build-app.sh`成功，生成本地App；构建后及试启动后严格签名均通过。此build ID明确表示基于77aed99的本地增量，不是已发布版本。相关测试日志位于`/tmp/flow-f1-{swift-full,python-regression,ios-regression,tls,build}.log`。
- 合成夹具提供6条API/认证失败/未响应/无扩展名图片/HTML/统计记录，并支持新增请求和全过滤空态，HTTP读取通过。已启动对应隔离App，但两次CUA检查均提示Mac锁屏，不能执行真实点击、视觉或窗口交互验收；不得将编译、合成接口返回或单元测试代替UI通过。
- BLOCKED仅针对剩余原生窗口验收，代码/回归/构建已完成。已终止本轮自有合成App和夹具（PID1567/1476），退出码143、7001无监听；没有操作真实手机、VPN、原运行目录或抓包任务。用户解锁后重新使用独立目录启动夹具，完成全部/过滤/搜索/恢复/无结果/详情与增量验证，方可标记DONE。
- 本轮仅本地保存，不推送、合并或更新已发布安装包。`git diff --check`通过。

### 解锁后补验（2026-11-04）

用户确认解锁后恢复同一FLOW-F1。使用现有`77aed99-flow-f1`本地App、`tests/ios_native_ui_fixture.py`和独立目录`/tmp/flow-f1-ui-20261104-unlocked`，只监听127.0.0.1:7001；没有启动代理/ADB、连接手机、访问业务服务或修改VPN。CUA通过准确App路径选择原生窗口，而非浏览器验收。以下结果由实际点击后的AX状态及窗口截图核对：

| 场景 | 实际结果 |
| --- | --- |
| 初始全部 | 6/6，开关off；API、401认证失败、无响应、图片、网页、统计均显示 |
| 开启筛选 | 3/6，已过滤3条；保留API/401/无响应，隐藏图片/网页/统计 |
| 选中资源再过滤 | 图片详情先可读取，开启筛选后立即回到“选择一个接口查看详情” |
| 搜索叠加 | 筛选开启时搜索401显示1/6，仍为已过滤3条；选中接口的Response详情保留 |
| 无匹配搜索 | 0/6，显示关闭筛选或更换关键词提示，旧详情清除 |
| 恢复全部 | 清空搜索并关闭开关恢复6/6，不删除源数据 |
| 增量轮询 | 合成加入1条API和1张图片，无需点刷新即4/8、已过滤4条 |
| 全过滤空态 | 切换来源重置增量缓存后，3条非接口得到0/3，关闭筛选恢复3/3 |
| 清空后继续 | 原6条清空为0/0；随后两条新记录在筛选开启时1/2，关闭后2/2，旧6条不复活 |
| 详情与慢返回 | 有效项关闭筛选后详情保留；图片详情加载中开启筛选，同步恢复后未重新显示旧图片详情 |
| 服务失败与恢复 | 合成503显示“同步中断”和中文恢复动作，不展示夹具中的原始HTTP409；恢复服务后重新选择接口能读取详情 |

开关在AX中提供角色、on/off值和完整说明；未改变系统全键盘导航偏好。常规Tab从搜索框到列表，未将完整键盘导航记为本轮已通过项。不会用该限制扩大为不相关的系统设置调整。

验收复用证据：`git diff 3f1284f HEAD --name-only -- macos-native/Sources capture_console scripts tests`为空，源码与既有126项Swift、199项Python等记录一致；读取Swift原日志确认126项/18 suites通过。`codesign --verify --deep --strict --verbose=2 macos-native/build/抓包工具.app`再次通过，本轮无需重复构建和重跑未改变代码的整套测试。

清理：原验收App正常退出码0；退出后的CUA读取又唤起同一路径App，核对其PID15200后仅终止该自有实例。夹具PID14379随后退出143；`pgrep`确认无夹具/抓包App，`lsof`确认7001无监听。未留下合成服务占用端口，也没有把合成App当作真实运行环境留给用户。

结论：先前锁屏导致的原生UI验收阻塞已解除，FLOW-F1本地功能验收完成。仅更新本地记录，不推送、不发包；本轮没有增加真机抓包或系统全键盘导航覆盖。

# 桌面操作文案精简

## 设计

- Android真机：保留连接条件、兼容性/15分钟上限、VPN影响和同意项。四步说明只描述用户动作；自动处理细节、Google登录失败处理、Banner判断和断线恢复放入“连接与恢复说明”。技术限制仍在技术详情。按钮名称保持与后端提示一致，取消重复显示终止按钮的帮助段落。
- iPhone：缩短安装、信任、节点导入、转发与恢复说明；明确“发起导入”不等于“已安装/已连接”。VPN保持开启、切换前记录原节点/路由、结束手动恢复、凭据保密不可省略。危险操作确认不弱化。
- 共用接口等待提示使用“设备”，不误指所有平台均为模拟器。安装/日志已简洁的文案不做无意义替换。
- 专业、直接的中文，保留HTTP(S)、VPN、USB、Request/Response等必要名词。无自动成功承诺，无协议/路由行为变化。

## 验收

1. 新增Swift文案约束：主要说明/单步长度限制及VPN、信任、恢复和导入确认关键语义；先观察旧文案超长的RED，再实现。
2. `swift test --package-path macos-native`；Python Android copy与iOS guidance契约测试，必要时调整为等价语义检查，不取消安全断言。
3. 构建独立命名的本地预览，使用环回合成服务验证准备、抓取、连接失败及恢复状态；不触及真实手机、代理或现有运行目录。检查折叠前后、换行、按钮可见与无内容截断。
4. `git diff --check`，只提交本任务，保留其他任务未提交文档。不推送或发包，不重启用户正在试用的稳定版。

## 验收记录

- 旧版Swift约束测试3项中，iPhone测试发现两段超过100字符（131、132），记录RED后修改。
- 最终`swift test --package-path macos-native`：208项通过，包含新增3项；日志`/tmp/operation-copy-swift.log`。
- `.venv-console/bin/python -m unittest tests.test_android_physical_copy tests.test_ios_setup_guidance`：8项通过。最初误用pytest时环境无该模块，已改用项目现有unittest，不安装额外依赖。
- 合成fixture五种Android状态、iPhone说明响应和no-store冒烟通过；新增`--ios-guidance`仅用于预览，不访问真实设备。
- `EMBED_RUNTIME=0 AI_CAPTURE_BUILD_ID=copy-20261115 bash macos-native/scripts/build-app.sh`构建及签名校验通过；这是本地界面验收构建，不是可分发完整运行时安装包。
- 独立bundle与临时运行目录中检查Android初始/准备中/抓包中/失败/恢复，以及iPhone安装、信任、导入和手动恢复步骤。文字换行正常；补充说明可展开；风险提示保持可见。仅使用合成数据，未进行真机或流量验收。
- 独立预览及fixture已退出，Applications稳定版原进程仍在运行。未改手机、VPN、原节点配置，未覆盖稳定版或发布远端。

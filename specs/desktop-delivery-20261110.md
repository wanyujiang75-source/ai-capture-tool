# 2026-11-10 当前分支推送及本机更新

仅DELIVERY-1110，本轮只处理交付，不继续上一轮手机网络恢复，不改产品逻辑。

## 范围与约束

- 复用codex/ios-device-trial工作树。origin为wanyujiang75-source/ai-capture-tool，推送同名分支；不合并main、不发Release、不移动旧标签、不强制推送。
- 固定产品7603b15，源码测试结果与提交一致时复用：后端88、真实隔离代理3、Swift191。正常构建完整release及嵌入运行时，检查新ios_shadowrocket模块/原生二进制、build ID和严格签名。
- 不含未提交的specs/android-copy-capture-trial.md，无APK、真实CA/描述文件、用户配置或钥匙串资料进入包或提交。
- 当前真实运行时/Applications/抓包工具.app，后端7001/build5f70d0db9dc1，iPhone ready/stopped/#90/127。退出会关闭现用测试代理，但保留同Mac身份，重开不会自动抓包。手机原美国节点已选回、路由尚未确认；不靠改手机来完成安装验收。
- 仅正常退出本工具，等托管进程退出后原子移动旧bundle至私有本机备份，复制新bundle到应用程序再启动；若失败可恢复原bundle，不覆盖运行中的程序。7001若由无关进程占用则停止交付排查，不杀无关进程。

## 验收步骤

1. 只读核对远端、当前状态及待推送列表；登记任务。记录当前身份元数据与保留归档文件SHA256，不记录正文/密钥；不将运行时备份纳入仓库。
2. 使用现有构建脚本CONFIGURATION=release、AI_CAPTURE_BUILD_ID固定产品短SHA；独立测试运行目录，运行包内模块/生命周期回归，避免生成文件污染签名目录。签名和新源码摘要复核。
3. 原生桌面正常退出，确认原进程/7001/自有iPhone代理退出；安装新bundle再通过原生UI启动。确认7001的新build ID、idle/未自动录制及保留记录；确认新节点导入入口在实际窗口可达，不为了验收向手机重复导入、安装证书或切换节点。
4. 比较保留归档和持久身份元数据摘要；临时会话目录正常退出清理属预期，不比较旧会话临时CA。若持久身份仍一致则不读取/导出钥匙串私钥。
5. 本地记录验收结果并提交，只推送当前分支，ls-remote确认远端SHA与本地一致；保留旧应用私有备份及当前工作树，不推送无关脏文件。

## 验收结果

- 产品固定7603b154c1acadade8c1e487573ada48acdc7af7，release构建成功，Web构建成功。新模块与源码SHA匹配，backend不含APK、私钥、描述文件或用户数据库；requirements与运行时沿用构建缓存，未升级依赖。没有把未提交的Android副本规格加入包或提交。
- 最终app内Python、包内后端优先的PYTHONPATH、独立CAPTURE_RUNTIME_DIR运行新节点/引导及既有iOS回归、三轮包内生命周期，共89项8.905秒通过。产品源码未再变，复用上轮191项Swift及3项真实隔离链路结果。
- 旧桌面通过原生退出及继续退出确认正常结束；原应用PID87759、后端87765和iPhone代理7987均退出，7001及53952无监听。未杀无关进程、未操作手机VPN或路由。
- 第一次暂存复制的签名复核发现两个sqlite3 pyc为本轮摘要脚本以未带-B的构建Python生成，替换前已拦截，旧应用未动。仅删除source/stage中这两个本轮生成文件，原签名重新严格验证成功；随后所有运行时校验均-B。并非忽略签名失败或重签掩盖污染。
- 旧bundle移动到私有/tmp/capture-delivery-1110/previous-抓包工具.app，新bundle经Applications隐藏stage校验后移动为/Applications/抓包工具.app。原生从准确路径启动，7001报告build7603b154c1ac；首次显示暂停/idle/can_resume，不自动开始记录。
- 通过新版原生“重新连接iPhone”验证入口，复用Capture iPhone Test 1cc4c5、192.168.76.70:53952；节点操作区正确识别iPhone_AA7，导入按钮可见但未点击，不向真实手机重复导入。随后服务waiting_phone/idle，仅等待本人验证，未声称手机重新接通或路由恢复完成。
- 小火箭发送副本实际仅root证书及Web Clip、权限600；不含Wi-Fi/VPN载荷。未展开真实密码或节点二维码。接口#90仍127条。
- 正常退出后、安装启动后、复用连接后分别复核：7条历史、505个保留归档文件和持久身份元数据SHA完全一致。安装后codesign --verify --deep --strict再次通过。
- 代码/规划推送至origin/codex/ios-device-trial，初次远端d28ecbca1222577dfcaad7d31fc8b0d8cf8058b7与本地HEAD一致；本验收记录随后同步同分支。main、旧标签及GitHub Release/安装包未更新。无关specs/android-copy-capture-trial.md保持原样未提交。

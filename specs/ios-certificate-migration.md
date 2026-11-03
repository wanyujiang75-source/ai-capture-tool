# IOS-C2 Certificate Migration Acceptance

## Scope

用户要求启动新版桌面并迁移长期证书，验证指定iPhone14_Test上的PokeHub。复用IOS-C1本地构建，不扩大为全部iOS流程改造。禁止修改原VPN节点、订阅、现用配置、DNS或默认路由；手机VPN必须保持开启。只处理本工具的旧证书和既有Capture-Mac专用节点，保留已存在的精确域名规则。

## Steps

1. 核对App版本、指定USB设备、旧本工具profile与当前连接；只显示本工具诊断摘要。
2. 必要时请用户移除旧本工具profile；不能在未确认恢复前跳过桌面的清理保护。
3. 用新版桌面创建/复用一年期身份。针对保留VPN的路径，生成同一身份的证书+检查WebClip派生profile，去除Wi-Fi payload；验证不含VPN、Wi-Fi、私钥或代理认证。原始文件不修改，不向其他设备发送。
4. 经本机分享交付iPhone14_Test；用户亲自安装、信任和更新既有Capture-Mac专用节点凭据，不选择它为全局节点、不修改其他规则。
5. 以实际手机认证HTTPS回调验证连接；用PokeHub只读页面触发业务请求，核对当次记录与有界Request/Response。不读取/提交账号密码或无关内容。
6. 用户仍需交互时保留准确等待状态；完成后记录证据和边界并本地提交，不推送发包。不能完成时写明外部条件，不伪造通过。

## Acceptance

- 正在运行的是ios-c1-reuse-20261103；实际运行目录不是合成UI fixture。
- 派生profile的CA指纹、证书期限、检查URL与本次身份一致，payload仅root证书和WebClip；没有私钥、Wi-Fi配置、VPN配置或认证密码。
- 旧profile移除和新profile安装有用户或指定USB读取证明；信任以实际手机HTTPS成功为准。
- 新会话中PokeHub目标域名的业务请求及响应正文可见；不将Mac测试或检查域名计为业务成功。
- 手机VPN不关闭，原节点和配置不编辑；只更新专用抓包节点。未开启其他手机录制。
- 原生桌面截图/API摘要与时间记录互相支持；凭据、网络名称、证书私钥和业务正文不写入仓库。

## Evidence

2026-11-03：任务开始，指定测试机在线；尚未迁移或开启新代理。现有桌面进程未运行，使用已通过签名及回归的IOS-C1构建。

18:23-18:27：经原生UI启动本地新版，API核对build_id为`ios-c1-reuse-20261103`，使用真实`runtime-native`而非fixture；严格签名通过。iPhone页项目为PokeHub，连接为needs_cleanup、记录idle、没有新session。指定手机USB的GetProfileList返回Acknowledged，ProfileMetadata为空，没有旧抓包profile；没有调用安装/删除接口。

手机自动化工具因agent未安装不能点击或截图，未擅自安装agent。用已有pymobiledevice3的USB userspace只读截图成功，手机在主屏幕。没有再次使用iPhone镜像、改账户或锁屏设置。

Mac到PokeHub业务域名的无认证根路径对照为HTTP404、TLS校验0、约0.56秒，表示网络与证书可达，不能当成PokeHub接口捕获。Mac系统代理保持原样。

已打开旧连接清理确认，但未假称手机网络已恢复，随后取消并保留原状态。通过异步问题请求用户仅确认当前Wi-Fi代理、VPN连接与普通网页，并停在小火箭首页；当前等待该必要手机信息，因此IOS-C2记录BLOCKED。尚未产生新CA、投送配置或录制流量。其他iPhone和原VPN配置没有操作。本轮文档diff检查通过；产品代码未变，不重复构建或冒充实机验收通过。

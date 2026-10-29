# iOS 真机 PokeHub 试验

## 范围

- 仅用户指定的 iPhone 与 PokeHub；现有 Android 桌面、后端和抓包保留。
- 复用已安装 mitmproxy 的标准 HTTP 代理，不修改平台准入代码。
- 代理只监听本机指定局域网地址，要求临时认证；管理页面仅监听回环地址。
- 独立端口、证书和运行目录，不复用 Android CA，不提交任何证书私钥、账号或原始流量。
- 首先只解密 Safari 对照域名；确定 PokeHub 域名后再扩展到目标域名。其他 HTTPS 保持透传。
- 限制大正文内存使用；只记录验收需要的域名、方法、响应状态和正文大小，不把业务正文或 Token 写入项目记录。

## 初始手工试验（历史）

手机与 Mac 位于可互通的 Wi-Fi。用户自行在手机填写 HTTP 代理及临时认证，使用 Safari 下载本次测试 CA，并按 iOS 要求安装及开启 SSL 信任。说明证书用于本机 HTTPS 解密，避免测试期间使用银行等无关应用。不得自动修改系统信任或绕过证书绑定。

## 验收层次

1. Mac 自检：认证缺失被拒绝，配置本次 CA 后 HTTPS 可通过。仅代表代理可用。
2. iPhone 对照：Safari 经代理请求 HTTPS，确认请求来自手机而不是 Mac。
3. PokeHub：用户操作业务页，核对确实经过代理且可读取目标 Request/Response。Safari 成功不能替代这一步。
4. 若应用不遵循系统代理或拒绝测试 CA，记录限制，不声称已支持 iOS，不自动转向 VPN 或越狱。
5. 试验结束前用户恢复原 Wi-Fi 代理并移除本次证书，再停止本试验代理；不终止不属于本试验的进程。

## 当前证据

- 2026-10-29：USB 连接的 iPhone 14 Pro，系统 26.5.2，已配对、开发者模式启用，锁定查询不要求密码。
- 开发工具应用查询成功但返回空数组，不能据此判定未安装 PokeHub；用户已明确确认安装、打开及同一 Wi-Fi。
- 现有 Android 抓包 #73 曾报告 running；其只读 flows 查询随后 8 秒超时，未重启或修改，需区别于本试验结果。

## 自动化实现计划

目标：桌面“连接 iPhone（试用）”入口完成自动准备，以可移除 Wi-Fi + CA + HTTPS 检查快捷方式配置文件替代手输代理。仅支持普通个人密码 Wi-Fi；名称读取失败时让用户填名称，不读取或保存 Wi-Fi 密码。通过 macOS 共享发送文件，用户选择自己的 iPhone；不新开局域网文件下载服务。

架构：独立 Python 服务管理自有 mitmproxy 子进程；新路由只绑定已有本机后端，不更改 Android 平台标记。代理随机端口、仅局域网接口、随机认证；其他 HTTPS 透传。子进程只写有界状态与最近接口预览，不保存完整抓包或凭据到仓库。原生 sheet 展示步骤、自动轮询、配置分享与有界响应预览。

- [x] Python RED：配置字段、SSID 限制、认证校验、非手机自检不得触发完成、目标域名限制、有界数据、子进程失败/停止/重复启动。
- [x] 实现 `ios_setup.py` 的地址/端口选择、配置生成、生命周期与状态；`ios_pairing_proxy.py` 仅解密检查域名和 PokeHub 已知 API；`ios_setup_api.py` 独立路由接入与 shutdown 清理。
- [x] Swift RED：等待安装/信任/可连接/有流量/停止状态，错误不泄露原始 JSON，重复提交防护。
- [x] 实现集中式文案、controller 和 native sheet；自动分享文件入口和检查二维码；无手动端口、用户名或代理密码输入。
- [x] 隔离真实代理验证认证与 HTTPS，配置文件 plist 校验；模拟桌面进程退出并验证代理退出、私钥与凭据清理、重开保留手机清理提示。
- [x] 最终 Python/Swift 回归与桌面打包；不重启用户活动 Android 抓包。
- [x] 更新使用说明和证据；实机未完成则明确缺口，不写成 iOS 已支持或已验收。

安全：手机配置仅由用户安装和删除，默认 24 小时后自动移除；不带 Wi-Fi 密码、设备管理、VPN、根证书私钥或不可删除标记。首次信任由用户完成。结束按钮要求用户先删除手机配置；意外退出仍停止自有代理，但不得假称手机代理已恢复。状态文件最多最近 20 条、每个正文最多 16 KiB，大体积正文流式转发。已验证 HTTPS 不等于已抓到 PokeHub，目标响应必须单独计数。

复核补充：代理生命周期同时绑定后台服务与发起桌面进程的 UID/PID/启动时间，避免桌面崩溃后继续采集。
异常退出清理临时私钥、配置及预览，但保留不含凭据的 `cleanup-required` 标记；下次打开必须先确认手机配置已删除。
WebSocket 升级仅作不保留历史的 TCP 透传；序列化后的状态限制为 1.5 MB，超限淘汰最旧预览，计数保留。
Mac 自检与实机验收严格分开。当前尚未收到 Wi-Fi 名称，也未在 iPhone 安装配置、确认信任或验证 PokeHub 响应。

可重复验收：

```sh
python3 -m unittest -q tests.test_ios_setup tests.test_console_api tests.test_device_network
CAPTURE_TEST_IOS_PROXY=1 python3 -m unittest -v tests.test_ios_setup_integration
swift test --package-path macos-native
python3 -m unittest -q tests.test_native_app_packaging
git diff --check
```

Python 需使用已包含 FastAPI/mitmproxy 的项目运行时；真实代理测试只启停自身创建的进程，不修改手机、Mac 或 Android 网络。
打包测试不应设置自定义 `AI_CAPTURE_BUILD_ID`，因为已有测试要求默认 Git 提交标识格式。

本地验收结果：126 项 Python 相关回归、101 项 Swift 回归、8 项打包回归通过。
隔离真实代理及包内运行时分别通过认证拒绝、HTTPS、自检归属、桌面进程退出与清理恢复测试。
最终构建 `ios-setup-20261029` 已生成并通过签名检查；未替换正在运行的旧桌面，原生窗口视觉与 iPhone 端到端验收尚未完成。

### 参考

- https://docs.mitmproxy.org/stable/concepts/modes/
- https://docs.mitmproxy.org/stable/concepts/certificates/
- https://support.apple.com/en-us/102390
- https://developer.apple.com/documentation/devicemanagement/wifi

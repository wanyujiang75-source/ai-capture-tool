# 模拟器失效代理网络恢复

## 范围与证据

本机项目设备 `device-1` / `emulator-5554` 没有活动抓包，抓包端口 9090 无监听；Android 中 `http_proxy=10.0.2.2:9090`、`global_http_proxy_host=10.0.2.2`、`global_http_proxy_port=9090` 仍存在。宿主机直接及现有宿主机代理访问 Google generate_204 均成功，模拟器能解析 ssl.gstatic.com 并访问宿主机网关。

## 修复约束

- 不启动抓包来掩盖失效代理；先恢复正常网络。
- 不清除应用、Google 账号或系统网络数据，不关闭其他代理程序，不改变宿主机代理。
- 现有 clear_android_proxy 如果只删除历史兼容键而遗漏生效配置，统一修正该方法，让停止、清理和网络模式切换共用。
- 只检查和操作当前项目设备；不自动结束其他进程。

## 根因与实现

旧清理 API 实测返回 mode=direct，但 global_http_proxy_host/port 仍为 10.0.2.2/9090，系统 ProxyTracker 也没有发出清空代理广播。Android ProxyTracker 在历史 http_proxy 键被删除时不更新内存代理。改为写入空代理 `:0`，由 Android 正常清空缓存、同步持久化配置并广播给应用；保留该值，避免立即删除导致异步观察者错过重置。来源：[Android ProxyTracker.java](https://android.googlesource.com/platform/packages/modules/Connectivity/+/refs/heads/main/service/src/com/android/server/connectivity/ProxyTracker.java)，loadDeprecatedGlobalHttpProxy 与 setGlobalProxy。

回归测试先运行，3 项中 2 项出现预期失败：旧方法没有重置有效代理，且仍发送 delete 而不是 put :0。实现仅修改统一 clear_android_proxy 命令，所有停止与网络切换调用复用该修复。

启动脚本的 clear_android_http_proxy 原本先重置后立即删除，存在异步观察者尚未处理就丢失重置值的竞态。同范围增加脚本行为测试，先复现 missing 而非 :0 的预期失败，再移除立即删除步骤。

## 验收

1. 通过现有网络清理 API 验证 Android 配置与实际生效代理是否一致。
2. 若修改代码，先增加回归验证完整清理、失败传播和重复清理。
3. Google Play 在真实模拟器显示内容，不仅用 ping 作为联网证据。
4. 记录代理最终值、Google 页面结果和桌面端状态；保留 Google 登录态。

## 2026-10-15 验收记录

- `python3 -m unittest -q tests.test_device_network tests.test_console_core tests.test_console_api tests.test_package_install`：196 项通过；`bash -n scripts/ai_capture.sh`、`git diff --check` 通过。
- Android 已广播 `sending Proxy Broadcast for [] 0`；持久化 `http_proxy=:0`、host 为空、port 为 0；直接查询 ConnectivityManager 的有效全局代理为 null。
- 临时只读 Java/Dex 探针在设备内使用 Android 自身 TLS 信任和有效代理发起 HTTPS 请求，Google generate_204 与 ssl.gstatic.com generate_204 均为 204，Google Play 商店页面与 Google Accounts 均为 200；未传账号、Cookie 或 Token。
- 桌面代码构建 `c2d85e1f34d8`，深度严格签名通过，已重新打开；本地后端 active_session=null、health=idle。通过新构建的清代理 API 重复操作后，设备内 Play=200、gstatic=204。
- 临时设备探针及宿主机测试文件在验收后移除，不安装测试应用，不清数据或登录态。
- 剩余验收：Mac 处于锁屏状态，CUA 两次无法访问原生窗口，已请求用户解锁。网络/TLS 已验证恢复，但 Google Play 应用窗口视觉结果暂未验证，因此任务保留 BLOCKED，而非宣称全部验收完成。
- 仅本机代码提交和桌面更新，本轮未推送 GitHub 或发布安装包。

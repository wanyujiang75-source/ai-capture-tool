# Android USB 连接助手

独立包 `com.local.capture.bridge`，不修改测试应用。使用 WireGuard 官方 tunnel 库
1.0.20260102（Apache-2.0，源代码 https://git.zx2c4.com/wireguard-android/）。
VPN 接管由 Android 系统弹窗确认；不申请存储、无障碍、Root 或系统证书权限。

助手采用可调试构建，仅让已获用户授权的 ADB 将临时配置写入助手自己的私有目录。
不要在不可信电脑上允许 USB 调试。密钥不放在 Intent、公共下载目录或应用日志。
桌面每两秒续约，20 秒未续约或15分钟硬上限时自动释放临时 VPN，Android 不保证
第三方原 VPN 自动重连。停止时桌面尝试打开原 VPN 恢复，并核对实际 VPN 所属包；
无法确认时保留恢复提示。助手可保留供下次使用；不会自动启动或开机抓包。

构建机需 Java 17+、Android SDK 35 和网络：`bash android-bridge/build.sh`。
用户安装桌面发行包后无需安装 Java、Gradle 或自行编译。
桌面打包复制此 APK 与独立的 physical-runtime；原模拟器/iPhone运行时不变。

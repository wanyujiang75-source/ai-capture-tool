# 2026-11-09 macOS 桌面发布

仅 RELEASE-1109。相对 20261105 发布，产品变更只有 Android 真机只读条件检查模块（尚非免 Root Release 抓包功能），原生 UI 未改。PokeHub 独立副本补丁只是研究资料，不携带 APK、密钥或实验运行数据。

固定发布说明提交后构建，CONFIGURATION=release，开发签名，不宣称已公证。先测试打包回归，再生成最终 ZIP，独立目录解包；检查源码/build ID/架构/最低系统和说明文件、敏感文件与签名。用最终运行时执行相关后端测试和三轮隔离生命周期测试，禁止包内 pyc。只监听测试 loopback，临时合成数据，不操作用户运行目录。

验收通过才创建 GitHub prerelease 草稿上传 ZIP 和 SHA256，核对 digest/大小/提交后公开；匿名下载校验。旧版本及 main 不变，不更新本机 /Applications 应用。保留最近七条的删除警告、安装指南和现有未覆盖场景。

## 证据

- 固定构建源码 6432488f2a99ddd094664af4e89ee7000020e123；CONFIGURATION=release，build ID=6432488f2a99，development/ad-hoc，原生二进制 arm64，最低 macOS14。
- `tests.test_native_app_packaging` 与 `tests.test_android_physical_capabilities` 合计21项通过（62.701秒）。最终包内 Python 执行 physical、retention、console_core、ios_lifecycle、ios_results、ios_packaged_lifecycle 共126项通过（13.169秒），含三轮隔离正常/异常服务重启。没有真机操作。
- 初次最终包126项虽通过，但未显式指定 CAPTURE_RUNTIME_DIR，导入服务在解包副本 backend/runtime 创建合成 console.db，导致签名复核失败。ZIP 内无该目录。未忽略失败：使用新的 verified 解包目录并显式设置独立 test-runtime，完整复跑126项，随后 codesign --verify --deep --strict 成功。未更改产品代码或掩盖原始失败。
- 三份指南与来源一致，包内后端 Python 源码与固定提交一致，requirements SHA 匹配；后端无 APK/私钥/证书/描述文件/用户数据库/真实配置。ZIP完整性与本地校验文件通过。
- ZIP为99,437,665字节，SHA256=121a9ce0815157b459cf40837a95be3a97b675ac6c843442f260c16fb7c391e5；SHA文件124字节，digest=a39271dc71067fbb87537b392d230fe10acd6f2a355952bbfb862d29ea7ba952。GitHub两项均uploaded且摘要相同。
- 2026-11-09T03:03:56Z公开prerelease desktop-preview-20261109-6432488，targetCommitish和标签解引用都为6432488。main仍为c4a7d6cc0c9f15852a72792ada51e03b89d26cf7，旧Release保留。
- 匿名 curl 下载ZIP及SHA文件成功，下载ZIP的完整SHA与源文件一致，两个文件分别cmp逐字节一致；最终公开URL已核对。
- npm构建提示既有开发依赖8项风险（2 low/1 moderate/5 high），不在本轮升级依赖；`npm audit --omit=dev --json`生产依赖报告0项，不把打包通过解释为开发依赖无风险。源码与锁文件无额外变化。
- 日志位于 /tmp/capture-release-1109-{tests,build,final-tests,final-tests-isolated,download}.log；验证副本位于 /tmp/capture-release-20261109-6432488/verified。未覆盖/Applications应用、未操作手机/VPN/原配置，未公开PokeHub副本。

发布页：https://github.com/wanyujiang75-source/ai-capture-tool/releases/tag/desktop-preview-20261109-6432488

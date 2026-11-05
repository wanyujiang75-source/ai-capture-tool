# 2026-11-05 桌面预览包发布

## 范围

仅执行RELEASE-1105。当前已验收源码基线ec6e2ba，包含断点BP-0至BP-3与BP-4部分真机验收、接口来源整理、请求/响应键值换行及最近7次历史自动删除。上一发布be6d054是其祖先，不存在发布回退。Android真机断点和整机休眠/唤醒仍未现场覆盖，不将预览包宣称为完整多平台正式版。

- 更新安装说明，首次启动前突出自动删除历史与备份要求。
- 当前功能分支提交发布文档后，以固定提交构建并设置相同build ID；标签desktop-preview-20261105-<短SHA>，ZIP为AI-Capture-Desktop-20261105-<短SHA>-development-arm64.zip。
- 沿用ad-hoc未公证预览，不关闭Gatekeeper，不读取或上传真实证书、账号、抓包数据或VPN配置。
- 不覆盖旧Release，不移动旧标签，不合并main。只更新当前开发分支与新Release资产。当前/Applications应用继续运行，不重新安装或操作真实设备。

## 验收步骤

1. 复用未变化产品的238项后端及184项Swift报告；重新运行原生安装包回归。构建使用CONFIGURATION=release，检查脚本没有造成源码或依赖锁文件意外变化。
2. 独立解包后核对最低系统、arm64、build ID、包内后端源码一致、内嵌运行时依赖、三份安装/断点文档。检查无本机私有配置或运行数据。
3. 对最终解包App的运行时执行历史清理及归档相关回归，并独立启用三轮包生命周期测试；禁止写入包内pyc，测试后严格签名继续有效。
4. 在不触碰用户运行目录的前提下，用最终内嵌服务读取合成历史并检查清理。正常用户App保持原PID/版本、七条记录与身份摘要不变。此前相同原生二进制的窗口验收可通过SHA一致性复用。
5. 构建通过后提交固定标签，先创建草稿上传ZIP和校验文件，确认两者uploaded、大小/digest与本地一致再公开为prerelease。
6. 匿名下载公开ZIP和校验文件，SHA-256与原件字节一致；核对标签来源、旧Release保留，记录URL和证据。失败保持DOING并诊断，不公开不完整包。

## 发布前证据

- 固定源码提交4933585ac550e9f015e231032bcd2b6abecf5e27，原生/后端代码相对已验收5f70d0d未变；本次新增安装与发布说明。main保持不变。
- `CONFIGURATION=release PYTHONDONTWRITEBYTECODE=1 <已安装包内Python> -B -m unittest tests.test_native_app_packaging -v`：8项通过，60.688秒，包括重定位运行时、签名、开发ZIP、正式分发公证门禁。
- `CONFIGURATION=release TRACEDECK_VERSION=20261105-4933585 TRACEDECK_RELEASE_KIND=development AI_CAPTURE_BUILD_ID=4933585ac550 MACOS_SIGN_IDENTITY=- PYTHONDONTWRITEBYTECODE=1 release/package.sh` 成功，源码与锁文件无额外变化。
- ZIP 99,434,512字节，SHA-256 `99ef94599a62b3251deeb7270bcc4804afed98b4a780bd82c9716b5510480334`；校验文件SHA-256 `67192d521529eae35f7fdf80a8d2eb3bed8a53d0866302a75cdf6b6009fb6c33`。
- 解包到/tmp/capture-release-20261105/extracted；macOS最低14.0、arm64、build ID正确，后端capture_console与源码递归diff一致。安装说明.md和INSTALL.md与源安装说明逐字节一致，BREAKPOINTS.md与断点教程一致；运行时requirements摘要匹配、无绝对符号链接。
- 后端资源扫描无用户数据库、APK、mobileconfig、pem/key、local.json、.env、HAR或pcap。完整npm构建审计提示既有开发依赖8项(2 low/1 moderate/5 high)，另行`npm audit --omit=dev --json`为0；不将此解释为全部开发依赖安全，未执行无关依赖升级。node_modules不在桌面ZIP中。
- 首轮在/tmp运行239项回归出现18错误和1失败，均由测试按相对路径读取仓库脚本导致；任务保持DOING。改回仓库工作目录，并显式优先导入/断言capture_console来自解包backend后，同一239项全部通过(11.600秒)，含11项清理边界及最终解包App的三轮正常/异常重启。没有修改产品代码或忽略失败测试。
- 最终解包App测试前后严格签名均通过。对已安装App与最终App的可执行文件各复制一份到独立比较目录，仅从这两份临时副本移除代码签名后cmp完全一致；原包未修改，因此复用上一轮真实原生窗口七条历史、请求/响应展示验收。
- 当前/Applications主进程87759和后端87765保持，7001仍报告5f70d0db9dc1且无活动抓包；3个原身份文件摘要一致。没有停止用户桌面端或操作手机/VPN/节点/原配置。
- 源码分支与新标签已推送；创建prerelease草稿后上传两项资产，上传过程仅进程环境GODEBUG=http2client=0，不更改系统代理或VPN。GitHub两项资产均为uploaded，大小和digest与本地一致。
- 本机日志：/tmp/capture-release-20261105/packaging-tests.log、package.log、final-bundle-tests.log、final-bundle-tests-corrected.log、npm-production-audit.json；不上传测试运行数据。

## 公开下载验证

- 2026-11-05 14:36:57（Asia/Shanghai）公开为prerelease，标签`desktop-preview-20261105-4933585`；`isDraft=false`、`isPrerelease=true`。标签指向4933585ac550e9f015e231032bcd2b6abecf5e27，Release的targetCommitish也明确设置为该提交。旧Release保留，main未合并。
- 发布页：https://github.com/wanyujiang75-source/ai-capture-tool/releases/tag/desktop-preview-20261105-4933585
- 通过不带认证的`curl -q`下载公开资产；124字节校验文件下载完成并与源文件cmp一致。ZIP首次连接持续低速，停止本任务下载进程后改用仅影响该进程的`--http1.1 --continue-at -`，遇到瞬时LibreSSL连接错误后重试。为避免单连接长期低速，保留已下载前缀，按服务端支持的HTTP Range分段续传；没有改VPN或系统代理。
- 所有续传完成后按原始偏移排序17个片段，逐段校验文件长度、区间连续且无重叠，并以1MiB有界读取与源ZIP逐字节比较；全部99,434,512字节一致，完整流SHA-256为`99ef94599a62b3251deeb7270bcc4804afed98b4a780bd82c9716b5510480334`，与匿名下载的校验文件和GitHub资产digest一致。最终续传的8个请求均HTTP 206且退出0，完整性不依赖某一次未完成传输。
- 公开下载验证日志：`/tmp/capture-release-20261105/public-download-verification.log`。最终复核`gh release view`仍非草稿且targetCommitish正确；`git ls-remote`确认标签解引用为4933585、main仍c4a7d6cc0c9f15852a72792ada51e03b89d26cf7；旧be6d054与d2795fe两个Release仍保留。原/Applications主进程87759及后端87765仍运行。
- 安装包下载：https://github.com/wanyujiang75-source/ai-capture-tool/releases/download/desktop-preview-20261105-4933585/AI-Capture-Desktop-20261105-4933585-development-arm64.zip
- RELEASE-1105验收完成。最后提交仅同步本文件、goal.md和progress.md的证据，不重建或移动已发布的4933585标签。

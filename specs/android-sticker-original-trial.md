# StickerHub 原版真机抓包对照

## 范围

2026-11-09 ANDROID-STICKER1，一加d5f39352。用户选择正式版StickerHub，延续允许临时VPN转发与测试证书的边界。不得Root、改包、注入、复制登录态、清应用数据、修改原配置或关闭VPN。手机存在多个类似包，必须先核对Play安装来源及应用label，不使用测试包。

## 步骤与验收

1. 读取正式包label、版本、APK路径与SHA256；核对VPN原配置/模式/节点和转发基线。
2. 复用上一轮已验证的有界、仅回环监听、认证代理，经Mac既有代理出网；独立临时Clash配置，原文件保留。对照域名及StickerHub业务HTTPS解密，其他HTTPS透传。
3. 独立短期CA只装用户证书；由用户处理安全确认及密码。先浏览器对照，再正式包只读业务操作，记录实际TLS/HTTP结果；需要登录则用户处理。
4. 不以域名或CONNECT代替完整请求响应。若证书被拒绝，记录错误与边界，不重复盲试或扩大权限。
5. 恢复原配置/模式/节点，VPN仍开启；移除本轮CA/配置/文件/USB转发/服务/密钥；复核原APK摘要及网络。未恢复不报完成，业务未通过不报抓包成功。

## 实施限制

产品代码和安装包不变，无远端发布。临时脚本及包含敏感数据的记录仅存在私有目录，正文有界，不把凭据/账号正文提交仓库。检查既有工作树修改，不修改已有android-copy-capture-trial.md。上一轮PokeHub失败不代替StickerHub实测结果。

## 当前检查记录

- 正式包确认：Google Play来源com.meta.inno.sticker，label=StickerHub，3.18.14(195)，target36，无debuggable/networkSecurityConfig声明；只读复制base及arm64供核验，12个原APK摘要保存在私有目录。
- 原版libapp.so包含业务域名pbzhiqxtoqqgizddjblb.supabase.co；运行时Dart3.10.7。只提取域名和版本，不打印包中密钥；静态特征不代替真实抓包。
- VPN基线仍为运行中、自动配置、规则模式、PROXIES=US/日用专线美国[0.2]，系统http_proxy=null。原forward23761/36166，reverse空；本轮UI工具新增forward61689，需要收尾移除。
- 私有诊断目录/tmp/sticker-original-moDze0；复用上轮有界记录原型并替换目标域名及临时配置名；3项测试通过。本机无认证407、认证TLS对照200、非测试站点透传200。临时服务PID10339、回环端口62138/62139，最长30分钟自动退出；尚未添加reverse、安装CA或切换手机配置。若等待用户超时，必须先核对服务再继续。
- 正式版停在Google/访客登录页，已请求用户自行登录；暂不自动创建访客或操作账号。安全确认、密码仍由本人处理。抓包验收尚未执行。

登录后续：用户确认已登录，手机显示画册更新提醒（未点击更新或改变提醒设置）。本轮公有CA已放入Download/Capture-Sticker-Trial-moDze0.crt，已导航到CA安装警告，等待用户自行确认；没有切换原VPN配置。新增自有reverse62138/62139，手机curl显式指定本轮CA的USB对照HTTP200/TLS验证0。登录后原进程近期日志CERTIFICATE_VERIFY_FAILED计数0，仅作对照基线；系统CA信任和业务正文尚未验证。

## 最终实测与判定

用户确认安装CA后，发现首个服务已按30分钟上限退出。复用同一本轮CA重新启动受限服务（PID16767、回环端口53463/53464），移除旧reverse并重建本轮转发，未生成第二张证书。此时才启用独立的Capture-Sticker-moDze0配置，原配置文件及节点未编辑。

- 浏览器HTTPS对照：Chrome打开example.com带本轮测试标记的页面，页面正常，代理记录HTTP200和正文。本机及USB对照也通过，不能将这些结果算作StickerHub业务成功。
- 原版业务：仅force-stop/start原版应用，不清数据。画册页面显示网络不可用；业务域名出现41次ClientHello及41次客户端TLS失败，0条业务HTTP响应记录。
- 原版进程PID21216日志明确记录HandshakeException及`CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate(handshake.cc:298)`；涉及群聊消息、帖子消息及团队计数的读取失败。未保存账号正文到仓库。
- 结论：本轮用户CA代理路径无法取得StickerHub原版完整请求/响应，失败位于客户端证书链验证。浏览器通过不代表应用信任该CA；现有证据不能进一步断言存在显式证书固定，也不能外推所有Android应用。
- ANDROID-STICKER1完整正文目标保持BLOCKED；诊断及恢复已完成。本轮不扩大到Root、改包、注入或原VPN配置修改。

## 恢复与收尾验收

- 恢复原Clash配置“自动”、规则模式、US分组及“日用 专线 美国[0.2]”节点。仅删除本轮Capture-Sticker-moDze0配置；原“自动”和“新配置”保留。
- VPN持续CONNECTED，实例network189及创建时间2026-11-09T03:51:20.059Z保持不变；系统http_proxy仍为null。
- 仅卸载本轮用户CA“Capture Sticker Trial moDze0”（user:c6f4b5d9.0），原四项Charles/Capture Oneplus/charles WLAN/reqable WLAN凭据保留。删除手机Download中的本轮crt文件。
- 本轮reverse全部移除；UI工具forward61689已移除，forward列表仅剩原23761→10156、36166→10157。
- 临时服务10339/16767均已退出；本轮私钥、认证state、临时VPN配置及5份原始对照归档已删除。只保留私有诊断代码、摘要、无正文事件日志及公有证书用于核对。
- 12个原APK的SHA256前后完全一致。恢复后启动原版，新进程PID23278，画册正常显示7/216、星星8，无网络不可用提示；该进程新日志CERTIFICATE_VERIFY_FAILED计数0。此项只证明已观察页面恢复，不宣称全部业务验收通过。
- 临时诊断原型3项测试通过；产品代码、构建和发布均未修改。

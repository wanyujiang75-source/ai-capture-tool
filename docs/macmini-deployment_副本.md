# AI抓包工具 Mac mini 闭环部署手册

适用版本：V1.1  
目标：把当前本机能力整理为可部署到 Mac mini 的闭环服务，用户第一次访问页面后按初始化向导完成准入。

## 1. 部署边界

- Web 服务部署在 Mac mini 上，默认监听 `0.0.0.0:7001`。
- 抓包、模拟器、Frida、mitmproxy 都运行在 Mac mini 本机。
- 用户通过浏览器访问 `http://<mac-mini-ip>:7001`。
- 用户第一次访问先进入“初始化向导”，不是直接进入复杂控制台。
- Google 登录在模拟器里由人工完成，系统不保存 Google 密码。
- 释放、休眠、升级不能执行 `wipe-data`、`pm clear`、`uninstall`。

## 2. 目录结构

建议部署目录：

```text
~/ai-capture-tool/
  current -> releases/<version>/
  releases/
    <version>/
  shared/
    config/
      .env.macmini
      devices.macmini.json
    runtime/
      console.db
      captures/
      apks/
```

`current` 可以随版本切换，`shared` 永久保留。升级时不得删除 `shared/runtime`，否则会丢失应用库、历史抓包文件和初始化状态。

## 3. 打包

在开发机项目根目录执行：

```bash
deploy/macmini/package.sh
```

产物在：

```text
release/ai-capture-tool-<version>.tar.gz
release/ai-capture-tool-<version>.tar.gz.sha256
```

包内包含：

- FastAPI 后端。
- React/Vite 构建产物。
- 抓包脚本。
- Frida server 和 Hook 脚本。
- Mac mini 部署脚本。
- 设备配置模板和部署文档。

包内不包含：

- 当前机器的 `runtime/captures`。
- 当前机器的 SQLite 运行数据。
- 当前机器的模拟器数据目录。
- APK 上传缓存。

这些运行数据需要在 Mac mini 上通过 `shared/runtime` 持久化。

## 4. 首次安装

把 tar 包传到 Mac mini 后执行：

```bash
mkdir -p ~/ai-capture-tool/releases
tar -xzf ai-capture-tool-<version>.tar.gz -C ~/ai-capture-tool/releases/<version>
ln -sfn ~/ai-capture-tool/releases/<version> ~/ai-capture-tool/current
cd ~/ai-capture-tool/current
deploy/macmini/bootstrap.sh --install-deps --create-avds --install-service
```

如果 Mac mini 已经安装依赖，可以省略 `--install-deps`。如果已经提前创建好 AVD，可以省略 `--create-avds`。

初始化完成后访问：

```text
http://<mac-mini-ip>:7001
```

## 5. 首次访问向导

页面会自动进入初始化向导，按顺序完成：

1. 服务环境检查：Python、Node、adb、emulator、mitmweb、Frida、Android SDK。
2. 设备池检查：确认 `Capture_AVD_01/02/03` 已创建。
3. 启动模拟器：选择设备后点击启动。
4. Google 登录：点击“去登录 Google”，在模拟器内人工登录。
5. Frida 准入：点击“启动 Frida”，页面校验 `frida-ps`。
6. 上传或选择 App：上传生产包或测试包。
7. 抓包冒烟测试：启动抓包，人工操作 App，确认接口出现。
8. 完成初始化：至少一台设备通过 Google + Frida + 抓包冒烟后才能完成。

完成初始化后，后续访问默认进入主控制台。顶部仍保留“环境检查”入口，可随时重新打开向导。

## 6. 设备池

默认配置文件：

```text
~/ai-capture-tool/shared/config/devices.macmini.json
```

默认设备策略：

- `device-1`：`Capture_AVD_01`，常驻，端口 `9090/9091/27042`。
- `device-2`：`Capture_AVD_02`，常驻，端口 `9100/9101/27142`。
- `device-3`：`Capture_AVD_03`，按需，端口 `9110/9111/27242`。
- `device-4`：预留，默认禁用。

修改设备配置后需要重启 Web 服务。

## 7. 服务管理

手动启动：

```bash
cd ~/ai-capture-tool/current
deploy/macmini/start_service.sh
```

前台启动：

```bash
cd ~/ai-capture-tool/current
deploy/macmini/start_service.sh --foreground
```

安装或重装 launchd：

```bash
cd ~/ai-capture-tool/current
deploy/macmini/install_launchd.sh
```

停止后台服务：

```bash
cd ~/ai-capture-tool/current
CAPTURE_RUNTIME_DIR=~/ai-capture-tool/shared/runtime scripts/stop_web_services.sh
```

查看日志：

```text
~/ai-capture-tool/shared/runtime/web-backend.log
~/ai-capture-tool/shared/runtime/launchd.out.log
~/ai-capture-tool/shared/runtime/launchd.err.log
```

## 8. 升级

上传新包后执行：

```bash
cd ~/ai-capture-tool/current
deploy/macmini/upgrade.sh /path/to/ai-capture-tool-<version>.tar.gz
```

升级脚本会：

- 解压到 `~/ai-capture-tool/releases/<version>`。
- 切换 `current`。
- 运行 bootstrap，但不会覆盖已有 `.env.macmini`。
- 如果已安装 launchd，会重装并重启服务。

## 9. 回滚

回滚到上一个 release：

```bash
cd ~/ai-capture-tool/current
deploy/macmini/rollback.sh
```

回滚到指定目录：

```bash
cd ~/ai-capture-tool/current
deploy/macmini/rollback.sh ~/ai-capture-tool/releases/<version>
```

回滚不会删除 `shared/runtime`。

## 10. 常见问题

### 页面显示缺少 Google Play

该设备不是 Google Play AVD。需要使用 `google_apis_playstore` 系统镜像重新创建 AVD，不能通过安装单个 APK 修复。

### 页面显示未登录 Google

点击“去登录 Google”，在模拟器内手动登录。登录完成后回页面点击“重新检查”。

### Frida 不可用

先确认模拟器已 root 或具备 `su`。然后在页面点击“启动 Frida”。如果仍失败，查看：

```text
~/ai-capture-tool/shared/runtime/frida-server-<port>.log
```

### 抓包没有接口

先确认：

- App 已经打开并在前台。
- 当前设备 Google、Frida、抓包链路为绿色。
- App 产生了真实网络请求。
- 当前 App 没有使用不支持的自定义协议或更强的加密封装。

### 多人同时使用

V1.1 默认支持 2 台常驻设备并发，第三台按需。多人同时使用时，每个用户应占用不同设备。单台设备同时只能有一个 active capture。

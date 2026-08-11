# AI抓包工具 macOS 应用图标设计

## 目标

为原生 macOS 桌面端提供正式应用图标，使 Finder、Dock、启动器和发行包能够稳定识别“抓包 / 网络分析”产品定位。图标不承担 AI 品牌表达，不使用文字或字母缩写。

## 视觉方案

采用已确认的“数据包透镜”方向：

- 外形：macOS 风格圆角方形主体，四角透明，保留充足安全边距。
- 背景：深海军蓝向高亮蓝的克制渐变，保持当前产品白色界面与蓝色主操作色的一致性。
- 主符号：白色放大镜，表达接口检查与网络分析。
- 镜片内容：一条青蓝色数据包轨迹穿过三个白色节点，表达请求在网络链路中的流动。
- 风格：几何、平面、少量层次，不使用写实光效、复杂纹理、文字、字母、机器人、大脑、盾牌或虫子图形。
- 小尺寸：在 16px/32px 下至少能辨认放大镜轮廓和一条数据轨迹，不要求三个节点全部保留细节。

## 资源规格

- 主源文件：`macos-native/Resources/AppIcon.png`。
- 主源尺寸：`1024 x 1024`，PNG，sRGB。
- 图标主体不触碰画布边缘；透明角区不能带有色边或底色残留。
- 构建时生成 `AppIcon.iconset` 所需尺寸，并使用 `iconutil` 生成 `AppIcon.icns`。
- `.icns` 进入 `AI抓包工具.app/Contents/Resources/AppIcon.icns`。
- `Info.plist` 设置 `CFBundleIconFile=AppIcon`。

## 构建接入

- `macos-native/scripts/build-app.sh` 在签名前生成并复制图标资源。
- 图标生成失败时构建直接失败，不能静默生成无图标应用。
- 所有资源写入完成后再执行现有整包签名与 `codesign --verify --deep --strict`。
- 发行脚本继续复用原生 App 构建产物，不单独维护第二份图标。

## 验收

- 主 PNG 尺寸为 `1024 x 1024`，具有 alpha 通道和透明四角。
- `iconutil` 能从生成的 iconset 成功产出有效 `.icns`。
- 构建后的 `Info.plist` 指向实际存在的 `AppIcon.icns`。
- `codesign --verify --deep --strict` 通过。
- Finder 与 Dock 显示新图标，不再使用 macOS 默认应用图标。
- 16px、32px、128px 和 512px 预览中，放大镜与网络轨迹均无明显糊边、裁切或色键残留。

## 非目标

- 不修改 Web 端 favicon、移动端图标或品牌名称。
- 不引入运行时图标切换、主题变体或多套品牌方案。
- 不在图标中放置敏感流量、真实接口数据或第三方商标。

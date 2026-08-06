# macOS Native Distributable Desktop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a true macOS native SwiftUI desktop app that other users can install locally and use with the existing AI抓包工具 capture runtime.

**Architecture:** Add a new `macos-native/` SwiftUI app while preserving the existing FastAPI capture runtime as the single capture engine. The native app owns setup guidance, backend lifecycle, API calls, native file selection, native flow list/detail screens, and packaging. The existing Web/Tauri surface remains available as a transitional/debug path, not the target desktop product.

**Tech Stack:** Swift 6.2, SwiftUI, Foundation URLSession, Process, macOS Application Support directories, existing FastAPI APIs, existing Python/ADB/Frida/mitmproxy runtime.

---

## File Structure

- Create `macos-native/Package.swift`: Swift package for the native app development build.
- Create `macos-native/Sources/AICaptureNativeApp/AICaptureNativeApp.swift`: `@main` SwiftUI app entry.
- Create `macos-native/Sources/AICaptureNativeApp/AppState.swift`: shared observable state for runtime, devices, apps, sessions, and flows.
- Create `macos-native/Sources/AICaptureNativeApp/RuntimeManager.swift`: starts, monitors, stops, and reports the local FastAPI runtime.
- Create `macos-native/Sources/AICaptureNativeApp/APIClient.swift`: typed wrapper around existing FastAPI endpoints.
- Create `macos-native/Sources/AICaptureNativeApp/Models.swift`: Codable models for status, devices, apps, sessions, flows, and details.
- Create `macos-native/Sources/AICaptureNativeApp/ContentView.swift`: native root shell, sidebar, and main layout.
- Create `macos-native/Sources/AICaptureNativeApp/SetupView.swift`: first-run dependency/readiness screen.
- Create `macos-native/Sources/AICaptureNativeApp/DeviceAppView.swift`: device pool and app library UI.
- Create `macos-native/Sources/AICaptureNativeApp/CaptureView.swift`: one-click capture and stop controls.
- Create `macos-native/Sources/AICaptureNativeApp/FlowViews.swift`: real-time interface list and request/response detail panels.
- Create `macos-native/Sources/AICaptureNativeApp/LogView.swift`: native log/runtime directory controls.
- Create `macos-native/scripts/build-app.sh`: builds a local `.app` wrapper from the Swift executable and bundled resources.
- Create `macos-native/README.md`: native desktop development, packaging, and user prerequisites.

## Task 1: Native SwiftUI Skeleton

**Files:**
- Create: `macos-native/Package.swift`
- Create: `macos-native/Sources/AICaptureNativeApp/AICaptureNativeApp.swift`
- Create: `macos-native/Sources/AICaptureNativeApp/AppState.swift`
- Create: `macos-native/Sources/AICaptureNativeApp/ContentView.swift`
- Create: `macos-native/README.md`

- [x] **Step 1: Create Swift package manifest**

Create `macos-native/Package.swift`:

```swift
// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "AICaptureNative",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "AI抓包工具", targets: ["AICaptureNativeApp"])
    ],
    targets: [
        .executableTarget(
            name: "AICaptureNativeApp",
            path: "Sources/AICaptureNativeApp"
        )
    ]
)
```

- [x] **Step 2: Add minimal app state**

Create `AppState.swift`:

```swift
import Foundation

@MainActor
final class AppState: ObservableObject {
    enum RuntimeStatus: Equatable {
        case starting
        case ready(String)
        case failed(String)
    }

    @Published var runtimeStatus: RuntimeStatus = .starting
    @Published var selectedSection: SidebarSection = .setup
}

enum SidebarSection: String, CaseIterable, Identifiable {
    case setup = "环境"
    case devices = "设备与应用"
    case capture = "抓包"
    case flows = "接口"
    case logs = "日志"

    var id: String { rawValue }
}
```

- [x] **Step 3: Add SwiftUI entry and shell**

Create `AICaptureNativeApp.swift`:

```swift
import SwiftUI

@main
struct AICaptureNativeApp: App {
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .frame(minWidth: 1180, minHeight: 760)
        }
        .windowStyle(.titleBar)
        .commands {
            CommandGroup(after: .appInfo) {
                Button("刷新状态") {
                    appState.runtimeStatus = .starting
                }
                .keyboardShortcut("r", modifiers: [.command])
            }
        }
    }
}
```

Create `ContentView.swift`:

```swift
import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        NavigationSplitView {
            List(SidebarSection.allCases, selection: $appState.selectedSection) { section in
                Text(section.rawValue)
                    .tag(section)
            }
            .navigationTitle("AI抓包工具")
        } detail: {
            VStack(alignment: .leading, spacing: 18) {
                Text(title)
                    .font(.largeTitle.bold())
                Text("原生 macOS 桌面端骨架已启动。后续阶段会接入本机抓包运行时、设备池、应用库和接口分析。")
                    .foregroundStyle(.secondary)
                runtimeBadge
                Spacer()
            }
            .padding(28)
        }
    }

    private var title: String {
        appState.selectedSection.rawValue
    }

    private var runtimeBadge: some View {
        Group {
            switch appState.runtimeStatus {
            case .starting:
                Label("内部服务准备中", systemImage: "hourglass")
            case .ready(let url):
                Label("内部服务已就绪：\(url)", systemImage: "checkmark.circle.fill")
            case .failed(let message):
                Label("内部服务异常：\(message)", systemImage: "xmark.octagon.fill")
            }
        }
        .font(.headline)
        .padding(12)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}
```

- [x] **Step 4: Add native README**

Create `macos-native/README.md`:

```markdown
# AI抓包工具 macOS 原生桌面端

这是新的 SwiftUI 原生桌面端，不使用 React/WebView 作为主界面。

V1 目标：

- 原生 macOS 窗口。
- 管理本机 FastAPI 抓包运行时。
- 调用现有后端 API 完成设备、应用、抓包和接口分析。
- 后续打包成 `.app/.dmg` 供其他 Mac 用户本机安装使用。

开发验证：

```bash
cd macos-native
swift build
swift run "AI抓包工具"
```
```

- [x] **Step 5: Verify skeleton build**

Run:

```bash
cd macos-native && swift build
```

Expected: build exits 0.

- [x] **Step 6: Commit skeleton**

```bash
git add macos-native docs/superpowers/specs/2026-08-06-macos-native-distributable-design.md docs/superpowers/plans/2026-08-06-macos-native-distributable.md
git commit -m "feat: add native macos desktop skeleton"
```

## Task 2: Backend Runtime Manager

**Files:**
- Create: `macos-native/Sources/AICaptureNativeApp/RuntimeManager.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/AppState.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/AICaptureNativeApp.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/ContentView.swift`

- [x] **Step 1: Add runtime manager**

Create `RuntimeManager.swift` with a class that resolves:

```text
~/Library/Application Support/AI抓包工具/runtime-native/
```

and initially connects to an already running local backend at `http://127.0.0.1:7001`. If it cannot connect, it reports `failed("未检测到本机抓包后端")`. Process-spawn support is added in a later task so this stage stays testable and safe.

- [x] **Step 2: Wire startup health check**

On app launch, call the runtime manager once. Update `AppState.runtimeStatus` to `.ready(url)` if `/api/status` returns HTTP 200.

- [x] **Step 3: Verify with current backend**

Run the existing desktop or web backend, then run:

```bash
cd macos-native
./scripts/build-app.sh
open "build/AI抓包工具.app"
```

Expected: native window shows internal service ready.

Note: SwiftPM裸可执行文件在当前 macOS 环境下会立即退出，因此先补了最小 `.app` 包装脚本作为真实窗口验收入口。

## Task 3: API Models and Device/App Lists

**Files:**
- Create: `macos-native/Sources/AICaptureNativeApp/APIClient.swift`
- Create: `macos-native/Sources/AICaptureNativeApp/Models.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/AppState.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/DeviceAppView.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/ContentView.swift`

- [ ] **Step 1: Add Codable models**

Define minimal Codable models for `/api/devices` and `/api/apps` using optional fields for backward-compatible decoding.

- [ ] **Step 2: Add API client**

Implement `getDevices()` and `getApps()` using `URLSession`.

- [ ] **Step 3: Add native device/app list**

Show device cards and grouped app list in SwiftUI, without WebView.

- [ ] **Step 4: Verify live data**

With backend running, the native app must show at least the same selected device/app data that `/api/devices` and `/api/apps` return.

## Task 4: Native Capture Controls

**Files:**
- Modify: `macos-native/Sources/AICaptureNativeApp/APIClient.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/CaptureView.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/AppState.swift`

- [ ] **Step 1: Add capture APIs**

Implement `startCapture(appId:deviceId:)`, `stopCapture(deviceId:)`, `launchApp(appId:deviceId:)`, and `prepareFrida(deviceId:)`.

- [ ] **Step 2: Add one-click capture UI**

Native UI should expose one primary button: `一键开始抓包`, plus `停止抓包` while running.

- [ ] **Step 3: Verify real capture**

Start capture from the native app, operate the emulator, and confirm a new session appears.

## Task 5: Native Flow List and Detail

**Files:**
- Modify: `macos-native/Sources/AICaptureNativeApp/APIClient.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/Models.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/FlowViews.swift`

- [ ] **Step 1: Add flow APIs**

Implement list/detail/curl calls for existing capture endpoints.

- [ ] **Step 2: Add polling**

Poll active session flows every 2 seconds while capture is running.

- [ ] **Step 3: Add native details**

Use native tabs for Request and Response. Show headers, body, timing, files, and cURL in native SwiftUI views.

- [ ] **Step 4: Verify request/response**

Start a capture, open a flow, and confirm Request/Response content is visible without opening a browser.

## Task 6: Local APK Upload and Packaging

**Files:**
- Modify: `macos-native/Sources/AICaptureNativeApp/APIClient.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/DeviceAppView.swift`
- Create: `macos-native/scripts/build-app.sh`
- Modify: `macos-native/README.md`

- [ ] **Step 1: Add native file importer**

Use SwiftUI file importer for `.apk`, `.apks`, and `.zip`.

- [ ] **Step 2: POST binary upload**

Upload selected package to `/api/apps/install?device_id=...&environment=...`.

- [ ] **Step 3: Build `.app` wrapper**

Create `macos-native/scripts/build-app.sh` to build the Swift executable and assemble a local `.app` bundle with Info.plist and packaged backend resources.

- [ ] **Step 4: Verify copied app**

Copy the `.app` to a temporary directory and open it. It should show first-run setup instead of crashing when dependencies are missing.

## Self-Review

- Spec coverage: Tasks cover native skeleton, runtime status, devices/apps, capture, flows, APK upload, and app packaging.
- Placeholder scan: No TBD/TODO placeholders remain. Later tasks describe exact files and verification outcomes.
- Scope control: V1 keeps FastAPI as the capture engine and only replaces the user-facing desktop UI with SwiftUI.

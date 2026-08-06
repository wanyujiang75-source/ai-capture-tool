import SwiftUI

struct CaptureView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            header
            selectionPanel
            actionPanel
            messagePanel
            Spacer()
        }
        .padding(28)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Color(nsColor: .windowBackgroundColor))
        .task {
            if appState.deviceLoadState == .idle || appState.appLoadState == .idle {
                await appState.refreshDeviceAndApps()
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("抓包")
                .font(.largeTitle.bold())
            Text("选择设备和应用后，可在原生桌面端启动 Frida、打开 App、开始或停止抓包。")
                .foregroundStyle(.secondary)
        }
    }

    private var selectionPanel: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("目标选择")
                .font(.title2.bold())
            Picker("设备", selection: selectedDeviceBinding) {
                if appState.devices.isEmpty {
                    Text("暂无设备").tag("")
                } else {
                    ForEach(appState.devices) { device in
                        Text("\(device.id) · \(device.adbSerial ?? "-")").tag(device.id)
                    }
                }
            }
            Picker("应用", selection: selectedAppBinding) {
                if appState.apps.isEmpty {
                    Text("暂无应用").tag(0)
                } else {
                    ForEach(appState.apps) { app in
                        Text("\(app.name ?? "未命名应用") · \(app.packageName ?? "-")").tag(app.id)
                    }
                }
            }
            selectedSummary
        }
        .padding(18)
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.separator, lineWidth: 1)
        }
    }

    private var actionPanel: some View {
        HStack(spacing: 12) {
            Button {
                Task {
                    await appState.refreshDeviceAndApps()
                }
            } label: {
                Label("刷新", systemImage: "arrow.clockwise")
            }
            Button {
                Task {
                    await appState.prepareSelectedFrida()
                }
            } label: {
                Label("启动 Frida", systemImage: "bolt.fill")
            }
            Button {
                Task {
                    await appState.launchSelectedApp()
                }
            } label: {
                Label("打开应用", systemImage: "app.badge")
            }
            Button {
                Task {
                    await appState.startSelectedCapture()
                }
            } label: {
                Label("一键开始抓包", systemImage: "record.circle")
            }
            .buttonStyle(.borderedProminent)
            Button(role: .destructive) {
                Task {
                    await appState.stopSelectedCapture()
                }
            } label: {
                Label("停止抓包", systemImage: "stop.circle")
            }
        }
        .disabled(isBusy)
    }

    private var messagePanel: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Circle()
                    .fill(messageColor)
                    .frame(width: 9, height: 9)
                Text(messageTitle)
                    .font(.headline)
            }
            Text(appState.captureMessage.isEmpty ? "等待操作。" : appState.captureMessage)
                .foregroundStyle(.secondary)
            if let activeSessionID = appState.activeSessionID {
                Text("当前 Session：#\(activeSessionID)")
                    .font(.callout.monospaced())
                    .foregroundStyle(.secondary)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private var selectedSummary: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("当前设备：\(appState.selectedDevice?.name ?? appState.selectedDeviceID ?? "-")")
            Text("当前应用：\(appState.selectedApp?.name ?? "-")")
            Text("默认模式：\(appState.selectedApp?.defaultMode ?? "auto")")
        }
        .font(.callout)
        .foregroundStyle(.secondary)
    }

    private var selectedDeviceBinding: Binding<String> {
        Binding {
            appState.selectedDeviceID ?? ""
        } set: { value in
            appState.selectedDeviceID = value.isEmpty ? nil : value
        }
    }

    private var selectedAppBinding: Binding<Int> {
        Binding {
            appState.selectedAppID ?? 0
        } set: { value in
            appState.selectedAppID = value == 0 ? nil : value
        }
    }

    private var isBusy: Bool {
        appState.captureActionState == .loading
    }

    private var messageTitle: String {
        switch appState.captureActionState {
        case .idle:
            "待操作"
        case .loading:
            "执行中"
        case .loaded:
            "已完成"
        case .failed:
            "执行失败"
        }
    }

    private var messageColor: Color {
        switch appState.captureActionState {
        case .idle:
            .gray
        case .loading:
            .orange
        case .loaded:
            .green
        case .failed:
            .red
        }
    }
}

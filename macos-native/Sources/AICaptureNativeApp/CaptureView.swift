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
            if appState.deviceLoadState == .idle {
                await appState.refreshDevices()
            }
            await appState.monitorForegroundTarget()
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("抓包")
                .font(.largeTitle.bold())
            Text("打开设备中的目标 App 后自动识别并检查抓包能力。")
                .foregroundStyle(.secondary)
        }
    }

    private var selectionPanel: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("目标选择")
                .font(.title2.bold())
            HStack(spacing: 12) {
                Picker("设备", selection: selectedDeviceBinding) {
                    if appState.devices.isEmpty {
                        Text("暂无设备").tag("")
                    } else {
                        ForEach(appState.devices) { device in
                            Text("\(device.id) · \(device.adbSerial ?? "-")").tag(device.id)
                        }
                    }
                }
                Button {
                    Task {
                        await appState.startSelectedDevice()
                    }
                } label: {
                    Label("打开模拟器", systemImage: "iphone.gen3.radiowaves.left.and.right")
                }
            }
            foregroundTargetCard
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
                    await appState.refreshDevices()
                    await appState.refreshForegroundTarget(forceResolve: true)
                }
            } label: {
                Label("刷新", systemImage: "arrow.clockwise")
            }
            Button {
                Task {
                    _ = await appState.prepareSelectedEnvironment(visible: true)
                }
            } label: {
                Label("一键准备环境", systemImage: "checklist.checked")
            }
            Button {
                Task {
                    await appState.startSelectedCapture()
                }
            } label: {
                Label("一键开始抓包", systemImage: "record.circle")
            }
            .buttonStyle(.borderedProminent)
            .disabled(!appState.canStartForegroundCapture)
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

    private var foregroundTargetCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: appState.foregroundTarget?.app == nil ? "app.dashed" : "app.fill")
                    .foregroundStyle(foregroundTargetColor)
                Text(appState.foregroundTarget?.app?.name ?? "等待前台应用")
                    .font(.headline)
                Spacer()
                Text(foregroundStateLabel)
                    .font(.caption.bold())
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(.thinMaterial)
                    .clipShape(Capsule())
            }
            Text(appState.foregroundTarget?.packageName ?? "请在模拟器中打开需要分析的 App")
                .font(.callout.monospaced())
                .foregroundStyle(.secondary)
            if let activity = appState.foregroundTarget?.activity, !activity.isEmpty {
                Text(activity)
                    .font(.caption.monospaced())
                    .foregroundStyle(.secondary)
            }
            Text(appState.foregroundCaptureGuidance)
                .font(.callout)
                .foregroundStyle(.secondary)
        }
        .padding(14)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var foregroundStateLabel: String {
        switch appState.foregroundTarget?.captureState {
        case "ready": "可开始"
        case "waiting_traffic": "等待流量"
        case "capturable": "可抓包"
        case "blocked": "可自动准备"
        default: "自动检测"
        }
    }

    private var foregroundTargetColor: Color {
        switch appState.foregroundTarget?.captureState {
        case "ready", "capturable": .green
        case "blocked": .blue
        default: .orange
        }
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

    private var selectedDeviceBinding: Binding<String> {
        Binding {
            appState.selectedDeviceID ?? ""
        } set: { value in
            appState.selectedDeviceID = value.isEmpty ? nil : value
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

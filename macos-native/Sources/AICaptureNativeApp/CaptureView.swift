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
            if appState.deviceLoadState == .idle || appState.jenkinsLoadState == .idle {
                await appState.refreshCaptureTargets()
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
            Picker("应用", selection: selectedAppBinding) {
                if appState.jenkinsPackages.isEmpty {
                    Text("暂无 Jenkins 包").tag("")
                } else {
                    ForEach(appState.jenkinsPackages) { package in
                        Text("\(package.jobName) #\(package.buildNumber) · \(package.artifactFileName)").tag(package.id)
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
                    await appState.refreshCaptureTargets()
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
            Text("Jenkins 包：\(appState.selectedJenkinsPackage?.jobName ?? "-")")
            Text("构建产物：\(appState.selectedJenkinsPackage?.artifactFileName ?? "-")")
            Text("安装后应用：\(appState.selectedApp?.name ?? "操作时自动解析")")
            Text("默认模式：\(appState.selectedApp?.defaultMode ?? "flutter-socks")")
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

    private var selectedAppBinding: Binding<String> {
        Binding {
            appState.selectedJenkinsPackageID ?? ""
        } set: { value in
            appState.selectedJenkinsPackageID = value.isEmpty ? nil : value
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

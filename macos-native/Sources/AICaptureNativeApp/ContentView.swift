import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var appState: AppState
    @State private var showsRuntimeCheck = false

    var body: some View {
        NavigationSplitView {
            List(SidebarSection.allCases, selection: $appState.selectedSection) { section in
                Label(section.rawValue, systemImage: section.systemImage)
                    .tag(section)
            }
            .navigationTitle("抓包工具")
        } detail: {
            switch appState.selectedSection {
            case .capture:
                CaptureView(showsRuntimeCheck: $showsRuntimeCheck)
            case .install:
                DeviceAppView()
            case .flows:
                FlowViews()
            case .logs:
                LogsView()
            }
        }
        .toolbar {
            ToolbarItem {
                Button {
                    showsRuntimeCheck = true
                } label: {
                    Label(AppCopy.Navigation.runtimeCheck, systemImage: "stethoscope")
                }
            }
        }
        .sheet(isPresented: $showsRuntimeCheck) {
            RuntimeCheckView()
                .environmentObject(appState)
        }
        .overlay(alignment: .bottomTrailing) {
            if let notice = appState.notice {
                TransientNoticeView(notice: notice)
                    .padding(24)
                    .transition(.move(edge: .trailing).combined(with: .opacity))
            }
        }
        .animation(.easeInOut(duration: 0.2), value: appState.notice?.id)
        .task {
            await appState.refreshRuntimeStatus()
        }
    }
}

private struct TransientNoticeView: View {
    let notice: UserNotice

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: notice.tone == .success ? "checkmark.circle.fill" : "exclamationmark.circle.fill")
                .font(.title2)
                .foregroundStyle(accentColor)
            VStack(alignment: .leading, spacing: 6) {
                Text(notice.title)
                    .font(.headline)
                Text(notice.message)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(18)
        .frame(width: 390, alignment: .leading)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(accentColor, lineWidth: 2)
        }
        .shadow(color: accentColor.opacity(0.18), radius: 18, y: 8)
        .accessibilityElement(children: .combine)
    }

    private var accentColor: Color {
        notice.tone == .success ? .green : .red
    }
}

private struct RuntimeCheckView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HStack {
                VStack(alignment: .leading, spacing: 6) {
                    Text(AppCopy.Navigation.runtimeCheck)
                        .font(.largeTitle.bold())
                    Text("检查开始抓包所需的四项本机能力。")
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("关闭") {
                    dismiss()
                }
            }

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                checkCard(title: "本机环境", result: runtimeSummary, ok: runtimeOK)
                checkCard(title: "模拟器", result: emulatorSummary, ok: emulatorOK)
                checkCard(title: "网络", result: networkSummary, ok: emulatorOK)
                checkCard(title: "抓包组件", result: componentSummary, ok: componentOK)
            }

            DisclosureGroup("技术详情") {
                VStack(alignment: .leading, spacing: 8) {
                    if case let .ready(url) = appState.runtimeStatus {
                        LabeledContent("本机服务", value: url)
                    }
                    if let runtimeDirectory = appState.runtimeDirectory {
                        LabeledContent("运行目录", value: runtimeDirectory.path)
                    }
                    if let device = appState.selectedDevice {
                        LabeledContent("设备标识", value: device.adbSerial ?? device.id)
                        LabeledContent("设备配置", value: device.avdName ?? "-")
                    }
                    if case let .failed(issue) = appState.captureWorkflowState,
                       let technicalDetail = issue.technicalDetail,
                       !technicalDetail.isEmpty {
                        Text(technicalDetail)
                            .font(.caption.monospaced())
                            .textSelection(.enabled)
                    }
                }
                .padding(.top, 10)
            }

            HStack {
                Button {
                    Task {
                        await appState.refreshRuntimeStatus()
                    }
                } label: {
                    Label("重新检查", systemImage: "arrow.clockwise")
                }
                .buttonStyle(.borderedProminent)
                Spacer()
            }
        }
        .padding(28)
        .frame(minWidth: 720, minHeight: 520, alignment: .topLeading)
    }

    private func checkCard(title: String, result: String, ok: Bool) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: ok ? "checkmark.circle.fill" : "exclamationmark.circle.fill")
                    .foregroundStyle(ok ? .green : .orange)
                Text(title)
                    .font(.headline)
            }
            Text(result)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(16)
        .frame(maxWidth: .infinity, minHeight: 100, alignment: .topLeading)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private var runtimeOK: Bool {
        if case .ready = appState.runtimeStatus {
            return true
        }
        return false
    }

    private var runtimeSummary: String {
        runtimeOK ? "本机服务可用。" : "本机服务暂时不可用，请重新检查。"
    }

    private var emulatorOK: Bool {
        appState.selectedDevice?.emulator?.adbOnline == true
            && appState.selectedDevice?.emulator?.bootCompleted == true
            && appState.selectedDevice?.emulator?.unlocked == true
    }

    private var emulatorSummary: String {
        guard appState.selectedDevice?.emulator?.adbOnline == true else {
            return "模拟器尚未连接。"
        }
        guard appState.selectedDevice?.emulator?.bootCompleted == true else {
            return "Android 系统正在启动。"
        }
        guard appState.selectedDevice?.emulator?.unlocked == true else {
            return "请在模拟器中解锁屏幕。"
        }
        return "模拟器已连接并解锁。"
    }

    private var networkSummary: String {
        emulatorOK ? "开始抓包时会自动检查并切换网络模式。" : "连接模拟器后才能检查网络。"
    }

    private var componentOK: Bool {
        switch appState.captureWorkflowState {
        case .capturing, .restored:
            true
        case .failed:
            false
        default:
            emulatorOK
        }
    }

    private var componentSummary: String {
        switch appState.captureWorkflowState {
        case .capturing, .restored:
            "抓包组件正在工作。"
        case .failed:
            "抓包组件需要修复，请查看技术详情。"
        default:
            emulatorOK ? "开始抓包时会自动检查并启动。" : "模拟器就绪后才能检查。"
        }
    }
}

import SwiftUI

struct CaptureView: View {
    @EnvironmentObject private var appState: AppState
    @Binding var showsRuntimeCheck: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            header
            targetPanel
            workflowPanel
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
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 8) {
                Text(AppCopy.Navigation.capture)
                    .font(.largeTitle.bold())
                Text("打开模拟器中的应用，工具会自动识别并抓取接口。")
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button {
                Task {
                    await appState.startSelectedDevice()
                }
            } label: {
                Label(emulatorButtonTitle, systemImage: "iphone.gen3.radiowaves.left.and.right")
            }
        }
    }

    private var targetPanel: some View {
        VStack(alignment: .leading, spacing: 16) {
            if appState.showsDeviceSelector {
                Picker("使用设备", selection: selectedDeviceBinding) {
                    ForEach(appState.devices) { device in
                        Text(device.name ?? "Android 模拟器").tag(device.id)
                    }
                }
                .frame(maxWidth: 360)
            }

            HStack(spacing: 14) {
                Image(systemName: appState.foregroundTarget?.app == nil ? "app.dashed" : "app.fill")
                    .font(.title2)
                    .foregroundStyle(appState.foregroundTarget?.app == nil ? .orange : .blue)
                VStack(alignment: .leading, spacing: 4) {
                    Text(appState.foregroundTarget?.app?.name.map { "已识别“\($0)”" } ?? "等待应用")
                        .font(.headline)
                    Text(targetGuidance)
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }
        }
        .padding(18)
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.separator, lineWidth: 1)
        }
    }

    private var workflowPanel: some View {
        let state = appState.displayedCaptureWorkflowState
        let presentation = state.presentation
        return VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .top, spacing: 12) {
                Circle()
                    .fill(color(for: state.tone))
                    .frame(width: 11, height: 11)
                    .padding(.top, 7)
                VStack(alignment: .leading, spacing: 6) {
                    Text(presentation.title)
                        .font(.title2.bold())
                    Text(presentation.message)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                if state.tone == .progress {
                    ProgressView()
                        .controlSize(.small)
                }
            }

            HStack(spacing: 12) {
                if let action = presentation.primaryAction,
                   let title = presentation.primaryButtonTitle {
                    Button {
                        perform(action)
                    } label: {
                        Label(title, systemImage: primaryIcon(for: action))
                    }
                    .buttonStyle(.borderedProminent)
                }
                if let action = presentation.secondaryAction,
                   let title = presentation.secondaryButtonTitle {
                    Button(title) {
                        perform(action)
                    }
                }
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(color(for: state.tone).opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(color(for: state.tone).opacity(0.28), lineWidth: 1)
        }
    }

    private var selectedDeviceBinding: Binding<String> {
        Binding {
            appState.selectedDeviceID ?? ""
        } set: { value in
            appState.selectedDeviceID = value.isEmpty ? nil : value
        }
    }

    private var emulatorButtonTitle: String {
        appState.selectedDevice?.emulator?.adbOnline == true
            ? AppCopy.Capture.showEmulator
            : AppCopy.Capture.startEmulator
    }

    private var targetGuidance: String {
        if appState.foregroundTarget?.app != nil {
            return "工具会自动检查该应用的抓包环境。"
        }
        return "请在模拟器中打开需要分析的应用。"
    }

    private func perform(_ action: CaptureWorkflowAction) {
        switch action {
        case .startCapture:
            Task {
                await appState.startCaptureWorkflow()
            }
        case .stopCapture:
            Task {
                await appState.stopSelectedCapture()
            }
        case .showEmulator:
            Task {
                await appState.startSelectedDevice()
            }
        case .stopAndSwitch:
            Task {
                await appState.stopAndSwitchCapture()
            }
        case .continueCurrent:
            appState.continueCurrentCapture()
        case .openRuntimeCheck:
            showsRuntimeCheck = true
        }
    }

    private func primaryIcon(for action: CaptureWorkflowAction) -> String {
        switch action {
        case .startCapture:
            "record.circle"
        case .stopCapture, .stopAndSwitch:
            "stop.circle"
        case .showEmulator:
            "iphone.gen3.radiowaves.left.and.right"
        case .continueCurrent:
            "arrow.forward.circle"
        case .openRuntimeCheck:
            "stethoscope"
        }
    }

    private func color(for tone: CaptureWorkflowTone) -> Color {
        switch tone {
        case .neutral:
            .gray
        case .progress:
            .blue
        case .warning:
            .orange
        case .success:
            .green
        case .error:
            .red
        }
    }
}

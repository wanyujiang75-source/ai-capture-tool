import SwiftUI

struct CaptureHomeView: View {
    @EnvironmentObject private var appState: AppState
    @Binding var showsRuntimeCheck: Bool

    var body: some View {
        VStack(spacing: 0) {
            Picker(AppCopy.IOSCapture.platform, selection: $appState.selectedCapturePlatform) {
                ForEach(CapturePlatform.allCases) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented)
            .frame(width: 280)
            .padding(.top, 20)
            .frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 28)
            if appState.selectedCapturePlatform == .android {
                CaptureView(showsRuntimeCheck: $showsRuntimeCheck)
            } else {
                IOSCaptureView(controller: appState.iosController)
            }
        }
    }
}

struct IOSCaptureView: View {
    @EnvironmentObject private var appState: AppState
    @ObservedObject var controller: IOSSetupController
    @State private var showsSetup = false
    @State private var confirmsRemoval = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                HStack {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(AppCopy.IOSCapture.title).font(.largeTitle.bold())
                        Text(AppCopy.IOSCapture.summary).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button(controller.status.canPrepare ? AppCopy.IOSSetup.title : AppCopy.IOSCapture.configure) { showsSetup = true }
                }
                statusCard
                HStack(spacing: 12) {
                    if controller.status.isRecording {
                        Button(AppCopy.IOSCapture.stop) { Task { await controller.stopRecording() } }
                            .buttonStyle(.borderedProminent).disabled(controller.busy)
                    } else {
                        Button(AppCopy.IOSCapture.start) {
                            Task {
                                await controller.startRecording()
                                if controller.status.isRecording { await showResults() }
                            }
                        }.buttonStyle(.borderedProminent).disabled(!controller.canStartRecording)
                    }
                    Button(AppCopy.IOSCapture.viewResults) { Task { await showResults() } }
                        .disabled(controller.status.sessionID == nil || controller.busy)
                    Spacer()
                    if !controller.status.canPrepare || controller.status.identityReused == true {
                        Button(AppCopy.IOSSetup.stop, role: .destructive) { confirmsRemoval = true }
                            .disabled(controller.busy)
                    }
                }
                Text(AppCopy.IOSCapture.stopHelp).font(.callout).foregroundStyle(.secondary)
                Text(AppCopy.IOSCapture.scope).font(.callout).foregroundStyle(.secondary)
            }.padding(28)
        }
        .task { await controller.refresh() }
        .sheet(isPresented: $showsSetup) { IOSSetupView(controller: controller) }
        .alert(AppCopy.IOSSetup.remove, isPresented: $confirmsRemoval) {
            Button(AppCopy.IOSSetup.confirmRemoved) { Task { await controller.stop(phoneConfigurationRemoved: true) } }
            Button(AppCopy.IOSSetup.cancel, role: .cancel) {}
        } message: { Text(AppCopy.IOSSetup.removeHelp) }
    }

    private var statusCard: some View {
        let presentation = AppCopy.IOSCapture.presentation(controller.status)
        return VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: controller.issue != nil ? "exclamationmark.circle.fill" : "iphone")
                    .foregroundStyle(controller.issue != nil ? .red : .accentColor)
                Text(controller.operation?.title ?? presentation.0).font(.title3.bold())
                Spacer()
                if controller.busy { ProgressView().controlSize(.small) }
            }
            Text(presentation.1).foregroundStyle(.secondary)
            if let issue = controller.issue {
                Text(issue).foregroundStyle(.red)
                Button(AppCopy.IOSCapture.checkConnection) { Task { await controller.refresh() } }.disabled(controller.busy)
            }
        }
        .padding(20).frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.accentColor.opacity(0.06), in: RoundedRectangle(cornerRadius: 18))
    }

    private func showResults() async {
        guard let id = controller.status.sessionID else { return }
        await appState.refreshFlowSources()
        guard appState.flowSources.contains(where: { $0.id == id }) else {
            appState.showNotice(.failure(title: AppCopy.IOSCapture.resultsUnavailable, message: AppCopy.IOSCapture.sourcesFailed))
            return
        }
        appState.selectFlowSource(id)
        appState.selectedSection = .flows
    }
}

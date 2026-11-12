import SwiftUI

struct AndroidPhysicalView: View {
    @EnvironmentObject private var appState: AppState
    @ObservedObject var controller: AndroidPhysicalController
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                HStack {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(AppCopy.AndroidPhysical.heading).font(.largeTitle.bold())
                        Text(AppCopy.AndroidPhysical.subtitle).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button(AppCopy.AndroidPhysical.discover) { Task { await controller.discover() } }
                        .disabled(controller.busy)
                }
                VStack(alignment: .leading, spacing: 14) {
                    if controller.devices.isEmpty { Text(AppCopy.AndroidPhysical.noDevices) }
                    else if controller.devices.count > 1 {
                        Picker(AppCopy.AndroidPhysical.chooseDevice, selection: $controller.serial) {
                            ForEach(controller.devices) { Text(AppCopy.AndroidPhysical.phoneLabel(name: $0.label, serial: $0.serial)).tag($0.serial) }
                        }.disabled(!controller.status.canStart)
                    } else { Label(controller.devices[0].label, systemImage: "smartphone") }
                    if controller.devices.first(where: { $0.serial == controller.serial })?.status == "unauthorized" {
                        Text(AppCopy.AndroidPhysical.unauthorized).foregroundStyle(.orange)
                    }
                    Text(AppCopy.AndroidPhysical.boundary).foregroundStyle(.secondary)
                    Text(AppCopy.AndroidPhysical.network).foregroundStyle(.secondary)
                    Toggle(AppCopy.AndroidPhysical.consent, isOn: $controller.consent).disabled(!controller.status.canStart)
                }.padding(20).background(.quaternary.opacity(0.35), in: RoundedRectangle(cornerRadius: 18))
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text(controller.status.title).font(.title2.bold())
                        if controller.busy || [.preparing, .stopping, .terminating].contains(controller.status.phase) { ProgressView().controlSize(.small) }
                    }
                    if let label = controller.currentDeviceLabel {
                        Text(AppCopy.AndroidPhysical.currentDevice + "：" + label)
                        if !controller.isConnected(controller.status.serial ?? "") {
                            Text(AppCopy.AndroidPhysical.originalDisconnected).foregroundStyle(.orange)
                        }
                    }
                    if let message = controller.status.message { Text(message) }
                    if controller.status.phase == .capturing { Text(AppCopy.AndroidPhysical.count(controller.status)) }
                    if (controller.status.tlsFailures ?? 0) > 0 { Text(AppCopy.AndroidPhysical.tlsFailure).foregroundStyle(.orange) }
                    if let issue = controller.issue { Text(issue).foregroundStyle(.red) }
                    HStack {
                        Button(actionTitle) { Task { await controller.perform() } }.buttonStyle(.borderedProminent)
                            .disabled(!controller.canPerform)
                        if controller.canTerminate || controller.status.phase == .terminating {
                            Button(AppCopy.AndroidPhysical.terminate) { Task { await controller.terminate() } }
                                .disabled(!controller.canTerminate)
                                .help(AppCopy.AndroidPhysical.terminateHelp)
                        }
                        if let id = controller.status.sessionID {
                            Button(AppCopy.AndroidPhysical.results) {
                                Task {
                                    await appState.refreshFlowSources()
                                    appState.selectFlowSource(id)
                                    appState.selectedSection = .flows
                                }
                            }.disabled(controller.status.phase == .preparing)
                        }
                    }
                }.padding(20).frame(maxWidth: .infinity, alignment: .leading)
                    .background(.quaternary.opacity(0.35), in: RoundedRectangle(cornerRadius: 18))
                if let pending = controller.status.pendingRecoveries, !pending.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(AppCopy.AndroidPhysical.pendingTitle).font(.headline)
                        Text(AppCopy.AndroidPhysical.pendingHelp).foregroundStyle(.secondary)
                        ForEach(pending) { phone in
                            HStack {
                                Label(phone.label, systemImage: "exclamationmark.triangle")
                                Spacer()
                                Button(AppCopy.AndroidPhysical.recover) { Task { await controller.recover(phone.serial) } }
                                    .disabled(!controller.canRecover(phone.serial))
                            }
                        }
                    }.padding(20).background(.orange.opacity(0.08), in: RoundedRectangle(cornerRadius: 18))
                }
                VStack(alignment: .leading, spacing: 12) {
                    Text(AppCopy.AndroidPhysical.instructions).font(.headline)
                    ForEach(Array(AppCopy.AndroidPhysical.steps.enumerated()), id: \.offset) { index, step in Text("\(index + 1). \(step)") }
                    Text(AppCopy.AndroidPhysical.automatic).foregroundStyle(.secondary)
                    Text(AppCopy.AndroidPhysical.recovery).foregroundStyle(.secondary)
                    DisclosureGroup(AppCopy.AndroidPhysical.details) {
                        VStack(alignment: .leading) {
                            if let serial = controller.status.serial { Text(serial) }
                            if let package = controller.status.package { Text(package) }
                            if let upstream = controller.status.upstream { Text(upstream) }
                            if let vpn = controller.status.originalVPN { Text(vpn) }
                        }.textSelection(.enabled).font(.system(.caption, design: .monospaced))
                    }
                }
            }.padding(28)
        }.task {
            await controller.discover()
            while !Task.isCancelled {
                await controller.refresh()
                try? await Task.sleep(for: .seconds(2))
            }
        }
    }
    private var actionTitle: String {
        switch controller.status.action {
        case .start: AppCopy.AndroidPhysical.start
        case .stop: AppCopy.AndroidPhysical.stop
        case .recover: AppCopy.AndroidPhysical.recover
        case .none: controller.status.title
        }
    }
}

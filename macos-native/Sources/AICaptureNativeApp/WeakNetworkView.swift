import SwiftUI

struct WeakNetworkView: View {
    let deviceID: String?
    let online: Bool
    @StateObject private var controller = WeakNetworkController()
    @State private var showsDetails = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Label(AppCopy.WeakNetwork.title, systemImage: "wifi.exclamationmark")
                    .font(.headline)
                Spacer()
                Text(statusLabel)
                    .foregroundStyle(controller.status?.enabled == true ? .orange : .secondary)
            }
            Text(AppCopy.WeakNetwork.scope).font(.callout).foregroundStyle(.secondary)
            Picker(AppCopy.WeakNetwork.profile, selection: Binding(
                get: { controller.preset }, set: { controller.choosePreset($0) }
            )) {
                Text(AppCopy.WeakNetwork.normalProfile).tag("normal")
                Text(AppCopy.WeakNetwork.light).tag("light")
                Text(AppCopy.WeakNetwork.severe).tag("severe")
                Text(AppCopy.WeakNetwork.custom).tag("custom")
            }
            .pickerStyle(.segmented)
            .frame(maxWidth: 480)
            .disabled(controller.busy)
            HStack(spacing: 18) {
                field(AppCopy.WeakNetwork.upload, at: \.upload)
                field(AppCopy.WeakNetwork.download, at: \.download)
                field(AppCopy.WeakNetwork.latency, at: \.latency)
            }
            .disabled(controller.busy || controller.preset == "normal")
            Text(AppCopy.WeakNetwork.units).font(.caption).foregroundStyle(.secondary)
            if let applied = controller.status?.profile, controller.status?.enabled == true {
                Text(AppCopy.WeakNetwork.applied(applied)).font(.callout).foregroundStyle(.orange)
            }
            HStack {
                Button(controller.preset == "normal" ? AppCopy.WeakNetwork.restore : AppCopy.WeakNetwork.apply) {
                    Task { await controller.apply() }
                }
                    .disabled(deviceID == nil || controller.busy ||
                              (controller.preset != "normal" && (!online || controller.status?.pendingRestore == true)))
                if controller.preset != "normal" {
                    Button(AppCopy.WeakNetwork.restore) { Task { await controller.restore() } }
                        .disabled(deviceID == nil || controller.busy)
                }
                if controller.busy { ProgressView().controlSize(.small) }
                if controller.status?.technicalDetail.isEmpty == false {
                    Button(AppCopy.Navigation.runtimeCheck) { showsDetails = true }
                }
            }
            Text(controller.busy ? AppCopy.WeakNetwork.changing : message)
                .font(.callout)
                .foregroundStyle(controller.issue != nil || controller.status?.pendingRestore == true ? .orange : .secondary)
                .textSelection(.enabled)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay { RoundedRectangle(cornerRadius: 18).stroke(.separator, lineWidth: 1) }
        .task(id: deviceID) {
            await controller.selectDevice(deviceID)
            while !Task.isCancelled {
                do { try await Task.sleep(for: .seconds(5)) } catch { return }
                await controller.refresh()
            }
        }
        .sheet(isPresented: $showsDetails) {
            VStack(alignment: .leading, spacing: 16) {
                Text(AppCopy.Navigation.runtimeCheck).font(.title2.bold())
                Text(AppCopy.WeakNetwork.technicalDetail).font(.headline)
                ScrollView { Text(controller.status?.technicalDetail ?? "").textSelection(.enabled) }
                Button(AppCopy.WeakNetwork.close) { showsDetails = false }
            }
            .padding(24)
            .frame(width: 580, height: 300)
        }
    }

    private var message: String {
        if let issue = controller.issue { return issue }
        if controller.status?.pendingRestore == true { return controller.status?.message ?? "" }
        if !online { return AppCopy.WeakNetwork.offline }
        return controller.status?.message ?? AppCopy.WeakNetwork.checking
    }

    private var statusLabel: String {
        guard let status = controller.status else { return AppCopy.WeakNetwork.checking }
        if status.pendingRestore { return AppCopy.WeakNetwork.pending }
        if !status.available { return AppCopy.WeakNetwork.failed }
        return status.enabled ? AppCopy.WeakNetwork.active : AppCopy.WeakNetwork.normal
    }

    private func field(_ title: String, at keyPath: ReferenceWritableKeyPath<WeakNetworkController, String>) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            TextField(title, text: Binding(get: { controller[keyPath: keyPath] }, set: {
                controller.editValue($0, at: keyPath)
            }))
                .textFieldStyle(.roundedBorder)
                .frame(maxWidth: 180)
        }
    }
}

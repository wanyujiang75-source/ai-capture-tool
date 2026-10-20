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
                Text(AppCopy.WeakNetwork.twoG).tag("2g")
                Text(AppCopy.WeakNetwork.threeG).tag("3g")
                Text(AppCopy.WeakNetwork.fourG).tag("4g")
                Text(AppCopy.WeakNetwork.unlimited).tag("unlimited")
            }
            .pickerStyle(.segmented)
            .frame(maxWidth: 480)
            .disabled(controller.busy)
            if let selected = controller.profile {
                Text(AppCopy.WeakNetwork.selected(selected)).font(.callout)
            } else {
                Text(controller.preset == "unlimited"
                     ? AppCopy.WeakNetwork.unlimitedDescription : AppCopy.WeakNetwork.selectProfile)
                    .font(.callout)
            }
            Text(AppCopy.WeakNetwork.units).font(.caption).foregroundStyle(.secondary)
            if let applied = controller.status?.profile, controller.status?.enabled == true {
                Text(AppCopy.WeakNetwork.applied(applied)).font(.callout).foregroundStyle(.orange)
            }
            HStack {
                Button(controller.preset == "unlimited" ? AppCopy.WeakNetwork.restore : AppCopy.WeakNetwork.apply) {
                    Task { await controller.apply() }
                }
                    .disabled(deviceID == nil || controller.busy ||
                              (controller.preset != "unlimited" &&
                               (!online || controller.profile == nil || controller.status?.pendingRestore == true)))
                if controller.preset != "unlimited" {
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

}

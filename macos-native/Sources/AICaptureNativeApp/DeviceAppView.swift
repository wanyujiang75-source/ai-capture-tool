import SwiftUI
import UniformTypeIdentifiers

struct DeviceAppView: View {
    @EnvironmentObject private var appState: AppState
    @State private var showingAPKPicker = false
    @State private var searchText = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                installationTarget
                localPackageSection
                jenkinsSection
            }
            .padding(28)
            .frame(maxWidth: .infinity, alignment: .topLeading)
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .fileImporter(
            isPresented: $showingAPKPicker,
            allowedContentTypes: [UTType(filenameExtension: "apk", conformingTo: .data) ?? .data],
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case let .success(urls):
                guard let fileURL = urls.first else {
                    return
                }
                Task {
                    await appState.installLocalAPK(fileURL)
                }
            case .failure:
                let message = "无法读取所选 APK，请重新选择文件。"
                appState.localInstallMessage = message
                appState.localInstallState = .failed(message)
                appState.showNotice(.failure(title: "无法读取安装包", message: message))
            }
        }
        .task {
            if appState.deviceLoadState == .idle || appState.jenkinsLoadState == .idle {
                await appState.refreshWorkspaceData()
            }
        }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline, spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                Text(AppCopy.Navigation.installApps)
                    .font(.largeTitle.bold())
                Text(AppCopy.Install.pageDescription)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button {
                Task {
                    await appState.refreshWorkspaceData()
                }
            } label: {
                Label("刷新安装包", systemImage: "arrow.clockwise")
            }
        }
    }

    @ViewBuilder
    private var installationTarget: some View {
        if appState.showsDeviceSelector {
            SectionPanel(title: "安装目标") {
                Picker("使用设备", selection: selectedDeviceBinding) {
                    ForEach(appState.devices) { device in
                        Text(device.name ?? "模拟器").tag(device.id)
                    }
                }
                .frame(maxWidth: 420)
            }
        } else if let readinessMessage {
            HStack(spacing: 10) {
                Image(systemName: "exclamationmark.circle.fill")
                    .foregroundStyle(.orange)
                Text(readinessMessage)
                    .foregroundStyle(.secondary)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.orange.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }
    }

    private var localPackageSection: some View {
        SectionPanel(title: "安装本地 APK") {
            HStack(spacing: 14) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("选择 Mac 中的 APK 安装到当前模拟器。")
                        .foregroundStyle(.secondary)
                    if !appState.localInstallMessage.isEmpty {
                        Text(appState.localInstallMessage)
                            .font(.callout)
                            .foregroundStyle(localInstallMessageColor)
                    }
                }
                Spacer()
                if appState.localInstallState == .loading {
                    ProgressView()
                        .controlSize(.small)
                }
                Button {
                    showingAPKPicker = true
                } label: {
                    Label(AppCopy.Install.chooseAPK, systemImage: "folder.badge.plus")
                }
                .buttonStyle(.borderedProminent)
                .disabled(appState.localInstallState == .loading)
            }
        }
    }

    private var jenkinsSection: some View {
        SectionPanel(title: "Jenkins 测试包") {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 10) {
                    Image(systemName: "magnifyingglass")
                        .foregroundStyle(.secondary)
                    TextField(AppCopy.Install.searchPlaceholder, text: $searchText)
                        .textFieldStyle(.plain)
                    if !searchText.isEmpty {
                        Button {
                            searchText = ""
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundStyle(.secondary)
                        }
                        .buttonStyle(.plain)
                        .help("清空搜索")
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .background(Color(nsColor: .controlBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 10))

                if !appState.jenkinsMessage.isEmpty {
                    Text(appState.jenkinsMessage)
                        .font(.callout)
                        .foregroundStyle(jenkinsMessageColor)
                }

                jenkinsContent
            }
        }
    }

    @ViewBuilder
    private var jenkinsContent: some View {
        switch appState.jenkinsLoadState {
        case .idle, .loading:
            ProgressView("正在获取 Jenkins 最新安装包…")
                .padding(.vertical, 12)
        case .failed:
            EmptyStateView(text: AppCopy.Install.jenkinsUnavailable)
        case .loaded:
            if appState.jenkinsPackages.isEmpty {
                EmptyStateView(text: AppCopy.Install.missingArtifact)
            } else if filteredPackages.isEmpty {
                EmptyStateView(text: "没有匹配的安装包，请更换搜索关键词。")
            } else {
                LazyVStack(spacing: 10) {
                    ForEach(filteredPackages) { package in
                        JenkinsPackageRow(
                            package: package,
                            installing: appState.installingJenkinsPackageID == package.id,
                            disabled: appState.jenkinsInstallState == .loading
                        ) {
                            Task {
                                await appState.installJenkinsPackage(package)
                            }
                        }
                    }
                }
            }
        }
    }

    private var filteredPackages: [JenkinsPackage] {
        let query = searchText.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !query.isEmpty else {
            return appState.jenkinsPackages
        }
        return appState.jenkinsPackages.filter { package in
            [
                package.jobName,
                package.artifactFileName,
                String(package.buildNumber),
            ].contains { $0.lowercased().contains(query) }
        }
    }

    private var selectedDeviceBinding: Binding<String> {
        Binding {
            appState.selectedDeviceID ?? ""
        } set: { value in
            appState.selectedDeviceID = value.isEmpty ? nil : value
        }
    }

    private var readinessMessage: String? {
        guard let device = appState.selectedDevice,
              device.emulator?.adbOnline == true else {
            return AppCopy.Install.emulatorOffline
        }
        guard device.emulator?.bootCompleted == true else {
            return AppCopy.Install.emulatorBooting
        }
        guard device.emulator?.unlocked == true else {
            return AppCopy.Install.emulatorLocked
        }
        return nil
    }

    private var jenkinsMessageColor: Color {
        switch appState.jenkinsInstallState {
        case .failed:
            .red
        case .loaded:
            .green
        default:
            .secondary
        }
    }

    private var localInstallMessageColor: Color {
        switch appState.localInstallState {
        case .failed:
            .red
        case .loaded:
            .green
        default:
            .secondary
        }
    }
}

private struct SectionPanel<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(title)
                .font(.title2.bold())
            content
        }
        .padding(18)
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.separator, lineWidth: 1)
        }
    }
}

private struct JenkinsPackageRow: View {
    let package: JenkinsPackage
    let installing: Bool
    let disabled: Bool
    let install: () -> Void

    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 8) {
                    Text(package.jobName)
                        .font(.headline)
                    StatusPill(text: "#\(package.buildNumber)", color: .blue)
                    StatusPill(
                        text: package.environment == "production" ? "生产包" : "测试包",
                        color: .orange
                    )
                }
                Text(package.artifactFileName)
                    .font(.callout.monospaced())
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                if let buildTime = package.buildTime, !buildTime.isEmpty {
                    Text(buildTime)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
            Button(action: install) {
                Label(
                    installing ? "正在安装…" : "安装应用",
                    systemImage: installing ? "hourglass" : "square.and.arrow.down"
                )
            }
            .buttonStyle(.borderedProminent)
            .disabled(disabled)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}

private struct StatusPill: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.caption.bold())
            .foregroundStyle(color)
            .padding(.horizontal, 9)
            .padding(.vertical, 5)
            .background(color.opacity(0.12))
            .clipShape(Capsule())
    }
}

private struct EmptyStateView: View {
    let text: String

    var body: some View {
        Text(text)
            .foregroundStyle(.secondary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.vertical, 12)
    }
}

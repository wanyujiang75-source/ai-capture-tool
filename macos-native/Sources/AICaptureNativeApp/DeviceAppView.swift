import SwiftUI
import UniformTypeIdentifiers

struct DeviceAppView: View {
    @EnvironmentObject private var appState: AppState
    @State private var showingAPKPicker = false

    private let columns = [
        GridItem(.adaptive(minimum: 320), spacing: 14, alignment: .top)
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                header
                loadSummary
                deviceSection
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
            case .success(let urls):
                guard let fileURL = urls.first else { return }
                Task { await appState.installLocalAPK(fileURL) }
            case .failure(let error):
                appState.localInstallMessage = "无法读取所选 APK：\(error.localizedDescription)"
                appState.localInstallState = .failed(appState.localInstallMessage)
            }
        }
        .task {
            if appState.deviceLoadState == .idle, appState.appLoadState == .idle {
                await appState.refreshWorkspaceData()
            }
        }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 8) {
                Text("设备与应用")
                    .font(.largeTitle.bold())
                Text("选择设备后，可安装本地 APK 或 Jenkins 测试包；打开任一 App 后会自动识别抓包目标。")
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button {
                Task {
                    await appState.refreshWorkspaceData()
                }
            } label: {
                Label("刷新列表", systemImage: "arrow.clockwise")
            }
            .buttonStyle(.borderedProminent)
        }
    }

    private var localPackageSection: some View {
        SectionPanel(title: "自主安装", subtitle: "本地 APK") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 12) {
                    Text("安装设备：\(appState.selectedDeviceID ?? "未选择")")
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button {
                        showingAPKPicker = true
                    } label: {
                        Label("选择本地 APK", systemImage: "folder.badge.plus")
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(appState.localInstallState == .loading)
                    if appState.localInstallState == .loading {
                        ProgressView()
                            .controlSize(.small)
                    }
                }
                Text(appState.localInstallMessage.isEmpty
                     ? "本地 APK 默认作为生产包安装；安装完成后请在模拟器中手动打开。"
                     : appState.localInstallMessage)
                    .font(.callout)
                    .foregroundStyle(localInstallMessageColor)
            }
        }
    }

    private var loadSummary: some View {
        HStack(spacing: 10) {
            LoadStateBadge(title: "设备", count: appState.devices.count, state: appState.deviceLoadState)
            LoadStateBadge(title: "Jenkins", count: appState.jenkinsPackages.count, state: appState.jenkinsLoadState)
        }
    }

    private var deviceSection: some View {
        SectionPanel(title: "设备池", subtitle: "\(appState.devices.count) 台") {
            switch appState.deviceLoadState {
            case .idle:
                EmptyStateView(text: "尚未加载设备。")
            case .loading:
                ProgressView("正在读取设备状态...")
                    .padding(.vertical, 12)
            case .failed(let message):
                EmptyStateView(text: "设备读取失败：\(message)")
            case .loaded:
                if appState.devices.isEmpty {
                    EmptyStateView(text: "暂无设备。")
                } else {
                    LazyVGrid(columns: columns, spacing: 14) {
                        ForEach(appState.devices) { device in
                            DeviceCard(
                                device: device,
                                selected: appState.selectedDeviceID == device.id
                            )
                            .onTapGesture {
                                appState.selectedDeviceID = device.id
                            }
                        }
                    }
                }
            }
        }
    }

    private var jenkinsSection: some View {
        SectionPanel(title: "Jenkins 测试包", subtitle: "\(appState.jenkinsPackages.count) 个最新包") {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 12) {
                    Picker("安装设备", selection: selectedDeviceBinding) {
                        if appState.devices.isEmpty {
                            Text("暂无设备").tag("")
                        } else {
                            ForEach(appState.devices) { device in
                                Text("\(device.id) · \(device.adbSerial ?? "-")").tag(device.id)
                            }
                        }
                    }
                    .frame(maxWidth: 420)

                    Button {
                        Task {
                            await appState.refreshJenkinsPackages()
                        }
                    } label: {
                        Label("刷新 Jenkins", systemImage: "arrow.clockwise")
                    }

                    if appState.jenkinsInstallState == .loading {
                        ProgressView()
                            .controlSize(.small)
                    }
                }

                if !appState.jenkinsMessage.isEmpty {
                    Text(appState.jenkinsMessage)
                        .font(.callout)
                        .foregroundStyle(jenkinsMessageColor)
                }

                switch appState.jenkinsLoadState {
                case .idle:
                    EmptyStateView(text: "尚未加载 Jenkins 安装包。")
                case .loading:
                    ProgressView("正在读取 Jenkins 最新安装包...")
                        .padding(.vertical, 12)
                case .failed(let message):
                    EmptyStateView(text: "Jenkins 读取失败：\(message)")
                case .loaded:
                    if appState.jenkinsPackages.isEmpty {
                        EmptyStateView(text: "没有找到最新可安装包。")
                    } else {
                        LazyVStack(spacing: 10) {
                            ForEach(appState.jenkinsPackages) { package in
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
        }
    }

    private var selectedDeviceBinding: Binding<String> {
        Binding {
            appState.selectedDeviceID ?? ""
        } set: { value in
            appState.selectedDeviceID = value.isEmpty ? nil : value
        }
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
    let subtitle: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text(title)
                    .font(.title2.bold())
                Text(subtitle)
                    .font(.headline)
                    .foregroundStyle(.secondary)
                Spacer()
            }
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

private struct LoadStateBadge: View {
    let title: String
    let count: Int
    let state: LoadState

    var body: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(color)
                .frame(width: 9, height: 9)
            Text(title)
                .fontWeight(.semibold)
            Text(label)
                .foregroundStyle(.secondary)
        }
        .font(.callout)
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.thinMaterial)
        .clipShape(Capsule())
    }

    private var label: String {
        switch state {
        case .idle:
            "待加载"
        case .loading:
            "加载中"
        case .loaded:
            "\(count)"
        case .failed:
            "失败"
        }
    }

    private var color: Color {
        switch state {
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

private struct DeviceCard: View {
    let device: CaptureDevice
    let selected: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(device.name ?? device.id)
                        .font(.headline)
                    Text("\(device.id) · \(device.adbSerial ?? "-")")
                        .font(.callout.monospaced())
                        .foregroundStyle(.secondary)
                }
                Spacer()
                StatusPill(text: deviceStatus, color: deviceStatusColor)
            }
            HStack {
                InfoChip(text: "AVD \(device.avdName ?? "-")")
                InfoChip(text: "代理 \(device.proxyPort ?? "-")")
                InfoChip(text: "Frida \(device.fridaPort ?? "-")")
            }
            HStack {
                InfoChip(text: device.runtimePolicy ?? "unknown")
                InfoChip(text: device.capture?.health ?? "idle")
                InfoChip(text: googleText)
            }
            if let foreground = device.emulator?.foreground, !foreground.isEmpty {
                Text(foreground)
                    .font(.caption.monospaced())
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(selected ? Color.accentColor.opacity(0.12) : Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay {
            RoundedRectangle(cornerRadius: 16)
                .stroke(selected ? Color.accentColor : Color.clear, lineWidth: 1.5)
        }
    }

    private var deviceStatus: String {
        if device.emulator?.adbOnline == true {
            "在线"
        } else if device.emulator?.processRunning == true {
            "启动中"
        } else {
            "离线"
        }
    }

    private var deviceStatusColor: Color {
        if device.emulator?.adbOnline == true {
            .green
        } else if device.emulator?.processRunning == true {
            .orange
        } else {
            .gray
        }
    }

    private var googleText: String {
        device.googleState?.ok == true ? "Google 已登录" : "Google 未就绪"
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
                    StatusPill(text: package.environment == "production" ? "生产包" : "测试包", color: .orange)
                }
                Text(package.artifactFileName)
                    .font(.callout.monospaced())
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                Text(package.buildTime ?? "-")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button {
                install()
            } label: {
                Label(installing ? "安装中" : "安装", systemImage: installing ? "hourglass" : "square.and.arrow.down")
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

private struct InfoChip: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.caption)
            .foregroundStyle(.secondary)
            .lineLimit(1)
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(.thinMaterial)
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

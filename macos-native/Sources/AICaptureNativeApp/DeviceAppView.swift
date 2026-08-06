import SwiftUI

struct DeviceAppView: View {
    @EnvironmentObject private var appState: AppState

    private let columns = [
        GridItem(.adaptive(minimum: 320), spacing: 14, alignment: .top)
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                header
                loadSummary
                deviceSection
                appSection
            }
            .padding(28)
            .frame(maxWidth: .infinity, alignment: .topLeading)
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .task {
            if appState.deviceLoadState == .idle, appState.appLoadState == .idle {
                await appState.refreshDeviceAndApps()
            }
        }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 8) {
                Text("设备与应用")
                    .font(.largeTitle.bold())
                Text("原生读取本机后端的设备池和应用库，后续会在这里接入启动模拟器、上传 APK 和打开应用。")
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button {
                Task {
                    await appState.refreshDeviceAndApps()
                }
            } label: {
                Label("刷新列表", systemImage: "arrow.clockwise")
            }
            .buttonStyle(.borderedProminent)
        }
    }

    private var loadSummary: some View {
        HStack(spacing: 10) {
            LoadStateBadge(title: "设备", count: appState.devices.count, state: appState.deviceLoadState)
            LoadStateBadge(title: "应用", count: appState.apps.count, state: appState.appLoadState)
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
                            DeviceCard(device: device)
                        }
                    }
                }
            }
        }
    }

    private var appSection: some View {
        SectionPanel(title: "应用库", subtitle: "\(appState.apps.count) 个") {
            switch appState.appLoadState {
            case .idle:
                EmptyStateView(text: "尚未加载应用。")
            case .loading:
                ProgressView("正在读取应用库...")
                    .padding(.vertical, 12)
            case .failed(let message):
                EmptyStateView(text: "应用读取失败：\(message)")
            case .loaded:
                if appState.apps.isEmpty {
                    EmptyStateView(text: "暂无应用。")
                } else {
                    VStack(alignment: .leading, spacing: 18) {
                        ForEach(groupedApps, id: \.environment) { group in
                            VStack(alignment: .leading, spacing: 10) {
                                Text(group.environment)
                                    .font(.headline)
                                    .foregroundStyle(.secondary)
                                LazyVGrid(columns: columns, spacing: 14) {
                                    ForEach(group.apps) { app in
                                        AppCard(app: app)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    private var groupedApps: [(environment: String, apps: [CaptureApp])] {
        let groups = Dictionary(grouping: appState.apps) { app in
            environmentTitle(app.environment)
        }
        return groups
            .map { (environment: $0.key, apps: $0.value.sorted { ($0.name ?? "") < ($1.name ?? "") }) }
            .sorted { $0.environment < $1.environment }
    }

    private func environmentTitle(_ environment: String?) -> String {
        switch environment {
        case "prod", "production":
            "生产包"
        case "test":
            "测试包"
        case let value? where !value.isEmpty:
            value
        default:
            "未分类"
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
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 16))
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

private struct AppCard: View {
    let app: CaptureApp

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(app.name ?? "未命名应用")
                        .font(.headline)
                    Text(app.packageName ?? "-")
                        .font(.callout.monospaced())
                        .foregroundStyle(.secondary)
                }
                Spacer()
                StatusPill(text: app.defaultMode ?? "auto", color: .blue)
            }
            if let activity = app.activity, !activity.isEmpty {
                Text(activity)
                    .font(.caption.monospaced())
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            HStack {
                InfoChip(text: "版本 \(versionText)")
                InfoChip(text: app.platform ?? "android")
                InfoChip(text: validationText)
            }
            if let message = app.lastValidationMessage, !message.isEmpty {
                Text(message)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private var versionText: String {
        let name = app.versionName?.isEmpty == false ? app.versionName! : "-"
        let code = app.versionCode?.isEmpty == false ? app.versionCode! : "-"
        return "\(name) (\(code))"
    }

    private var validationText: String {
        app.lastValidationStatus?.isEmpty == false ? app.lastValidationStatus! : "未校验"
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

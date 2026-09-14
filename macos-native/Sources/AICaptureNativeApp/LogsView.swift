import AppKit
import SwiftUI

struct LogsView: View {
    @StateObject private var controller = LogcatController()
    @State private var displayMode: LogcatDisplayMode = .table
    @State private var copySucceeded = false
    @State private var logDevices: [CaptureDevice] = []
    @State private var blockedDevices: [AndroidDeviceDiscovery] = []
    @State private var selectedLogDeviceID: String?
    @State private var foregroundApp: ForegroundAppState?
    @State private var discoveryMessage = AppCopy.Log.deviceOffline
    @State private var isRefreshingDevices = false

    private let apiClient = APIClient()

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            header
            targetBar
            controlBar
            statusBar
            logConsole
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Color(nsColor: .windowBackgroundColor))
        .task {
            await refreshLogDevices()
        }
        .task(id: selectionKey) {
            await monitorSelectedLogTarget()
        }
        .onDisappear {
            Task {
                await controller.stop()
            }
        }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline, spacing: 16) {
            VStack(alignment: .leading, spacing: 6) {
                Text(AppCopy.Navigation.logs)
                    .font(.largeTitle.bold())
                Text(AppCopy.Log.pageDescription)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Label("仅保存在本机内存，可能包含敏感调试信息", systemImage: "lock.shield")
                .font(.callout)
                .foregroundStyle(.secondary)
        }
    }

    private var targetBar: some View {
        HStack(spacing: 14) {
            Picker("Android 设备", selection: selectedDeviceBinding) {
                if logDevices.isEmpty {
                    Text("暂无可调试设备").tag("")
                } else {
                    ForEach(logDevices) { device in
                        Text(device.logDisplayName).tag(device.id)
                    }
                }
            }
            .frame(minWidth: 260, maxWidth: 380)

            Button {
                Task {
                    await refreshLogDevices()
                }
            } label: {
                if isRefreshingDevices {
                    HStack(spacing: 6) {
                        ProgressView()
                            .controlSize(.small)
                        Text(AppCopy.Log.refreshingDevices)
                    }
                } else {
                    Label(AppCopy.Log.refreshDevices, systemImage: "arrow.clockwise")
                }
            }
            .disabled(isRefreshingDevices)

            HStack(spacing: 7) {
                Image(systemName: controller.source == .app ? "app.fill" : "info.circle")
                    .foregroundStyle(.secondary)
                if controller.source == .app {
                    Text(foregroundApp == nil ? "等待前台应用" : "已识别前台应用")
                } else {
                    Text(AppCopy.Log.noApplicationRequired)
                }
            }
            .font(.callout)
            .lineLimit(1)

            Picker("日志来源", selection: $controller.source) {
                ForEach(LogcatSource.allCases) { source in
                    Text(source.title).tag(source)
                }
            }
            .pickerStyle(.segmented)
            .frame(width: 260)
        }
        .padding(14)
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay {
            RoundedRectangle(cornerRadius: 16)
                .stroke(.separator, lineWidth: 1)
        }
    }

    private var controlBar: some View {
        HStack(spacing: 10) {
            Button {
                if controller.isPaused {
                    controller.resume()
                } else {
                    controller.pause()
                }
            } label: {
                Label(
                    controller.isPaused ? AppCopy.Log.resumeDisplay : AppCopy.Log.pauseDisplay,
                    systemImage: controller.isPaused ? "play.fill" : "pause.fill"
                )
            }
            .disabled(!controller.isPolling)

            Button {
                Task {
                    await controller.clear()
                }
            } label: {
                Label(AppCopy.Log.clear, systemImage: "trash")
            }

            Button(action: copyFilteredLogs) {
                Label(
                    copySucceeded ? "已复制" : AppCopy.Log.copyAll,
                    systemImage: copySucceeded ? "checkmark" : "doc.on.doc"
                )
            }
            .disabled(controller.filteredEntries.isEmpty)
            .help("复制当前搜索和级别筛选后的全部日志")

            Divider()
                .frame(height: 22)

            TextField("搜索标签或消息", text: $controller.searchText)
                .textFieldStyle(.roundedBorder)
                .frame(minWidth: 220, maxWidth: 380)

            Picker("最低级别", selection: $controller.minimumLevel) {
                ForEach(LogcatMinimumLevel.allCases) { level in
                    Text(level.title).tag(level)
                }
            }
            .frame(width: 190)

            Picker("显示方式", selection: $displayMode) {
                ForEach(LogcatDisplayMode.allCases) { mode in
                    Text(mode.title).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .frame(width: 130)

            Toggle("自动滚动", isOn: $controller.autoScroll)
                .toggleStyle(.switch)

            Spacer()

            Text("\(controller.filteredEntries.count) / \(controller.presentedEntries.count) 条")
                .font(.callout.monospacedDigit())
                .foregroundStyle(.secondary)
        }
    }

    private var statusBar: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Circle()
                    .fill(statusColor)
                    .frame(width: 9, height: 9)
                Text(statusTitle)
                    .fontWeight(.semibold)
                Text(controller.message)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                Spacer()
            }
            if controller.truncated {
                Label("较早日志已达到内存上限并被丢弃。", systemImage: "exclamationmark.triangle.fill")
                    .font(.callout)
                    .foregroundStyle(.orange)
            }
            if let recoveryAction = controller.lastIssue?.recoveryAction,
               !recoveryAction.isEmpty {
                Text(recoveryAction)
                    .font(.callout)
                    .foregroundStyle(.orange)
            } else if hasUnauthorizedPhysicalDevice {
                Text(AppCopy.Log.physicalAuthorization)
                    .font(.callout)
                    .foregroundStyle(.orange)
            } else if logDevices.isEmpty {
                Text(deviceDiscoveryGuidance)
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var logConsole: some View {
        VStack(spacing: 0) {
            if displayMode == .table {
                logHeader
                Divider()
            }
            if controller.filteredEntries.isEmpty {
                emptyConsole
            } else {
                switch displayMode {
                case .table:
                    logRows
                case .plainText:
                    plainTextLogs
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay {
            RoundedRectangle(cornerRadius: 14)
                .stroke(.separator, lineWidth: 1)
        }
    }

    private var logHeader: some View {
        HStack(spacing: 10) {
            Text("时间")
                .frame(width: 150, alignment: .leading)
            Text("级别")
                .frame(width: 42, alignment: .leading)
            Text(AppCopy.Log.tag)
                .frame(width: 180, alignment: .leading)
            Text("消息")
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .font(.caption.bold().monospaced())
        .foregroundStyle(.secondary)
        .padding(.horizontal, 12)
        .padding(.vertical, 9)
        .background(Color(nsColor: .controlBackgroundColor))
    }

    private var emptyConsole: some View {
        VStack(spacing: 10) {
            Image(systemName: emptyIcon)
                .font(.system(size: 28))
                .foregroundStyle(.secondary)
            Text(emptyTitle)
                .font(.headline)
            Text(emptyDetail)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var logRows: some View {
        ScrollViewReader { proxy in
            ScrollView([.vertical, .horizontal]) {
                LazyVStack(spacing: 0) {
                    ForEach(controller.filteredEntries) { entry in
                        LogcatRow(entry: entry)
                            .id(entry.cursor)
                    }
                }
                .frame(minWidth: 850, alignment: .topLeading)
            }
            .onChange(of: controller.filteredEntries.last?.cursor) { _, cursor in
                guard controller.autoScroll, !controller.isPaused, let cursor else {
                    return
                }
                proxy.scrollTo(cursor, anchor: .bottom)
            }
        }
    }

    private var plainTextLogs: some View {
        SelectableLogTextView(text: LogcatTextFormatter.plainText(controller.filteredEntries))
    }

    private func copyFilteredLogs() {
        let text = LogcatTextFormatter.plainText(controller.filteredEntries)
        guard !text.isEmpty else {
            return
        }
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(text, forType: .string)
        copySucceeded = true
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(2))
            copySucceeded = false
        }
    }

    private var selectedDeviceBinding: Binding<String> {
        Binding {
            selectedLogDeviceID ?? ""
        } set: { value in
            selectedLogDeviceID = value.isEmpty ? nil : value
        }
    }

    private var selectedLogDevice: CaptureDevice? {
        guard let selectedLogDeviceID else {
            return nil
        }
        return logDevices.first { $0.id == selectedLogDeviceID }
    }

    private var selectionKey: String {
        [
            selectedLogDeviceID ?? "",
            controller.source.rawValue,
            String(isRefreshingDevices)
        ].joined(separator: "|")
    }

    @MainActor
    private func refreshLogDevices() async {
        isRefreshingDevices = true
        defer { isRefreshingDevices = false }
        await controller.stop()
        do {
            let response = try await apiClient.discoverLogDevices()
            logDevices = response.devices
            blockedDevices = response.blockedDevices
            discoveryMessage = response.userMessage
            if let selectedLogDeviceID,
               response.devices.contains(where: { $0.id == selectedLogDeviceID }) {
                self.selectedLogDeviceID = selectedLogDeviceID
            } else {
                selectedLogDeviceID = response.devices.first?.id
            }
        } catch {
            logDevices = []
            blockedDevices = []
            selectedLogDeviceID = nil
            discoveryMessage = (error as? APIClientError)?.userFacingIssue.message
                ?? "无法读取 Android 设备，请检查本机服务后重试。"
        }
    }

    @MainActor
    private func monitorSelectedLogTarget() async {
        guard !isRefreshingDevices else {
            return
        }
        guard let selectedLogDevice else {
            foregroundApp = nil
            await controller.configure(deviceID: nil, packageName: nil)
            return
        }

        while !Task.isCancelled {
            if controller.state == "error" {
                return
            }
            if controller.source == .app {
                do {
                    let detectedApp = try await apiClient.getForegroundApp(deviceID: selectedLogDevice.id)
                    guard !Task.isCancelled else {
                        return
                    }
                    switch detectedApp.state {
                    case "ready":
                        foregroundApp = detectedApp
                        await controller.configure(
                            deviceID: selectedLogDevice.id,
                            packageName: detectedApp.packageName,
                            deviceKind: selectedLogDevice.kind
                        )
                    case "device_offline":
                        foregroundApp = nil
                        await controller.reportDeviceOffline(kind: selectedLogDevice.kind)
                        return
                    case "device_locked":
                        foregroundApp = nil
                        await controller.reportDeviceLocked()
                    default:
                        foregroundApp = nil
                        await controller.configure(
                            deviceID: selectedLogDevice.id,
                            packageName: nil,
                            deviceKind: selectedLogDevice.kind
                        )
                    }
                } catch {
                    guard !Task.isCancelled else {
                        return
                    }
                    foregroundApp = nil
                    await controller.reportConnectionFailure(error)
                }
            } else {
                foregroundApp = nil
                await controller.configure(
                    deviceID: selectedLogDevice.id,
                    packageName: nil,
                    deviceKind: selectedLogDevice.kind
                )
            }

            if Task.isCancelled {
                await controller.stop()
                return
            }
            if controller.state == "error" {
                return
            }
            do {
                try await Task.sleep(for: .seconds(2))
            } catch {
                return
            }
        }
    }

    private var deviceDiscoveryGuidance: String {
        if hasUnauthorizedPhysicalDevice {
            return AppCopy.Log.physicalAuthorization
        }
        if blockedDevices.contains(where: { $0.kind == .physical }) {
            return "已检测到 Android 真机，但连接尚未建立。请检查 USB 或无线调试后刷新。"
        }
        return "\(discoveryMessage) \(AppCopy.Log.physicalSetup)"
    }

    private var hasUnauthorizedPhysicalDevice: Bool {
        blockedDevices.contains(where: { $0.kind == .physical && $0.status == .unauthorized })
    }

    private var statusTitle: String {
        switch controller.state {
        case "streaming":
            "日志实时读取中"
        case "waiting_app":
            "等待应用"
        case "device_locked":
            "等待解锁"
        case "starting":
            "正在连接"
        case "error":
            "日志连接中断"
        case "offline":
            "设备未连接"
        default:
            "等待连接"
        }
    }

    private var statusColor: Color {
        switch controller.state {
        case "streaming":
            .green
        case "waiting_app", "device_locked", "starting":
            .orange
        case "error", "offline":
            .red
        default:
            .gray
        }
    }

    private var emptyIcon: String {
        if controller.state == "device_locked" {
            return "lock.fill"
        }
        return controller.state == "waiting_app" ? "app.badge.clock" : "text.alignleft"
    }

    private var emptyTitle: String {
        if !controller.searchText.isEmpty {
            return "没有匹配的日志"
        }
        if controller.state == "device_locked" {
            return "等待设备解锁"
        }
        return controller.state == "waiting_app" ? "等待应用运行" : "暂无日志"
    }

    private var emptyDetail: String {
        if !controller.searchText.isEmpty {
            return "调整搜索内容或最低日志级别后重试。"
        }
        return controller.message
    }
}

private struct SelectableLogTextView: NSViewRepresentable {
    let text: String

    func makeNSView(context: Context) -> NSScrollView {
        let scrollView = NSTextView.scrollableTextView()
        guard let textView = scrollView.documentView as? NSTextView else {
            return scrollView
        }
        textView.isEditable = false
        textView.isSelectable = true
        textView.isRichText = false
        textView.allowsUndo = false
        textView.usesFindBar = true
        textView.font = .monospacedSystemFont(ofSize: NSFont.smallSystemFontSize, weight: .regular)
        textView.textColor = .labelColor
        textView.backgroundColor = .textBackgroundColor
        textView.textContainerInset = NSSize(width: 12, height: 12)
        textView.isHorizontallyResizable = true
        textView.textContainer?.widthTracksTextView = false
        textView.textContainer?.containerSize = NSSize(
            width: CGFloat.greatestFiniteMagnitude,
            height: CGFloat.greatestFiniteMagnitude
        )
        scrollView.hasHorizontalScroller = true
        scrollView.autohidesScrollers = true
        return scrollView
    }

    func updateNSView(_ scrollView: NSScrollView, context: Context) {
        guard let textView = scrollView.documentView as? NSTextView, textView.string != text else {
            return
        }
        let selectedRanges = textView.selectedRanges
        let visibleOrigin = scrollView.contentView.bounds.origin
        textView.string = text
        let textLength = (text as NSString).length
        let validRanges = selectedRanges.compactMap { value -> NSValue? in
            let range = value.rangeValue
            guard range.location <= textLength else {
                return nil
            }
            return NSValue(
                range: NSRange(
                    location: range.location,
                    length: min(range.length, textLength - range.location)
                )
            )
        }
        if !validRanges.isEmpty {
            textView.selectedRanges = validRanges
        }
        scrollView.contentView.scroll(to: visibleOrigin)
        scrollView.reflectScrolledClipView(scrollView.contentView)
    }
}

private enum LogcatDisplayMode: String, CaseIterable, Identifiable {
    case table
    case plainText

    var id: String { rawValue }

    var title: String {
        switch self {
        case .table:
            "表格"
        case .plainText:
            "纯文本"
        }
    }
}

private struct LogcatRow: View {
    let entry: LogcatEntry

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Text(entry.timestamp.isEmpty ? "-" : entry.timestamp)
                .frame(width: 150, alignment: .leading)
            Text(entry.level.isEmpty ? "-" : entry.level)
                .fontWeight(.bold)
                .frame(width: 42, alignment: .leading)
            Text(entry.tag.isEmpty ? "-" : entry.tag)
                .frame(width: 180, alignment: .leading)
                .lineLimit(1)
            Text(messageText)
                .frame(maxWidth: .infinity, alignment: .leading)
                .textSelection(.enabled)
        }
        .font(.system(.caption, design: .monospaced))
        .foregroundStyle(levelColor)
        .padding(.horizontal, 12)
        .padding(.vertical, 5)
        .background(entry.cursor.isMultiple(of: 2) ? Color.clear : Color.primary.opacity(0.025))
    }

    private var messageText: String {
        entry.message.isEmpty ? entry.raw : entry.message
    }

    private var levelColor: Color {
        switch entry.level.uppercased() {
        case "V", "D":
            .secondary
        case "W":
            .orange
        case "E", "F":
            .red
        default:
            .primary
        }
    }
}

private extension LogcatSource {
    var title: String {
        switch self {
        case .app:
            "应用"
        case .system:
            "系统"
        case .crash:
            "崩溃"
        }
    }
}

import AppKit
import SwiftUI

struct LogsView: View {
    @EnvironmentObject private var appState: AppState
    @StateObject private var controller = LogcatController()
    @State private var displayMode: LogcatDisplayMode = .table
    @State private var copySucceeded = false

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
        .task(id: selectionKey) {
            if appState.apps.isEmpty || appState.devices.isEmpty {
                await appState.refreshDeviceAndApps()
            }
            await controller.configure(
                deviceID: appState.selectedDeviceID,
                packageName: appState.selectedApp?.packageName
            )
        }
        .onDisappear {
            controller.cancelPolling()
        }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline, spacing: 16) {
            VStack(alignment: .leading, spacing: 6) {
                Text("Android 日志")
                    .font(.largeTitle.bold())
                Text("实时读取应用、系统与崩溃 Logcat，不依赖 Frida。")
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
            Picker("设备", selection: selectedDeviceBinding) {
                if appState.devices.isEmpty {
                    Text("暂无在线设备").tag("")
                } else {
                    ForEach(appState.devices) { device in
                        Text("\(device.id) · \(device.adbSerial ?? "-")").tag(device.id)
                    }
                }
            }
            .frame(minWidth: 250, maxWidth: 340)

            Picker("应用", selection: selectedAppBinding) {
                if appState.apps.isEmpty {
                    Text("暂无已安装应用").tag(0)
                } else {
                    ForEach(appState.apps) { app in
                        Text("\(app.name ?? app.packageName ?? "应用") · \(app.packageName ?? "-")")
                            .tag(app.id)
                    }
                }
            }
            .frame(minWidth: 300, maxWidth: 430)
            .disabled(controller.source != .app)

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
                    controller.isPaused ? "继续" : "暂停",
                    systemImage: controller.isPaused ? "play.fill" : "pause.fill"
                )
            }

            Button {
                Task {
                    await controller.clear()
                }
            } label: {
                Label("清空", systemImage: "trash")
            }

            Button(action: copyFilteredLogs) {
                Label(
                    copySucceeded ? "已复制" : "复制当前结果",
                    systemImage: copySucceeded ? "checkmark" : "doc.on.doc"
                )
            }
            .disabled(controller.filteredEntries.isEmpty)
            .help("复制当前搜索和级别筛选后的全部日志")

            Divider()
                .frame(height: 22)

            TextField("搜索 Tag 或消息", text: $controller.searchText)
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

            Text("\(controller.filteredEntries.count) / \(controller.entries.count) 条")
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
            Text("Tag")
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
            appState.selectedDeviceID ?? ""
        } set: { value in
            appState.selectedDeviceID = value.isEmpty ? nil : value
        }
    }

    private var selectedAppBinding: Binding<Int> {
        Binding {
            appState.selectedAppID ?? 0
        } set: { value in
            appState.selectedAppID = value == 0 ? nil : value
        }
    }

    private var selectionKey: String {
        [
            appState.selectedDeviceID ?? "",
            appState.selectedApp?.packageName ?? "",
            controller.source.rawValue
        ].joined(separator: "|")
    }

    private var statusTitle: String {
        switch controller.state {
        case "streaming":
            "实时读取"
        case "waiting_app":
            "等待应用"
        case "starting":
            "正在连接"
        case "error":
            "连接异常"
        case "offline":
            "设备离线"
        default:
            "未连接"
        }
    }

    private var statusColor: Color {
        switch controller.state {
        case "streaming":
            .green
        case "waiting_app", "starting":
            .orange
        case "error", "offline":
            .red
        default:
            .gray
        }
    }

    private var emptyIcon: String {
        controller.state == "waiting_app" ? "app.badge.clock" : "text.alignleft"
    }

    private var emptyTitle: String {
        if !controller.searchText.isEmpty {
            return "没有匹配的日志"
        }
        return controller.state == "waiting_app" ? "等待目标应用启动" : "暂无日志"
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

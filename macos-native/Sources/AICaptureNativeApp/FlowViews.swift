import AppKit
import SwiftUI

struct FlowViews: View {
    @EnvironmentObject private var appState: AppState
    @State private var detailTab = "request"
    @State private var searchText = ""
    @State private var onlyInterfaces = false

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            header
            sourcePicker
            BreakpointToolbar(controller: appState.breakpointController)
            if appState.flowSessionID == nil {
                emptyCapture
            } else {
                flowContent
            }
        }
        .padding(28)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Color(nsColor: .windowBackgroundColor))
        .task(id: appState.flowSessionID) {
            await pollFlows()
        }
        .task { await appState.refreshFlowSources() }
        .onChange(of: filteredFlows.map(\.id)) { _, ids in
            appState.reconcileFlowSelection(visibleIDs: Set(ids))
        }
    }

    private var sourcePicker: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Picker(AppCopy.IOSCapture.source, selection: Binding(
                    get: { appState.selectedFlowSourceID }, set: { appState.selectFlowSource($0) }
                )) {
                    Text(AppCopy.IOSCapture.currentAndroid).tag(nil as Int?)
                    ForEach(appState.flowSources) { Text($0.title).tag(Optional($0.id)) }
                }
                Button(AppCopy.IOSCapture.refreshSources) { Task { await appState.refreshFlowSources() } }
            }
            if let issue = appState.flowSourcesIssue { Text(issue).font(.callout).foregroundStyle(.red) }
        }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline, spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                Text(AppCopy.Navigation.flows)
                    .font(.largeTitle.bold())
                Text("抓包运行后实时展示最新接口，点击行查看 Request、Response 和 cURL。")
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button(role: .destructive) {
                appState.clearCurrentFlows()
            } label: {
                Label(AppCopy.Flow.clearList, systemImage: "trash")
            }
            .disabled(appState.visibleFlows.isEmpty)
            .help(AppCopy.Flow.clearExplanation)
        }
    }

    private var emptyCapture: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(AppCopy.Flow.notStarted)
                .font(.headline)
            Text("请先在“抓包”页开始抓包。")
                .foregroundStyle(.secondary)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 18))
    }

    private var flowContent: some View {
        HSplitView {
            flowList
                .frame(minWidth: 460, idealWidth: 560, maxHeight: .infinity, alignment: .topLeading)
            flowDetail
                .frame(minWidth: 520, maxHeight: .infinity, alignment: .topLeading)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .layoutPriority(1)
    }

    private var flowList: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(AppCopy.Flow.captureNumber(appState.flowSessionID ?? 0))
                    .font(.title2.bold())
                Text("\(filteredFlows.count) / \(appState.visibleFlows.count) 条")
                    .foregroundStyle(.secondary)
                Spacer()
                stateText(appState.flowLoadState)
            }
            searchField
            HStack(spacing: 10) {
                Toggle(isOn: $onlyInterfaces) {
                    Label(AppCopy.Flow.onlyInterfaces, systemImage: "line.3.horizontal.decrease.circle")
                }
                .toggleStyle(.button)
                .help(AppCopy.Flow.filterExplanation)
                if onlyInterfaces {
                    Text(AppCopy.Flow.filteredCount(appState.visibleFlows.count - interfaceFlows.count))
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
            }
            listContent
        }
        .padding(16)
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.separator, lineWidth: 1)
        }
    }

    private var searchField: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(.secondary)
            TextField("搜索 URL、Host、Path、方法或状态码", text: $searchText)
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
        .padding(.vertical, 9)
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .overlay {
            RoundedRectangle(cornerRadius: 10)
                .stroke(.separator, lineWidth: 1)
        }
    }

    @ViewBuilder
    private var listContent: some View {
        if appState.visibleFlows.isEmpty {
            if appState.flowLoadState == .loading { ProgressView(AppCopy.Flow.syncing).padding() }
            if case let .failed(message) = appState.flowLoadState { Text(message).foregroundStyle(.red).padding() }
            Text(appState.selectedFlowSource?.isIOS == true ? AppCopy.IOSCapture.waiting : AppCopy.Flow.waiting)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
        } else if filteredFlows.isEmpty {
            Text(onlyInterfaces ? AppCopy.Flow.noFilteredResults : AppCopy.Flow.noSearchResults)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
        } else {
            List(filteredFlows) { flow in
                FlowRow(flow: flow)
                    .contextMenu {
                        Button(BreakpointCopy.setRule) {
                            appState.breakpointController.seed(url: flow.url ?? "", method: flow.method ?? "GET")
                        }
                    }
                    .contentShape(Rectangle())
                    .listRowBackground(rowBackground(for: flow))
                    .onTapGesture {
                        selectFlow(flow)
                    }
            }
            .listStyle(.plain)
        }
    }

    private var filteredFlows: [FlowSummary] {
        FlowListPresentation.filtered(onlyInterfaces ? interfaceFlows : appState.visibleFlows, query: searchText)
    }

    private var interfaceFlows: [FlowSummary] {
        FlowListPresentation.filtered(appState.visibleFlows, query: "", scope: .interfaces)
    }

    private var flowDetail: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let detail = appState.selectedFlowDetail {
                Text(detail.url ?? detail.id)
                    .font(.headline.monospaced())
                    .fixedSize(horizontal: false, vertical: true)
                    .textSelection(.enabled)
                Picker("", selection: $detailTab) {
                    Text("Request").tag("request")
                    Text("Response").tag("response")
                    Text("cURL").tag("curl")
                }
                .pickerStyle(.segmented)
                if let stages = detail.breakpoints, !stages.isEmpty {
                    BreakpointArchiveView(stages: stages).id(detail.id)
                }
                detailBody(detail)
            } else {
                if appState.flowDetailLoadState == .loading { ProgressView("正在加载接口详情…") }
                if case let .failed(message) = appState.flowDetailLoadState {
                    Text(message).foregroundStyle(.red)
                } else { Text("选择一个接口查看详情。")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .center)
                }
            }
        }
        .padding(16)
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.separator, lineWidth: 1)
        }
    }

    @ViewBuilder
    private func detailBody(_ detail: FlowDetail) -> some View {
        switch appState.flowDetailLoadState {
        case .loading:
            ProgressView("正在加载接口详情…")
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        case let .failed(message):
            Text(message)
                .foregroundStyle(.red)
        case .idle, .loaded:
            switch detailTab {
            case "request":
                CodeBlock(
                    title: "Request Body (\(detail.requestBodyKind ?? "text"))",
                    content: FlowListPresentation.requestBody(detail)
                )
            case "response":
                CodeBlock(
                    title: "Response Body (\(detail.responseBodyKind ?? "text"))",
                    content: FlowListPresentation.responseBody(detail)
                )
            default:
                CodeBlock(
                    title: "cURL",
                    content: FlowBodyPresentation(
                        text: appState.flowCurlIssue ?? (appState.selectedFlowCurl.isEmpty ? "正在生成 cURL…" : appState.selectedFlowCurl),
                        isTruncated: false,
                        sizeBytes: 0,
                        fullFileURL: nil
                    )
                )
            }
        }
    }

    private func preferredDetailTab(for detail: FlowDetail) -> String {
        let requestIsEmpty = detail.requestJSON == nil && (detail.requestText ?? "").isEmpty
        let responseExists = detail.responseJSON != nil || !(detail.responseText ?? "").isEmpty
        return requestIsEmpty && responseExists ? "response" : "request"
    }

    private func stateText(_ state: LoadState) -> some View {
        switch state {
        case .idle:
            return Text(AppCopy.Flow.waitingSync).foregroundStyle(.secondary)
        case .loading:
            return Text(AppCopy.Flow.syncing).foregroundStyle(.orange)
        case .loaded:
            if let status = appState.selectedFlowSource?.status, status != "running" {
                return Text("已停止").foregroundStyle(.secondary)
            }
            return Text(AppCopy.Flow.live).foregroundStyle(.green)
        case .failed:
            return Text("同步中断").foregroundStyle(.red)
        }
    }

    private func rowBackground(for flow: FlowSummary) -> Color {
        appState.selectedFlowID == flow.id ? Color.accentColor.opacity(0.12) : Color.clear
    }

    private func selectFlow(_ flow: FlowSummary) {
        Task {
            await appState.loadFlowDetail(flow)
            if appState.selectedFlowID == flow.id, let detail = appState.selectedFlowDetail {
                detailTab = preferredDetailTab(for: detail)
            }
        }
    }

    private func pollFlows() async {
        while !Task.isCancelled, appState.flowSessionID != nil {
            await appState.refreshFlowSources()
            await appState.refreshFlows()
            try? await Task.sleep(for: .seconds(2))
        }
    }
}

private struct FlowRow: View {
    let flow: FlowSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                Text(flow.time ?? "-")
                    .font(.caption.monospaced())
                    .foregroundStyle(.secondary)
                    .frame(width: 112, alignment: .leading)
                Text(flow.method ?? "-")
                    .font(.caption.bold())
                    .frame(width: 52)
                Text(FlowListPresentation.statusLabel(flow.status))
                    .font(.caption.bold())
                    .foregroundStyle(statusColor)
                    .frame(width: 82)
                Text(durationText)
                    .font(.caption.bold())
                    .foregroundStyle(.blue)
                    .frame(width: 78)
                Spacer()
            }
            Text(FlowListPresentation.endpoint(for: flow))
                .font(.callout.monospaced())
                .fixedSize(horizontal: false, vertical: true)
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.vertical, 8)
    }

    private var durationText: String {
        guard let totalDurationMs = flow.totalDurationMs, !totalDurationMs.isEmpty else {
            return "-"
        }
        return "\(totalDurationMs)ms"
    }

    private var statusColor: Color {
        if flow.status == "200" {
            return .green
        }
        if flow.status == "NO_RESPONSE" {
            return .orange
        }
        return .secondary
    }
}

private struct CodeBlock: View {
    let title: String
    let content: FlowBodyPresentation

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
            if content.isTruncated {
                HStack(spacing: 12) {
                    Text(AppCopy.Flow.largeBodyPreview(sizeBytes: content.sizeBytes))
                        .foregroundStyle(.secondary)
                    Spacer()
                    if let fullFileURL = content.fullFileURL {
                        Button(AppCopy.Flow.showFullBodyFile) {
                            NSWorkspace.shared.activateFileViewerSelecting([fullFileURL])
                        }
                    }
                }
                .padding(10)
                .background(Color.orange.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
            ReadOnlyCodeTextView(text: content.text)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .layoutPriority(1)
        }
    }
}

private struct ReadOnlyCodeTextView: NSViewRepresentable {
    let text: String

    final class Coordinator {
        var renderedText = ""
    }

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeNSView(context: Context) -> NSScrollView {
        let scrollView = NSTextView.scrollableTextView()
        scrollView.hasVerticalScroller = true
        scrollView.hasHorizontalScroller = true
        scrollView.autohidesScrollers = true
        scrollView.borderType = .noBorder
        scrollView.drawsBackground = true
        scrollView.backgroundColor = .textBackgroundColor

        guard let textView = scrollView.documentView as? NSTextView else {
            return scrollView
        }
        textView.isEditable = false
        textView.isSelectable = true
        textView.isRichText = false
        textView.usesFindBar = true
        textView.font = .monospacedSystemFont(ofSize: NSFont.systemFontSize, weight: .regular)
        textView.textColor = .labelColor
        textView.backgroundColor = .textBackgroundColor
        textView.textContainerInset = NSSize(width: 12, height: 12)
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = true
        textView.minSize = .zero
        textView.maxSize = NSSize(
            width: CGFloat.greatestFiniteMagnitude,
            height: CGFloat.greatestFiniteMagnitude
        )
        textView.textContainer?.containerSize = NSSize(
            width: CGFloat.greatestFiniteMagnitude,
            height: CGFloat.greatestFiniteMagnitude
        )
        textView.textContainer?.widthTracksTextView = false
        textView.layoutManager?.allowsNonContiguousLayout = true
        return scrollView
    }

    func updateNSView(_ scrollView: NSScrollView, context: Context) {
        guard let textView = scrollView.documentView as? NSTextView,
              context.coordinator.renderedText != text else {
            return
        }
        context.coordinator.renderedText = text
        textView.string = text
        textView.scrollToBeginningOfDocument(nil)
    }
}

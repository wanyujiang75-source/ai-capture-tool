import SwiftUI

struct FlowViews: View {
    @EnvironmentObject private var appState: AppState
    @State private var detailTab = "request"
    @State private var searchText = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            header
            if appState.activeSessionID == nil {
                emptySession
            } else {
                flowContent
            }
        }
        .padding(28)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Color(nsColor: .windowBackgroundColor))
        .task(id: appState.activeSessionID) {
            await pollFlows()
        }
    }

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 8) {
                Text("接口")
                    .font(.largeTitle.bold())
                Text("抓包运行后实时展示最新接口，点击行查看 Request、Response 和 cURL。")
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button {
                Task {
                    await appState.refreshFlows()
                }
            } label: {
                Label("刷新接口", systemImage: "arrow.clockwise")
            }
        }
    }

    private var emptySession: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("当前没有 active session。")
                .font(.headline)
            Text("先在“抓包”页启动抓包；操作 App 后，这里会自动显示接口。")
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
                .frame(minWidth: 460, idealWidth: 560)
            flowDetail
                .frame(minWidth: 520)
        }
    }

    private var flowList: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Session #\(appState.activeSessionID ?? 0)")
                    .font(.title2.bold())
                Text("\(filteredFlows.count) / \(appState.flows.count) 条")
                    .foregroundStyle(.secondary)
                Spacer()
                stateText(appState.flowLoadState)
            }
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
                    .help("清除搜索")
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
            if appState.flows.isEmpty {
                Text("暂无接口。操作 App 后会自动刷新。")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
            } else if filteredFlows.isEmpty {
                Text("没有匹配的接口，请调整搜索内容。")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
            } else {
                List(filteredFlows) { flow in
                    FlowRow(flow: flow)
                        .contentShape(Rectangle())
                        .listRowBackground(rowBackground(for: flow))
                        .onTapGesture {
                            selectFlow(flow)
                        }
                }
                .listStyle(.plain)
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

    private var filteredFlows: [FlowSummary] {
        FlowListPresentation.filtered(appState.flows, query: searchText)
    }

    private var flowDetail: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let detail = appState.selectedFlowDetail {
                Text(detail.url ?? detail.id)
                    .font(.headline.monospaced())
                    .lineLimit(2)
                    .textSelection(.enabled)
                Picker("", selection: $detailTab) {
                    Text("Request").tag("request")
                    Text("Response").tag("response")
                    Text("cURL").tag("curl")
                }
                .pickerStyle(.segmented)
                detailBody(detail)
            } else {
                Text("选择一个接口查看详情。")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .center)
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
            ProgressView("正在加载详情...")
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        case .failed(let message):
            Text(message)
                .foregroundStyle(.red)
        case .idle, .loaded:
            switch detailTab {
            case "request":
                CodeBlock(title: "Request Body (\(detail.requestBodyKind ?? "unknown"))", text: requestText(detail))
            case "response":
                CodeBlock(title: "Response Body (\(detail.responseBodyKind ?? "unknown"))", text: responseText(detail))
            default:
                CodeBlock(title: "cURL", text: appState.selectedFlowCurl.isEmpty ? "暂无 cURL" : appState.selectedFlowCurl)
            }
        }
    }

    private func requestText(_ detail: FlowDetail) -> String {
        if let requestJSON = detail.requestJSON {
            return requestJSON.description
        }
        if let requestText = detail.requestText, !requestText.isEmpty {
            return requestText
        }
        return "No request body"
    }

    private func responseText(_ detail: FlowDetail) -> String {
        if let responseJSON = detail.responseJSON {
            return responseJSON.description
        }
        if let responseText = detail.responseText, !responseText.isEmpty {
            return responseText
        }
        return "No response body"
    }

    private func preferredDetailTab(for detail: FlowDetail) -> String {
        if !hasRequestBody(detail), hasResponseBody(detail) {
            return "response"
        }
        return "request"
    }

    private func hasRequestBody(_ detail: FlowDetail) -> Bool {
        detail.requestJSON != nil || !(detail.requestText ?? "").isEmpty
    }

    private func hasResponseBody(_ detail: FlowDetail) -> Bool {
        detail.responseJSON != nil || !(detail.responseText ?? "").isEmpty
    }

    private func stateText(_ state: LoadState) -> some View {
        switch state {
        case .idle:
            return Text("待刷新").foregroundStyle(.secondary)
        case .loading:
            return Text("刷新中").foregroundStyle(.orange)
        case .loaded:
            return Text("已同步").foregroundStyle(.green)
        case .failed:
            return Text("失败").foregroundStyle(.red)
        }
    }

    private func rowBackground(for flow: FlowSummary) -> Color {
        appState.selectedFlowID == flow.id ? Color.accentColor.opacity(0.12) : Color.clear
    }

    private func selectFlow(_ flow: FlowSummary) {
        Task {
            await appState.loadFlowDetail(flow)
            if let detail = appState.selectedFlowDetail {
                detailTab = preferredDetailTab(for: detail)
            }
        }
    }

    private func pollFlows() async {
        while !Task.isCancelled, appState.activeSessionID != nil {
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
                Text(flow.status ?? "-")
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
    let text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
            ScrollView {
                Text(text)
                    .font(.system(.body, design: .monospaced))
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
            }
            .background(Color(nsColor: .textBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
    }
}

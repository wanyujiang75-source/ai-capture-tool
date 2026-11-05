import SwiftUI

struct CaptureSourcePicker: View {
    @EnvironmentObject private var appState: AppState
    @State private var showingHistory = false
    @State private var historyQuery = ""
    @State private var refreshingHistory = false

    private var groups: CaptureSourceGroups {
        CaptureSourceGroups(sources: appState.flowSources, activeAndroidID: appState.activeSessionID)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 12) {
                if let source = appState.selectedFlowSource ?? groups.current.first(where: { $0.id == appState.flowSessionID }) {
                    Label(source.displayName, systemImage: source.isIOS ? "iphone" : "smartphone")
                        .font(.headline)
                    if source.applicationName != nil { Text(source.platformLabel).foregroundStyle(.secondary) }
                    Text(source.statusLabel).foregroundStyle(source.isRunning ? .green : .secondary)
                } else {
                    Text(AppCopy.FlowSource.current).font(.headline)
                }
                Spacer(minLength: 8)
                if appState.flowSessionID != nil, !appState.isViewingLiveCapture {
                    Button(AppCopy.FlowSource.returnToCurrent) { appState.selectCurrentFlowSource() }
                }
                if groups.current.count > 1 {
                    Menu(AppCopy.FlowSource.switchCapture) {
                        ForEach(groups.current) { source in
                            Button(source.title) {
                                appState.selectFlowSource(source.id == appState.activeSessionID ? nil : source.id)
                            }
                        }
                    }
                    .fixedSize()
                }
                Button {
                    historyQuery = ""
                    showingHistory = true
                } label: { Label(AppCopy.FlowSource.history, systemImage: "clock.arrow.circlepath") }
            }
            if let issue = appState.flowSourcesIssue { Text(issue).font(.callout).foregroundStyle(.red) }
        }
        .sheet(isPresented: $showingHistory) { historyPanel }
    }

    private var historyPanel: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text(AppCopy.FlowSource.history).font(.title2.bold())
                Text(AppCopy.FlowSource.recentHistory(limit: CaptureSourceGroups.historyLimit))
                    .foregroundStyle(.secondary)
                Spacer()
                if refreshingHistory { ProgressView().controlSize(.small) }
                Button(AppCopy.FlowSource.refresh) {
                    refreshingHistory = true
                    Task {
                        await appState.refreshFlowSources()
                        refreshingHistory = false
                    }
                }.disabled(refreshingHistory)
                Button(AppCopy.FlowSource.close) { showingHistory = false }.keyboardShortcut(.cancelAction)
            }
            TextField(AppCopy.FlowSource.search, text: $historyQuery).textFieldStyle(.roundedBorder)
            Text(AppCopy.FlowSource.retentionHint).font(.callout).foregroundStyle(.secondary)
            if let issue = appState.flowSourcesIssue { Text(issue).foregroundStyle(.red) }
            let records = groups.matchingHistory(historyQuery)
            if records.isEmpty {
                Text(groups.history.isEmpty ? AppCopy.FlowSource.noHistory : AppCopy.FlowSource.noMatches)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    LazyVStack(spacing: 0) {
                        ForEach(records) { source in
                            Button {
                                appState.selectFlowSource(source.id)
                                showingHistory = false
                            } label: {
                                HStack {
                                    VStack(alignment: .leading, spacing: 5) {
                                        Text(source.title).font(.headline)
                                        Text(source.applicationName == nil ? source.startedLabel : "\(source.platformLabel) · \(source.startedLabel)")
                                            .foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    Text(source.statusLabel).foregroundStyle(.secondary)
                                    Image(systemName: "chevron.right").foregroundStyle(.secondary)
                                }
                                .padding(.vertical, 12)
                                .padding(.horizontal, 8)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            Divider()
                        }
                    }
                }
            }
        }
        .padding(24)
        .frame(width: 620, height: 480)
    }
}

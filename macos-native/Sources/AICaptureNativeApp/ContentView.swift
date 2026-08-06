import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        NavigationSplitView {
            List(SidebarSection.allCases, selection: $appState.selectedSection) { section in
                Label(section.rawValue, systemImage: section.systemImage)
                    .tag(section)
            }
            .navigationTitle("AI抓包工具")
        } detail: {
            switch appState.selectedSection {
            case .setup:
                runtimeOverview
            case .devices:
                DeviceAppView()
            case .capture:
                CaptureView()
            case .flows, .logs:
                placeholderView
            }
        }
        .task {
            await appState.refreshRuntimeStatus()
        }
    }

    private var runtimeOverview: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(appState.selectedSection.rawValue)
                .font(.largeTitle.bold())
            Text("原生 macOS 桌面端正在接入本机抓包运行时。当前阶段检测现有 FastAPI 后端，后续会继续接入设备池、应用库和接口分析。")
                .foregroundStyle(.secondary)
            runtimeBadge
            runtimeDetails
            Button {
                Task {
                    await appState.refreshRuntimeStatus()
                }
            } label: {
                Label("重新检测后端", systemImage: "arrow.clockwise")
            }
            .buttonStyle(.borderedProminent)
            Spacer()
        }
        .padding(28)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Color(nsColor: .windowBackgroundColor))
    }

    private var placeholderView: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(appState.selectedSection.rawValue)
                .font(.largeTitle.bold())
            Text("该原生模块将在后续任务接入。当前已完成运行时检测、设备池和应用库读取。")
                .foregroundStyle(.secondary)
            Spacer()
        }
        .padding(28)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Color(nsColor: .windowBackgroundColor))
    }

    private var runtimeBadge: some View {
        Group {
            switch appState.runtimeStatus {
            case .starting:
                Label("内部服务准备中", systemImage: "hourglass")
            case .ready(let url):
                Label("内部服务已就绪：\(url)", systemImage: "checkmark.circle.fill")
                    .foregroundStyle(.green)
            case .failed(let message):
                Label("内部服务异常：\(message)", systemImage: "xmark.octagon.fill")
                    .foregroundStyle(.red)
            }
        }
        .font(.headline)
        .padding(12)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var runtimeDetails: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let runtimeDirectory = appState.runtimeDirectory {
                LabeledContent("运行目录", value: runtimeDirectory.path)
            }
            if let lastRuntimeCheckAt = appState.lastRuntimeCheckAt {
                LabeledContent("最近检测") {
                    Text(lastRuntimeCheckAt, format: .dateTime.month().day().hour().minute().second())
                }
            }
        }
        .font(.callout)
        .padding(14)
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay {
            RoundedRectangle(cornerRadius: 14)
                .stroke(.separator, lineWidth: 1)
        }
    }
}

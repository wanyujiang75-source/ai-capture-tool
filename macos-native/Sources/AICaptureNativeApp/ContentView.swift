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
            VStack(alignment: .leading, spacing: 18) {
                Text(appState.selectedSection.rawValue)
                    .font(.largeTitle.bold())
                Text("原生 macOS 桌面端骨架已启动。后续阶段会接入本机抓包运行时、设备池、应用库和接口分析。")
                    .foregroundStyle(.secondary)
                runtimeBadge
                Spacer()
            }
            .padding(28)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .background(Color(nsColor: .windowBackgroundColor))
        }
    }

    private var runtimeBadge: some View {
        Group {
            switch appState.runtimeStatus {
            case .starting:
                Label("内部服务准备中", systemImage: "hourglass")
            case .ready(let url):
                Label("内部服务已就绪：\(url)", systemImage: "checkmark.circle.fill")
            case .failed(let message):
                Label("内部服务异常：\(message)", systemImage: "xmark.octagon.fill")
            }
        }
        .font(.headline)
        .padding(12)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}

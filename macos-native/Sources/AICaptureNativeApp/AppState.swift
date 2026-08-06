import Foundation

@MainActor
final class AppState: ObservableObject {
    enum RuntimeStatus: Equatable {
        case starting
        case ready(String)
        case failed(String)
    }

    @Published var runtimeStatus: RuntimeStatus = .starting
    @Published var runtimeDirectory: URL?
    @Published var lastRuntimeCheckAt: Date?
    @Published var selectedSection: SidebarSection = .setup

    private let runtimeManager: RuntimeManager

    init(runtimeManager: RuntimeManager = RuntimeManager()) {
        self.runtimeManager = runtimeManager
        self.runtimeDirectory = runtimeManager.runtimeDirectory
    }

    func refreshRuntimeStatus() async {
        runtimeStatus = .starting
        runtimeDirectory = runtimeManager.runtimeDirectory
        runtimeStatus = await runtimeManager.checkStatus()
        lastRuntimeCheckAt = Date()
    }
}

enum SidebarSection: String, CaseIterable, Identifiable {
    case setup = "环境"
    case devices = "设备与应用"
    case capture = "抓包"
    case flows = "接口"
    case logs = "日志"

    var id: String { rawValue }

    var systemImage: String {
        switch self {
        case .setup:
            "checklist"
        case .devices:
            "iphone.gen3.radiowaves.left.and.right"
        case .capture:
            "record.circle"
        case .flows:
            "list.bullet.rectangle"
        case .logs:
            "doc.text.magnifyingglass"
        }
    }
}

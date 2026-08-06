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
    @Published var selectedSection: SidebarSection = .devices
    @Published var devices: [CaptureDevice] = []
    @Published var apps: [CaptureApp] = []
    @Published var deviceLoadState: LoadState = .idle
    @Published var appLoadState: LoadState = .idle

    private let runtimeManager: RuntimeManager
    private let apiClient: APIClient

    init(
        runtimeManager: RuntimeManager = RuntimeManager(),
        apiClient: APIClient = APIClient()
    ) {
        self.runtimeManager = runtimeManager
        self.apiClient = apiClient
        self.runtimeDirectory = runtimeManager.runtimeDirectory
    }

    func refreshRuntimeStatus() async {
        runtimeStatus = .starting
        runtimeDirectory = runtimeManager.runtimeDirectory
        runtimeStatus = await runtimeManager.checkStatus()
        lastRuntimeCheckAt = Date()
    }

    func refreshDeviceAndApps() async {
        await refreshApps()
        await refreshDevices()
    }

    func refreshApps() async {
        appLoadState = .loading
        do {
            apps = try await apiClient.getApps()
            appLoadState = .loaded
        } catch {
            appLoadState = .failed(error.localizedDescription)
        }
    }

    func refreshDevices() async {
        deviceLoadState = .loading
        do {
            devices = try await apiClient.getDevices()
            deviceLoadState = .loaded
        } catch {
            deviceLoadState = .failed(error.localizedDescription)
        }
    }
}

enum LoadState: Equatable {
    case idle
    case loading
    case loaded
    case failed(String)
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

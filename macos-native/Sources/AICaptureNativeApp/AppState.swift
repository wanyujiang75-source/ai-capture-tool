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
    @Published var jenkinsPackages: [JenkinsPackage] = []
    @Published var jenkinsLoadState: LoadState = .idle
    @Published var jenkinsInstallState: LoadState = .idle
    @Published var jenkinsMessage = ""
    @Published var selectedDeviceID: String?
    @Published var selectedAppID: Int?
    @Published var captureActionState: LoadState = .idle
    @Published var captureMessage = ""
    @Published var activeSessionID: Int?
    @Published var flows: [FlowSummary] = []
    @Published var flowLoadState: LoadState = .idle
    @Published var selectedFlowID: String?
    @Published var selectedFlowDetail: FlowDetail?
    @Published var selectedFlowCurl = ""
    @Published var flowDetailLoadState: LoadState = .idle

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

    func refreshWorkspaceData() async {
        await refreshDeviceAndApps()
        await refreshJenkinsPackages()
    }

    func refreshApps() async {
        appLoadState = .loading
        do {
            apps = try await apiClient.getApps()
            reconcileSelections()
            appLoadState = .loaded
        } catch {
            appLoadState = .failed(error.localizedDescription)
        }
    }

    func refreshDevices() async {
        deviceLoadState = .loading
        do {
            devices = try await apiClient.getDevices()
            reconcileSelections()
            deviceLoadState = .loaded
        } catch {
            deviceLoadState = .failed(error.localizedDescription)
        }
    }

    func refreshJenkinsPackages() async {
        jenkinsLoadState = .loading
        do {
            jenkinsPackages = try await apiClient.getJenkinsPackages()
            jenkinsLoadState = .loaded
        } catch {
            jenkinsLoadState = .failed(error.localizedDescription)
        }
    }

    var selectedDevice: CaptureDevice? {
        guard let selectedDeviceID else {
            return nil
        }
        return devices.first { $0.id == selectedDeviceID }
    }

    var selectedApp: CaptureApp? {
        guard let selectedAppID else {
            return nil
        }
        return apps.first { $0.id == selectedAppID }
    }

    func prepareSelectedFrida() async {
        guard let selectedDeviceID else {
            setCaptureFailure("请先选择设备。")
            return
        }
        captureActionState = .loading
        do {
            _ = try await apiClient.prepareFrida(deviceId: selectedDeviceID)
            captureMessage = "Frida 已启动。"
            captureActionState = .loaded
            await refreshDevices()
        } catch {
            setCaptureFailure(error.localizedDescription)
        }
    }

    func launchSelectedApp() async {
        guard let selectedDeviceID, let selectedAppID else {
            setCaptureFailure("请先选择设备和应用。")
            return
        }
        captureActionState = .loading
        do {
            _ = try await apiClient.launchApp(appId: selectedAppID, deviceId: selectedDeviceID)
            captureMessage = "应用已打开。"
            captureActionState = .loaded
            await refreshDevices()
        } catch {
            setCaptureFailure(error.localizedDescription)
        }
    }

    func startSelectedCapture() async {
        guard let selectedDeviceID, let selectedApp else {
            setCaptureFailure("请先选择设备和应用。")
            return
        }
        captureActionState = .loading
        do {
            let response = try await apiClient.startCapture(
                appId: selectedApp.id,
                deviceId: selectedDeviceID,
                mode: nil
            )
            activeSessionID = response.session?.id
            selectedFlowID = nil
            selectedFlowDetail = nil
            selectedFlowCurl = ""
            flows = []
            let sessionText = response.session?.id.map { "#\($0)" } ?? ""
            let modeText = response.session?.mode ?? selectedApp.defaultMode ?? "auto"
            captureMessage = "抓包已启动 \(sessionText)，模式 \(modeText)。"
            captureActionState = .loaded
            await refreshDevices()
        } catch {
            setCaptureFailure(error.localizedDescription)
        }
    }

    func stopSelectedCapture() async {
        guard let selectedDeviceID else {
            setCaptureFailure("请先选择设备。")
            return
        }
        captureActionState = .loading
        do {
            let response = try await apiClient.stopCapture(deviceId: selectedDeviceID)
            activeSessionID = nil
            flows = []
            selectedFlowID = nil
            selectedFlowDetail = nil
            selectedFlowCurl = ""
            let okText = response.ok == false ? "停止结果异常" : "抓包已停止"
            captureMessage = okText
            captureActionState = .loaded
            await refreshDevices()
        } catch {
            setCaptureFailure(error.localizedDescription)
        }
    }

    func installJenkinsPackage(_ package: JenkinsPackage) async {
        guard let selectedDeviceID else {
            jenkinsMessage = "请先选择安装设备。"
            jenkinsInstallState = .failed(jenkinsMessage)
            return
        }
        jenkinsInstallState = .loading
        do {
            let response = try await apiClient.installJenkinsPackage(
                package,
                deviceId: selectedDeviceID,
                environment: package.environment ?? "test"
            )
            if let installedApp = response.app {
                selectedAppID = installedApp.id
                jenkinsMessage = "已安装 \(installedApp.name ?? package.artifactFileName)。"
            } else {
                jenkinsMessage = "已安装 \(package.artifactFileName)。"
            }
            jenkinsInstallState = .loaded
            await refreshDeviceAndApps()
        } catch {
            jenkinsMessage = error.localizedDescription
            jenkinsInstallState = .failed(error.localizedDescription)
        }
    }

    private func reconcileSelections() {
        if selectedDeviceID == nil || !devices.contains(where: { $0.id == selectedDeviceID }) {
            selectedDeviceID = devices.first?.id
        }
        if selectedAppID == nil || !apps.contains(where: { $0.id == selectedAppID }) {
            selectedAppID = apps.first?.id
        }
    }

    private func setCaptureFailure(_ message: String) {
        captureMessage = message
        captureActionState = .failed(message)
    }

    func refreshFlows() async {
        guard let activeSessionID else {
            flowLoadState = .idle
            flows = []
            return
        }
        flowLoadState = .loading
        do {
            flows = try await apiClient.getFlows(sessionID: activeSessionID)
            flowLoadState = .loaded
        } catch {
            flowLoadState = .failed(error.localizedDescription)
        }
    }

    func loadFlowDetail(_ flow: FlowSummary) async {
        guard let activeSessionID else {
            flowDetailLoadState = .failed("当前没有 active session。")
            return
        }
        selectedFlowID = flow.id
        flowDetailLoadState = .loading
        do {
            selectedFlowDetail = try await apiClient.getFlowDetail(sessionID: activeSessionID, flowID: flow.id)
            selectedFlowCurl = try await apiClient.getFlowCurl(sessionID: activeSessionID, flowID: flow.id)
            flowDetailLoadState = .loaded
        } catch {
            flowDetailLoadState = .failed(error.localizedDescription)
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

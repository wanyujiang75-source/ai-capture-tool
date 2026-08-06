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
    @Published var installingJenkinsPackageID: String?
    @Published var jenkinsMessage = ""
    @Published var selectedDeviceID: String?
    @Published var selectedAppID: Int?
    @Published var selectedJenkinsPackageID: String?
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
    private var installedAppIDByJenkinsTargetKey: [String: Int] = [:]

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
        if case .ready = runtimeStatus {
            await refreshWorkspaceData()
        }
    }

    func refreshDeviceAndApps() async {
        await refreshApps()
        await refreshDevices()
    }

    func refreshCaptureTargets() async {
        await refreshApps()
        await refreshDevices()
        await refreshJenkinsPackages()
    }

    func refreshWorkspaceData() async {
        await refreshDevices()
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
            syncActiveSessionFromSelectedDevice()
            deviceLoadState = .loaded
        } catch {
            deviceLoadState = .failed(error.localizedDescription)
        }
    }

    func refreshJenkinsPackages() async {
        jenkinsLoadState = .loading
        do {
            jenkinsPackages = try await apiClient.getJenkinsPackages()
            reconcileSelections()
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

    var selectedJenkinsPackage: JenkinsPackage? {
        guard let selectedJenkinsPackageID else {
            return nil
        }
        return jenkinsPackages.first { $0.id == selectedJenkinsPackageID }
    }

    func startSelectedDevice() async {
        guard let selectedDeviceID else {
            setCaptureFailure("请先选择设备。")
            return
        }
        captureActionState = .loading
        captureMessage = "正在打开模拟器：\(selectedDeviceID)。"
        do {
            let response = try await apiClient.startDevice(deviceId: selectedDeviceID, visible: true)
            let resultText = response.ok == false ? "模拟器启动命令已返回异常，请查看日志。" : "模拟器启动命令已发送，正在刷新设备状态。"
            captureMessage = resultText
            captureActionState = .loaded
            await refreshDevices()
        } catch {
            setCaptureFailure(error.localizedDescription)
        }
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
        guard let selectedDeviceID else {
            setCaptureFailure("请先选择设备。")
            return
        }
        captureActionState = .loading
        do {
            let app = try await resolveSelectedTargetApp()
            _ = try await apiClient.launchApp(appId: app.id, deviceId: selectedDeviceID)
            captureMessage = "应用已打开：\(app.name ?? app.packageName ?? "目标应用")。"
            captureActionState = .loaded
            await refreshDevices()
        } catch {
            setCaptureFailure(error.localizedDescription)
        }
    }

    func startSelectedCapture() async {
        guard let selectedDeviceID else {
            setCaptureFailure("请先选择设备。")
            return
        }
        captureActionState = .loading
        do {
            let selectedApp = try await resolveSelectedTargetApp()
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
            if await recoverExistingCaptureIfNeeded(error) {
                return
            }
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
        jenkinsInstallState = .loading
        installingJenkinsPackageID = package.id
        jenkinsMessage = "正在校验安装环境：准备将 \(package.artifactFileName) 安装到 \(selectedDeviceID ?? "目标模拟器")。"
        jenkinsMessage = "正在安装 \(package.artifactFileName)：正在从 Jenkins 下载构建产物并执行 Android 包安装，请保持模拟器在线且不要关闭窗口。"
        do {
            if let installedApp = try await installJenkinsPackageOnSelectedDevice(package) {
                jenkinsMessage = "已安装 \(installedApp.name ?? package.artifactFileName)。"
            } else {
                jenkinsMessage = "已安装 \(package.artifactFileName)。"
            }
            jenkinsInstallState = .loaded
        } catch {
            let message = friendlyJenkinsInstallError(error)
            jenkinsMessage = message
            jenkinsInstallState = .failed(message)
        }
        installingJenkinsPackageID = nil
    }

    private func selectedDeviceInstallReadinessMessage() -> String? {
        guard selectedDeviceID != nil else {
            return "未选择安装目标：请先选择一台已启动的 Android 模拟器后再安装。"
        }
        guard let selectedDevice else {
            return "未发现安装目标：请先启动模拟器，待设备在线后再安装。"
        }
        guard selectedDevice.emulator?.adbOnline == true else {
            return "模拟器未在线：请先启动 Android 模拟器，待设备进入在线状态后再安装。"
        }
        guard selectedDevice.emulator?.bootCompleted == true else {
            return "模拟器启动中：请等待 Android 系统启动完成后再安装。"
        }
        guard selectedDevice.emulator?.unlocked == true else {
            return "模拟器已锁定：请先解锁模拟器后再安装。"
        }
        return nil
    }

    private func resolveSelectedTargetApp() async throws -> CaptureApp {
        guard let package = selectedJenkinsPackage else {
            if selectedJenkinsPackageID != nil {
                throw UserVisibleError("当前 Jenkins 包已不可用：请刷新 Jenkins 列表后重新选择。")
            }
            throw UserVisibleError("请先选择 Jenkins 安装包。")
        }

        if let selectedDeviceID {
            let targetKey = jenkinsInstallCacheKey(deviceID: selectedDeviceID, packageID: package.id)
            if let appID = installedAppIDByJenkinsTargetKey[targetKey],
               let installedApp = apps.first(where: { $0.id == appID }) {
                selectedAppID = installedApp.id
                return installedApp
            }
        }

        captureMessage = "正在安装 \(package.artifactFileName)：首次使用该 Jenkins 构建前，需要先安装到当前模拟器。"
        let installedApp = try await installJenkinsPackageOnSelectedDevice(package)
        guard let installedApp else {
            throw UserVisibleError("Jenkins 包已安装，但后端未返回可启动应用信息，请刷新后重试。")
        }
        return installedApp
    }

    private func installJenkinsPackageOnSelectedDevice(_ package: JenkinsPackage) async throws -> CaptureApp? {
        await refreshDevices()
        if let readinessMessage = selectedDeviceInstallReadinessMessage() {
            throw UserVisibleError(readinessMessage)
        }
        guard let selectedDeviceID else {
            throw UserVisibleError("未选择安装目标：请先选择一台已启动的 Android 模拟器后再安装。")
        }
        let response = try await apiClient.installJenkinsPackage(
            package,
            deviceId: selectedDeviceID,
            environment: package.environment ?? "test"
        )
        if let installedApp = response.app {
            selectedAppID = installedApp.id
            let targetKey = jenkinsInstallCacheKey(deviceID: selectedDeviceID, packageID: package.id)
            installedAppIDByJenkinsTargetKey[targetKey] = installedApp.id
        }
        await refreshDeviceAndApps()
        return response.app.flatMap { responseApp in
            apps.first(where: { $0.id == responseApp.id }) ?? responseApp
        }
    }

    private func jenkinsInstallCacheKey(deviceID: String, packageID: String) -> String {
        "\(deviceID)|\(packageID)"
    }

    private func friendlyJenkinsInstallError(_ error: Error) -> String {
        let message = error.localizedDescription
        if message.contains("emulator is not ready for package install") {
            return "模拟器未就绪：请先启动 Android 模拟器，待系统启动完成后再安装。"
        }
        if message.contains("emulator is locked") {
            return "模拟器已锁定：请先解锁模拟器后再安装。"
        }
        if message.contains("another capture session is active") {
            return "当前设备正在抓包：请先停止抓包任务后再安装。"
        }
        if message.contains("dirty capture process state") {
            return "当前设备存在未清理的抓包进程：请先停止或清理抓包后再安装。"
        }
        return message
    }

    private func reconcileSelections() {
        if selectedDeviceID == nil || !devices.contains(where: { $0.id == selectedDeviceID }) {
            selectedDeviceID = devices.first?.id
        }
        if selectedAppID == nil || !apps.contains(where: { $0.id == selectedAppID }) {
            selectedAppID = apps.first?.id
        }
        if selectedJenkinsPackageID == nil || !jenkinsPackages.contains(where: { $0.id == selectedJenkinsPackageID }) {
            selectedJenkinsPackageID = jenkinsPackages.first?.id
        }
    }

    @discardableResult
    private func syncActiveSessionFromSelectedDevice() -> Int? {
        guard let selectedDevice else {
            return nil
        }
        if let sessionID = selectedDevice.activeSession?.id {
            if activeSessionID != sessionID {
                activeSessionID = sessionID
                flows = []
                selectedFlowID = nil
                selectedFlowDetail = nil
                selectedFlowCurl = ""
                flowDetailLoadState = .idle
            }
            return sessionID
        }
        if selectedDevice.capture?.health != "running" {
            activeSessionID = nil
            flows = []
            selectedFlowID = nil
            selectedFlowDetail = nil
            selectedFlowCurl = ""
            flowDetailLoadState = .idle
        }
        return nil
    }

    private func recoverExistingCaptureIfNeeded(_ error: Error) async -> Bool {
        let message = error.localizedDescription
        guard message.contains("another capture session is active") || message.contains("已有抓包任务") else {
            return false
        }
        await refreshDevices()
        guard let sessionID = syncActiveSessionFromSelectedDevice() else {
            setCaptureFailure("当前设备已有抓包任务运行中，但未能读取 Session；请先停止抓包后再重新开始。")
            return true
        }
        captureMessage = "当前设备已有抓包任务 #\(sessionID)，已自动接入现有 Session；接口页会继续实时刷新。"
        captureActionState = .loaded
        selectedSection = .flows
        await refreshFlows()
        return true
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

private struct UserVisibleError: LocalizedError {
    let message: String

    init(_ message: String) {
        self.message = message
    }

    var errorDescription: String? {
        message
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

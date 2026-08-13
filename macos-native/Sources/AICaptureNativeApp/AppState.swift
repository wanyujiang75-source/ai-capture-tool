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
    @Published var captureActionState: LoadState = .idle
    @Published var captureMessage = ""
    @Published var activeSessionID: Int?
    @Published var flows: [FlowSummary] = []
    @Published var flowLoadState: LoadState = .idle
    @Published var selectedFlowID: String?
    @Published var selectedFlowDetail: FlowDetail?
    @Published var selectedFlowCurl = ""
    @Published var flowDetailLoadState: LoadState = .idle
    @Published var foregroundTarget: ForegroundTargetResponse?
    @Published var foregroundTargetLoadState: LoadState = .idle
    @Published var localInstallState: LoadState = .idle
    @Published var localInstallMessage = ""

    private let runtimeManager: RuntimeManager
    private let apiClient: APIClient
    private let foregroundAPI: any ForegroundTargetAPI
    private let packageInstallAPI: any LocalPackageInstallAPI
    private var lastForegroundComponent: String?
    private var lastForegroundDeviceID: String?

    init(
        runtimeManager: RuntimeManager = .shared,
        apiClient: APIClient = APIClient(),
        foregroundAPI: (any ForegroundTargetAPI)? = nil,
        packageInstallAPI: (any LocalPackageInstallAPI)? = nil
    ) {
        self.runtimeManager = runtimeManager
        self.apiClient = apiClient
        self.foregroundAPI = foregroundAPI ?? apiClient
        self.packageInstallAPI = packageInstallAPI ?? apiClient
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

    var hasForegroundSessionMismatch: Bool {
        guard let activePackage = selectedDevice?.activeSession?.packageName,
              let targetPackage = foregroundTarget?.app?.packageName else {
            return false
        }
        return !activePackage.isEmpty && activePackage != targetPackage
    }

    var canStartForegroundCapture: Bool {
        guard let target = foregroundTarget else {
            return false
        }
        return ["ready", "blocked"].contains(target.captureState)
            && target.app != nil
            && !hasForegroundSessionMismatch
            && selectedDeviceID != nil
    }

    var foregroundCaptureGuidance: String {
        if hasForegroundSessionMismatch {
            return "当前设备正在抓取另一个应用，请先停止现有抓包任务。"
        }
        guard let target = foregroundTarget else {
            return "请在设备中打开需要分析的 App，工具会自动识别。"
        }
        switch target.captureState {
        case "ready":
            return "已识别前台应用，可以开始抓包。"
        case "waiting_traffic":
            return "抓包运行中，请操作 App 触发网络请求。"
        case "capturable":
            return "已捕获当前应用接口，抓包能力验证通过。"
        case "blocked":
            return "前台应用已识别；开始抓包时会自动准备 Frida 和网络环境。"
        default:
            return "正在检测前台应用。"
        }
    }

    func refreshForegroundTarget(forceResolve: Bool = false) async {
        guard let selectedDeviceID else {
            foregroundTarget = nil
            foregroundTargetLoadState = .idle
            lastForegroundComponent = nil
            lastForegroundDeviceID = nil
            return
        }
        foregroundTargetLoadState = .loading
        do {
            let foreground = try await foregroundAPI.getForegroundApp(deviceID: selectedDeviceID)
            guard foreground.state == "ready", let component = foreground.component, !component.isEmpty else {
                foregroundTarget = nil
                selectedAppID = nil
                lastForegroundComponent = nil
                lastForegroundDeviceID = selectedDeviceID
                foregroundTargetLoadState = .loaded
                return
            }

            let targetChanged = lastForegroundDeviceID != selectedDeviceID || lastForegroundComponent != component
            if forceResolve || targetChanged || foregroundTarget == nil {
                let resolved = try await foregroundAPI.resolveForegroundTarget(deviceID: selectedDeviceID)
                foregroundTarget = resolved
                lastForegroundComponent = component
                lastForegroundDeviceID = selectedDeviceID
                if let app = resolved.app {
                    selectedAppID = app.id
                    if let index = apps.firstIndex(where: { $0.id == app.id }) {
                        apps[index] = app
                    } else {
                        apps.append(app)
                    }
                }
            } else if activeSessionID != nil, let appID = foregroundTarget?.app?.id {
                let response = try await foregroundAPI.getAppReadiness(appID: appID, deviceID: selectedDeviceID)
                let state = (response.readiness.flowCount ?? 0) > 0 ? "capturable" : "waiting_traffic"
                foregroundTarget = foregroundTarget?.updating(captureState: state, readiness: response.readiness)
            }
            foregroundTargetLoadState = .loaded
        } catch {
            foregroundTargetLoadState = .failed(error.localizedDescription)
        }
    }

    func monitorForegroundTarget() async {
        while !Task.isCancelled {
            await refreshForegroundTarget()
            try? await Task.sleep(for: .seconds(2))
        }
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

    func prepareSelectedEnvironment(visible: Bool = false) async -> Bool {
        guard let selectedDeviceID else {
            setCaptureFailure("请先选择设备。")
            return false
        }
        captureActionState = .loading
        captureMessage = "正在一键准备环境：检查依赖、Google Play 镜像、模拟器、Google 登录、网络模式和 Frida 准入。"
        do {
            let response = try await apiClient.prepareSystem(deviceId: selectedDeviceID, visible: visible)
            let message = response.prepare.userMessage ?? "环境准备流程已完成。"
            captureMessage = message
            await refreshDevices()
            if response.prepare.ok == true {
                captureActionState = .loaded
                return true
            }
            captureActionState = .failed(message)
            return false
        } catch {
            setCaptureFailure(error.localizedDescription)
            return false
        }
    }

    func startSelectedCapture() async {
        guard let selectedDeviceID else {
            setCaptureFailure("请先选择设备。")
            return
        }
        if hasForegroundSessionMismatch {
            setCaptureFailure(foregroundCaptureGuidance)
            return
        }
        await refreshForegroundTarget(forceResolve: true)
        guard let targetApp = foregroundTarget?.app, canStartForegroundCapture else {
            setCaptureFailure(foregroundCaptureGuidance)
            return
        }
        captureActionState = .loading
        do {
            let prepared = await prepareSelectedEnvironment()
            guard prepared else {
                return
            }
            captureActionState = .loading
            let response = try await apiClient.startCapture(
                appId: targetApp.id,
                deviceId: selectedDeviceID,
                mode: nil
            )
            activeSessionID = response.session?.id
            selectedFlowID = nil
            selectedFlowDetail = nil
            selectedFlowCurl = ""
            flows = []
            let sessionText = response.session?.id.map { "#\($0)" } ?? ""
            let modeText = response.session?.mode ?? targetApp.defaultMode ?? "auto"
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
            didStopCapture()
            let okText = response.ok == false ? "停止结果异常" : "抓包已停止"
            captureMessage = okText
            captureActionState = .loaded
            await refreshDevices()
            await refreshForegroundTarget(forceResolve: true)
        } catch {
            setCaptureFailure(error.localizedDescription)
        }
    }

    func didStopCapture() {
        activeSessionID = nil
        flows = []
        selectedFlowID = nil
        selectedFlowDetail = nil
        selectedFlowCurl = ""
        if let foregroundTarget {
            self.foregroundTarget = foregroundTarget.updating(captureState: "ready", readiness: nil)
        }
    }

    func installJenkinsPackage(_ package: JenkinsPackage) async {
        jenkinsInstallState = .loading
        installingJenkinsPackageID = package.id
        jenkinsMessage = "正在安装 \(package.artifactFileName)：正在从 Jenkins 下载构建产物并执行 Android 包安装，请保持模拟器在线且不要关闭窗口。"
        do {
            if let installedApp = try await installJenkinsPackageOnSelectedDevice(package) {
                jenkinsMessage = "已安装 \(installedApp.name ?? package.artifactFileName)。请在模拟器中打开该应用，工具会自动识别并检查抓包能力。"
            } else {
                jenkinsMessage = "已安装 \(package.artifactFileName)。请在模拟器中打开该应用，工具会自动识别并检查抓包能力。"
            }
            jenkinsInstallState = .loaded
        } catch {
            let message = friendlyJenkinsInstallError(error)
            jenkinsMessage = message
            jenkinsInstallState = .failed(message)
        }
        installingJenkinsPackageID = nil
    }

    func installLocalAPK(_ fileURL: URL) async {
        guard fileURL.pathExtension.lowercased() == "apk" else {
            let message = "请选择扩展名为 .apk 的 Android 安装包。"
            localInstallMessage = message
            localInstallState = .failed(message)
            return
        }
        if let readinessMessage = selectedDeviceInstallReadinessMessage() {
            localInstallMessage = readinessMessage
            localInstallState = .failed(readinessMessage)
            return
        }
        guard let selectedDeviceID else {
            let message = "未选择安装目标：请先选择一台已启动的 Android 模拟器后再安装。"
            localInstallMessage = message
            localInstallState = .failed(message)
            return
        }

        localInstallState = .loading
        localInstallMessage = "正在安装 \(fileURL.lastPathComponent)：正在校验 APK 并安装到 \(selectedDeviceID)，请保持模拟器在线。"
        let accessing = fileURL.startAccessingSecurityScopedResource()
        defer {
            if accessing {
                fileURL.stopAccessingSecurityScopedResource()
            }
        }
        do {
            let installedApp = try await packageInstallAPI.installLocalAPK(
                fileURL: fileURL,
                deviceID: selectedDeviceID,
                environment: "production"
            )
            if let app = installedApp, !apps.contains(where: { $0.id == app.id }) {
                apps.append(app)
            }
            didInstallPackage()
            let name = installedApp?.name ?? fileURL.lastPathComponent
            localInstallMessage = "已安装 \(name)。请在模拟器中打开该应用，工具会自动识别并检查抓包能力。"
            localInstallState = .loaded
        } catch {
            let message = friendlyJenkinsInstallError(error)
            localInstallMessage = message
            localInstallState = .failed(message)
        }
    }

    func didInstallPackage() {
        foregroundTarget = nil
        selectedAppID = nil
        lastForegroundComponent = nil
        lastForegroundDeviceID = nil
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
            if let index = apps.firstIndex(where: { $0.id == installedApp.id }) {
                apps[index] = installedApp
            } else {
                apps.append(installedApp)
            }
        }
        didInstallPackage()
        await refreshDevices()
        return response.app
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

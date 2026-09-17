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
    @Published var selectedSection: SidebarSection = .capture
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
    @Published private(set) var clearedFlowIDs: Set<String> = []
    @Published var foregroundTarget: ForegroundTargetResponse?
    @Published var foregroundTargetLoadState: LoadState = .idle
    @Published var localInstallState: LoadState = .idle
    @Published var localInstallMessage = ""
    @Published var captureWorkflowState: CaptureWorkflowState = .ready
    @Published var notice: UserNotice?

    private let runtimeManager: RuntimeManager
    private let apiClient: APIClient
    private let foregroundAPI: any ForegroundTargetAPI
    private let packageInstallAPI: any LocalPackageInstallAPI
    private let flowAPI: any FlowAPI
    private let captureWorkflowAPI: any CaptureWorkflowAPI
    private let workflowPollInterval: Duration
    private var lastForegroundComponent: String?
    private var lastForegroundDeviceID: String?
    private var flowRefreshRequestID: UUID?
    private var flowDetailRequestID: UUID?
    private var captureWorkflowRunID: UUID?
    private var deviceStartRunID: UUID?
    private var noticeDismissTask: Task<Void, Never>?

    var visibleFlows: [FlowSummary] {
        flows.filter { !clearedFlowIDs.contains($0.id) }
    }

    var hasClearedFlows: Bool {
        !clearedFlowIDs.isEmpty
    }

    init(
        runtimeManager: RuntimeManager = .shared,
        apiClient: APIClient = APIClient(),
        foregroundAPI: (any ForegroundTargetAPI)? = nil,
        packageInstallAPI: (any LocalPackageInstallAPI)? = nil,
        flowAPI: (any FlowAPI)? = nil,
        captureWorkflowAPI: (any CaptureWorkflowAPI)? = nil,
        workflowPollInterval: Duration = .seconds(2)
    ) {
        self.runtimeManager = runtimeManager
        self.apiClient = apiClient
        self.foregroundAPI = foregroundAPI ?? apiClient
        self.packageInstallAPI = packageInstallAPI ?? apiClient
        self.flowAPI = flowAPI ?? apiClient
        self.captureWorkflowAPI = captureWorkflowAPI ?? apiClient
        self.workflowPollInterval = workflowPollInterval
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
            devices = try await captureWorkflowAPI.getDevices()
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
            jenkinsLoadState = .failed(AppCopy.Install.jenkinsUnavailable)
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

    var showsDeviceSelector: Bool {
        devices.count > 1
    }

    var displayedCaptureWorkflowState: CaptureWorkflowState {
        if captureWorkflowState == .ready, selectedDevice?.emulator?.adbOnline != true {
            return .emulatorOffline
        }
        return captureWorkflowState
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
                let flowCount = response.readiness.flowCount ?? 0
                let state = flowCount > 0 ? "capturable" : "waiting_traffic"
                foregroundTarget = foregroundTarget?.updating(captureState: state, readiness: response.readiness)
                switch captureWorkflowState {
                case let .capturing(name, _), let .restored(name):
                    setWorkflowState(.capturing(name: name, flowCount: flowCount))
                default:
                    break
                }
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
        let runID = UUID()
        deviceStartRunID = runID
        captureActionState = .loading
        setWorkflowState(.startingEmulator)
        do {
            let response = try await captureWorkflowAPI.startDevice(deviceId: selectedDeviceID, visible: true)
            guard deviceStartRunID == runID else {
                return
            }
            guard response.ok != false else {
                deviceStartRunID = nil
                setWorkflowFailure(
                    code: "emulator_start_failed",
                    title: "模拟器启动失败",
                    message: "请打开运行检查并根据修复建议重试。",
                    technicalDetail: response.stderr ?? response.userMessage
                )
                return
            }
            for _ in 0..<150 {
                await refreshDevices()
                guard deviceStartRunID == runID else {
                    return
                }
                guard let emulator = selectedDevice?.emulator else {
                    deviceStartRunID = nil
                    setWorkflowFailure(
                        code: "emulator_disconnected",
                        title: "模拟器连接中断",
                        message: "请打开运行检查，恢复模拟器连接后重试。"
                    )
                    return
                }
                if emulator.adbOnline != true {
                    setWorkflowState(.startingEmulator)
                } else if emulator.bootCompleted != true {
                    setWorkflowState(.bootingAndroid)
                } else if emulator.unlocked != true {
                    setWorkflowState(.waitingForUnlock)
                } else {
                    deviceStartRunID = nil
                    captureActionState = .loaded
                    setWorkflowState(.ready)
                    return
                }
                await waitForNextWorkflowCheck()
            }
            deviceStartRunID = nil
            setWorkflowFailure(
                code: "emulator_start_timeout",
                title: "模拟器启动超时",
                message: "Android 未在预期时间内就绪，请打开运行检查后重试。"
            )
        } catch {
            guard deviceStartRunID == runID else {
                return
            }
            deviceStartRunID = nil
            setWorkflowFailure(
                code: "emulator_start_failed",
                title: "模拟器启动失败",
                message: "请打开运行检查并根据修复建议重试。",
                technicalDetail: error.localizedDescription
            )
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
        let appName = foregroundTarget?.app?.name ?? "当前应用"
        setWorkflowState(.preparing(name: appName))
        do {
            let response = try await captureWorkflowAPI.prepareSystem(deviceId: selectedDeviceID, visible: visible)
            await refreshDevices()
            if response.prepare.ok == true {
                captureActionState = .loaded
                return true
            }
            setWorkflowFailure(
                code: "capture_prepare_failed",
                title: "抓包环境准备失败",
                message: "请打开运行检查并完成未通过的项目。",
                technicalDetail: response.prepare.userMessage
            )
            return false
        } catch {
            setWorkflowFailure(
                code: "capture_prepare_failed",
                title: "抓包环境准备失败",
                message: "请打开运行检查并完成未通过的项目。",
                technicalDetail: error.localizedDescription
            )
            return false
        }
    }

    func startSelectedCapture() async {
        await startCaptureWorkflow()
    }

    func startCaptureWorkflow() async {
        let runID = UUID()
        captureWorkflowRunID = runID
        captureActionState = .loading
        await refreshDevices()

        guard captureWorkflowRunID == runID else {
            return
        }
        guard let selectedDeviceID, let initialDevice = selectedDevice else {
            setWorkflowFailure(
                code: "emulator_missing",
                title: "未找到可用模拟器",
                message: "请打开运行检查，创建或修复抓包模拟器后重试。"
            )
            return
        }

        if initialDevice.emulator?.adbOnline != true {
            setWorkflowState(.startingEmulator)
            do {
                let response = try await captureWorkflowAPI.startDevice(deviceId: selectedDeviceID, visible: true)
                guard response.ok != false else {
                    setWorkflowFailure(
                        code: "emulator_start_failed",
                        title: "模拟器启动失败",
                        message: "请打开运行检查并根据修复建议重试。",
                        technicalDetail: response.stderr ?? response.userMessage
                    )
                    return
                }
            } catch {
                setWorkflowFailure(
                    code: "emulator_start_failed",
                    title: "模拟器启动失败",
                    message: "请打开运行检查并根据修复建议重试。",
                    technicalDetail: error.localizedDescription
                )
                return
            }
        }

        while captureWorkflowRunID == runID, !Task.isCancelled {
            await refreshDevices()
            guard captureWorkflowRunID == runID else {
                return
            }
            guard let device = selectedDevice else {
                setWorkflowFailure(
                    code: "emulator_disconnected",
                    title: "模拟器连接中断",
                    message: "请打开运行检查，恢复模拟器连接后重试。"
                )
                return
            }
            guard device.emulator?.adbOnline == true else {
                setWorkflowState(.startingEmulator)
                await waitForNextWorkflowCheck()
                continue
            }
            guard device.emulator?.bootCompleted == true else {
                setWorkflowState(.bootingAndroid)
                await waitForNextWorkflowCheck()
                continue
            }
            guard device.emulator?.unlocked == true else {
                setWorkflowState(.waitingForUnlock)
                await waitForNextWorkflowCheck()
                continue
            }

            await refreshForegroundTarget(forceResolve: foregroundTarget == nil)
            guard captureWorkflowRunID == runID else {
                return
            }

            if let activeSession = device.activeSession, let activePackage = activeSession.packageName {
                activeSessionID = activeSession.id
                if let targetPackage = foregroundTarget?.app?.packageName, targetPackage != activePackage {
                    setWorkflowState(.conflict(currentApp: displayName(forPackage: activePackage)))
                    captureWorkflowRunID = nil
                    return
                }
                let currentName = foregroundTarget?.app?.name ?? displayName(forPackage: activePackage)
                setWorkflowState(.restored(name: currentName))
                captureWorkflowRunID = nil
                return
            }

            guard let targetApp = foregroundTarget?.app else {
                setWorkflowState(.waitingForApp)
                await waitForNextWorkflowCheck()
                continue
            }

            let appName = targetApp.name ?? targetApp.packageName ?? "当前应用"
            setWorkflowState(.appDetected(name: appName))
            setWorkflowState(.preparing(name: appName))
            do {
                let prepare = try await captureWorkflowAPI.prepareSystem(
                    deviceId: selectedDeviceID,
                    visible: false
                )
                guard prepare.prepare.ok == true else {
                    setWorkflowFailure(
                        code: "capture_prepare_failed",
                        title: "抓包环境准备失败",
                        message: "请打开运行检查并完成未通过的项目。",
                        technicalDetail: prepare.prepare.userMessage
                    )
                    return
                }

                setWorkflowState(.startingCapture(name: appName))
                let response = try await captureWorkflowAPI.startCapture(
                    appId: targetApp.id,
                    deviceId: selectedDeviceID,
                    mode: nil
                )
                guard let sessionID = response.session?.id else {
                    setWorkflowFailure(
                        code: "capture_start_failed",
                        title: "抓包启动失败",
                        message: "工具没有创建抓包任务，请运行检查后重试。",
                        technicalDetail: response.output
                    )
                    return
                }
                activeSessionID = sessionID
                resetFlowPresentation()
                setWorkflowState(.capturing(name: appName, flowCount: 0))
                showNotice(
                    .success(
                        title: "抓包已开始",
                        message: "正在记录“\(appName)”的接口。"
                    )
                )
                captureWorkflowRunID = nil
                return
            } catch {
                if await recoverExistingCaptureIfNeeded(error) {
                    captureWorkflowRunID = nil
                    return
                }
                setWorkflowFailure(
                    code: "capture_start_failed",
                    title: "抓包启动失败",
                    message: "请打开运行检查，修复未通过的项目后重试。",
                    technicalDetail: error.localizedDescription
                )
                return
            }
        }
    }

    func stopSelectedCapture() async {
        captureWorkflowRunID = nil
        guard let selectedDeviceID else {
            setCaptureFailure("请先选择设备。")
            return
        }
        captureActionState = .loading
        do {
            let response = try await captureWorkflowAPI.stopCapture(deviceId: selectedDeviceID)
            let serverConfirmedStop = response.session?.status == "stopped"
            if response.ok == false && !serverConfirmedStop {
                captureMessage = AppCopy.Capture.stopFailedMessage
                captureActionState = .failed(captureMessage)
                showNotice(
                    .failure(
                        title: AppCopy.Capture.stopFailedTitle,
                        message: captureMessage
                    )
                )
                return
            }
            didStopCapture()
            setWorkflowState(.stopped)
            let networkRecoveryPending = response.cleanupOk == false || (response.ok == false && serverConfirmedStop)
            showNotice(
                .success(
                    title: AppCopy.Capture.stoppedTitle,
                    message: networkRecoveryPending
                        ? AppCopy.Capture.stoppedWithNetworkPending
                        : AppCopy.Capture.stoppedMessage
                )
            )
            await refreshDevices()
            await refreshForegroundTarget(forceResolve: true)
        } catch {
            captureMessage = AppCopy.Capture.stopFailedMessage
            captureActionState = .failed(captureMessage)
            showNotice(
                .failure(
                    title: AppCopy.Capture.stopFailedTitle,
                    message: captureMessage
                )
            )
        }
    }

    func stopAndSwitchCapture() async {
        await stopSelectedCapture()
        guard case .stopped = captureWorkflowState else {
            return
        }
        await startCaptureWorkflow()
    }

    func continueCurrentCapture() {
        guard let activePackage = selectedDevice?.activeSession?.packageName else {
            return
        }
        setWorkflowState(.restored(name: displayName(forPackage: activePackage)))
    }

    func didStopCapture() {
        activeSessionID = nil
        resetFlowPresentation()
        if let foregroundTarget {
            self.foregroundTarget = foregroundTarget.updating(captureState: "ready", readiness: nil)
        }
        captureWorkflowState = .stopped
    }

    func installJenkinsPackage(_ package: JenkinsPackage) async {
        jenkinsInstallState = .loading
        installingJenkinsPackageID = package.id
        jenkinsMessage = AppCopy.Install.installingJenkins(
            jobName: package.jobName,
            buildNumber: package.buildNumber
        )
        do {
            if let installedApp = try await installJenkinsPackageOnSelectedDevice(package) {
                jenkinsMessage = AppCopy.Install.installed(
                    appName: installedApp.name ?? package.jobName
                )
            } else {
                jenkinsMessage = AppCopy.Install.installed(appName: package.jobName)
            }
            jenkinsInstallState = .loaded
            showNotice(.success(title: "应用安装完成", message: jenkinsMessage))
        } catch {
            let issue = friendlyInstallIssue(error)
            jenkinsMessage = issue.message
            jenkinsInstallState = .failed(issue.message)
            showNotice(.failure(title: issue.title, message: issue.message))
        }
        installingJenkinsPackageID = nil
    }

    func installLocalAPK(_ fileURL: URL) async {
        guard fileURL.pathExtension.lowercased() == "apk" else {
            let message = "请选择扩展名为 .apk 的 Android 安装包。"
            localInstallMessage = message
            localInstallState = .failed(message)
            showNotice(.failure(title: "无法安装应用", message: message))
            return
        }
        if let readinessMessage = selectedDeviceInstallReadinessMessage() {
            localInstallMessage = readinessMessage
            localInstallState = .failed(readinessMessage)
            showNotice(.failure(title: "暂时无法安装应用", message: readinessMessage))
            return
        }
        guard let selectedDeviceID else {
            let message = "未选择安装目标：请先选择一台已启动的 Android 模拟器后再安装。"
            localInstallMessage = message
            localInstallState = .failed(message)
            showNotice(.failure(title: "暂时无法安装应用", message: message))
            return
        }

        localInstallState = .loading
        localInstallMessage = AppCopy.Install.installingLocal(fileName: fileURL.lastPathComponent)
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
            localInstallMessage = AppCopy.Install.installed(appName: name)
            localInstallState = .loaded
            showNotice(.success(title: "应用安装完成", message: localInstallMessage))
        } catch {
            let issue = friendlyInstallIssue(error)
            localInstallMessage = issue.message
            localInstallState = .failed(issue.message)
            showNotice(.failure(title: issue.title, message: issue.message))
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
            return AppCopy.Install.emulatorOffline
        }
        guard let selectedDevice else {
            return AppCopy.Install.emulatorOffline
        }
        guard selectedDevice.emulator?.adbOnline == true else {
            return AppCopy.Install.emulatorOffline
        }
        guard selectedDevice.emulator?.bootCompleted == true else {
            return AppCopy.Install.emulatorBooting
        }
        guard selectedDevice.emulator?.unlocked == true else {
            return AppCopy.Install.emulatorLocked
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

    private func friendlyInstallIssue(_ error: Error) -> UserFacingIssue {
        let apiIssue = (error as? APIClientError)?.userFacingIssue
        let technicalDetail = apiIssue?.technicalDetail ?? error.localizedDescription
        if technicalDetail.contains("emulator is not ready for package install") {
            return .init(
                code: "emulator_not_ready",
                title: "暂时无法安装应用",
                message: AppCopy.Install.emulatorOffline,
                technicalDetail: technicalDetail
            )
        }
        if technicalDetail.contains("emulator is locked") {
            return .init(
                code: "emulator_locked",
                title: "暂时无法安装应用",
                message: AppCopy.Install.emulatorLocked,
                technicalDetail: technicalDetail
            )
        }
        if technicalDetail.contains("another capture session is active") {
            return .init(
                code: "capture_active",
                title: "暂时无法安装应用",
                message: AppCopy.Install.captureConflict,
                technicalDetail: technicalDetail
            )
        }
        if technicalDetail.contains("INSTALL_FAILED_UPDATE_INCOMPATIBLE")
            || technicalDetail.localizedCaseInsensitiveContains("signature") {
            return .init(
                code: "signature_conflict",
                title: "应用签名不一致",
                message: AppCopy.Install.signatureConflict,
                technicalDetail: technicalDetail
            )
        }
        return apiIssue ?? .init(
            code: "app_install_failed",
            title: "应用安装失败",
            message: "请确认安装包有效，并在运行检查中确认模拟器状态后重试。",
            technicalDetail: technicalDetail
        )
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
                flowLoadState = .idle
                flowDetailLoadState = .idle
                clearedFlowIDs = []
                flowRefreshRequestID = nil
                flowDetailRequestID = nil
            }
            return sessionID
        }
        if selectedDevice.capture?.health != "running" {
            activeSessionID = nil
            flows = []
            selectedFlowID = nil
            selectedFlowDetail = nil
            selectedFlowCurl = ""
            flowLoadState = .idle
            flowDetailLoadState = .idle
            clearedFlowIDs = []
            flowRefreshRequestID = nil
            flowDetailRequestID = nil
        }
        return nil
    }

    private func recoverExistingCaptureIfNeeded(_ error: Error) async -> Bool {
        let apiIssue = (error as? APIClientError)?.userFacingIssue
        let technicalDetail = apiIssue?.technicalDetail ?? error.localizedDescription
        let isCaptureConflict = apiIssue?.code == "capture_active"
            || technicalDetail.contains("another capture session is active")
            || technicalDetail.contains("已有抓包任务")
        guard isCaptureConflict else {
            return false
        }
        await refreshDevices()
        guard let sessionID = syncActiveSessionFromSelectedDevice() else {
            setWorkflowFailure(
                code: "capture_recovery_failed",
                title: "无法恢复正在运行的抓包",
                message: "请在运行检查中停止旧任务后重试。",
                technicalDetail: technicalDetail
            )
            return true
        }
        activeSessionID = sessionID
        let packageName = selectedDevice?.activeSession?.packageName ?? foregroundTarget?.packageName ?? "当前应用"
        let appName = foregroundTarget?.app?.packageName == packageName
            ? foregroundTarget?.app?.name
            : nil
        setWorkflowState(.restored(name: appName ?? displayName(forPackage: packageName)))
        await refreshFlows()
        return true
    }

    private func waitForNextWorkflowCheck() async {
        try? await Task.sleep(for: workflowPollInterval)
    }

    private func displayName(forPackage packageName: String) -> String {
        apps.first(where: { $0.packageName == packageName })?.name ?? packageName
    }

    private func setWorkflowState(_ state: CaptureWorkflowState) {
        captureWorkflowState = state
        let presentation = state.presentation
        captureMessage = presentation.message
        switch state.tone {
        case .progress:
            captureActionState = .loading
        case .error:
            captureActionState = .failed(presentation.message)
        case .neutral:
            captureActionState = state == .ready || state == .emulatorOffline ? .idle : .loaded
        case .warning, .success:
            captureActionState = .loaded
        }
    }

    private func setWorkflowFailure(
        code: String,
        title: String,
        message: String,
        technicalDetail: String? = nil
    ) {
        captureWorkflowRunID = nil
        setWorkflowState(
            .failed(
                UserFacingIssue(
                    code: code,
                    title: title,
                    message: message,
                    recoveryAction: AppCopy.Navigation.runtimeCheck,
                    technicalDetail: technicalDetail
                )
            )
        )
        showNotice(.failure(title: title, message: message))
    }

    private func resetFlowPresentation() {
        flows = []
        selectedFlowID = nil
        selectedFlowDetail = nil
        selectedFlowCurl = ""
        flowLoadState = .idle
        flowDetailLoadState = .idle
        clearedFlowIDs = []
        flowRefreshRequestID = nil
        flowDetailRequestID = nil
    }

    private func setCaptureFailure(_ message: String) {
        captureMessage = message
        captureActionState = .failed(message)
    }

    func refreshFlows() async {
        guard let requestedSessionID = activeSessionID else {
            flowLoadState = .idle
            flows = []
            clearedFlowIDs = []
            flowRefreshRequestID = nil
            flowDetailRequestID = nil
            return
        }
        let requestID = UUID()
        flowRefreshRequestID = requestID
        flowLoadState = .loading
        do {
            let refreshedFlows = try await flowAPI.getFlows(sessionID: requestedSessionID)
            guard activeSessionID == requestedSessionID, flowRefreshRequestID == requestID else {
                return
            }
            flows = refreshedFlows
            switch captureWorkflowState {
            case let .capturing(name, _), let .restored(name):
                setWorkflowState(.capturing(name: name, flowCount: visibleFlows.count))
            default:
                break
            }
            if let selectedFlowID, !refreshedFlows.contains(where: { $0.id == selectedFlowID }) {
                self.selectedFlowID = nil
                selectedFlowDetail = nil
                selectedFlowCurl = ""
                flowDetailLoadState = .idle
                flowDetailRequestID = nil
            }
            flowLoadState = .loaded
            flowRefreshRequestID = nil
        } catch {
            guard activeSessionID == requestedSessionID, flowRefreshRequestID == requestID else {
                return
            }
            flowLoadState = .failed(error.localizedDescription)
            flowRefreshRequestID = nil
        }
    }

    func clearCurrentFlows() {
        clearedFlowIDs.formUnion(flows.map(\.id))
        selectedFlowID = nil
        selectedFlowDetail = nil
        selectedFlowCurl = ""
        flowDetailLoadState = .idle
        flowDetailRequestID = nil
        showNotice(.success(title: "列表已清空", message: AppCopy.Flow.cleared))
    }

    func loadFlowDetail(_ flow: FlowSummary) async {
        guard let requestedSessionID = activeSessionID else {
            flowDetailLoadState = .failed(AppCopy.Flow.notStarted)
            return
        }
        let requestID = UUID()
        flowDetailRequestID = requestID
        selectedFlowID = flow.id
        selectedFlowDetail = nil
        selectedFlowCurl = ""
        flowDetailLoadState = .loading
        do {
            let detail = try await flowAPI.getFlowDetail(sessionID: requestedSessionID, flowID: flow.id)
            guard isCurrentDetailRequest(requestID, sessionID: requestedSessionID, flowID: flow.id) else {
                return
            }
            selectedFlowDetail = detail
            let curl = try await flowAPI.getFlowCurl(sessionID: requestedSessionID, flowID: flow.id)
            guard isCurrentDetailRequest(requestID, sessionID: requestedSessionID, flowID: flow.id) else {
                return
            }
            selectedFlowCurl = curl
            flowDetailLoadState = .loaded
            flowDetailRequestID = nil
        } catch {
            guard isCurrentDetailRequest(requestID, sessionID: requestedSessionID, flowID: flow.id) else {
                return
            }
            flowDetailLoadState = .failed(error.localizedDescription)
            flowDetailRequestID = nil
        }
    }

    private func isCurrentDetailRequest(_ requestID: UUID, sessionID: Int, flowID: String) -> Bool {
        activeSessionID == sessionID
            && selectedFlowID == flowID
            && flowDetailRequestID == requestID
            && !clearedFlowIDs.contains(flowID)
    }

    func showNotice(_ notice: UserNotice) {
        noticeDismissTask?.cancel()
        self.notice = notice
        noticeDismissTask = Task { [weak self] in
            try? await Task.sleep(for: notice.duration)
            guard !Task.isCancelled, self?.notice?.id == notice.id else {
                return
            }
            self?.notice = nil
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
    case capture = "抓包"
    case install = "安装应用"
    case flows = "接口"
    case logs = "日志"

    var id: String { rawValue }

    var systemImage: String {
        switch self {
        case .capture:
            "record.circle"
        case .install:
            "square.and.arrow.down"
        case .flows:
            "list.bullet.rectangle"
        case .logs:
            "doc.text.magnifyingglass"
        }
    }
}

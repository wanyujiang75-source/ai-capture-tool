import Testing
@testable import AICaptureNativeApp

@Suite
struct CaptureWorkflowStateTests {
    @Test
    func everyWorkflowStateUsesApprovedUserCopy() {
        let cases: [(CaptureWorkflowState, CaptureWorkflowPresentation)] = [
            (
                .ready,
                .init(
                    title: "准备开始抓包",
                    message: "打开模拟器中的应用，工具会自动识别并抓取接口。",
                    primaryAction: .startCapture,
                    primaryButtonTitle: "开始抓包"
                )
            ),
            (
                .emulatorOffline,
                .init(
                    title: "尚未启动模拟器",
                    message: "点击“开始抓包”，工具会自动启动模拟器。",
                    primaryAction: .startCapture,
                    primaryButtonTitle: "开始抓包"
                )
            ),
            (
                .startingEmulator,
                .init(
                    title: "正在启动模拟器…",
                    message: "首次启动可能需要几分钟，请保持窗口打开。"
                )
            ),
            (
                .bootingAndroid,
                .init(
                    title: "正在启动 Android…",
                    message: "系统启动完成后会自动继续。"
                )
            ),
            (
                .waitingForUnlock,
                .init(
                    title: "等待解锁",
                    message: "请在模拟器中解锁屏幕，解锁后会自动继续。",
                    secondaryAction: .showEmulator,
                    secondaryButtonTitle: "显示模拟器"
                )
            ),
            (
                .waitingForApp,
                .init(
                    title: "等待应用",
                    message: "请在模拟器中打开需要分析的应用。",
                    secondaryAction: .showEmulator,
                    secondaryButtonTitle: "显示模拟器"
                )
            ),
            (
                .appDetected(name: "Melody"),
                .init(
                    title: "已识别“Melody”",
                    message: "正在检查该应用的抓包环境。"
                )
            ),
            (
                .preparing(name: "Melody"),
                .init(
                    title: "正在准备抓包环境…",
                    message: "正在检查模拟器网络和抓包组件。"
                )
            ),
            (
                .startingCapture(name: "Melody"),
                .init(
                    title: "正在启动抓包…",
                    message: "即将开始记录“Melody”的接口。"
                )
            ),
            (
                .capturing(name: "Melody", flowCount: 0),
                .init(
                    title: "正在抓取“Melody”",
                    message: "请操作应用以触发接口请求。",
                    primaryAction: .stopCapture,
                    primaryButtonTitle: "停止抓包"
                )
            ),
            (
                .capturing(name: "Melody", flowCount: 8),
                .init(
                    title: "已捕获 8 个接口",
                    message: "新接口将继续实时显示。",
                    primaryAction: .stopCapture,
                    primaryButtonTitle: "停止抓包"
                )
            ),
            (
                .stopped,
                .init(
                    title: "抓包已停止",
                    message: "已保留本次抓包结果。",
                    primaryAction: .startCapture,
                    primaryButtonTitle: "开始抓包"
                )
            ),
            (
                .restored(name: "Melody"),
                .init(
                    title: "已恢复正在运行的抓包",
                    message: "继续操作“Melody”即可。",
                    primaryAction: .stopCapture,
                    primaryButtonTitle: "停止抓包"
                )
            ),
            (
                .conflict(currentApp: "PokeHub"),
                .init(
                    title: "其他应用正在抓包",
                    message: "当前正在抓取“PokeHub”。",
                    primaryAction: .stopAndSwitch,
                    primaryButtonTitle: "停止并切换",
                    secondaryAction: .continueCurrent,
                    secondaryButtonTitle: "继续当前任务"
                )
            ),
        ]

        for (state, expected) in cases {
            #expect(state.presentation == expected)
        }
    }

    @Test
    func failureKeepsTechnicalDetailsOutOfPresentation() {
        let issue = UserFacingIssue(
            code: "capture_component_failed",
            title: "抓包组件启动失败",
            message: "请运行检查后重试。",
            recoveryAction: "打开运行检查",
            technicalDetail: "frida-ps failed on 127.0.0.1:27042"
        )

        let presentation = CaptureWorkflowState.failed(issue).presentation

        #expect(presentation.title == "抓包组件启动失败")
        #expect(presentation.message == "请运行检查后重试。")
        #expect(presentation.primaryButtonTitle == "打开运行检查")
        #expect(!presentation.message.contains("frida"))
        #expect(!presentation.message.contains("27042"))
        #expect(issue.technicalDetail == "frida-ps failed on 127.0.0.1:27042")
    }

    @Test
    func centralizedCopyUsesApprovedNavigationAndOperations() {
        #expect(AppCopy.Navigation.capture == "抓包")
        #expect(AppCopy.Navigation.installApps == "安装应用")
        #expect(AppCopy.Navigation.flows == "接口")
        #expect(AppCopy.Navigation.logs == "日志")
        #expect(AppCopy.Flow.clearList == "清空列表")
        #expect(AppCopy.Log.pauseDisplay == "暂停显示")
        #expect(AppCopy.Log.copyAll == "复制全部")
        #expect(AppCopy.Install.chooseAPK == "选择 APK")
    }

    @Test
    func workflowToneComesFromStateInsteadOfViewTextMatching() {
        #expect(CaptureWorkflowState.ready.tone == .neutral)
        #expect(CaptureWorkflowState.startingEmulator.tone == .progress)
        #expect(CaptureWorkflowState.waitingForUnlock.tone == .warning)
        #expect(CaptureWorkflowState.capturing(name: "Melody", flowCount: 2).tone == .success)
        #expect(
            CaptureWorkflowState.failed(
                .init(
                    code: "failed",
                    title: "启动失败",
                    message: "请重试。"
                )
            ).tone == .error
        )
    }
}

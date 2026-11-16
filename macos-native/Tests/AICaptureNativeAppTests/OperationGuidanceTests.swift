import Testing
@testable import AICaptureNativeApp

struct OperationGuidanceTests {
    @Test func androidPrimaryGuidanceIsCompactAndPreservesConsent() {
        let primary = [AppCopy.AndroidPhysical.boundary, AppCopy.AndroidPhysical.network,
                       AppCopy.AndroidPhysical.consent]
        #expect(primary.joined().count <= 260)
        #expect(AppCopy.AndroidPhysical.steps.count == 4)
        #expect(AppCopy.AndroidPhysical.steps.allSatisfy { $0.count <= 65 })
        #expect(primary.joined().contains("临时替换手机 VPN"))
        #expect(primary.joined().contains("不再由原 VPN 保护"))
        #expect(primary.joined().contains("30 分钟"))
        #expect(AppCopy.AndroidPhysical.steps.joined().contains("停止并恢复网络"))
        #expect(AppCopy.AndroidPhysical.recovery.contains("检查网络恢复"))
    }

    @Test func androidEvidenceMessagesRemainActionableWithoutClaimingBusinessSuccess() {
        for state in ["waiting", "responded", "partial", "server_error", "connection_failed", "quiet", "unknown"] {
            let message = AppCopy.AndroidPhysical.applicationMessage(state)
            #expect(!message.isEmpty)
            #expect(message.count <= 70)
        }
        #expect(AppCopy.AndroidPhysical.applicationMessage("responded").contains("业务结果"))
        #expect(AppCopy.AndroidPhysical.applicationMessage("quiet").contains("不代表断网"))
    }

    @Test func iphoneSetupExplainsManualConfirmationAndRecoveryConcisely() {
        for text in [AppCopy.IOSSetup.summary, AppCopy.IOSSetup.nodeSummary,
                     AppCopy.IOSSetup.nodeSent, AppCopy.IOSSetup.vpnSwitch,
                     AppCopy.IOSSetup.vpnPreparation, AppCopy.IOSSetup.vpnRestore,
                     AppCopy.IOSSetup.installHelp, AppCopy.IOSSetup.verifyHelp] {
            #expect(text.count <= 100)
        }
        #expect(AppCopy.IOSSetup.nodeSent.contains("确认"))
        #expect(AppCopy.IOSSetup.vpnPreparation.contains("VPN"))
        #expect(AppCopy.IOSSetup.vpnRestore.contains("恢复原节点和全局路由模式"))
        #expect(AppCopy.IOSSetup.vpnRestore.contains("不会自动替手机恢复"))
        let trust = AppCopy.IOSSetup.trustHelp("Test CA")
        #expect(trust.contains("Test CA") && trust.contains("完全信任") && trust.contains("解密"))
        #expect(AppCopy.IOSSetup.nodeSecretHelp.contains("请勿分享"))
    }
}

import AppKit
import Sparkle
import SwiftUI

@MainActor
final class DesktopUpdater: NSObject, ObservableObject, SPUUpdaterDelegate {
    @Published private(set) var isUpdating = false
    private var installApproved = false
    private var updater: SPUUpdater?
    private let blocker: @MainActor () async -> DesktopUpdateBlocker?

    init(blocker: @escaping @MainActor () async -> DesktopUpdateBlocker?) {
        self.blocker = blocker
    }

    var blocksQuit: Bool { isUpdating && !installApproved }

    func checkForUpdates() {
        guard !isUpdating else { return }
        guard Bundle.main.object(forInfoDictionaryKey: "SUFeedURL") != nil else {
            showMessage("请手动更新", detail: "请从发布页下载新版。安装支持应用内更新的正式版后，可以在此检查更新。")
            return
        }
        isUpdating = true
        Task { [self] in
            if let blocked = await blocker() {
                isUpdating = false
                showMessage("暂时无法更新", detail: blocked.message)
                return
            }
            if updater == nil {
                let driver = DesktopUpdateDriver(hostBundle: .main, delegate: nil)
                driver.approveInstall = { [weak self] in await self?.approveInstall() ?? false }
                let candidate = SPUUpdater(hostBundle: .main, applicationBundle: .main, userDriver: driver, delegate: self)
                do {
                    try candidate.start()
                    updater = candidate
                } catch {
                    isUpdating = false
                    showMessage("无法检查更新", detail: error.localizedDescription)
                    return
                }
            }
            guard let updater, updater.canCheckForUpdates else {
                isUpdating = false
                return
            }
            updater.checkForUpdates()
        }
    }

    func updater(_ updater: SPUUpdater, didFinishUpdateCycleFor updateCheck: SPUUpdateCheck, error: (any Error)?) {
        installApproved = false
        isUpdating = false
    }

    private func approveInstall() async -> Bool {
        if let blocked = await blocker() {
            showMessage("已延后安装", detail: blocked.message)
            return false
        }
        installApproved = true
        return true
    }

    private func showMessage(_ title: String, detail: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = detail
        alert.addButton(withTitle: "好")
        alert.addButton(withTitle: "打开发布页")
        if alert.runModal() == .alertSecondButtonReturn,
           let url = URL(string: "https://github.com/wanyujiang75-source/ai-capture-tool/releases") {
            NSWorkspace.shared.open(url)
        }
    }
}

@MainActor
private final class DesktopUpdateDriver: SPUStandardUserDriver {
    var approveInstall: (@MainActor () async -> Bool)?

    override func showReady(toInstallAndRelaunch reply: @escaping (SPUUserUpdateChoice) -> Void) {
        let alert = NSAlert()
        alert.messageText = "新版已下载"
        alert.informativeText = "安装后将重新打开抓包工具。"
        alert.addButton(withTitle: "安装并重启")
        alert.addButton(withTitle: "稍后再说")
        guard alert.runModal() == .alertFirstButtonReturn else {
            // At the installation stage, Skip cancels the pending install without skipping the version.
            reply(.skip)
            return
        }
        Task {
            let approved = await approveInstall?() == true
            reply(approved ? .install : .skip)
        }
    }

    override func showUpdateFound(
        with appcastItem: SUAppcastItem,
        state: SPUUserUpdateState,
        reply: @escaping (SPUUserUpdateChoice) -> Void
    ) {
        guard state.stage == .installing else {
            super.showUpdateFound(with: appcastItem, state: state, reply: reply)
            return
        }
        showReady(toInstallAndRelaunch: reply)
    }
}

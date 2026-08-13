import AppKit
import SwiftUI

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private static let mainWindowIdentifier = NSUserInterfaceItemIdentifier("ai-capture-main-window")
    private let fallbackAppState = AppState()
    private var fallbackWindowController: NSWindowController?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApplication.shared.setActivationPolicy(.regular)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { [weak self] in
            self?.presentMainWindowIfNeeded(NSApplication.shared)
        }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag {
            presentMainWindowIfNeeded(sender)
        }
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        RuntimeManager.shared.shutdown()
    }

    @discardableResult
    func presentMainWindowIfNeeded(_ application: NSApplication) -> NSWindow {
        if let window = application.windows.first(where: { $0.identifier == Self.mainWindowIdentifier })
            ?? application.windows.first(where: { $0.canBecomeMain }) {
            window.identifier = Self.mainWindowIdentifier
            window.makeKeyAndOrderFront(nil)
            application.activate()
            return window
        }

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1180, height: 760),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.identifier = Self.mainWindowIdentifier
        window.title = "抓包工具"
        window.minSize = NSSize(width: 1180, height: 760)
        window.isReleasedWhenClosed = false
        window.contentViewController = NSHostingController(
            rootView: ContentView().environmentObject(fallbackAppState)
        )
        window.center()

        let controller = NSWindowController(window: window)
        fallbackWindowController = controller
        controller.showWindow(nil)
        application.activate()
        return window
    }
}

@main
struct AICaptureNativeApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .frame(minWidth: 1180, minHeight: 760)
        }
        .windowStyle(.titleBar)
        .commands {
            CommandGroup(after: .appInfo) {
                Button("刷新状态") {
                    Task {
                        await appState.refreshRuntimeStatus()
                    }
                }
                .keyboardShortcut("r", modifiers: [.command])
            }
        }
    }
}

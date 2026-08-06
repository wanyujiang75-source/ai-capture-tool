import SwiftUI

@main
struct AICaptureNativeApp: App {
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
                    appState.runtimeStatus = .starting
                }
                .keyboardShortcut("r", modifiers: [.command])
            }
        }
    }
}

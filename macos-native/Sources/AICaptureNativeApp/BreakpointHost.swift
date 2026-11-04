import SwiftUI

struct BreakpointHost: View {
    @ObservedObject var controller: BreakpointController
    var body: some View {
        Color.clear.frame(width: 0, height: 0)
            .sheet(isPresented: $controller.showsPanel) { BreakpointPanel(controller: controller) }
            .task {
                while !Task.isCancelled {
                    await controller.refreshLease()
                    do { try await Task.sleep(for: .milliseconds(500)) } catch { break }
                }
            }
            .task {
                while !Task.isCancelled {
                    await controller.poll()
                    do { try await Task.sleep(for: .milliseconds(500)) } catch { break }
                }
            }
            .task {
                while !Task.isCancelled {
                    await controller.refreshSources()
                    do { try await Task.sleep(for: .seconds(2)) } catch { break }
                }
            }
    }
}

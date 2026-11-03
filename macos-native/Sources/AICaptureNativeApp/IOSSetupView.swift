import AppKit
import CoreImage.CIFilterBuiltins
import CoreWLAN
import SwiftUI

struct IOSSetupView: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var controller: IOSSetupController
    @State private var ssid = ""
    @State private var confirmsRemoval = false

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                VStack(alignment: .leading, spacing: 6) {
                    Text(AppCopy.IOSSetup.title).font(.title.bold())
                    Text(controller.status.identityReused == true ? AppCopy.IOSSetup.reconnectSummary : AppCopy.IOSSetup.summary)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button(AppCopy.IOSSetup.close) { dismiss() }
            }
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    let presentation = AppCopy.IOSCapture.presentation(controller.status)
                    VStack(alignment: .leading, spacing: 8) {
                        Text(controller.operation?.title ?? presentation.0).font(.headline)
                        Text(presentation.1).foregroundStyle(.secondary)
                        if controller.busy { ProgressView().controlSize(.small) }
                        if let issue = controller.issue { Text(issue).foregroundStyle(.red) }
                    }
                    .padding(18).frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.accentColor.opacity(0.07), in: RoundedRectangle(cornerRadius: 14))

                    if controller.status.canPrepare {
                        TextField(AppCopy.IOSSetup.wifi, text: $ssid).textFieldStyle(.roundedBorder)
                        Text(AppCopy.IOSSetup.wifiHelp).font(.callout).foregroundStyle(.secondary)
                        Button(controller.status.canResume == true ? AppCopy.IOSSetup.reconnect : AppCopy.IOSSetup.prepare) { Task { await controller.prepare(ssid: ssid) } }
                            .buttonStyle(.borderedProminent).disabled(controller.busy || ssid.isEmpty)
                    }
                    Text(AppCopy.IOSSetup.lifetimeHelp).font(.callout).foregroundStyle(.secondary)
                    if let profile = controller.profileURL {
                        if controller.status.identityReused != true { shareInstructions(profile) }
                        instructions
                    }
                    if !controller.status.canPrepare || controller.status.identityReused == true {
                        Text(AppCopy.IOSSetup.removeHelp).font(.caption).foregroundStyle(.secondary)
                        Button(AppCopy.IOSSetup.stop) { confirmsRemoval = true }.disabled(controller.busy)
                    }
                }.padding(2)
            }
        }
        .padding(26).frame(width: 820, height: 700)
        .task {
            await controller.refresh()
            if ssid.isEmpty {
                ssid = CWWiFiClient.shared().interface()?.ssid() ?? controller.status.ssid ?? ""
            }
            while !Task.isCancelled {
                await controller.refresh()
                if let configured = controller.status.configuredSSID { ssid = configured }
                do { try await Task.sleep(for: .seconds(2)) } catch { break }
            }
        }
        .alert(AppCopy.IOSSetup.remove, isPresented: $confirmsRemoval) {
            Button(AppCopy.IOSSetup.confirmRemoved) { Task { await controller.stop(phoneConfigurationRemoved: true) } }
            Button(AppCopy.IOSSetup.cancel, role: .cancel) {}
        } message: { Text(AppCopy.IOSSetup.removeHelp) }
    }

    private var instructions: some View {
        HStack(alignment: .top, spacing: 20) {
            VStack(alignment: .leading, spacing: 12) {
                if controller.status.identityReused == true {
                    DisclosureGroup(AppCopy.IOSSetup.reinstall) {
                        VStack(alignment: .leading, spacing: 12) {
                            if let profile = controller.profileURL { shareInstructions(profile) }
                            installationInstructions
                        }
                    }
                } else {
                    installationInstructions
                }
                Text(AppCopy.IOSSetup.verify).font(.headline)
                Text(AppCopy.IOSSetup.verifyHelp)
            }.font(.callout)
            if let value = controller.status.checkURL, let image = qrImage(value) {
                Image(nsImage: image).interpolation(.none).resizable().frame(width: 140, height: 140)
                    .padding(8).background(.white)
                    .accessibilityLabel(AppCopy.IOSSetup.verify)
            }
        }
    }

    private func shareInstructions(_ profile: URL) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            ShareLink(item: profile) { Label(AppCopy.IOSSetup.share, systemImage: "square.and.arrow.up") }
                .buttonStyle(.borderedProminent)
            Text(AppCopy.IOSSetup.shareHelp).font(.callout).foregroundStyle(.secondary)
        }
    }

    private var installationInstructions: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(AppCopy.IOSSetup.install).font(.headline)
            Text(AppCopy.IOSSetup.installHelp)
            Text(AppCopy.IOSSetup.trust).font(.headline)
            Text(AppCopy.IOSSetup.trustHelp(controller.status.certificateName ?? "Capture iPhone Test"))
        }
    }

    private func qrImage(_ text: String) -> NSImage? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(text.utf8)
        guard let output = filter.outputImage,
              let image = CIContext().createCGImage(output, from: output.extent) else { return nil }
        return NSImage(cgImage: image, size: NSSize(width: image.width, height: image.height))
    }
}

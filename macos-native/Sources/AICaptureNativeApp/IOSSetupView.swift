import AppKit
import CoreImage.CIFilterBuiltins
import CoreWLAN
import SwiftUI

struct IOSSetupView: View {
    @Environment(\.dismiss) private var dismiss
    @StateObject private var controller = IOSSetupController()
    @State private var ssid = ""
    @State private var confirmsRemoval = false
    @State private var selectedFlow: IOSSetupFlow?

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                VStack(alignment: .leading, spacing: 6) {
                    Text(AppCopy.IOSSetup.title).font(.title.bold())
                    Text(AppCopy.IOSSetup.summary).foregroundStyle(.secondary)
                }
                Spacer()
                Button(AppCopy.IOSSetup.close) { dismiss() }
            }
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    let presentation = AppCopy.IOSSetup.status(controller.status.phase, count: controller.status.flowCount)
                    VStack(alignment: .leading, spacing: 8) {
                        Text(controller.busy ? (controller.stopping ? AppCopy.IOSSetup.stopping : AppCopy.IOSSetup.preparing) : presentation.0).font(.headline)
                        Text(presentation.1).foregroundStyle(.secondary)
                        if controller.busy { ProgressView().controlSize(.small) }
                        if let issue = controller.issue { Text(issue).foregroundStyle(.red) }
                    }
                    .padding(18).frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.accentColor.opacity(0.07), in: RoundedRectangle(cornerRadius: 14))

                    if controller.status.canPrepare {
                        TextField(AppCopy.IOSSetup.wifi, text: $ssid).textFieldStyle(.roundedBorder)
                        Text(AppCopy.IOSSetup.wifiHelp).font(.callout).foregroundStyle(.secondary)
                        Button(AppCopy.IOSSetup.prepare) { Task { await controller.prepare(ssid: ssid) } }
                            .buttonStyle(.borderedProminent).disabled(controller.busy || ssid.isEmpty)
                    }
                    if let profile = controller.profileURL {
                        ShareLink(item: profile) { Label(AppCopy.IOSSetup.share, systemImage: "square.and.arrow.up") }
                            .buttonStyle(.borderedProminent)
                        Text(AppCopy.IOSSetup.shareHelp).font(.callout).foregroundStyle(.secondary)
                        instructions
                    }
                    if !controller.status.flows.isEmpty {
                        Text(AppCopy.IOSSetup.results).font(.headline)
                        ForEach(controller.status.flows.reversed()) { flow in
                            Button {
                                selectedFlow = flow
                            } label: {
                                HStack(alignment: .top) {
                                    Text(flow.method).font(.caption.monospaced()).frame(width: 48)
                                    Text("\(flow.status)").foregroundStyle(flow.status < 400 ? .green : .orange)
                                    Text(flow.url).lineLimit(3).frame(maxWidth: .infinity, alignment: .leading)
                                }.padding(.vertical, 6)
                            }.buttonStyle(.plain)
                        }
                    }
                    Text(AppCopy.IOSSetup.limited).font(.caption).foregroundStyle(.secondary)
                    if !controller.status.canPrepare {
                        Text(AppCopy.IOSSetup.removeHelp).font(.caption).foregroundStyle(.secondary)
                        Button(AppCopy.IOSSetup.stop) { confirmsRemoval = true }.disabled(controller.busy)
                    }
                }.padding(2)
            }
        }
        .padding(26).frame(width: 820, height: 700)
        .task {
            ssid = CWWiFiClient.shared().interface()?.ssid() ?? ""
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
        .sheet(item: $selectedFlow) { flow in
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text(flow.url).font(.headline).lineLimit(3)
                    Spacer()
                    Button(AppCopy.IOSSetup.close) { selectedFlow = nil }
                }
                Text("Request").font(.headline)
                IOSPreviewText(text: flow.requestBody.isEmpty ? AppCopy.IOSSetup.emptyBody : flow.requestBody)
                Text("Response").font(.headline)
                IOSPreviewText(text: flow.responseBody.isEmpty ? AppCopy.IOSSetup.emptyBody : flow.responseBody)
                if flow.truncated { Text(AppCopy.IOSSetup.truncated).foregroundStyle(.secondary) }
            }.padding(24).frame(width: 740, height: 580)
        }
    }

    private var instructions: some View {
        HStack(alignment: .top, spacing: 20) {
            VStack(alignment: .leading, spacing: 12) {
                Text(AppCopy.IOSSetup.install).font(.headline)
                Text(AppCopy.IOSSetup.installHelp)
                Text(AppCopy.IOSSetup.trust).font(.headline)
                Text(AppCopy.IOSSetup.trustHelp(controller.status.certificateName ?? "Capture iPhone Test"))
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

    private func qrImage(_ text: String) -> NSImage? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(text.utf8)
        guard let output = filter.outputImage,
              let image = CIContext().createCGImage(output, from: output.extent) else { return nil }
        return NSImage(cgImage: image, size: NSSize(width: image.width, height: image.height))
    }
}

private struct IOSPreviewText: NSViewRepresentable {
    let text: String
    func makeNSView(context: Context) -> NSScrollView {
        let scroll = NSTextView.scrollableTextView()
        if let view = scroll.documentView as? NSTextView {
            view.isEditable = false
            view.isSelectable = true
            view.font = .monospacedSystemFont(ofSize: 12, weight: .regular)
        }
        return scroll
    }
    func updateNSView(_ view: NSScrollView, context: Context) {
        if let editor = view.documentView as? NSTextView, editor.string != text { editor.string = text }
    }
}

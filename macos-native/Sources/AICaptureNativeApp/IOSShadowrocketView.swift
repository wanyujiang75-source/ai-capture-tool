import AppKit
import CoreImage.CIFilterBuiltins
import SwiftUI

struct IOSShadowrocketView: View {
    @ObservedObject var controller: IOSShadowrocketController
    let isRecording: Bool
    @State private var showPassword = false
    @State private var manualExpanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(AppCopy.IOSSetup.nodeTitle).font(.headline)
            Text(AppCopy.IOSSetup.nodeSummary).fixedSize(horizontal: false, vertical: true)
            if controller.loading {
                HStack { ProgressView().controlSize(.small); Text(AppCopy.IOSSetup.nodeLoading) }
            }
            if let issue = controller.issue { Text(issue).foregroundStyle(.red) }
            if let info = controller.info {
                if !info.devices.isEmpty {
                    Picker(AppCopy.IOSSetup.nodeDevice, selection: $controller.selectedDeviceID) {
                        Text(AppCopy.IOSSetup.nodeChoose).tag(String?.none)
                        ForEach(info.devices) { device in Text(device.name).tag(Optional(device.id)) }
                    }.disabled(controller.sending)
                    Button(AppCopy.IOSSetup.nodeImport) { Task { await controller.send() } }
                        .buttonStyle(.borderedProminent)
                        .disabled(controller.selectedDeviceID == nil || controller.sending || isRecording)
                } else {
                    Text(AppCopy.IOSSetup.nodeFallback).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                }
                if controller.sending {
                    HStack { ProgressView().controlSize(.small); Text(AppCopy.IOSSetup.nodeSending) }
                }
                if let result = controller.delivery {
                    Text(result == .confirmationRequired ? AppCopy.IOSSetup.nodeSent : AppCopy.IOSSetup.nodeFallback)
                        .foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                }
                DisclosureGroup(AppCopy.IOSSetup.nodeManual, isExpanded: $manualExpanded) {
                    VStack(alignment: .leading, spacing: 10) {
                        Text(AppCopy.IOSSetup.nodeManualHelp).fixedSize(horizontal: false, vertical: true)
                        LabeledContent(AppCopy.IOSSetup.nodeHost) { Text(info.host).textSelection(.enabled) }
                        LabeledContent(AppCopy.IOSSetup.nodePort) { Text(String(info.port)).textSelection(.enabled) }
                        LabeledContent(AppCopy.IOSSetup.nodeUsername) { Text(info.username).textSelection(.enabled) }
                        LabeledContent(AppCopy.IOSSetup.nodePassword) {
                            Text(showPassword ? info.password : "••••••••").textSelection(.enabled)
                            Button(showPassword ? AppCopy.IOSSetup.hidePassword : AppCopy.IOSSetup.showPassword) {
                                showPassword.toggle()
                            }
                        }.accessibilityElement(children: .contain)
                        if let url = info.safeImportURL {
                            DisclosureGroup(AppCopy.IOSSetup.nodeQR) {
                                IOSConnectionQRCode(value: url, label: AppCopy.IOSSetup.nodeQR)
                            }
                        }
                        Text(AppCopy.IOSSetup.nodeSecretHelp).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                    }.padding(.top, 8)
                }
            }
            Button(AppCopy.IOSSetup.nodeRefresh) { Task { await controller.load() } }
                .disabled(controller.loading || controller.sending || isRecording)
            DisclosureGroup(AppCopy.IOSSetup.nodeMigrationTitle) {
                Text(AppCopy.IOSSetup.nodeMigrationHelp).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
        }
        .task { await controller.load() }
        .onChange(of: controller.delivery) { _, value in
            if value == .manualRequired { manualExpanded = true }
        }
        .onChange(of: controller.info?.importURL) { _, _ in showPassword = false }
        .onChange(of: controller.info?.devices.count, initial: true) { _, count in
            if count == 0 { manualExpanded = true }
        }
        .onDisappear { controller.clear() }
    }
}

struct IOSConnectionQRCode: View {
    let value: String
    let label: String

    var body: some View {
        if let image = qrImage {
            Image(nsImage: image).interpolation(.none).resizable().frame(width: 140, height: 140)
                .padding(8).background(.white).accessibilityLabel(label)
        }
    }

    private var qrImage: NSImage? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(value.utf8)
        guard let output = filter.outputImage,
              let image = CIContext().createCGImage(output, from: output.extent) else { return nil }
        return NSImage(cgImage: image, size: NSSize(width: image.width, height: image.height))
    }
}

import AppKit
import SwiftUI

struct BreakpointEditorView: View {
    @ObservedObject var controller: BreakpointController
    let detail: BreakpointDetail
    @State private var reveal = false
    @State private var reviewing = false
    @State private var confirmingAbort = false
    @State private var error: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(BreakpointCopy.paused(detail.stage)).font(.headline)
            TimelineView(.periodic(from: .now, by: 1)) { _ in
                Text(BreakpointCopy.countdown(controller.pending.first { $0.id == detail.id }.map(controller.remaining) ?? 0))
                    .foregroundStyle(.orange)
            }
            if let error { Text(error).foregroundStyle(.red) }
            HStack {
                Toggle(BreakpointCopy.showSecrets, isOn: $reveal)
                Spacer()
                Button(BreakpointCopy.formatJSON) {
                    do { try controller.draft?.formatJSON(); error = nil }
                    catch { self.error = BreakpointCopy.issue(error) }
                }.disabled(!controller.canEdit || !detail.original.editableBody)
            }
            if reviewing { comparison } else { fields }
            HStack {
                Button(BreakpointCopy.abort, role: .destructive) { confirmingAbort = true }
                Spacer()
                Button(BreakpointCopy.original) { Task { await controller.resolve("original") } }
                Button(reviewing ? BreakpointCopy.apply : BreakpointCopy.review) {
                    do {
                        _ = try controller.draft?.patch(stage: detail.stage, original: detail.original)
                        error = nil
                        if reviewing { Task { await controller.resolve("apply") } } else { reviewing = true }
                    } catch { self.error = BreakpointCopy.issue(error) }
                }.buttonStyle(.borderedProminent)
            }.disabled(!controller.canEdit)
        }
        .padding(.leading, 12)
        .confirmationDialog(BreakpointCopy.abort, isPresented: $confirmingAbort) {
            Button(BreakpointCopy.abort, role: .destructive) { Task { await controller.resolve("abort") } }
        } message: { Text(BreakpointCopy.abortWarning) }
    }

    private var fields: some View {
        VStack(alignment: .leading, spacing: 10) {
            if detail.stage == "request" {
                HStack {
                    Picker(BreakpointCopy.method, selection: field(\.method)) { ForEach(BreakpointDraft.methods, id: \.self) { Text($0) } }
                        .frame(width: 180)
                    TextField(BreakpointCopy.url, text: field(\.url))
                }
            } else {
                Text(detail.original.url).font(.caption.monospaced()).lineLimit(2).textSelection(.enabled)
                TextField(BreakpointCopy.status, text: field(\.status)).frame(width: 210)
            }
            HStack {
                Text(BreakpointCopy.headers).font(.headline)
                Spacer()
                Button(BreakpointCopy.addHeader) { controller.draft?.headers.append(["", ""]) }
                    .disabled((controller.draft?.headers.count ?? 0) >= 200)
            }
            ScrollView {
                VStack(spacing: 5) {
                    ForEach(Array((controller.draft?.headers ?? []).indices), id: \.self) { index in
                        headerRow(index)
                    }
                }
            }.frame(minHeight: 80, maxHeight: 150)
            Text(BreakpointCopy.body).font(.headline)
            if !detail.original.editableBody || detail.original.text == nil { Text(BreakpointCopy.limited).foregroundStyle(.secondary) }
            BreakpointTextEditor(text: field(\.body), editable: controller.canEdit && detail.original.editableBody && detail.original.text != nil,
                                 label: BreakpointCopy.body, onLimit: { error = BreakpointCopy.limited })
                .frame(minHeight: 130, maxHeight: .infinity)
        }.disabled(!controller.canEdit)
    }

    private func headerRow(_ index: Int) -> some View {
        let pair = controller.draft?.headers[index] ?? ["", ""]
        let managed = BreakpointDraft.managedHeaders.contains(pair[0].lowercased())
        let secret = BreakpointDraft.sensitiveHeaders.contains(pair[0].lowercased())
        return HStack {
            TextField(BreakpointCopy.headerName, text: header(index, 0)).frame(width: 180).disabled(managed || (secret && !reveal))
            if secret && !reveal { Text(BreakpointCopy.hidden).frame(maxWidth: .infinity, alignment: .leading) }
            else { TextField(BreakpointCopy.headerValue, text: header(index, 1)).disabled(managed) }
            Button(BreakpointCopy.removeHeader) { controller.draft?.headers.remove(at: index) }.disabled(managed || (secret && !reveal))
        }
    }
    private func header(_ row: Int, _ column: Int) -> Binding<String> {
        Binding(get: { guard let draft = controller.draft, draft.headers.indices.contains(row) else { return "" }; return draft.headers[row][column] },
                set: { guard controller.draft?.headers.indices.contains(row) == true else { return }; controller.draft?.headers[row][column] = $0 })
    }
    private func field(_ key: WritableKeyPath<BreakpointDraft, String>) -> Binding<String> {
        Binding(get: { controller.draft?[keyPath: key] ?? "" }, set: { controller.draft?[keyPath: key] = $0 })
    }

    private var comparison: some View {
        VStack(alignment: .leading) {
            Button(BreakpointCopy.backToEdit) { reviewing = false }
            HStack {
                version(BreakpointDraft(original: detail.original), title: BreakpointCopy.before)
                version(controller.draft ?? BreakpointDraft(original: detail.original), title: BreakpointCopy.draft)
            }
        }.frame(maxHeight: .infinity)
    }
    private func version(_ draft: BreakpointDraft, title: String) -> some View {
        let heads = draft.headers.map { pair in
            "\(pair[0]): \(!reveal && BreakpointDraft.sensitiveHeaders.contains(pair[0].lowercased()) ? BreakpointCopy.hidden : pair[1])"
        }.joined(separator: "\n")
        return VStack(alignment: .leading) {
            Text(title).font(.headline)
            BreakpointTextEditor(text: .constant("\(detail.stage == "request" ? draft.method : draft.status) \(draft.url)\n\(heads)\n\n\(draft.body)"),
                                 editable: false, label: title)
        }.frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct BreakpointTextEditor: NSViewRepresentable {
    @Binding var text: String
    var editable = true
    let label: String
    var onLimit: () -> Void = {}
    final class Coordinator: NSObject, NSTextViewDelegate {
        var parent: BreakpointTextEditor
        init(_ parent: BreakpointTextEditor) { self.parent = parent }
        func textDidChange(_ notification: Notification) {
            if let view = notification.object as? NSTextView { parent.text = view.string }
        }
        func textView(_ textView: NSTextView, shouldChangeTextIn affectedCharRange: NSRange, replacementString: String?) -> Bool {
            guard let replacementString else { return true }
            guard replacementString.utf8.count <= 262144,
                  (textView.string as NSString).replacingCharacters(in: affectedCharRange, with: replacementString).utf8.count <= 262144 else {
                parent.onLimit(); return false
            }
            return true
        }
    }
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeNSView(context: Context) -> NSScrollView {
        let scroll = NSTextView.scrollableTextView()
        let view = scroll.documentView as! NSTextView
        view.delegate = context.coordinator
        view.isRichText = false; view.isSelectable = true; view.allowsUndo = false
        view.isAutomaticQuoteSubstitutionEnabled = false; view.isAutomaticDashSubstitutionEnabled = false
        view.isAutomaticTextReplacementEnabled = false; view.isAutomaticSpellingCorrectionEnabled = false
        view.font = .monospacedSystemFont(ofSize: 12, weight: .regular)
        view.textContainerInset = NSSize(width: 8, height: 8)
        view.setAccessibilityLabel(label)
        return scroll
    }
    func updateNSView(_ scroll: NSScrollView, context: Context) {
        context.coordinator.parent = self
        let view = scroll.documentView as! NSTextView
        view.isEditable = editable
        if view.string != text { view.string = text }
    }
}

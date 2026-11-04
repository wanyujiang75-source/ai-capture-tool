import SwiftUI

struct BreakpointToolbar: View {
    @ObservedObject var controller: BreakpointController
    var compact = false
    var body: some View {
        HStack(spacing: 12) {
            if !compact {
                Button(BreakpointCopy.rules) { controller.panelTab = "rules"; controller.showsPanel = true }
                Button(controller.status?.enabled == true ? BreakpointCopy.disable : BreakpointCopy.enable) {
                    Task { await controller.setEnabled(controller.status?.enabled != true) }
                }
                .disabled(!controller.canControl)
            }
            Button {
                controller.panelTab = "pending"; controller.showsPanel = true
            } label: { Label(BreakpointCopy.queue(controller.pending.count), systemImage: "pause.circle") }
            .help(BreakpointCopy.globalHelp)
        }
    }
}

struct BreakpointPanel: View {
    @ObservedObject var controller: BreakpointController
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text(BreakpointCopy.title).font(.title.bold())
                Spacer()
                Button(BreakpointCopy.close) { dismiss() }.keyboardShortcut(.cancelAction)
            }
            HStack {
                Text(controller.title).font(.headline)
                if controller.sources.count > 1 {
                    Menu(BreakpointCopy.chooseCapture) {
                        ForEach(controller.sources) { source in
                            Button(source.title) { Task { await controller.bind(source.id); await controller.poll() } }
                        }
                    }.disabled(!controller.canRebind)
                }
                Spacer()
                Button(BreakpointCopy.refresh) { Task { await controller.poll() } }.disabled(controller.busy)
            }
            Text(BreakpointCopy.reuse).font(.callout).foregroundStyle(.secondary)
            if let issue = controller.issue { Text(issue).foregroundStyle(.red).textSelection(.enabled) }
            if let message = controller.message { Text(message).foregroundStyle(.secondary) }
            if controller.busy { ProgressView(BreakpointCopy.processing).controlSize(.small) }
            Picker(BreakpointCopy.title, selection: $controller.panelTab) {
                Text(BreakpointCopy.queue(controller.pending.count)).tag("pending")
                Text(BreakpointCopy.rules).tag("rules")
            }.pickerStyle(.segmented)
            if controller.panelTab == "rules" {
                BreakpointRulesView(controller: controller)
            } else {
                pendingContent
            }
        }
        .padding(24)
        .frame(minWidth: 1000, idealWidth: 1140, minHeight: 650, idealHeight: 760)
    }

    private var pendingContent: some View {
        HSplitView {
            VStack(alignment: .leading, spacing: 12) {
                Button(BreakpointCopy.release) { Task { await controller.releaseAll() } }
                    .disabled(!controller.canControl || controller.pending.isEmpty)
                    .help(BreakpointCopy.releaseHelp)
                if controller.pending.isEmpty {
                    Text(BreakpointCopy.empty).foregroundStyle(.secondary).padding(.vertical)
                    Spacer()
                } else {
                    List(selection: Binding<String?>(get: { controller.selectedID }, set: { id in
                        if let id { Task { await controller.select(id) } }
                    })) {
                        ForEach(controller.pending) { item in
                            VStack(alignment: .leading, spacing: 6) {
                                Text(BreakpointCopy.stage(item.stage)).font(.headline)
                                Text(controller.status?.rules.first { $0.id == item.matchedRule }?.spec.path ?? BreakpointCopy.waiting)
                                    .lineLimit(2).font(.caption.monospaced())
                                Text(item.state == "paused" ? BreakpointCopy.waiting : BreakpointCopy.processing)
                                    .foregroundStyle(item.state == "paused" ? .orange : .secondary)
                            }.padding(6).frame(maxWidth: .infinity, alignment: .leading).tag(item.id)
                        }
                    }.listStyle(.plain)
                }
            }.frame(minWidth: 260, idealWidth: 290, maxWidth: 350).padding(.trailing, 10)
            Group {
                if controller.loadingDetail { ProgressView(BreakpointCopy.loading) }
                else if let detail = controller.detail, controller.draft != nil {
                    BreakpointEditorView(controller: controller, detail: detail).id(detail.id)
                } else {
                    Text(controller.selectedID == nil ? BreakpointCopy.selectPending : BreakpointCopy.ended).foregroundStyle(.secondary)
                }
            }.frame(minWidth: 600, maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}

private struct BreakpointRulesView: View {
    @ObservedObject var controller: BreakpointController
    @State private var editing: BreakpointRuleSpec?
    @State private var editingID: String?
    @State private var revision = 0
    @State private var url = ""
    @State private var error: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                TextField(BreakpointCopy.ruleURL, text: $url)
                Button(BreakpointCopy.newRule) {
                    do { editing = try .seed(url: url, method: "GET"); editingID = nil; revision = 0; error = nil }
                    catch { self.error = BreakpointCopy.issue(error) }
                }.disabled(!controller.canControl)
                Menu(BreakpointCopy.templates) {
                    ForEach(Array(controller.templates.enumerated()), id: \.offset) { _, template in
                        Button("\(template.method) \(template.endpoint)") {
                            editing = template; editingID = nil; revision = 0
                        }
                    }
                }.disabled(!controller.canControl || controller.templates.isEmpty)
                Button(controller.status?.enabled == true ? BreakpointCopy.disable : BreakpointCopy.enable) {
                    Task { await controller.setEnabled(controller.status?.enabled != true) }
                }.disabled(!controller.canControl)
            }
            if let error { Text(error).foregroundStyle(.red) }
            if editing != nil { ruleForm }
            List(controller.status?.rules ?? []) { rule in
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("\(rule.spec.method) \(rule.spec.endpoint)").font(.callout.monospaced()).textSelection(.enabled)
                        Text("\(BreakpointCopy.stage(rule.spec.stage)) · \(rule.spec.once ? BreakpointCopy.once : BreakpointCopy.continuous) · \(rule.consumed ? BreakpointCopy.consumed : rule.spec.enabled ? BreakpointCopy.ruleEnabled : BreakpointCopy.ruleDisabled)")
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button(BreakpointCopy.editRule) { editing = rule.spec; editingID = rule.id; revision = rule.revision }
                    Button(rule.spec.enabled ? BreakpointCopy.disableRule : BreakpointCopy.enableRule) {
                        var spec = rule.spec; spec.enabled.toggle()
                        Task { await controller.saveRule(spec, id: rule.id, revision: rule.revision) }
                    }
                }.disabled(!controller.canControl)
            }.listStyle(.plain)
        }
        .onAppear { takeSeed() }
        .onChange(of: controller.ruleSeed) { _, _ in takeSeed() }
    }
    private func takeSeed() {
        if let seed = controller.ruleSeed { editing = seed; editingID = nil; revision = 0 }
    }
    private var ruleForm: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(editing?.endpoint ?? "").font(.callout.monospaced()).textSelection(.enabled)
            HStack {
                Picker(BreakpointCopy.method, selection: field(\.method)) { ForEach(BreakpointDraft.methods, id: \.self) { Text($0) } }
                Picker(BreakpointCopy.stageLabel, selection: field(\.stage)) {
                    ForEach(["request", "response", "both"], id: \.self) { Text(BreakpointCopy.stage($0)).tag($0) }
                }
                Picker(BreakpointCopy.match, selection: field(\.pathMatch)) {
                    Text(BreakpointCopy.exact).tag("exact"); Text(BreakpointCopy.prefix).tag("prefix")
                }
            }
            TextField(BreakpointCopy.path, text: field(\.path))
            HStack {
                Toggle(BreakpointCopy.once, isOn: Binding(get: { editing?.once ?? true }, set: { editing?.once = $0 }))
                Picker(BreakpointCopy.timeout, selection: Binding(get: { editing?.timeoutSeconds ?? 30 }, set: { editing?.timeoutSeconds = $0 })) {
                    ForEach([15, 30, 60], id: \.self) { Text("\($0) s").tag($0) }
                }.frame(width: 200)
                Spacer()
                Button(BreakpointCopy.cancel) { editing = nil; controller.ruleSeed = nil }
                Button(BreakpointCopy.saveRule) { save(enable: false) }
                Button(BreakpointCopy.saveEnable) { save(enable: true) }.buttonStyle(.borderedProminent)
            }
        }.padding(16).background(.quaternary.opacity(0.3)).clipShape(RoundedRectangle(cornerRadius: 12))
            .disabled(!controller.canControl)
    }
    private func field(_ key: WritableKeyPath<BreakpointRuleSpec, String>) -> Binding<String> {
        Binding(get: { editing?[keyPath: key] ?? "" }, set: { editing?[keyPath: key] = $0 })
    }
    private func save(enable: Bool) {
        guard let editing else { return }
        Task {
            await controller.saveRule(editing, id: editingID ?? UUID().uuidString, revision: revision, enable: enable)
            if controller.issue == nil { self.editing = nil }
        }
    }
}

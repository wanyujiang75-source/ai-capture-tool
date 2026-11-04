import SwiftUI

struct BreakpointAudit: Decodable {
    let action: String
    let reason: String
    let adopted: Bool
    let original: BreakpointVersion
    let effective: BreakpointVersion
}

struct BreakpointVersion: Decodable {
    let url: String
    let method: String
    let status: Int?
    let headers: [[String]]
    let bodyText: String?
    let bodyAvailable: Bool?
    let bodyTruncated: Bool?
    enum CodingKeys: String, CodingKey {
        case url, method, status, headers
        case bodyText = "body_text", bodyAvailable = "body_available", bodyTruncated = "body_truncated"
    }
}

struct BreakpointArchiveView: View {
    let stages: [String: BreakpointAudit]
    @State private var expanded = false
    @State private var stage = "request"
    @State private var version = "effective"
    @State private var reveal = false
    var body: some View {
        DisclosureGroup(BreakpointCopy.archive, isExpanded: $expanded) {
            VStack(alignment: .leading, spacing: 8) {
                Text(BreakpointCopy.archiveHelp).font(.caption).foregroundStyle(.secondary)
                Picker(BreakpointCopy.stageLabel, selection: $stage) {
                    ForEach(stages.keys.sorted(), id: \.self) { Text(BreakpointCopy.stage($0)).tag($0) }
                }
                Picker(BreakpointCopy.review, selection: $version) {
                    Text(BreakpointCopy.before).tag("original"); Text(BreakpointCopy.after).tag("effective")
                }.pickerStyle(.segmented)
                Toggle(BreakpointCopy.showSecrets, isOn: $reveal)
                if let audit = stages[stage] ?? stages.values.first {
                    Text(BreakpointCopy.auditAction(audit.action, adopted: audit.adopted)).font(.caption)
                    let value = version == "original" ? audit.original : audit.effective
                    if value.bodyTruncated == true { Text(BreakpointCopy.archiveTruncated).foregroundStyle(.orange) }
                    BreakpointTextEditor(text: .constant(render(value)), editable: false, label: BreakpointCopy.archive)
                        .frame(height: 180)
                }
            }.padding(.vertical, 8)
        }.onChange(of: stages.keys.sorted()) { _, _ in reveal = false }
    }
    private func render(_ value: BreakpointVersion) -> String {
        let headers = value.headers.filter { $0.count == 2 }.map {
            "\($0[0]): \(!reveal && BreakpointDraft.sensitiveHeaders.contains($0[0].lowercased()) ? BreakpointCopy.hidden : $0[1])"
        }.joined(separator: "\n")
        return "\(value.method) \(value.url)\n\(value.status.map(String.init) ?? "")\n\(headers)\n\n\(value.bodyAvailable == true ? value.bodyText ?? "" : BreakpointCopy.archiveUnavailable)"
    }
}

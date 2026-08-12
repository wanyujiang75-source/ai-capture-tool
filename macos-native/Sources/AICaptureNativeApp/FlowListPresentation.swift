import Foundation

enum FlowListPresentation {
    static func filtered(_ flows: [FlowSummary], query: String) -> [FlowSummary] {
        let normalizedQuery = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !normalizedQuery.isEmpty else {
            return flows
        }
        return flows.filter { flow in
            [flow.url, flow.host, flow.path, flow.method, flow.status]
                .compactMap { $0?.lowercased() }
                .contains { $0.contains(normalizedQuery) }
        }
    }

    static func endpoint(for flow: FlowSummary) -> String {
        if let url = nonempty(flow.url) {
            return url
        }
        if let host = nonempty(flow.host), let path = nonempty(flow.path) {
            return host + (path.hasPrefix("/") ? path : "/\(path)")
        }
        return nonempty(flow.path) ?? nonempty(flow.host) ?? "-"
    }

    private static func nonempty(_ value: String?) -> String? {
        guard let value = value?.trimmingCharacters(in: .whitespacesAndNewlines), !value.isEmpty else {
            return nil
        }
        return value
    }
}

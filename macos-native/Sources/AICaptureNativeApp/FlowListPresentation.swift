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

    static func statusLabel(_ status: String?) -> String {
        status == "NO_RESPONSE" ? AppCopy.Flow.noResponse : nonempty(status) ?? "-"
    }

    static func requestBodyText(_ detail: FlowDetail) -> String {
        if let requestJSON = detail.requestJSON {
            return requestJSON.description
        }
        if let requestText = nonempty(detail.requestText) {
            return requestText
        }
        return AppCopy.Flow.noRequestBody
    }

    static func responseBodyText(_ detail: FlowDetail) -> String {
        if let responseJSON = detail.responseJSON {
            return responseJSON.description
        }
        if let responseText = nonempty(detail.responseText) {
            return responseText
        }
        if detail.status == "NO_RESPONSE" {
            return AppCopy.Flow.responsePending
        }
        return AppCopy.Flow.responseWithoutBody(statusCode: nonempty(detail.status) ?? "-")
    }

    private static func nonempty(_ value: String?) -> String? {
        guard let value = value?.trimmingCharacters(in: .whitespacesAndNewlines), !value.isEmpty else {
            return nil
        }
        return value
    }
}

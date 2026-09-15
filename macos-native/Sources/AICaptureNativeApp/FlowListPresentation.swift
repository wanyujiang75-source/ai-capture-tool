import Foundation

struct FlowBodyPresentation: Equatable {
    let text: String
    let isTruncated: Bool
    let sizeBytes: Int
    let fullFileURL: URL?
}

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
        requestBody(detail).text
    }

    static func requestBody(_ detail: FlowDetail) -> FlowBodyPresentation {
        bodyPresentation(text: requestText(detail), info: detail.requestBody)
    }

    static func responseBodyText(_ detail: FlowDetail) -> String {
        responseBody(detail).text
    }

    static func responseBody(_ detail: FlowDetail) -> FlowBodyPresentation {
        bodyPresentation(text: responseText(detail), info: detail.responseBody)
    }

    private static func requestText(_ detail: FlowDetail) -> String {
        if let requestJSON = detail.requestJSON {
            return requestJSON.description
        }
        if let requestText = nonempty(detail.requestText) {
            return requestText
        }
        return AppCopy.Flow.noRequestBody
    }

    private static func responseText(_ detail: FlowDetail) -> String {
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

    private static func bodyPresentation(text: String, info: FlowBodyInfo?) -> FlowBodyPresentation {
        FlowBodyPresentation(
            text: text,
            isTruncated: info?.truncated ?? false,
            sizeBytes: info?.sizeBytes ?? 0,
            fullFileURL: nonempty(info?.path).map { URL(fileURLWithPath: $0) }
        )
    }

    private static func nonempty(_ value: String?) -> String? {
        guard let value = value?.trimmingCharacters(in: .whitespacesAndNewlines), !value.isEmpty else {
            return nil
        }
        return value
    }
}

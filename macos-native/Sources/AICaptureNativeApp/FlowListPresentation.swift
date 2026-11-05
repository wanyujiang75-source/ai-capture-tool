import Foundation

struct FlowBodyPresentation: Equatable {
    let text: String
    let isTruncated: Bool
    let sizeBytes: Int
    let fullFileURL: URL?
    var notice: String? = nil
}

enum FlowListPresentation {
    static func filtered(_ flows: [FlowSummary], query: String, scope: FlowTrafficScope = .all) -> [FlowSummary] {
        let normalizedQuery = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return flows.filter { flow in
            guard scope == .all || FlowTrafficFilter.isInterface(flow) else { return false }
            return normalizedQuery.isEmpty || [flow.url, flow.host, flow.path, flow.method, flow.status]
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
        bodyPresentation(text: requestText(detail), info: detail.requestBody, legacyKind: detail.requestBodyKind)
    }

    static func responseBodyText(_ detail: FlowDetail) -> String {
        responseBody(detail).text
    }

    static func responseBody(_ detail: FlowDetail) -> FlowBodyPresentation {
        bodyPresentation(text: responseText(detail), info: detail.responseBody, legacyKind: detail.responseBodyKind)
    }

    private static func requestText(_ detail: FlowDetail) -> String {
        if let text = detail.requestText, !text.isEmpty { return text }
        if let requestJSON = detail.requestJSON {
            return requestJSON.jsonText
        }
        if (detail.requestBody?.kind ?? detail.requestBodyKind) == "binary" { return AppCopy.Flow.binaryBody }
        if (detail.requestBody?.sizeBytes ?? 0) > 0 { return AppCopy.Flow.unavailableBody }
        return AppCopy.Flow.noRequestBody
    }

    private static func responseText(_ detail: FlowDetail) -> String {
        if let text = detail.responseText, !text.isEmpty { return text }
        if let responseJSON = detail.responseJSON {
            return responseJSON.jsonText
        }
        if (detail.responseBody?.kind ?? detail.responseBodyKind) == "binary" { return AppCopy.Flow.binaryBody }
        if (detail.responseBody?.sizeBytes ?? 0) > 0 { return AppCopy.Flow.unavailableBody }
        if detail.status == "NO_RESPONSE" {
            return AppCopy.Flow.responsePending
        }
        return AppCopy.Flow.responseWithoutBody(statusCode: nonempty(detail.status) ?? "-")
    }

    private static func bodyPresentation(text: String, info: FlowBodyInfo?, legacyKind: String?) -> FlowBodyPresentation {
        let exceedsLimit = text.utf8.count > FlowJSONFormatter.inputLimit
        let preview = exceedsLimit ? String(decoding: text.utf8.prefix(FlowJSONFormatter.inputLimit), as: UTF8.self) : text
        let truncated = (info?.truncated ?? false) || exceedsLimit
        let formatted: String
        let isBinary = (info?.kind ?? legacyKind) == "binary"
        if truncated || isBinary {
            formatted = preview
        } else if info?.contentType?.lowercased().split(separator: ";").first?.trimmingCharacters(in: .whitespaces) == "application/x-www-form-urlencoded" {
            formatted = FlowDetailPresentation.formText(preview)
        } else {
            formatted = FlowJSONFormatter.formatted(preview) ?? preview
        }
        return FlowBodyPresentation(
            text: formatted,
            isTruncated: truncated,
            sizeBytes: info?.sizeBytes ?? text.utf8.count,
            fullFileURL: nonempty(info?.path).map { URL(fileURLWithPath: $0) },
            notice: isBinary ? AppCopy.Flow.binaryBody : (text == AppCopy.Flow.unavailableBody ? text : nil)
        )
    }

    private static func nonempty(_ value: String?) -> String? {
        guard let value = value?.trimmingCharacters(in: .whitespacesAndNewlines), !value.isEmpty else {
            return nil
        }
        return value
    }
}

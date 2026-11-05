import Foundation

enum FlowDetailPresentation {
    static let metadataLimit = 32 * 1024

    static func request(_ detail: FlowDetail) -> FlowBodyPresentation {
        let body = FlowListPresentation.requestBody(detail)
        var sections: [String] = []
        if let url = detail.url, let marker = url.firstIndex(of: "?"), !url[..<marker].contains("#") {
            // Bound before URL decoding/splitting; old archives can contain
            // arbitrarily long URLs and metadata, independent of body limits.
            let query = limited(url[url.index(after: marker)...], bytes: metadataLimit)
            let raw = String(query.text.prefix(while: { $0 != "#" }))
            if !raw.isEmpty {
                let rendered = limited(pairText(raw, form: false), bytes: metadataLimit)
                let truncated = (query.truncated && !query.text.contains("#")) || rendered.truncated
                let suffix = truncated ? "\n" + AppCopy.Flow.metadataPreview : ""
                sections.append(AppCopy.Flow.queryParameters + "\n" + rendered.text + suffix)
            }
        }
        sections.append(AppCopy.Flow.requestHeaders + "\n" + headers(detail, key: "request_headers"))
        sections.append(AppCopy.Flow.requestBody + "\n" + body.text)
        return document(sections, body: body)
    }

    static func response(_ detail: FlowDetail) -> FlowBodyPresentation {
        let body = FlowListPresentation.responseBody(detail)
        return document([
            AppCopy.Flow.responseStatus(FlowListPresentation.statusLabel(detail.status)),
            AppCopy.Flow.responseHeaders + "\n" + headers(detail, key: "response_headers"),
            AppCopy.Flow.responseBody + "\n" + body.text,
        ], body: body)
    }

    static func formText(_ text: String) -> String {
        guard text.utf8.count <= FlowJSONFormatter.inputLimit else { return text }
        let formatted = pairText(text, form: true)
        guard formatted.utf8.count <= FlowJSONFormatter.outputLimit,
              formatted.split(separator: "\n").count <= FlowJSONFormatter.lineLimit else { return text }
        return formatted
    }

    private static func document(_ sections: [String], body: FlowBodyPresentation) -> FlowBodyPresentation {
        FlowBodyPresentation(text: sections.joined(separator: "\n\n"), isTruncated: body.isTruncated,
                             sizeBytes: body.sizeBytes, fullFileURL: body.fullFileURL, notice: body.notice)
    }

    private static func headers(_ detail: FlowDetail, key: String) -> String {
        guard case let .object(meta) = detail.metaJSON,
              case let .object(summary) = meta["summary"],
              case let .array(pairs) = summary[key] else { return AppCopy.Flow.noHeaders }
        if pairs.isEmpty { return AppCopy.Flow.emptyHeaders }
        var lines: [String] = []
        var size = 0
        for pair in pairs {
            guard case let .array(values) = pair, values.count == 2,
                  case let .string(name) = values[0], case let .string(value) = values[1] else { continue }
            let budget = max(0, metadataLimit - size - 3)
            let head = limited(name, bytes: budget)
            let tail = limited(value, bytes: max(0, budget - head.text.utf8.count))
            let line = limited(escaped(head.text) + ": " + escaped(tail.text), bytes: max(0, metadataLimit - size))
            lines.append(line.text)
            size += line.text.utf8.count + 1
            if head.truncated || tail.truncated || line.truncated || size >= metadataLimit {
                lines.append(AppCopy.Flow.metadataPreview)
                break
            }
        }
        return lines.isEmpty ? AppCopy.Flow.noHeaders : lines.joined(separator: "\n")
    }

    private static func pairText(_ text: String, form: Bool) -> String {
        text.split(separator: "&").map { field in
            field.split(separator: "=", maxSplits: 1, omittingEmptySubsequences: false).map { part in
                let raw = form ? part.replacingOccurrences(of: "+", with: " ") : String(part)
                return escaped(raw.removingPercentEncoding ?? raw)
            }.joined(separator: ": ")
        }.joined(separator: "\n")
    }

    private static func escaped(_ text: String) -> String {
        text.replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\r", with: "\\r")
            .replacingOccurrences(of: "\n", with: "\\n")
            .replacingOccurrences(of: "\t", with: "\\t")
    }

    private static func limited(_ text: some StringProtocol, bytes limit: Int) -> (text: String, truncated: Bool) {
        var bytes = Array(text.utf8.prefix(limit + 1))
        let truncated = bytes.count > limit
        if truncated { bytes.removeLast() }
        // Drop an incomplete UTF-8 suffix rather than invent a replacement character.
        while let last = bytes.last, last >= 128, String(bytes: bytes, encoding: .utf8) == nil {
            bytes.removeLast()
        }
        return (String(decoding: bytes, as: UTF8.self), truncated)
    }
}

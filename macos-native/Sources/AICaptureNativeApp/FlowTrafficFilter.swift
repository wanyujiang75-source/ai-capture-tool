import Foundation

enum FlowTrafficScope: Equatable {
    case all
    case interfaces
}

enum FlowTrafficFilter {
    private static let telemetryHosts = [
        "google-analytics.com", "app-measurement.com", "crashlytics.com",
        "doubleclick.net", "googlesyndication.com", "googleadservices.com",
        "ingest.sentry.io", "ingest.us.sentry.io", "ingest.de.sentry.io",
        "api.mixpanel.com", "api-js.mixpanel.com", "api2.amplitude.com", "api.segment.io"
    ]
    private static let staticExtensions: Set<String> = [
        "png", "jpg", "jpeg", "gif", "webp", "avif", "svg", "ico", "bmp", "heic",
        "mp3", "m4a", "aac", "wav", "ogg", "mp4", "m4v", "mov", "webm", "m3u8", "ts",
        "css", "js", "mjs", "map", "woff", "woff2", "ttf", "otf", "eot", "html", "htm",
        "pdf", "zip", "gz", "apk", "ipa", "dmg"
    ]

    static func isInterface(_ flow: FlowSummary) -> Bool {
        let method = (flow.method ?? "").uppercased()
        if method == "CONNECT" || method == "OPTIONS" { return false }
        let url = flow.url.flatMap(URLComponents.init(string:))
        let host = (url?.host ?? flow.host ?? "").lowercased().trimmingCharacters(in: CharacterSet(charactersIn: "."))
        let path = (url?.path ?? flow.path ?? "").components(separatedBy: "?")[0].lowercased()
        if telemetryHosts.contains(where: { host == $0 || host.hasSuffix("." + $0) }) { return false }
        if host == "capture-check.invalid" { return false }
        if host == "captive.apple.com" && path == "/hotspot-detect.html" { return false }
        if ["connectivitycheck.gstatic.com", "connectivitycheck.android.com", "clients3.google.com"].contains(host)
            && ["/generate_204", "/gen_204"].contains(path) { return false }

        let requestType = mime(flow.requestContentType)
        let responseType = mime(flow.responseContentType)
        if flow.hasRequestJSON == true || flow.hasResponseJSON == true
            || isDataType(requestType) || isDataType(responseType) { return true }
        // Prefer keeping uncertain business calls, including uploads and HTML error responses.
        if method != "GET" && method != "HEAD" { return true }
        if let status = Int(flow.status ?? ""), status >= 400 { return true }
        let segments = path.split(separator: "/")
        if segments.contains(where: {
            ["api", "apis", "rest", "rpc", "graphql", "portal"].contains(String($0))
                || ($0.first == "v" && $0.count > 1 && $0.dropFirst().allSatisfy(\.isNumber))
        }) { return true }

        if ["image/", "audio/", "video/", "font/"].contains(where: { responseType.hasPrefix($0) }) { return false }
        if ["text/html", "application/xhtml+xml", "text/css", "text/javascript", "application/javascript",
            "application/x-javascript", "application/pdf", "application/zip", "application/gzip",
            "application/vnd.apple.mpegurl", "application/x-mpegurl", "application/vnd.ms-fontobject"].contains(responseType) { return false }
        return !staticExtensions.contains((path as NSString).pathExtension)
    }

    private static func mime(_ value: String?) -> String {
        (value ?? "").components(separatedBy: ";")[0].trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }

    private static func isDataType(_ type: String) -> Bool {
        if type == "application/xhtml+xml" { return false }
        return ["application/json", "application/x-ndjson", "application/xml", "text/xml", "application/graphql",
                "application/x-www-form-urlencoded", "multipart/form-data", "text/event-stream"].contains(type)
            || (type.hasPrefix("application/") && (type.hasSuffix("+json") || type.hasSuffix("+xml")))
            || type.hasPrefix("application/grpc")
    }
}

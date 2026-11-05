import Foundation

extension CaptureSource {
    var isRunning: Bool { status == "running" }
    var platformLabel: String { isIOS ? "iPhone" : "Android" }
    var applicationName: String? {
        let name = (appName ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        return name.isEmpty || ["iphone", "android"].contains(name.lowercased())
            ? nil : name
    }
    var displayName: String { applicationName ?? AppCopy.FlowSource.unnamed(platform: platformLabel) }
    var title: String { "\(displayName) · #\(id)" }
    var statusLabel: String {
        switch status {
        case "running": AppCopy.FlowSource.running
        case "stopped": AppCopy.FlowSource.stopped
        case "failed": AppCopy.FlowSource.failed
        default: AppCopy.FlowSource.unknown
        }
    }
    var startedDate: Date? {
        guard let startedAt else { return nil }
        let parser = ISO8601DateFormatter()
        if let date = parser.date(from: startedAt) { return date }
        parser.formatOptions.insert(.withFractionalSeconds)
        return parser.date(from: startedAt)
    }
    var startedLabel: String {
        guard let date = startedDate else { return AppCopy.FlowSource.unknownTime }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return formatter.string(from: date)
    }
}

struct CaptureSourceGroups {
    let current: [CaptureSource]
    let history: [CaptureSource]

    init(sources: [CaptureSource], activeAndroidID: Int?) {
        var all = sources
        // The Android status endpoint can update before the source list does.
        if let id = activeAndroidID, !all.contains(where: { $0.id == id }) {
            all.append(CaptureSource(id: id, platform: "android", status: "running", appName: nil, mode: nil))
        }
        current = all.filter(\.isRunning).sorted { $0.id > $1.id }
        history = all.filter { !$0.isRunning }.sorted { $0.id > $1.id }
    }

    func matchingHistory(_ query: String) -> [CaptureSource] {
        let words = query.split(whereSeparator: \.isWhitespace)
        return history.filter { source in
            let value = "\(source.title) \(source.platformLabel) \(source.startedLabel) \(source.statusLabel)"
            return words.allSatisfy { value.localizedStandardContains($0) }
        }
    }
}

@MainActor
extension AppState {
    var isViewingLiveCapture: Bool {
        selectedFlowSource?.isRunning ?? (flowSessionID != nil && flowSessionID == activeSessionID)
    }

    var emptyFlowsMessage: String {
        if hasClearedFlows { return isViewingLiveCapture ? AppCopy.Flow.cleared : AppCopy.Flow.historyCleared }
        guard isViewingLiveCapture else { return AppCopy.Flow.historyEmpty }
        return selectedFlowSource?.isIOS == true ? AppCopy.IOSCapture.waiting : AppCopy.Flow.waiting
    }
}

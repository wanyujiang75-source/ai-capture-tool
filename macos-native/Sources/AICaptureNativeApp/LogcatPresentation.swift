import Foundation

struct LogcatMessagePresentation: Equatable, Sendable {
    let fullText: String
    let previewText: String
    let isCollapsible: Bool
}

enum LogcatPresentation {
    private static let previewCharacterLimit = 360
    private static let previewLineLimit = 3

    private struct MultilineGroup {
        var entry: LogcatEntry
        var lastCursor: Int64
    }

    static func coalesced(_ entries: [LogcatEntry]) -> [LogcatEntry] {
        let logicalEntries = combineMultilineEntries(entries.sorted { $0.cursor < $1.cursor })
        guard !logicalEntries.isEmpty else {
            return []
        }

        var groups: [(entry: LogcatEntry, count: Int)] = []
        for entry in logicalEntries {
            if let last = groups.last,
               isStructured(entry),
               isDuplicate(last.entry, entry) {
                groups[groups.count - 1].count += 1
            } else {
                groups.append((entry, 1))
            }
        }

        return groups.map { group in
            guard group.count > 1 else {
                return group.entry
            }
            return replacingMessage(
                in: group.entry,
                with: "\(group.entry.message)\n\n[\(AppCopy.Log.repeated(group.count))]"
            )
        }
    }

    static func message(for entry: LogcatEntry) -> LogcatMessagePresentation {
        let fullText = entry.message.isEmpty ? entry.raw : entry.message
        let lines = fullText.split(separator: "\n", omittingEmptySubsequences: false)
        let hasAdditionalLines = lines.count > previewLineLimit
        let linePreview = lines.prefix(previewLineLimit).joined(separator: "\n")
        let hasAdditionalCharacters = linePreview.count > previewCharacterLimit
        let isCollapsible = hasAdditionalLines || fullText.count > previewCharacterLimit

        guard isCollapsible else {
            return LogcatMessagePresentation(
                fullText: fullText,
                previewText: fullText,
                isCollapsible: false
            )
        }

        var previewText = String(linePreview.prefix(previewCharacterLimit))
        if hasAdditionalCharacters {
            previewText += "…"
        } else if hasAdditionalLines {
            previewText += "\n…"
        }
        return LogcatMessagePresentation(
            fullText: fullText,
            previewText: previewText,
            isCollapsible: true
        )
    }

    private static func combineMultilineEntries(_ entries: [LogcatEntry]) -> [LogcatEntry] {
        var groups: [MultilineGroup] = []
        for entry in entries {
            guard let previous = groups.last,
                  shouldCombine(previous, entry) else {
                groups.append(MultilineGroup(entry: entry, lastCursor: entry.cursor))
                continue
            }

            groups[groups.count - 1] = MultilineGroup(
                entry: LogcatEntry(
                    cursor: previous.entry.cursor,
                    timestamp: previous.entry.timestamp,
                    pid: previous.entry.pid,
                    tid: previous.entry.tid,
                    level: previous.entry.level,
                    tag: previous.entry.tag,
                    message: [previous.entry.message, entry.message].joined(separator: "\n"),
                    raw: combinedRaw(previous.entry.raw, entry.raw)
                ),
                lastCursor: entry.cursor
            )
        }
        return groups.map(\.entry)
    }

    private static func shouldCombine(_ previous: MultilineGroup, _ current: LogcatEntry) -> Bool {
        isStructured(previous.entry)
            && isStructured(current)
            && current.cursor == previous.lastCursor + 1
            && current.timestamp == previous.entry.timestamp
            && current.pid == previous.entry.pid
            && current.tid == previous.entry.tid
            && current.level == previous.entry.level
            && current.tag == previous.entry.tag
    }

    private static func isDuplicate(_ lhs: LogcatEntry, _ rhs: LogcatEntry) -> Bool {
        lhs.pid == rhs.pid
            && lhs.tid == rhs.tid
            && lhs.level == rhs.level
            && lhs.tag == rhs.tag
            && lhs.message == rhs.message
    }

    private static func isStructured(_ entry: LogcatEntry) -> Bool {
        !entry.timestamp.isEmpty
    }

    private static func combinedRaw(_ lhs: String, _ rhs: String) -> String {
        [lhs, rhs].filter { !$0.isEmpty }.joined(separator: "\n")
    }

    private static func replacingMessage(in entry: LogcatEntry, with message: String) -> LogcatEntry {
        LogcatEntry(
            cursor: entry.cursor,
            timestamp: entry.timestamp,
            pid: entry.pid,
            tid: entry.tid,
            level: entry.level,
            tag: entry.tag,
            message: message,
            raw: entry.raw
        )
    }
}

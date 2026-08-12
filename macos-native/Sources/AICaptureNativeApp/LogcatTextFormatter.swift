import Foundation

enum LogcatTextFormatter {
    static func plainText(_ entries: [LogcatEntry]) -> String {
        entries.map { entry in
            [
                valueOrDash(entry.timestamp),
                valueOrDash(entry.level),
                valueOrDash(entry.tag),
                message(for: entry)
            ].joined(separator: "\t")
        }.joined(separator: "\n")
    }

    private static func valueOrDash(_ value: String) -> String {
        value.isEmpty ? "-" : value
    }

    private static func message(for entry: LogcatEntry) -> String {
        valueOrDash(entry.message.isEmpty ? entry.raw : entry.message)
    }
}

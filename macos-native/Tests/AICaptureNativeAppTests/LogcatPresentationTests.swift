import Testing
@testable import AICaptureNativeApp

@Suite
struct LogcatPresentationTests {
    @Test
    func combinesMultilineEventsAndCollapsesConsecutiveDuplicates() {
        let entries = [
            entry(cursor: 1, timestamp: "09-14 17:09:01.100", message: "Network error"),
            entry(
                cursor: 2,
                timestamp: "09-14 17:09:01.100",
                message: "javax.net.ssl.SSLHandshakeException"
            ),
            entry(cursor: 3, timestamp: "09-14 17:09:01.100", message: "\tat SSLUtils.java:1"),
            entry(cursor: 4, timestamp: "09-14 17:09:02.200", message: "Network error"),
            entry(
                cursor: 5,
                timestamp: "09-14 17:09:02.200",
                message: "javax.net.ssl.SSLHandshakeException"
            ),
            entry(cursor: 6, timestamp: "09-14 17:09:02.200", message: "\tat SSLUtils.java:1")
        ]

        #expect(
            LogcatPresentation.coalesced(entries) == [
                entry(
                    cursor: 1,
                    timestamp: "09-14 17:09:01.100",
                    message: """
                    Network error
                    javax.net.ssl.SSLHandshakeException
                    \tat SSLUtils.java:1

                    [连续出现 2 次]
                    """
                )
            ]
        )
    }

    @Test
    func keepsDifferentEventsAndUnstructuredLinesSeparate() {
        let entries = [
            entry(cursor: 1, timestamp: "09-14 17:09:01.100", tag: "Network", message: "line"),
            entry(cursor: 2, timestamp: "09-14 17:09:01.100", tag: "Database", message: "line"),
            rawEntry(cursor: 3, text: "--------- beginning of main"),
            rawEntry(cursor: 4, text: "--------- beginning of system")
        ]

        #expect(LogcatPresentation.coalesced(entries) == entries)
    }

    @Test
    func longSingleLineUsesCompactPreviewWithoutChangingFullText() {
        let message = String(repeating: "A", count: 400)

        let presentation = LogcatPresentation.message(
            for: entry(cursor: 1, timestamp: "09-14 17:09:01.100", message: message)
        )

        #expect(presentation.fullText == message)
        #expect(presentation.previewText == String(repeating: "A", count: 360) + "…")
        #expect(presentation.isCollapsible)
    }

    @Test
    func multilineStackPreviewKeepsOnlyThreeLinesUntilExpanded() {
        let message = "first\nsecond\nthird\nfourth"

        let presentation = LogcatPresentation.message(
            for: entry(cursor: 1, timestamp: "09-14 17:09:01.100", message: message)
        )

        #expect(presentation.fullText == message)
        #expect(presentation.previewText == "first\nsecond\nthird\n…")
        #expect(presentation.isCollapsible)
    }

    @Test
    func shortMessageDoesNotOfferExpansion() {
        let message = "ordinary line"

        let presentation = LogcatPresentation.message(
            for: entry(cursor: 1, timestamp: "09-14 17:09:01.100", message: message)
        )

        #expect(
            presentation == LogcatMessagePresentation(
                fullText: message,
                previewText: message,
                isCollapsible: false
            )
        )
    }

    private func entry(
        cursor: Int64,
        timestamp: String,
        tag: String = "AU",
        message: String
    ) -> LogcatEntry {
        LogcatEntry(
            cursor: cursor,
            timestamp: timestamp,
            pid: 1234,
            tid: 1235,
            level: "E",
            tag: tag,
            message: message,
            raw: ""
        )
    }

    private func rawEntry(cursor: Int64, text: String) -> LogcatEntry {
        LogcatEntry(
            cursor: cursor,
            timestamp: "",
            pid: nil,
            tid: nil,
            level: "",
            tag: "",
            message: text,
            raw: text
        )
    }
}

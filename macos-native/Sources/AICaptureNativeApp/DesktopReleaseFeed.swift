import Foundation

final class DesktopReleaseFeed: NSObject, XMLParserDelegate {
    struct Entry {
        let asset: DesktopReleaseAsset
        let title: String
        let notes: String
        let publishedAt: Date
    }

    private struct Fields {
        var link: String?
        var title = ""
        var notes = ""
        var updated = ""
    }

    private var fields: Fields?
    private var text = ""
    private var entries: [Entry] = []
    private let dateFormatter = ISO8601DateFormatter()

    static func parse(_ data: Data) throws -> [Entry] {
        guard data.count <= 1_000_000 else { throw URLError(.dataLengthExceedsMaximum) }
        let parser = XMLParser(data: data)
        parser.shouldResolveExternalEntities = false
        let feed = DesktopReleaseFeed()
        parser.delegate = feed
        guard parser.parse() else { throw URLError(.cannotParseResponse) }
        return feed.entries
    }

    func parser(
        _ parser: XMLParser, didStartElement elementName: String, namespaceURI: String?,
        qualifiedName: String?, attributes: [String: String]
    ) {
        if elementName == "entry" { fields = Fields() }
        if elementName == "link", attributes["rel"] == "alternate" {
            fields?.link = attributes["href"]
        }
        text = ""
    }

    func parser(_ parser: XMLParser, foundCharacters string: String) {
        text += string
    }

    func parser(
        _ parser: XMLParser, didEndElement elementName: String,
        namespaceURI: String?, qualifiedName: String?
    ) {
        switch elementName {
        case "title": fields?.title = text
        case "updated": fields?.updated = text
        case "content": fields?.notes = text
        case "entry":
            if let fields,
               let link = fields.link.flatMap(URL.init(string:)),
               let date = dateFormatter.date(from: fields.updated) {
                let tag = link.lastPathComponent
                if let asset = DesktopReleaseAsset(tag: tag, isPreview: tag.hasPrefix("desktop-preview-")),
                   asset.releasePage.absoluteString == link.absoluteString {
                    let title = fields.title.trimmingCharacters(in: .whitespacesAndNewlines)
                    entries.append(Entry(
                        asset: asset, title: title.isEmpty ? tag : title,
                        notes: Self.plainText(fields.notes), publishedAt: date
                    ))
                }
            }
            fields = nil
        default: break
        }
    }

    private static func plainText(_ html: String) -> String {
        // The Atom feed escapes its HTML. Display the text without loading links or embedded media.
        let text = html
            .replacingOccurrences(of: #"(?i)<li(?:\s[^>]*)?>"#, with: "• ", options: .regularExpression)
            .replacingOccurrences(of: #"(?i)</(?:li|p|h[1-6])>\s*|<br\s*/?>"#, with: "\n", options: .regularExpression)
            .replacingOccurrences(of: #"<[^>]*>"#, with: "", options: .regularExpression)
            .replacingOccurrences(of: "&quot;", with: "\"")
            .replacingOccurrences(of: "&#39;", with: "'")
            .replacingOccurrences(of: "&lt;", with: "<")
            .replacingOccurrences(of: "&gt;", with: ">")
            .replacingOccurrences(of: "&amp;", with: "&")
        return String(text.prefix(12_000)).trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

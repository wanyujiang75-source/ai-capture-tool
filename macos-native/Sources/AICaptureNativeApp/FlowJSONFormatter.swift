import Foundation

enum FlowJSONFormatter {
    static let inputLimit = 256 * 1024
    static let outputLimit = 512 * 1024
    static let lineLimit = 8_000
    static let depthLimit = 64

    // Only change whitespace outside strings; re-encoding captured JSON loses
    // duplicate keys, number spelling and potentially precision.
    static func formatted(_ text: String) -> String? {
        guard text.utf8.count <= inputLimit else { return nil }
        let bytes = Array(text.utf8)
        var compact: [UInt8] = []
        var inString = false
        var escaped = false
        var depth = 0
        for byte in bytes {
            if inString {
                compact.append(byte)
                if escaped { escaped = false }
                else if byte == 92 { escaped = true }
                else if byte == 34 { inString = false }
            } else if byte == 34 {
                inString = true
                compact.append(byte)
            } else if ![9, 10, 13, 32].contains(byte) {
                if byte == 123 || byte == 91 { depth += 1 }
                if byte == 125 || byte == 93 {
                    // Foundation accepts trailing commas, but capture previews
                    // must not present incomplete JSON as a complete document.
                    guard compact.last != 44 else { return nil }
                    depth -= 1
                }
                guard (0...depthLimit).contains(depth) else { return nil }
                compact.append(byte)
            }
        }
        guard !inString, depth == 0,
              (try? JSONSerialization.jsonObject(with: Data(bytes), options: [.fragmentsAllowed])) != nil else {
            return nil
        }

        var result: [UInt8] = []
        var lines = 1
        for (index, byte) in compact.enumerated() {
            if inString {
                result.append(byte)
                if escaped { escaped = false }
                else if byte == 92 { escaped = true }
                else if byte == 34 { inString = false }
            } else {
                switch byte {
                case 34:
                    inString = true
                    result.append(byte)
                case 123, 91:
                    result.append(byte)
                    depth += 1
                    if compact[index + 1] != (byte == 123 ? 125 : 93) {
                        result += [10] + Array(repeating: 32, count: depth * 2)
                        lines += 1
                    }
                case 125, 93:
                    depth -= 1
                    if compact[index - 1] != (byte == 125 ? 123 : 91) {
                        result += [10] + Array(repeating: 32, count: depth * 2)
                        lines += 1
                    }
                    result.append(byte)
                case 44:
                    result += [44, 10] + Array(repeating: 32, count: depth * 2)
                    lines += 1
                case 58:
                    result += [58, 32]
                default:
                    result.append(byte)
                }
            }
            guard result.count <= outputLimit, lines <= lineLimit else { return nil }
        }
        return String(decoding: result, as: UTF8.self)
    }
}

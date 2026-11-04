import Darwin
import Foundation

struct BreakpointRuleLibrary {
    let directory: URL
    private var file: URL { directory.appendingPathComponent("breakpoint-rules.json") }

    func load() throws -> [BreakpointRuleSpec] {
        let fd = open(file.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)
        if fd < 0, errno == ENOENT { return [] }
        guard fd >= 0 else { throw BreakpointFailure("template_storage") }
        defer { close(fd) }
        var info = stat()
        guard fstat(fd, &info) == 0, info.st_mode & S_IFMT == S_IFREG, info.st_uid == getuid(),
              info.st_mode & 0o077 == 0, info.st_size <= 524288 else { throw BreakpointFailure("template_storage") }
        let data = try FileHandle(fileDescriptor: fd, closeOnDealloc: false).read(upToCount: 524289) ?? Data()
        let rules = try BreakpointWire.decode([BreakpointRuleSpec].self, from: data)
        guard rules.count <= 100, rules.allSatisfy(isSafe) else { throw BreakpointFailure("template_storage") }
        return rules
    }

    func save(_ rule: BreakpointRuleSpec) throws {
        guard isSafe(rule) else { throw BreakpointFailure("invalid_rule") }
        var rules = try load()
        rules.removeAll { $0 == rule }
        rules.insert(rule, at: 0)
        rules = Array(rules.prefix(100))
        var data = try BreakpointWire.encode(rules)
        while data.count > 524288 { rules.removeLast(); data = try BreakpointWire.encode(rules) }
        let temporary = directory.appendingPathComponent(".bp-rules-\(UUID().uuidString)")
        let fd = open(temporary.path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0o600)
        guard fd >= 0 else { throw BreakpointFailure("template_storage") }
        defer { close(fd); try? FileManager.default.removeItem(at: temporary) }
        try FileHandle(fileDescriptor: fd, closeOnDealloc: false).write(contentsOf: data)
        guard rename(temporary.path, file.path) == 0 else { throw BreakpointFailure("template_storage") }
    }

    private func isSafe(_ rule: BreakpointRuleSpec) -> Bool {
        guard rule.path.hasPrefix("/"), !rule.path.contains("?"), !rule.path.contains("#"),
              !rule.path.contains("\r"), !rule.path.contains("\n"), rule.path.utf8.count <= 8192,
              (1...65535).contains(rule.port), ["http", "https"].contains(rule.scheme),
              ["exact", "prefix"].contains(rule.pathMatch), ["request", "response", "both"].contains(rule.stage),
              [15, 30, 60].contains(rule.timeoutSeconds),
              let parsed = try? BreakpointRuleSpec.seed(url: rule.endpoint, method: rule.method) else { return false }
        return parsed.host == rule.host && parsed.path == rule.path && parsed.port == rule.port
    }
}

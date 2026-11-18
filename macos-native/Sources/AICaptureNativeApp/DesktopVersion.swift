import Foundation

struct DesktopVersion: Comparable, CustomStringConvertible {
    private let components: [Int]

    init?(_ value: String) {
        let parts = value.split(separator: ".", omittingEmptySubsequences: false)
        let numbers = parts.compactMap { part -> Int? in
            guard let number = Int(part), number >= 0, String(number) == part else { return nil }
            return number
        }
        guard parts.count == 3, numbers.count == 3 else { return nil }
        components = numbers
    }

    var description: String { components.map(String.init).joined(separator: ".") }

    static func < (lhs: Self, rhs: Self) -> Bool {
        lhs.components.lexicographicallyPrecedes(rhs.components)
    }
}

struct InstalledDesktopVersion {
    enum Availability: Equatable { case current, newer, unknown }

    let version: DesktopVersion?
    private let buildID: String?

    init(version: String?, buildID: String?) {
        self.version = version.flatMap(DesktopVersion.init)
        self.buildID = buildID?.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    static func read(from bundle: Bundle = .main) -> Self {
        let buildID = bundle.url(forResource: "backend-build-id", withExtension: "txt")
            .flatMap { try? String(contentsOf: $0, encoding: .utf8) }
        return Self(version: bundle.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String,
                    buildID: buildID)
    }

    func availability(for release: DesktopRelease) -> Availability {
        let tag = release.downloadURL.deletingLastPathComponent().lastPathComponent
        let prefix = "抓包工具桌面预览版 v"
        let publishedVersion: DesktopVersion?
        if release.isPreview {
            publishedVersion = release.title.hasPrefix(prefix)
                ? DesktopVersion(String(release.title.dropFirst(prefix.count))) : nil
        } else {
            publishedVersion = DesktopVersion(String(tag.dropFirst()))
        }

        if let version, let publishedVersion {
            return publishedVersion > version ? .newer : .current
        }
        if release.isPreview, publishedVersion == nil {
            let publishedBuild = tag.split(separator: "-").last
            if let buildID, let publishedBuild, buildID.hasPrefix(publishedBuild) {
                return .current
            }
            // Preview releases before the 1.0.0 transition did not include a version.
            if let version, let firstVersionedPreview = DesktopVersion("1.0.0"), version >= firstVersionedPreview {
                return .current
            }
        }
        return .unknown
    }
}

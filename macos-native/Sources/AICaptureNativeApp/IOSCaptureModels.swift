import Foundation

enum CapturePlatform: String, CaseIterable, Identifiable {
    case android = "Android"
    case iphone = "iPhone"
    var id: String { rawValue }
}

enum IOSConnectionState: String, Decodable, Sendable {
    case idle, preparing, ready
    case waitingPhone = "waiting_phone", waitingTrust = "waiting_trust", needsCleanup = "needs_cleanup"
}

enum IOSRecordingState: String, Decodable, Sendable {
    case idle, recording, stopped, failed
    case limitReached = "limit_reached"
}

struct IOSCaptureProject: Codable, Identifiable, Equatable, Sendable {
    let id: String
    let name: String
    let domains: [String]
}

struct IOSProjectDraft: Encodable, Sendable {
    let id: String?
    let name: String
    let domains: [String]
}

protocol IOSCaptureAPI: IOSSetupAPI {
    func getIOSProjects() async throws -> [IOSCaptureProject]
    func saveIOSProject(_ draft: IOSProjectDraft) async throws -> IOSCaptureProject
    func startIOSRecording(projectID: String?) async throws -> IOSSetupStatus
    func stopIOSRecording() async throws -> IOSSetupStatus
}

enum IOSCaptureOperation {
    case prepare, start, stop, end, save
    var title: String {
        switch self {
        case .prepare: AppCopy.IOSSetup.preparing
        case .start: AppCopy.IOSCapture.starting
        case .stop: AppCopy.IOSCapture.stopping
        case .end: AppCopy.IOSSetup.stopping
        case .save: AppCopy.IOSCapture.saving
        }
    }
}

struct CaptureSource: Decodable, Identifiable, Equatable {
    let id: Int
    let platform: String?
    let status: String?
    let appName: String?
    let mode: String?
    var startedAt: String? = nil
    enum CodingKeys: String, CodingKey {
        case id, platform, status, mode
        case appName = "app_name"
        case startedAt = "started_at"
    }
    var isIOS: Bool { platform == "ios" || mode == "ios-http-proxy" }
    var isAndroidPhysical: Bool { mode == "android-physical-wireguard" }
    var usesRevisionArchive: Bool { isIOS || isAndroidPhysical }
}

struct FlowPage: Decodable {
    let flows: [FlowSummary]
    let total: Int
    let cursor: Int
    let nextCursor: Int?
    enum CodingKeys: String, CodingKey { case flows, total, cursor; case nextCursor = "next_cursor" }
}

enum IOSQuitSafety {
    static func requiresWarning(runtimeDirectory: URL) -> Bool {
        FileManager.default.fileExists(atPath: runtimeDirectory.appendingPathComponent("ios-setup/cleanup-required").path)
    }
}

@MainActor
enum IOSFlowBoundary {
    // iPhone request times originate on this Mac, not on the phone's clock.
    private static let wholeSeconds = ISO8601DateFormatter()

    static func predates(_ flow: FlowSummary, boundary: Date) -> Bool {
        guard let time = flow.time else { return false }
        if let dot = time.firstIndex(of: ".") {
            let remainder = time[time.index(after: dot)...]
            let digits = remainder.prefix { $0.isASCII && $0.isNumber }
            guard !digits.isEmpty, digits.count <= 9,
                  let fraction = Double("0." + digits),
                  let date = wholeSeconds.date(from: String(time[..<dot]) + remainder.dropFirst(digits.count)) else { return false }
            // Foundation's fractional parser truncates microseconds to milliseconds.
            return date.addingTimeInterval(fraction) <= boundary
        }
        guard let date = wholeSeconds.date(from: time) else { return false }
        return date <= boundary
    }
}

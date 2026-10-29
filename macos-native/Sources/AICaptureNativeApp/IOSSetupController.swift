import Foundation

enum IOSSetupPhase: String, Decodable, Sendable {
    case idle, preparing, ready, capturing, stopped, failed
    case waitingPhone = "waiting_phone"
    case waitingTrust = "waiting_trust"
}

struct IOSSetupFlow: Decodable, Identifiable, Sendable {
    let id: String
    let method: String
    let url: String
    let status: Int
    let requestBody: String
    let responseBody: String
    let truncated: Bool
    enum CodingKeys: String, CodingKey {
        case id, method, url, status, truncated
        case requestBody = "request_body", responseBody = "response_body"
    }
}

struct IOSSetupStatus: Decodable, Sendable {
    let phase: IOSSetupPhase
    var flowCount = 0
    var flows: [IOSSetupFlow] = []
    var profilePath: String?
    var checkURL: String?
    var ssid: String?
    var certificateName: String?

    enum CodingKeys: String, CodingKey {
        case phase, flows, ssid
        case flowCount = "flow_count", profilePath = "profile_path", checkURL = "check_url"
        case certificateName = "certificate_name"
    }
    var hasCapturedTraffic: Bool { phase == .capturing && flowCount > 0 }
    var requiresPhoneSetup: Bool { phase == .waitingPhone || phase == .waitingTrust }
    var canPrepare: Bool { phase == .idle || phase == .stopped }
    var configuredSSID: String? { canPrepare ? nil : ssid }
}

protocol IOSSetupAPI: Sendable {
    func readIOSSetup() async throws -> IOSSetupStatus
    func prepareIOSSetup(ssid: String) async throws -> IOSSetupStatus
    func stopIOSSetup() async throws -> IOSSetupStatus
}

@MainActor
final class IOSSetupController: ObservableObject {
    @Published private(set) var status = IOSSetupStatus(phase: .idle)
    @Published private(set) var busy = false
    @Published private(set) var stopping = false
    @Published private(set) var issue: String?
    private let api: any IOSSetupAPI
    private var generation = UUID()

    init(api: any IOSSetupAPI = APIClient()) { self.api = api }

    var profileURL: URL? {
        guard status.phase != .stopped, status.phase != .failed, let path = status.profilePath,
              path.hasPrefix("/"), !path.contains("..") else { return nil }
        let url = URL(fileURLWithPath: path)
        guard url.lastPathComponent == "iPhone.mobileconfig",
              url.pathComponents.contains("ios-setup") else { return nil }
        return url
    }

    func refresh() async {
        guard !busy else { return }
        let current = generation
        do {
            let result = try await api.readIOSSetup()
            guard !Task.isCancelled, current == generation, !busy else { return }
            status = result
            issue = nil
        } catch {
            guard !Task.isCancelled, current == generation else { return }
            issue = AppCopy.IOSSetup.failed
        }
    }

    func prepare(ssid: String) async {
        guard !busy, status.canPrepare else { return }
        guard !ssid.isEmpty, ssid.utf8.count <= 32,
              !ssid.unicodeScalars.contains(where: { $0.value < 32 }) else {
            issue = AppCopy.IOSSetup.invalidSSID
            return
        }
        await update { try await self.api.prepareIOSSetup(ssid: ssid) }
    }

    func stop(phoneConfigurationRemoved: Bool) async {
        guard phoneConfigurationRemoved, !busy else { return }
        stopping = true
        defer { stopping = false }
        await update { try await self.api.stopIOSSetup() }
    }

    private func update(_ operation: () async throws -> IOSSetupStatus) async {
        generation = UUID()
        busy = true
        issue = nil
        defer { busy = false }
        do { status = try await operation() }
        catch { issue = AppCopy.IOSSetup.failed }
    }
}

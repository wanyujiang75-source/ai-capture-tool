import Foundation

enum AndroidCaptureTarget: String, CaseIterable, Identifiable {
    case emulator = "模拟器", physical = "真机（实验）"
    var id: String { rawValue }
}

enum AndroidPhysicalPhase: String, Decodable, Sendable {
    case idle, preparing, capturing, stopping, stopped, failed, unknown
    case waitingInstall = "waiting_install", waitingVPN = "waiting_vpn", recoveryRequired = "recovery_required"
    init(from decoder: any Decoder) throws {
        self = Self(rawValue: try decoder.singleValueContainer().decode(String.self)) ?? .unknown
    }
}

enum AndroidPhysicalAction { case start, stop, recover, none }

enum AndroidPhysicalQuitSafety {
    static func requiresWarning(runtimeDirectory: URL) -> Bool {
        FileManager.default.fileExists(atPath: runtimeDirectory.appendingPathComponent("android-physical/recovery.json").path)
    }
}

struct AndroidPhysicalStatus: Decodable, Sendable {
    var phase: AndroidPhysicalPhase
    var serial: String?
    var package: String?
    var message: String?
    var sessionID: Int?
    var flowCount: Int?
    var responseCount: Int?
    var tlsFailures: Int?
    var originalVPN: String?
    var upstream: String?
    enum CodingKeys: String, CodingKey {
        case phase, serial, package, message, upstream
        case sessionID = "session_id", flowCount = "flow_count", responseCount = "response_count"
        case tlsFailures = "tls_failures", originalVPN = "original_vpn"
    }
    var canStart: Bool { [.idle, .stopped, .failed].contains(phase) }
    var action: AndroidPhysicalAction {
        switch phase {
        case .idle, .stopped, .failed: .start
        case .preparing, .waitingInstall, .waitingVPN, .capturing: .stop
        case .recoveryRequired: .recover
        case .stopping, .unknown: .none
        }
    }
    var title: String { AppCopy.AndroidPhysical.title(phase) }
}

struct AndroidPhysicalDevice: Decodable, Identifiable, Sendable {
    let serial: String
    let model: String
    let status: String
    var id: String { serial }
    var label: String { model.isEmpty ? AppCopy.AndroidPhysical.device : model }
}

protocol AndroidPhysicalAPI: Sendable {
    func readAndroidPhysical() async throws -> AndroidPhysicalStatus
    func discoverAndroidPhysical() async throws -> [AndroidPhysicalDevice]
    func startAndroidPhysical(serial: String, consent: Bool) async throws -> AndroidPhysicalStatus
    func actAndroidPhysical(_ action: String) async throws -> AndroidPhysicalStatus
}

@MainActor
final class AndroidPhysicalController: ObservableObject {
    @Published private(set) var status = AndroidPhysicalStatus(phase: .idle)
    @Published private(set) var devices: [AndroidPhysicalDevice] = []
    @Published private(set) var busy = false
    @Published private(set) var issue: String?
    @Published var serial = ""
    @Published var consent = false
    private let api: any AndroidPhysicalAPI
    private var revision = 0
    init(api: any AndroidPhysicalAPI = APIClient()) { self.api = api }
    func refresh() async {
        guard !busy else { return }
        let version = revision
        do {
            let value = try await api.readAndroidPhysical()
            guard !Task.isCancelled, revision == version else { return }
            status = value
        } catch {
            guard !Task.isCancelled, revision == version else { return }
            issue = AppCopy.AndroidPhysical.connectionFailed
        }
    }
    func discover() async {
        do {
            devices = try await api.discoverAndroidPhysical()
            if !devices.contains(where: { $0.serial == serial }) { serial = devices.first?.serial ?? "" }
        } catch { issue = AppCopy.AndroidPhysical.discoveryFailed }
    }
    func perform() async {
        guard !busy else { return }
        let action = status.action
        guard action != .none else { return }
        if action == .start && (!consent || serial.isEmpty) { return }
        busy = true
        revision += 1
        issue = nil
        defer { busy = false }
        do {
            if action == .start { status = try await api.startAndroidPhysical(serial: serial, consent: consent) }
            else { status = try await api.actAndroidPhysical(action == .stop ? "stop" : "recover") }
        } catch {
            issue = (error as? APIClientError)?.userFacingIssue.message ?? AppCopy.AndroidPhysical.connectionFailed
        }
    }
}

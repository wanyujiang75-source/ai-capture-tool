import Foundation

enum AndroidCaptureTarget: String, CaseIterable, Identifiable {
    case emulator = "模拟器", physical = "真机（实验）"
    var id: String { rawValue }
}

enum AndroidPhysicalPhase: String, Decodable, Sendable {
    case idle, preparing, capturing, stopping, terminating, stopped, failed, unknown
    case waitingInstall = "waiting_install", waitingVPN = "waiting_vpn", recoveryRequired = "recovery_required"
    init(from decoder: any Decoder) throws {
        self = Self(rawValue: try decoder.singleValueContainer().decode(String.self)) ?? .unknown
    }
}

enum AndroidPhysicalAction { case start, stop, recover, none }

enum AndroidPhysicalQuitSafety {
    static func requiresWarning(runtimeDirectory: URL) -> Bool {
        let root = runtimeDirectory.appendingPathComponent("android-physical")
        if FileManager.default.fileExists(atPath: root.appendingPathComponent("recovery.json").path) { return true }
        let pending = try? FileManager.default.contentsOfDirectory(atPath: root.appendingPathComponent("pending-recovery").path)
        return pending?.contains(where: { $0.hasSuffix(".json") }) == true
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
    var deviceName: String?
    var pendingRecoveries: [AndroidPhysicalRecovery]?
    enum CodingKeys: String, CodingKey {
        case phase, serial, package, message, upstream
        case sessionID = "session_id", flowCount = "flow_count", responseCount = "response_count"
        case tlsFailures = "tls_failures", originalVPN = "original_vpn"
        case deviceName = "device_name", pendingRecoveries = "pending_recoveries"
    }
    var canStart: Bool { [.idle, .stopped, .failed].contains(phase) }
    var action: AndroidPhysicalAction {
        switch phase {
        case .idle, .stopped, .failed: .start
        case .preparing, .waitingInstall, .waitingVPN, .capturing: .stop
        case .recoveryRequired: .recover
        case .stopping, .terminating, .unknown: .none
        }
    }
    var title: String { AppCopy.AndroidPhysical.title(phase) }
}

struct AndroidPhysicalRecovery: Decodable, Identifiable, Sendable {
    let serial: String
    let name: String
    var id: String { serial }
    var label: String { AppCopy.AndroidPhysical.phoneLabel(name: name, serial: serial) }
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
    func recoverAndroidPhysical(serial: String) async throws -> AndroidPhysicalStatus
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
    private var refreshing = false
    init(api: any AndroidPhysicalAPI = APIClient()) { self.api = api }
    var canTerminate: Bool { !busy && ![.idle, .terminating, .unknown].contains(status.phase) }
    var canPerform: Bool {
        guard !busy else { return false }
        switch status.action {
        case .start:
            return consent && isConnected(serial) && !(status.pendingRecoveries ?? []).contains(where: { $0.serial == serial })
        case .recover: return isConnected(status.serial ?? "")
        case .stop: return true
        case .none: return false
        }
    }
    var currentDeviceLabel: String? {
        guard !status.canStart, let serial = status.serial else { return nil }
        return AppCopy.AndroidPhysical.phoneLabel(name: status.deviceName ?? "", serial: serial)
    }
    func isConnected(_ serial: String) -> Bool {
        devices.contains(where: { $0.serial == serial && $0.status == "device" })
    }
    func canRecover(_ serial: String) -> Bool {
        !busy && status.canStart && isConnected(serial) && (status.pendingRecoveries ?? []).contains(where: { $0.serial == serial })
    }
    func refresh() async {
        guard !busy, !refreshing else { return }
        refreshing = true
        defer { refreshing = false }
        let version = revision
        do {
            let value = try await api.readAndroidPhysical()
            let connected = try await api.discoverAndroidPhysical()
            guard !Task.isCancelled, revision == version else { return }
            status = value
            devices = connected
            if !value.canStart, let active = value.serial { serial = active }
            else if !connected.contains(where: { $0.serial == serial && $0.status == "device" }) {
                serial = connected.first(where: { $0.status == "device" })?.serial ?? connected.first?.serial ?? ""
                consent = false
            }
            issue = nil
        } catch {
            guard !Task.isCancelled, revision == version else { return }
            issue = AppCopy.AndroidPhysical.connectionFailed
        }
    }
    func discover() async {
        await refresh()
    }
    func perform() async {
        guard canPerform else { return }
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

    func terminate() async {
        guard canTerminate else { return }
        busy = true
        revision += 1
        issue = nil
        defer { busy = false }
        do {
            status = try await api.actAndroidPhysical("terminate")
            consent = false
        } catch {
            issue = (error as? APIClientError)?.userFacingIssue.message ?? AppCopy.AndroidPhysical.connectionFailed
        }
    }

    func recover(_ serial: String) async {
        guard canRecover(serial) else { return }
        busy = true
        revision += 1
        issue = nil
        defer { busy = false }
        do { status = try await api.recoverAndroidPhysical(serial: serial) }
        catch { issue = (error as? APIClientError)?.userFacingIssue.message ?? AppCopy.AndroidPhysical.connectionFailed }
    }
}

import Foundation

struct WeakNetworkProfile: Codable, Equatable, Sendable {
    let uploadKbps: Int
    let downloadKbps: Int
    let latencyMs: Int

    enum CodingKeys: String, CodingKey {
        case uploadKbps = "upload_kbps"
        case downloadKbps = "download_kbps"
        case latencyMs = "latency_ms"
    }
}

struct WeakNetworkStatus: Decodable, Equatable, Sendable {
    let enabled: Bool
    let pendingRestore: Bool
    let available: Bool
    let profile: WeakNetworkProfile?
    let message: String
    let technicalDetail: String

    enum CodingKeys: String, CodingKey {
        case enabled, available, profile, message
        case pendingRestore = "pending_restore"
        case technicalDetail = "technical_detail"
    }

    static let normal = Self(enabled: false, pendingRestore: false, available: true, profile: nil,
                             message: AppCopy.WeakNetwork.normal, technicalDetail: "")
}

protocol WeakNetworkAPI: Sendable {
    func readWeakNetwork(deviceID: String) async throws -> WeakNetworkStatus
    func applyWeakNetwork(deviceID: String, profile: WeakNetworkProfile) async throws -> WeakNetworkStatus
    func restoreWeakNetwork(deviceID: String) async throws -> WeakNetworkStatus
}

@MainActor
final class WeakNetworkController: ObservableObject {
    @Published private(set) var deviceID: String?
    @Published private(set) var status: WeakNetworkStatus?
    @Published private(set) var busy = false
    @Published private(set) var issue: String?
    @Published private(set) var preset = "unlimited"
    private var hasPendingSelection = false
    private var generation = UUID()
    private let api: any WeakNetworkAPI
    private static let profiles: [String: WeakNetworkProfile] = [
        "2g": .init(uploadKbps: 128, downloadKbps: 256, latencyMs: 600),
        "3g": .init(uploadKbps: 512, downloadKbps: 2048, latencyMs: 150),
        "4g": .init(uploadKbps: 5000, downloadKbps: 10000, latencyMs: 50),
    ]

    init(api: any WeakNetworkAPI = APIClient()) { self.api = api }

    var profile: WeakNetworkProfile? {
        Self.profiles[preset]
    }

    func choosePreset(_ value: String) {
        guard value == "unlimited" || Self.profiles[value] != nil else { return }
        preset = value
        hasPendingSelection = true
    }

    func selectDevice(_ id: String?) async {
        generation = UUID()
        deviceID = id
        status = nil
        issue = nil
        busy = false
        preset = "unlimited"
        hasPendingSelection = false
        await refresh()
    }

    func refresh() async {
        guard let id = deviceID, !busy else { return }
        let current = generation
        do {
            let result = try await api.readWeakNetwork(deviceID: id)
            guard current == generation, !busy, !Task.isCancelled else { return }
            status = result
            if !hasPendingSelection { synchronizePreset(with: result) }
            if issue == AppCopy.WeakNetwork.connectionFailed { issue = nil }
        } catch {
            guard current == generation, !Task.isCancelled else { return }
            issue = AppCopy.WeakNetwork.connectionFailed
        }
    }

    func apply() async {
        guard let id = deviceID, !busy else { return }
        if preset == "unlimited" {
            await restore()
            return
        }
        guard let profile else {
            issue = AppCopy.WeakNetwork.selectProfile
            return
        }
        await update { try await self.api.applyWeakNetwork(deviceID: id, profile: profile) }
    }

    func restore() async {
        guard let id = deviceID, !busy else { return }
        await update { try await self.api.restoreWeakNetwork(deviceID: id) }
    }

    private func synchronizePreset(with result: WeakNetworkStatus) {
        guard result.available, !result.pendingRestore else { return }
        preset = result.enabled
            ? Self.profiles.first(where: { $0.value == result.profile })?.key ?? ""
            : "unlimited"
    }

    private func update(_ operation: () async throws -> WeakNetworkStatus) async {
        generation = UUID()
        let current = generation
        busy = true
        issue = nil
        do {
            let result = try await operation()
            guard current == generation else { return }
            status = result
            if result.available, !result.pendingRestore {
                hasPendingSelection = false
                synchronizePreset(with: result)
            }
        } catch {
            guard current == generation else { return }
            issue = AppCopy.WeakNetwork.connectionFailed
            // A timeout is not proof that device mutation failed. Refresh its actual state.
            status = nil
        }
        busy = false
    }
}

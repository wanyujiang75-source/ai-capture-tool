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
    @Published var upload = "512"
    @Published var download = "2048"
    @Published var latency = "150"
    @Published var preset = "light"
    private var generation = UUID()
    private let api: any WeakNetworkAPI

    init(api: any WeakNetworkAPI = APIClient()) { self.api = api }

    var profile: WeakNetworkProfile? {
        guard let up = Int(upload), let down = Int(download), let delay = Int(latency),
              (32...100000).contains(up), (32...100000).contains(down), (0...5000).contains(delay)
        else { return nil }
        return .init(uploadKbps: up, downloadKbps: down, latencyMs: delay)
    }

    func choosePreset(_ value: String) {
        preset = value
        switch value {
        case "light": upload = "512"; download = "2048"; latency = "150"
        case "severe": upload = "128"; download = "256"; latency = "600"
        default: break
        }
    }

    func editValue(_ value: String, at keyPath: ReferenceWritableKeyPath<WeakNetworkController, String>) {
        guard self[keyPath: keyPath] != value else { return }
        self[keyPath: keyPath] = value
        preset = "custom"
    }

    func selectDevice(_ id: String?) async {
        generation = UUID()
        deviceID = id
        status = nil
        issue = nil
        busy = false
        await refresh()
    }

    func refresh() async {
        guard let id = deviceID, !busy else { return }
        let current = generation
        do {
            let result = try await api.readWeakNetwork(deviceID: id)
            guard current == generation, !busy, !Task.isCancelled else { return }
            status = result
            if issue == AppCopy.WeakNetwork.connectionFailed { issue = nil }
        } catch {
            guard current == generation, !Task.isCancelled else { return }
            issue = AppCopy.WeakNetwork.connectionFailed
        }
    }

    func apply() async {
        guard let id = deviceID, !busy else { return }
        if preset == "normal" {
            await restore()
            return
        }
        guard let profile else {
            issue = AppCopy.WeakNetwork.invalidInput
            return
        }
        await update { try await self.api.applyWeakNetwork(deviceID: id, profile: profile) }
    }

    func restore() async {
        guard let id = deviceID, !busy else { return }
        await update { try await self.api.restoreWeakNetwork(deviceID: id) }
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
        } catch {
            guard current == generation else { return }
            issue = AppCopy.WeakNetwork.connectionFailed
            // A timeout is not proof that device mutation failed. Refresh its actual state.
            status = nil
        }
        busy = false
    }
}

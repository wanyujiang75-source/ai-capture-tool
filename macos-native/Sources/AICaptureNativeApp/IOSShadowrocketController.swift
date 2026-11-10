import Foundation

struct IOSNodeDevice: Decodable, Identifiable, Sendable {
    let id: String
    let name: String
}

struct IOSShadowrocketInfo: Decodable, Sendable {
    let host: String
    let port: Int
    let username: String
    let password: String
    let importURL: String
    let profilePath: String
    var devices: [IOSNodeDevice]
    enum CodingKeys: String, CodingKey {
        case host, port, username, password, devices
        case importURL = "import_url", profilePath = "profile_path"
    }
    var profileURL: URL? {
        let url = URL(fileURLWithPath: profilePath)
        guard profilePath.hasPrefix("/"), !profilePath.contains(".."),
              url.lastPathComponent == "iPhone.mobileconfig", url.pathComponents.contains("ios-setup"),
              url.deletingLastPathComponent().lastPathComponent == "shadowrocket" else { return nil }
        return url
    }
    var safeImportURL: String? {
        guard let url = URL(string: importURL), url.scheme == "shadowrocket", url.host == "add",
              url.path.hasPrefix("/http://"), url.user == nil, url.password == nil else { return nil }
        return importURL
    }
}

struct IOSNodeDelivery: Decodable, Sendable {
    enum State: String, Decodable, Sendable {
        case confirmationRequired = "confirmation_required"
        case manualRequired = "manual_required"
    }
    let state: State
}

protocol IOSShadowrocketAPI: Sendable {
    func readShadowrocket() async throws -> IOSShadowrocketInfo
    func importShadowrocket(deviceID: String) async throws -> IOSNodeDelivery
}

@MainActor
final class IOSShadowrocketController: ObservableObject {
    @Published private(set) var info: IOSShadowrocketInfo?
    @Published private(set) var loading = false
    @Published private(set) var sending = false
    @Published private(set) var delivery: IOSNodeDelivery.State?
    @Published private(set) var issue: String?
    @Published var selectedDeviceID: String?
    private let api: any IOSShadowrocketAPI
    private var generation = UUID()

    init(api: any IOSShadowrocketAPI = APIClient()) { self.api = api }

    func clear() {
        generation = UUID()
        info = nil
        selectedDeviceID = nil
        delivery = nil
        issue = nil
        loading = false
        sending = false
    }

    func load() async {
        guard !loading, !sending else { return }
        generation = UUID()
        let current = generation
        loading = true
        info = nil
        delivery = nil
        issue = nil
        defer { if current == generation { loading = false } }
        do {
            let result = try await api.readShadowrocket()
            guard current == generation, !Task.isCancelled else { return }
            info = result
            if !result.devices.contains(where: { $0.id == selectedDeviceID }) {
                selectedDeviceID = result.devices.count == 1 ? result.devices[0].id : nil
            }
        } catch {
            guard current == generation, !Task.isCancelled else { return }
            selectedDeviceID = nil
            issue = AppCopy.IOSSetup.nodeLoadFailed
        }
    }

    func send() async {
        guard !loading, !sending, let info, let selectedDeviceID,
              info.devices.contains(where: { $0.id == selectedDeviceID }) else { return }
        let current = generation
        sending = true
        delivery = nil
        defer { if current == generation { sending = false } }
        do {
            let result = try await api.importShadowrocket(deviceID: selectedDeviceID)
            guard current == generation, !Task.isCancelled else { return }
            delivery = result.state
        } catch {
            guard current == generation, !Task.isCancelled else { return }
            self.info = nil
            self.selectedDeviceID = nil
            delivery = nil
            issue = AppCopy.IOSSetup.nodeLoadFailed
        }
    }
}

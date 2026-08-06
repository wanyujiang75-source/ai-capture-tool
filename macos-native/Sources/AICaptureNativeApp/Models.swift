import Foundation

struct DevicesResponse: Decodable {
    let system: SystemState?
    let devices: [CaptureDevice]
}

struct AppsResponse: Decodable {
    let apps: [CaptureApp]
}

struct SystemState: Decodable {
    let state: String?
    let updatedAt: String?

    private enum CodingKeys: String, CodingKey {
        case state
        case updatedAt = "updated_at"
    }
}

struct CaptureDevice: Decodable, Identifiable {
    let id: String
    let name: String?
    let avdName: String?
    let adbSerial: String?
    let proxyPort: String?
    let webPort: String?
    let fridaPort: String?
    let leaseStatus: String?
    let runtimePolicy: String?
    let releaseBehavior: String?
    let emulator: EmulatorState?
    let capture: CaptureState?
    let googleState: GoogleState?

    private enum CodingKeys: String, CodingKey {
        case id = "device_id"
        case name
        case avdName = "avd_name"
        case adbSerial = "adb_serial"
        case proxyPort = "proxy_port"
        case webPort = "web_port"
        case fridaPort = "frida_port"
        case leaseStatus = "lease_status"
        case runtimePolicy = "runtime_policy"
        case releaseBehavior = "release_behavior"
        case emulator
        case capture
        case googleState = "google_state"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = container.decodeFlexibleString(forKey: .id) ?? UUID().uuidString
        name = container.decodeFlexibleString(forKey: .name)
        avdName = container.decodeFlexibleString(forKey: .avdName)
        adbSerial = container.decodeFlexibleString(forKey: .adbSerial)
        proxyPort = container.decodeFlexibleString(forKey: .proxyPort)
        webPort = container.decodeFlexibleString(forKey: .webPort)
        fridaPort = container.decodeFlexibleString(forKey: .fridaPort)
        leaseStatus = container.decodeFlexibleString(forKey: .leaseStatus)
        runtimePolicy = container.decodeFlexibleString(forKey: .runtimePolicy)
        releaseBehavior = container.decodeFlexibleString(forKey: .releaseBehavior)
        emulator = try container.decodeIfPresent(EmulatorState.self, forKey: .emulator)
        capture = try container.decodeIfPresent(CaptureState.self, forKey: .capture)
        googleState = try container.decodeIfPresent(GoogleState.self, forKey: .googleState)
    }
}

struct EmulatorState: Decodable {
    let adbOnline: Bool?
    let bootCompleted: Bool?
    let unlocked: Bool?
    let processRunning: Bool?
    let foreground: String?

    private enum CodingKeys: String, CodingKey {
        case adbOnline = "adb_online"
        case bootCompleted = "boot_completed"
        case unlocked
        case processRunning = "process_running"
        case foreground
    }
}

struct CaptureState: Decodable {
    let health: String?
    let mode: String?
    let package: String?
    let web: String?
}

struct GoogleState: Decodable {
    let ok: Bool?
    let state: String?
    let userMessage: String?

    private enum CodingKeys: String, CodingKey {
        case ok
        case state
        case userMessage = "user_message"
    }
}

struct CaptureApp: Decodable, Identifiable {
    let id: Int
    let platform: String?
    let environment: String?
    let name: String?
    let packageName: String?
    let activity: String?
    let defaultMode: String?
    let versionName: String?
    let versionCode: String?
    let lastValidationStatus: String?
    let lastValidationMessage: String?
    let lastSuccessMode: String?

    private enum CodingKeys: String, CodingKey {
        case id
        case platform
        case environment
        case name
        case packageName = "package_name"
        case activity
        case defaultMode = "default_mode"
        case versionName = "version_name"
        case versionCode = "version_code"
        case lastValidationStatus = "last_validation_status"
        case lastValidationMessage = "last_validation_message"
        case lastSuccessMode = "last_success_mode"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = (try? container.decode(Int.self, forKey: .id)) ?? 0
        platform = container.decodeFlexibleString(forKey: .platform)
        environment = container.decodeFlexibleString(forKey: .environment)
        name = container.decodeFlexibleString(forKey: .name)
        packageName = container.decodeFlexibleString(forKey: .packageName)
        activity = container.decodeFlexibleString(forKey: .activity)
        defaultMode = container.decodeFlexibleString(forKey: .defaultMode)
        versionName = container.decodeFlexibleString(forKey: .versionName)
        versionCode = container.decodeFlexibleString(forKey: .versionCode)
        lastValidationStatus = container.decodeFlexibleString(forKey: .lastValidationStatus)
        lastValidationMessage = container.decodeFlexibleString(forKey: .lastValidationMessage)
        lastSuccessMode = container.decodeFlexibleString(forKey: .lastSuccessMode)
    }
}

extension KeyedDecodingContainer {
    func decodeFlexibleString(forKey key: Key) -> String? {
        if let value = try? decodeIfPresent(String.self, forKey: key) {
            return value
        }
        if let value = try? decodeIfPresent(Int.self, forKey: key) {
            return String(value)
        }
        if let value = try? decodeIfPresent(Bool.self, forKey: key) {
            return value ? "true" : "false"
        }
        return nil
    }
}

import Foundation

struct DevicesResponse: Decodable {
    let system: SystemState?
    let devices: [CaptureDevice]
}

struct AppsResponse: Decodable {
    let apps: [CaptureApp]
}

struct JenkinsPackagesResponse: Decodable {
    let source: JenkinsSourceSummary?
    let packages: [JenkinsPackage]
}

struct JenkinsSourceSummary: Decodable {
    let type: String?
    let baseURL: String?
    let count: Int?

    private enum CodingKeys: String, CodingKey {
        case type
        case baseURL = "base_url"
        case count
    }
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
    let activeSession: CaptureSession?

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
        case activeSession = "active_session"
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
        activeSession = try container.decodeIfPresent(CaptureSession.self, forKey: .activeSession)
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

struct CaptureApp: Decodable, Identifiable, Sendable {
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

struct ForegroundAppState: Decodable, Equatable, Sendable {
    let state: String
    let packageName: String?
    let activity: String?
    let component: String?

    private enum CodingKeys: String, CodingKey {
        case state
        case packageName = "package_name"
        case activity
        case component
    }
}

struct ForegroundAppVersion: Decodable, Sendable {
    let versionName: String?
    let versionCode: String?

    private enum CodingKeys: String, CodingKey {
        case versionName = "version_name"
        case versionCode = "version_code"
    }
}

struct ForegroundReadiness: Decodable, Sendable {
    let state: String?
    let flowCount: Int?

    private enum CodingKeys: String, CodingKey {
        case state
        case flowCount = "flow_count"
    }
}

struct ForegroundReadinessResponse: Decodable, Sendable {
    let readiness: ForegroundReadiness
}

struct ForegroundTargetResponse: Decodable, Sendable {
    let state: String
    let packageName: String?
    let activity: String?
    let component: String?
    let captureState: String
    let app: CaptureApp?
    let version: ForegroundAppVersion?
    let readiness: ForegroundReadiness?

    private enum CodingKeys: String, CodingKey {
        case state
        case packageName = "package_name"
        case activity
        case component
        case captureState = "capture_state"
        case app
        case version
        case readiness
    }

    func updating(captureState: String, readiness: ForegroundReadiness?) -> Self {
        Self(
            state: state,
            packageName: packageName,
            activity: activity,
            component: component,
            captureState: captureState,
            app: app,
            version: version,
            readiness: readiness
        )
    }
}

struct JenkinsPackage: Decodable, Identifiable {
    let id: String
    let jobName: String
    let buildNumber: Int
    let result: String?
    let timestamp: String?
    let buildTime: String?
    let artifactFileName: String
    let artifactRelativePath: String
    let artifactURL: String?
    let environment: String?

    private enum CodingKeys: String, CodingKey {
        case id
        case jobName = "job_name"
        case buildNumber = "build_number"
        case result
        case timestamp
        case buildTime = "build_time"
        case artifactFileName = "artifact_file_name"
        case artifactRelativePath = "artifact_relative_path"
        case artifactURL = "artifact_url"
        case environment
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        jobName = container.decodeFlexibleString(forKey: .jobName) ?? ""
        buildNumber = (try? container.decode(Int.self, forKey: .buildNumber)) ?? Int(container.decodeFlexibleString(forKey: .buildNumber) ?? "") ?? 0
        artifactFileName = container.decodeFlexibleString(forKey: .artifactFileName) ?? ""
        artifactRelativePath = container.decodeFlexibleString(forKey: .artifactRelativePath) ?? ""
        id = container.decodeFlexibleString(forKey: .id) ?? "\(jobName)-\(buildNumber)-\(artifactRelativePath)"
        result = container.decodeFlexibleString(forKey: .result)
        timestamp = container.decodeFlexibleString(forKey: .timestamp)
        buildTime = container.decodeFlexibleString(forKey: .buildTime)
        artifactURL = container.decodeFlexibleString(forKey: .artifactURL)
        environment = container.decodeFlexibleString(forKey: .environment)
    }
}

struct JenkinsInstallPayload: Encodable {
    let deviceId: String
    let jobName: String
    let buildNumber: Int
    let artifactRelativePath: String
    let environment: String

    private enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case jobName = "job_name"
        case buildNumber = "build_number"
        case artifactRelativePath = "artifact_relative_path"
        case environment
    }
}

struct JenkinsInstallResponse: Decodable {
    let ok: Bool?
    let app: CaptureApp?
    let archivePath: String?

    private enum CodingKeys: String, CodingKey {
        case ok
        case app
        case archivePath = "archive_path"
    }
}

struct BasicActionResponse: Decodable {
    let ok: Bool?
    let stdout: String?
    let stderr: String?
}

enum LogcatSource: String, Codable, CaseIterable, Identifiable, Sendable {
    case app
    case system
    case crash

    var id: String { rawValue }
}

struct LogcatEntry: Decodable, Identifiable, Equatable, Sendable {
    let cursor: Int64
    let timestamp: String
    let pid: Int?
    let tid: Int?
    let level: String
    let tag: String
    let message: String
    let raw: String

    var id: Int64 { cursor }
}

struct LogcatStartPayload: Encodable, Sendable {
    let source: LogcatSource
    let packageName: String

    private enum CodingKeys: String, CodingKey {
        case source
        case packageName = "package_name"
    }
}

struct LogcatActionResponse: Decodable, Equatable, Sendable {
    let deviceID: String
    let source: LogcatSource?
    let state: String
    let packageName: String
    let nextCursor: Int64
    let truncated: Bool
    let entries: [LogcatEntry]

    private enum CodingKeys: String, CodingKey {
        case deviceID = "device_id"
        case source
        case state
        case packageName = "package_name"
        case nextCursor = "next_cursor"
        case truncated
        case entries
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        deviceID = try container.decode(String.self, forKey: .deviceID)
        let rawSource = try container.decode(String.self, forKey: .source)
        source = LogcatSource(rawValue: rawSource)
        state = try container.decode(String.self, forKey: .state)
        packageName = try container.decode(String.self, forKey: .packageName)
        nextCursor = try container.decode(Int64.self, forKey: .nextCursor)
        truncated = try container.decode(Bool.self, forKey: .truncated)
        entries = try container.decode([LogcatEntry].self, forKey: .entries)
    }
}

typealias LogcatPollResponse = LogcatActionResponse

struct GooglePlayImageResponse: Decodable {
    let googlePlayImage: GooglePlayImageStatus

    private enum CodingKeys: String, CodingKey {
        case googlePlayImage = "google_play_image"
    }
}

struct GooglePlayImageStatus: Decodable {
    let ok: Bool?
    let userMessage: String?
    let fix: String?
    let recommendedPackage: String?

    private enum CodingKeys: String, CodingKey {
        case ok
        case userMessage = "user_message"
        case fix
        case recommendedPackage = "recommended_package"
    }
}

struct EnsureGooglePlayAvdResponse: Decodable {
    let ok: Bool?
    let userMessage: String?
    let fix: String?

    private enum CodingKeys: String, CodingKey {
        case ok
        case userMessage = "user_message"
        case fix
    }
}

struct SystemPrepareResponse: Decodable {
    let prepare: PrepareResult
}

struct PrepareResult: Decodable {
    let ok: Bool?
    let deviceID: String?
    let userMessage: String?
    let steps: [PrepareStep]?

    private enum CodingKeys: String, CodingKey {
        case ok
        case deviceID = "device_id"
        case userMessage = "user_message"
        case steps
    }
}

struct PrepareStep: Decodable, Identifiable {
    var id: String { key }

    let key: String
    let label: String?
    let ok: Bool?
    let status: String?
    let message: String?
}

struct CaptureStartPayload: Encodable {
    let appId: Int
    let deviceId: String
    let mode: String?

    private enum CodingKeys: String, CodingKey {
        case appId = "app_id"
        case deviceId = "device_id"
        case mode
    }
}

struct CaptureStartResponse: Decodable {
    let session: CaptureSession?
    let output: String?
    let requestedMode: String?

    private enum CodingKeys: String, CodingKey {
        case session
        case output
        case requestedMode = "requested_mode"
    }
}

struct CaptureStopResponse: Decodable {
    let ok: Bool?
    let session: CaptureSession?
    let stdout: String?
    let stderr: String?
}

struct CaptureSession: Decodable {
    let id: Int?
    let status: String?
    let mode: String?
    let outdir: String?
    let deviceId: String?
    let packageName: String?

    private enum CodingKeys: String, CodingKey {
        case id
        case status
        case mode
        case outdir
        case deviceId = "device_id"
        case packageName = "package_name"
    }
}

struct FlowsResponse: Decodable {
    let flows: [FlowSummary]
}

struct FlowSummary: Decodable, Identifiable {
    let id: String
    let flowId: String?
    let time: String?
    let method: String?
    let status: String?
    let host: String?
    let path: String?
    let url: String?
    let score: String?
    let kind: String?
    let hasRequestJSON: Bool?
    let hasResponseJSON: Bool?
    let totalDurationMs: String?

    private enum CodingKeys: String, CodingKey {
        case id
        case flowId = "flow_id"
        case time
        case method
        case status
        case host
        case path
        case url
        case score
        case kind
        case hasRequestJSON = "has_request_json"
        case hasResponseJSON = "has_response_json"
        case totalDurationMs = "total_duration_ms"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = container.decodeFlexibleString(forKey: .id) ?? UUID().uuidString
        flowId = container.decodeFlexibleString(forKey: .flowId)
        time = container.decodeFlexibleString(forKey: .time)
        method = container.decodeFlexibleString(forKey: .method)
        status = container.decodeFlexibleString(forKey: .status)
        host = container.decodeFlexibleString(forKey: .host)
        path = container.decodeFlexibleString(forKey: .path)
        url = container.decodeFlexibleString(forKey: .url)
        score = container.decodeFlexibleString(forKey: .score)
        kind = container.decodeFlexibleString(forKey: .kind)
        hasRequestJSON = try container.decodeIfPresent(Bool.self, forKey: .hasRequestJSON)
        hasResponseJSON = try container.decodeIfPresent(Bool.self, forKey: .hasResponseJSON)
        totalDurationMs = container.decodeFlexibleString(forKey: .totalDurationMs)
    }
}

struct FlowDetail: Decodable, Identifiable {
    let id: String
    let method: String?
    let status: String?
    let url: String?
    let requestBodyKind: String?
    let responseBodyKind: String?
    let requestJSON: JSONValue?
    let responseJSON: JSONValue?
    let requestText: String?
    let responseText: String?
    let metaJSON: JSONValue?
    let files: JSONValue?

    private enum CodingKeys: String, CodingKey {
        case id
        case method
        case status
        case url
        case requestBodyKind = "request_body_kind"
        case responseBodyKind = "response_body_kind"
        case requestJSON = "request_json"
        case responseJSON = "response_json"
        case requestText = "request_text"
        case responseText = "response_text"
        case metaJSON = "meta_json"
        case files
    }
}

enum JSONValue: Decodable, CustomStringConvertible {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else {
            self = .array(try container.decode([JSONValue].self))
        }
    }

    var description: String {
        switch self {
        case .string(let value):
            "\"\(value)\""
        case .number(let value):
            String(value)
        case .bool(let value):
            value ? "true" : "false"
        case .object(let value):
            prettyJSONObject(value)
        case .array(let value):
            prettyJSONArray(value)
        case .null:
            "null"
        }
    }

    private func prettyJSONObject(_ object: [String: JSONValue]) -> String {
        let lines = object.keys.sorted().map { key in
            "  \"\(key)\": \(object[key]?.description ?? "null")"
        }
        return "{\n\(lines.joined(separator: ",\n"))\n}"
    }

    private func prettyJSONArray(_ array: [JSONValue]) -> String {
        let lines = array.map { "  \($0.description)" }
        return "[\n\(lines.joined(separator: ",\n"))\n]"
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

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
    var phase: IOSSetupPhase
    var flowCount = 0
    var flows: [IOSSetupFlow] = []
    var profilePath: String?
    var checkURL: String?
    var ssid: String?
    var certificateName: String?
    var connectionState: IOSConnectionState?
    var recordingState: IOSRecordingState?
    var sessionID: Int?
    var project: IOSCaptureProject?
    var canResume: Bool?
    var identityReused: Bool?
    var routeChanged: Bool?
    var certificateExpiresAt: Double?

    enum CodingKeys: String, CodingKey {
        case phase, flows, ssid
        case flowCount = "flow_count", profilePath = "profile_path", checkURL = "check_url"
        case certificateName = "certificate_name"
        case connectionState = "connection_state", recordingState = "recording_state"
        case sessionID = "session_id", project
        case canResume = "can_resume", identityReused = "identity_reused", routeChanged = "route_changed"
        case certificateExpiresAt = "certificate_expires_at"
    }
    var isConnected: Bool { connectionState.map { $0 == .ready } ?? (phase == .ready || phase == .capturing) }
    var isRecording: Bool { recordingState.map { $0 == .recording } ?? (phase == .capturing) }
    var hasCapturedTraffic: Bool { isRecording && flowCount > 0 }
    var requiresPhoneSetup: Bool { phase == .waitingPhone || phase == .waitingTrust }
    var canPrepare: Bool { phase == .idle || phase == .stopped || canResume == true }
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
    @Published private(set) var operation: IOSCaptureOperation?
    @Published private(set) var projects: [IOSCaptureProject] = []
    @Published private(set) var projectsLoading = false
    @Published private(set) var projectsIssue: String?
    @Published var selectedProjectID: String?
    private let api: any IOSSetupAPI
    private var generation = UUID()
    private var readRequestID = UUID()
    private var projectGeneration = UUID()
    private var operationFailed = false

    init(api: any IOSSetupAPI = APIClient()) { self.api = api }

    var selectedProject: IOSCaptureProject? { projects.first { $0.id == selectedProjectID } }
    var canStartRecording: Bool {
        !busy && issue == nil && status.isConnected && !status.isRecording && selectedProject != nil
    }

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
        let request = UUID()
        readRequestID = request
        do {
            let result = try await api.readIOSSetup()
            guard !Task.isCancelled, current == generation, request == readRequestID, !busy else { return }
            status = result
            if !operationFailed { issue = nil }
        } catch {
            guard !Task.isCancelled, current == generation, request == readRequestID else { return }
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
        await update(.prepare, failure: AppCopy.IOSSetup.failed) { try await self.api.prepareIOSSetup(ssid: ssid) }
    }

    func stop(phoneConfigurationRemoved: Bool) async {
        guard phoneConfigurationRemoved, !busy else { return }
        stopping = true
        defer { stopping = false }
        await update(.end, failure: AppCopy.IOSCapture.endFailed) { try await self.api.stopIOSSetup() }
    }

    func refreshProjects() async {
        guard !busy, !projectsLoading, let captureAPI = api as? any IOSCaptureAPI else { return }
        let current = projectGeneration
        projectsLoading = true
        defer { projectsLoading = false }
        do {
            let result = try await captureAPI.getIOSProjects()
            guard !Task.isCancelled, current == projectGeneration else { return }
            projects = result
            if selectedProject == nil { selectedProjectID = status.project?.id ?? result.first?.id }
            projectsIssue = nil
        } catch {
            guard current == projectGeneration, !Task.isCancelled else { return }
            projectsIssue = AppCopy.IOSCapture.projectsFailed
        }
    }

    func saveProject(_ draft: IOSProjectDraft) async -> Bool {
        guard !busy, !status.isRecording, let captureAPI = api as? any IOSCaptureAPI else { return false }
        guard !draft.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              draft.name.count <= 80, !draft.domains.isEmpty, draft.domains.count <= 64 else {
            projectsIssue = AppCopy.IOSCapture.invalidProject
            return false
        }
        generation = UUID()
        projectGeneration = UUID()
        busy = true
        operation = .save
        defer { busy = false; operation = nil; projectGeneration = UUID() }
        do {
            let saved = try await captureAPI.saveIOSProject(draft)
            projects.removeAll { $0.id == saved.id }
            projects.append(saved)
            selectedProjectID = saved.id
            projectsIssue = nil
            return true
        } catch {
            projectsIssue = AppCopy.IOSCapture.saveFailed
            return false
        }
    }

    func startRecording() async {
        guard canStartRecording, let id = selectedProjectID, let captureAPI = api as? any IOSCaptureAPI else { return }
        await update(.start, failure: AppCopy.IOSCapture.startFailed) { try await captureAPI.startIOSRecording(projectID: id) }
    }

    func stopRecording() async {
        guard !busy, status.isRecording, let captureAPI = api as? any IOSCaptureAPI else { return }
        await update(.stop, failure: AppCopy.IOSCapture.stopFailed) { try await captureAPI.stopIOSRecording() }
    }

    private func update(_ kind: IOSCaptureOperation, failure: String, _ action: () async throws -> IOSSetupStatus) async {
        generation = UUID()
        busy = true
        operation = kind
        issue = nil
        operationFailed = false
        defer { busy = false; operation = nil }
        do { status = try await action() }
        catch {
            operationFailed = true
            issue = AppCopy.IOSSetup.pairingFailure(error, fallback: failure)
        }
    }
}

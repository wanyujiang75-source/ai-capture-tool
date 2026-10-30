import Foundation
import Testing
@testable import AICaptureNativeApp

private actor IOSCaptureSpy: IOSCaptureAPI {
    var status = IOSSetupStatus(phase: .ready)
    var starts = 0
    var ends = 0
    var fails = false
    var projectReads = 0
    var saveContinuation: CheckedContinuation<Void, Never>?
    var holdSave = false
    var holdRead = false
    var readContinuation: CheckedContinuation<IOSSetupStatus, Never>?
    let project = IOSCaptureProject(id: "pokehub", name: "PokeHub", domains: ["api.example.test"])
    func readIOSSetup() async throws -> IOSSetupStatus {
        if holdRead { return await withCheckedContinuation { readContinuation = $0 } }
        return status
    }
    func prepareIOSSetup(ssid: String) async throws -> IOSSetupStatus { status }
    func stopIOSSetup() async throws -> IOSSetupStatus {
        ends += 1
        status = IOSSetupStatus(phase: .stopped)
        return status
    }
    func getIOSProjects() async throws -> [IOSCaptureProject] { projectReads += 1; return [project] }
    func saveIOSProject(_ draft: IOSProjectDraft) async throws -> IOSCaptureProject {
        if holdSave { await withCheckedContinuation { saveContinuation = $0 } }
        return IOSCaptureProject(id: draft.id ?? "new", name: draft.name, domains: draft.domains)
    }
    func startIOSRecording(projectID: String) async throws -> IOSSetupStatus {
        starts += 1
        if fails { throw APIClientError.httpStatus(409, "raw private detail") }
        status = IOSSetupStatus(phase: .capturing, connectionState: .ready,
                                recordingState: .recording, sessionID: starts, project: project)
        return status
    }
    func stopIOSRecording() async throws -> IOSSetupStatus {
        status.phase = .ready
        status.recordingState = .stopped
        return status
    }
    func setFailure() { fails = true }
    func setStatus(_ value: IOSSetupStatus) { status = value }
    func suspendSave() { holdSave = true }
    func completeSave() { saveContinuation?.resume(); saveContinuation = nil }
    func isSaving() -> Bool { saveContinuation != nil }
    func suspendRead() { holdRead = true }
    func isReading() -> Bool { readContinuation != nil }
    func completeRead(_ oldStatus: IOSSetupStatus) {
        holdRead = false
        readContinuation?.resume(returning: oldStatus)
        readContinuation = nil
    }
}

private actor IOSFlowSpy: FlowAPI {
    var calls: [Int] = []
    var hideSources = false
    func getCaptureSources() async throws -> [CaptureSource] {
        hideSources ? [] : [CaptureSource(id: 12, platform: "ios", status: "running", appName: "PokeHub", mode: "ios-http-proxy")]
    }
    func getFlows(sessionID: Int) async throws -> [FlowSummary] { [] }
    func getFlowPage(sessionID: Int, cursor: Int) async throws -> FlowPage {
        calls.append(cursor)
        let id = cursor == 0 ? "a" : "b"
        let flow = try JSONDecoder().decode(FlowSummary.self, from: Data("{\"id\":\"\(id)\",\"status\":\"200\"}".utf8))
        return FlowPage(flows: [flow], total: 2, cursor: cursor + 1, nextCursor: cursor == 0 ? 1 : nil)
    }
    func getFlowDetail(sessionID: Int, flowID: String) async throws -> FlowDetail {
        try JSONDecoder().decode(FlowDetail.self, from: Data("{\"id\":\"\(flowID)\",\"response_text\":\"received\"}".utf8))
    }
    func getFlowCurl(sessionID: Int, flowID: String) async throws -> String {
        throw APIClientError.httpStatus(409, "incomplete request body")
    }
    func hideSource() { hideSources = true }
}

@MainActor
struct IOSCaptureIntegrationTests {
    @Test func lateStatusCannotUndoExplicitStartOrStop() async {
        let api = IOSCaptureSpy()
        let controller = IOSSetupController(api: api)
        await controller.refresh()
        await controller.refreshProjects()
        let ready = controller.status
        await api.suspendRead()
        let oldReadyPoll = Task { await controller.refresh() }
        while !(await api.isReading()) { await Task.yield() }
        await controller.startRecording()
        await api.completeRead(ready)
        await oldReadyPoll.value
        #expect(controller.status.isRecording)

        let recording = controller.status
        await api.suspendRead()
        let oldRecordingPoll = Task { await controller.refresh() }
        while !(await api.isReading()) { await Task.yield() }
        await controller.stopRecording()
        await api.completeRead(recording)
        await oldRecordingPoll.value
        #expect(controller.status.recordingState == .stopped)
        #expect(controller.status.isConnected)
    }

    @Test func sourceListCutoffDoesNotTurnIOSIntoLegacyAndroidFetching() async {
        let api = IOSFlowSpy()
        let state = AppState(flowAPI: api)
        await state.refreshFlowSources()
        state.selectFlowSource(12)
        await state.refreshFlows()
        await api.hideSource()
        await state.refreshFlowSources()
        #expect(state.selectedFlowSource?.isIOS == true)
        #expect(state.flowSources.contains { $0.id == 12 })
        await state.refreshFlows()
        #expect(await api.calls == [0, 1, 2])
        #expect(state.flows.count == 2)
    }

    @Test func projectRefreshIsExcludedWhileSaveIsInFlight() async {
        let api = IOSCaptureSpy()
        let controller = IOSSetupController(api: api)
        await controller.refreshProjects()
        await api.suspendSave()
        let save = Task { await controller.saveProject(IOSProjectDraft(id: nil, name: "New", domains: ["new.test"])) }
        while !(await api.isSaving()) { await Task.yield() }
        await controller.refreshProjects()
        #expect(await api.projectReads == 1)
        await api.completeSave()
        #expect(await save.value)
        #expect(controller.selectedProjectID == "new")
    }

    @Test func explicitStartStopRetainsConnectionAndRestartCreatesNewCapture() async {
        let api = IOSCaptureSpy()
        let controller = IOSSetupController(api: api)
        await controller.refresh()
        await controller.refreshProjects()
        #expect(await api.starts == 0)
        #expect(controller.canStartRecording)
        await controller.startRecording()
        #expect(controller.status.sessionID == 1)
        #expect(controller.status.isRecording)
        await controller.stopRecording()
        #expect(controller.status.isConnected)
        #expect(!controller.status.isRecording)
        #expect(await api.ends == 0)
        await controller.startRecording()
        #expect(controller.status.sessionID == 2)
        await controller.stop(phoneConfigurationRemoved: false)
        #expect(await api.ends == 0)
    }

    @Test func notTrustedCannotStartAndStartFailureDoesNotShowSuccess() async {
        let api = IOSCaptureSpy()
        await api.setStatus(IOSSetupStatus(phase: .waitingTrust))
        let controller = IOSSetupController(api: api)
        await controller.refresh()
        await controller.refreshProjects()
        await controller.startRecording()
        #expect(await api.starts == 0)
        await api.setStatus(IOSSetupStatus(phase: .ready))
        await controller.refresh()
        await api.setFailure()
        await controller.startRecording()
        #expect(!controller.status.isRecording)
        #expect(controller.issue == AppCopy.IOSCapture.startFailed)
    }

    @Test func projectsCanBeSavedButNotChangedWhileRecording() async {
        let api = IOSCaptureSpy()
        let controller = IOSSetupController(api: api)
        await controller.refresh()
        await controller.refreshProjects()
        #expect(await controller.saveProject(IOSProjectDraft(id: nil, name: "Other", domains: ["other.test"])))
        #expect(controller.selectedProjectID == "new")
        await controller.startRecording()
        #expect(!(await controller.saveProject(IOSProjectDraft(id: "new", name: "Changed", domains: ["changed.test"]))))
    }

    @Test func unifiedResultsPageAndClearAreIndependentOfAndroidCapture() async throws {
        let api = IOSFlowSpy()
        let state = AppState(flowAPI: api)
        state.activeSessionID = 3
        await state.refreshFlowSources()
        state.selectFlowSource(12)
        await state.refreshFlows()
        #expect(await api.calls == [0, 1])
        #expect(state.flows.map(\.id) == ["a", "b"])
        state.clearCurrentFlows()
        state.didStopCapture()
        #expect(state.flowSessionID == 12)
        #expect(state.visibleFlows.isEmpty)
        await state.refreshFlows()
        #expect(await api.calls == [0, 1, 2])
        #expect(state.visibleFlows.isEmpty)
        state.selectFlowSource(nil)
        #expect(state.flows.isEmpty)
        #expect(!state.hasClearedFlows)
    }

    @Test func curlFailureNeverHidesCapturedResponse() async throws {
        let state = AppState(flowAPI: IOSFlowSpy())
        state.activeSessionID = 1
        let flow = try JSONDecoder().decode(FlowSummary.self, from: Data("{\"id\":\"a\"}".utf8))
        await state.loadFlowDetail(flow)
        #expect(state.selectedFlowDetail?.responseText == "received")
        #expect(state.flowDetailLoadState == .loaded)
        #expect(state.flowCurlIssue == AppCopy.IOSCapture.curlUnavailable)
    }

    @Test func quitWarningUsesRecoveryMarkerEvenBeforeFirstStatusPoll() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let marker = root.appendingPathComponent("ios-setup/cleanup-required")
        try FileManager.default.createDirectory(at: marker.deletingLastPathComponent(), withIntermediateDirectories: true)
        #expect(!IOSQuitSafety.requiresWarning(runtimeDirectory: root))
        try Data("recover".utf8).write(to: marker)
        #expect(IOSQuitSafety.requiresWarning(runtimeDirectory: root))
    }
}

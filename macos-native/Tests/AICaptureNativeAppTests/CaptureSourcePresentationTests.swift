import Foundation
import Testing
@testable import AICaptureNativeApp

private actor SourcePresentationAPI: FlowAPI {
    var sources: [CaptureSource] = []
    func replace(_ sources: [CaptureSource]) { self.sources = sources }
    func getCaptureSources() async throws -> [CaptureSource] { sources }
    func getFlows(sessionID: Int) async throws -> [FlowSummary] { [] }
    func getFlowDetail(sessionID: Int, flowID: String) async throws -> FlowDetail { throw APIClientError.invalidResponse }
    func getFlowCurl(sessionID: Int, flowID: String) async throws -> String { "" }
}

@MainActor
struct CaptureSourcePresentationTests {
    @Test func genericDeviceNameIsNotRepeatedAsApplicationName() {
        let source = CaptureSource(id: 87, platform: "ios", status: "stopped", appName: "iPhone", mode: "ios-http-proxy")
        #expect(source.title == "iPhone 抓包 · #87")
    }

    @Test func freshPageSelectsRunningCaptureInsteadOfHistoricalRecords() async {
        let api = SourcePresentationAPI()
        await api.replace([
            CaptureSource(id: 87, platform: "ios", status: "stopped", appName: "iPhone", mode: "ios-http-proxy"),
            CaptureSource(id: 86, platform: "ios", status: "running", appName: "PokeHub", mode: "ios-http-proxy")
        ])
        let state = AppState(flowAPI: api)
        await state.refreshFlowSources()
        #expect(state.flowSessionID == 86)
    }

    @Test func historyAloneDoesNotSelectOrStartCapture() async {
        let api = SourcePresentationAPI()
        await api.replace([CaptureSource(id: 87, platform: "ios", status: "stopped", appName: "iPhone", mode: "ios-http-proxy")])
        let state = AppState(flowAPI: api)
        await state.refreshFlowSources()
        #expect(state.flowSessionID == nil)
        #expect(state.activeSessionID == nil)
        #expect(state.flows.isEmpty)
    }

    @Test func currentAndHistoryAreSeparatedAndSearchable() {
        let sources = [
            CaptureSource(id: 1, platform: "ios", status: "stopped", appName: "PokeHub", mode: nil),
            CaptureSource(id: 2, platform: "ios", status: "failed", appName: "Wishly", mode: nil),
            CaptureSource(id: 3, platform: "ios", status: "running", appName: "MelodyCraft", mode: nil),
            CaptureSource(id: 4, platform: "ios", status: nil, appName: nil, mode: nil)
        ]
        let groups = CaptureSourceGroups(sources: sources, activeAndroidID: 5)
        #expect(groups.current.map(\.id) == [5, 3])
        #expect(groups.history.map(\.id) == [4, 2, 1])
        #expect(groups.matchingHistory("POKE iphone").map(\.id) == [1])
        #expect(groups.matchingHistory("#2 已中断").map(\.id) == [2])
        #expect(groups.matchingHistory("未命中").isEmpty)
        #expect(sources[3].statusLabel == AppCopy.FlowSource.unknown)
        #expect(!sources[3].isRunning)
    }

    @Test func datesDecodeWithoutBreakingOldRecords() throws {
        let old = try JSONDecoder().decode(CaptureSource.self, from: Data(#"{"id":1,"platform":"ios","status":"stopped"}"#.utf8))
        #expect(old.startedAt == nil)
        #expect(old.startedLabel == AppCopy.FlowSource.unknownTime)
        let fractional = try JSONDecoder().decode(CaptureSource.self, from: Data(#"{"id":2,"started_at":"2026-11-05T08:00:00.125+08:00"}"#.utf8))
        let whole = CaptureSource(id: 3, platform: nil, status: nil, appName: nil, mode: nil, startedAt: "2026-11-05T00:00:00Z")
        #expect(try #require(fractional.startedDate).timeIntervalSince(#require(whole.startedDate)) == 0.125)
        #expect(fractional.startedLabel != AppCopy.FlowSource.unknownTime)
        let invalid = CaptureSource(id: 4, platform: nil, status: nil, appName: nil, mode: nil, startedAt: "invalid")
        #expect(invalid.startedDate == nil)
    }

    @Test func activeAndroidTakesPriorityAndIsNotDuplicated() async {
        let api = SourcePresentationAPI()
        let android = CaptureSource(id: 1, platform: "android", status: "running", appName: "PokeHub", mode: nil)
        await api.replace([android, CaptureSource(id: 2, platform: "ios", status: "running", appName: nil, mode: nil)])
        let state = AppState(flowAPI: api)
        state.activeSessionID = 1
        await state.refreshFlowSources()
        #expect(state.flowSessionID == 1)
        #expect(state.selectedFlowSourceID == nil)
        #expect(CaptureSourceGroups(sources: state.flowSources, activeAndroidID: 1).current.count == 2)
        state.selectFlowSource(2)
        state.selectCurrentFlowSource()
        #expect(state.flowSessionID == 1)
        #expect(state.selectedFlowSourceID == nil)
    }

    @Test func historySelectionSurvivesNewCurrentCapture() async {
        let api = SourcePresentationAPI()
        let history = CaptureSource(id: 1, platform: "ios", status: "stopped", appName: "PokeHub", mode: nil)
        await api.replace([history])
        let state = AppState(flowAPI: api)
        await state.refreshFlowSources()
        state.selectFlowSource(1)
        await api.replace([history, CaptureSource(id: 2, platform: "ios", status: "running", appName: "Wishly", mode: nil)])
        await state.refreshFlowSources()
        #expect(state.flowSessionID == 1)
        #expect(!state.isViewingLiveCapture)
        state.selectCurrentFlowSource()
        #expect(state.flowSessionID == 2)
        #expect(state.isViewingLiveCapture)
    }

    @Test func returningToCurrentDoesNotReuseHistoryAndResetsDetails() async {
        let api = SourcePresentationAPI()
        await api.replace([CaptureSource(id: 1, platform: "ios", status: "stopped", appName: nil, mode: nil)])
        let state = AppState(flowAPI: api)
        await state.refreshFlowSources()
        state.selectFlowSource(1)
        state.selectedFlowID = "old-request"
        state.selectedFlowCurl = "old-curl"
        state.selectCurrentFlowSource()
        await state.refreshFlowSources()
        #expect(state.flowSessionID == nil)
        #expect(state.selectedFlowID == nil)
        #expect(state.selectedFlowCurl.isEmpty)
        #expect(!state.isViewingLiveCapture)
    }

    @Test(arguments: ["stopped", "failed", "unknown"])
    func historicalEmptyRecordsDoNotPromptMoreTraffic(status: String) async {
        let api = SourcePresentationAPI()
        await api.replace([CaptureSource(id: 1, platform: "ios", status: status, appName: nil, mode: nil)])
        let state = AppState(flowAPI: api)
        await state.refreshFlowSources()
        state.selectFlowSource(1)
        #expect(state.emptyFlowsMessage == AppCopy.Flow.historyEmpty)
        #expect(!state.isViewingLiveCapture)
        state.clearCurrentFlows()
        #expect(state.notice?.message == AppCopy.Flow.historyCleared)
    }

    @Test func stoppedCurrentRecordBecomesHistoryWithoutLosingSelection() async {
        let api = SourcePresentationAPI()
        await api.replace([CaptureSource(id: 1, platform: "ios", status: "running", appName: "PokeHub", mode: nil)])
        let state = AppState(flowAPI: api)
        await state.refreshFlowSources()
        #expect(state.emptyFlowsMessage == AppCopy.IOSCapture.waiting)
        await api.replace([CaptureSource(id: 1, platform: "ios", status: "stopped", appName: "PokeHub", mode: nil)])
        await state.refreshFlowSources()
        #expect(state.flowSessionID == 1)
        #expect(state.emptyFlowsMessage == AppCopy.Flow.historyEmpty)
        #expect(!state.isViewingLiveCapture)
    }

    @Test func staleAndroidStatusDoesNotHideTheOnlyRunningIPhone() async {
        let api = SourcePresentationAPI()
        await api.replace([
            CaptureSource(id: 1, platform: "android", status: "stopped", appName: nil, mode: nil),
            CaptureSource(id: 2, platform: "ios", status: "running", appName: "PokeHub", mode: nil)
        ])
        let state = AppState(flowAPI: api)
        state.activeSessionID = 1
        await state.refreshFlowSources()
        #expect(state.flowSessionID == 2)
        state.selectFlowSource(1)
        state.selectCurrentFlowSource()
        #expect(state.flowSessionID == 2)
        #expect(state.activeSessionID == 1)
    }

    @Test func endedAndroidIsNotPresentedAsCurrentWhileDeviceStatusLags() async {
        let api = SourcePresentationAPI()
        await api.replace([CaptureSource(id: 1, platform: "android", status: "stopped", appName: nil, mode: nil)])
        let state = AppState(flowAPI: api)
        state.activeSessionID = 1
        state.selectedFlowID = "old-request"
        await state.refreshFlowSources()
        #expect(state.flowSessionID == nil)
        #expect(state.selectedFlowID == nil)
        #expect(state.activeSessionID == 1)
    }

    @Test func androidStopKeepsExistingResetBehavior() {
        let state = AppState(flowAPI: SourcePresentationAPI())
        state.activeSessionID = 1
        state.selectedFlowID = "old-request"
        state.didStopCapture()
        #expect(state.flowSessionID == nil)
        #expect(state.selectedFlowID == nil)
        #expect(state.captureWorkflowState == .stopped)
    }
}

import Foundation

@MainActor
final class BreakpointController: ObservableObject {
    @Published private(set) var sources: [CaptureSource] = []
    @Published private(set) var target: BreakpointTarget?
    @Published private(set) var status: BreakpointStatus?
    @Published private(set) var pending: [BreakpointPending] = []
    @Published private(set) var detail: BreakpointDetail?
    @Published var draft: BreakpointDraft?
    @Published private(set) var selectedID: String?
    @Published private(set) var issue: String?
    @Published private(set) var message: String?
    @Published private(set) var busy = false
    @Published private(set) var loadingDetail = false
    @Published private(set) var healthy = false
    @Published var showsPanel = false
    @Published var panelTab = "pending"
    @Published var ruleSeed: BreakpointRuleSpec?
    @Published private(set) var templates: [BreakpointRuleSpec] = []
    private let api: any BreakpointAPI
    private let flowAPI: any FlowAPI
    private let library: BreakpointRuleLibrary?
    private var polling = false
    private var generation = UUID()
    private var selection = UUID()
    private var ownsLease = false
    private var sampledAt = ContinuousClock.now
    private var discovering = false
    private var renewing = false

    init(api: any BreakpointAPI, flowAPI: any FlowAPI, library: BreakpointRuleLibrary? = nil) {
        self.api = api; self.flowAPI = flowAPI; self.library = library
        templates = (try? library?.load()) ?? []
    }
    var canControl: Bool { healthy && status?.transportAttached == true && status?.stopped == false && !busy }
    var canRebind: Bool { !busy && !ownsLease && status?.enabled != true && pending.isEmpty && (status?.inFlight ?? 0) == 0 }
    var canEdit: Bool {
        canControl && !loadingDetail && detail?.state == "paused"
        && pending.contains { $0.id == detail?.id && $0.state == "paused" && $0.revision == detail?.revision && remaining($0) > 0 }
    }
    var title: String {
        guard let target else { return BreakpointCopy.noCapture }
        return sources.first { String($0.id) == target.captureId }?.title ?? "本次抓包 #\(target.captureId)"
    }
    func remaining(_ item: BreakpointPending) -> Int {
        let elapsed = sampledAt.duration(to: .now).components
        return max(0, Int(ceil(item.remainingSeconds - Double(elapsed.seconds) - Double(elapsed.attoseconds) / 1e18)))
    }

    func poll() async {
        guard !polling else { return }
        polling = true
        defer { polling = false }
        if target == nil {
            await refreshSources()
            if target == nil, sources.count == 1 { await bind(sources[0].id) }
        }
        guard let target, !busy else { return }
        let run = generation
        do {
            let state = try BreakpointWire.decode(BreakpointStatus.self, from: await api.call(target, path: "", method: "GET", body: nil))
            let sample = ContinuousClock.now
            let page = try BreakpointWire.decode(BreakpointPage.self, from: await api.call(target, path: "/pending", method: "GET", body: nil))
            guard generation == run, !Task.isCancelled, !busy else { return }
            guard state.captureId == target.captureId, state.deviceId == target.deviceId, state.epoch == target.epoch,
                  page.data.count <= 20, page.nextCursor == nil else { throw BreakpointFailure("target_conflict") }
            status = state
            pending = page.data
            sampledAt = sample
            healthy = !state.stopped
            if issue == BreakpointCopy.disconnected { issue = nil }
            if !state.enabled { ownsLease = false }
            if let id = selectedID, !page.data.contains(where: { $0.id == id && $0.state == "paused" && (detail == nil || $0.revision == detail?.revision) }) {
                detail = nil; draft = nil; message = BreakpointCopy.ended
            }
        } catch {
            guard generation == run else { return }
            healthy = false; detail = nil; draft = nil; selectedID = nil
            issue = BreakpointCopy.issue(error)
            if ["capture_not_found", "capture_ended", "target_conflict"].contains((error as? BreakpointFailure)?.code ?? "") {
                self.target = nil; status = nil; pending = []; selectedID = nil; ownsLease = false
            }
        }
    }

    func refreshLease() async {
        guard ownsLease, !renewing, let target else { return }
        renewing = true
        defer { renewing = false }
        let run = generation
        do { _ = try await api.call(target, path: "/heartbeat", method: "POST", body: nil) }
        catch {
            guard generation == run, ownsLease else { return }
            healthy = false; detail = nil; draft = nil; selectedID = nil
            issue = BreakpointCopy.issue(error)
        }
    }

    func refreshSources() async {
        guard !discovering else { return }
        discovering = true
        defer { discovering = false }
        do { sources = try await flowAPI.getCaptureSources().filter { $0.status == "running" } }
        catch { if target == nil { issue = BreakpointCopy.disconnected } }
    }

    func bind(_ captureID: Int) async {
        guard canRebind else { return }
        busy = true
        generation = UUID()
        defer { busy = false }
        do {
            let value = try await api.context(captureID: captureID)
            // A newly opened desktop never silently renews another desktop's lease.
            _ = try await api.call(value, path: "/disable", method: "POST", body: nil)
            target = value; status = nil; pending = []; detail = nil; draft = nil; selectedID = nil
            selection = UUID(); loadingDetail = false
            ownsLease = false; healthy = false; issue = nil; message = nil
        } catch { issue = BreakpointCopy.issue(error) }
    }

    func setEnabled(_ enabled: Bool) async {
        guard canControl, let target else { return }
        await mutate {
            _ = try await self.api.call(target, path: enabled ? "/enable" : "/disable", method: "POST", body: nil)
            self.ownsLease = enabled
            if !enabled { self.detail = nil; self.draft = nil; self.selectedID = nil }
        }
        await poll()
    }

    func releaseAll() async {
        guard canControl, let target else { return }
        await mutate {
            _ = try await self.api.call(target, path: "/release-all", method: "POST", body: nil)
            self.ownsLease = false; self.detail = nil; self.draft = nil; self.selectedID = nil
            self.message = BreakpointCopy.releaseHelp
        }
        await poll()
    }

    func saveRule(_ spec: BreakpointRuleSpec, id: String = UUID().uuidString, revision: Int = 0, enable: Bool = false) async {
        guard canControl, let target else { return }
        var spec = spec
        if enable { spec.enabled = true }
        struct Payload: Encodable { let expectedRevision: Int; let rule: BreakpointRuleSpec }
        await mutate {
            _ = try await self.api.call(target, path: "/rules/\(id)", method: "PUT",
                                       body: BreakpointWire.encode(Payload(expectedRevision: revision, rule: spec)))
            if enable {
                _ = try await self.api.call(target, path: "/enable", method: "POST", body: nil)
                self.ownsLease = true
            }
            self.ruleSeed = nil
            if let library = self.library {
                do { try library.save(spec); self.templates = try library.load() }
                catch { self.message = BreakpointCopy.templateFailed }
            }
        }
        await poll()
    }

    func select(_ id: String) async {
        guard let target, healthy, !busy, pending.contains(where: { $0.id == id && $0.state == "paused" }) else { return }
        let request = UUID(); selection = request
        selectedID = id; detail = nil; draft = nil; loadingDetail = true; message = nil
        defer {
            if selection == request {
                loadingDetail = false
                if detail == nil { selectedID = nil }
            }
        }
        let run = generation
        do {
            let result = try BreakpointWire.decode(BreakpointDetail.self, from: await api.call(target, path: "/pending/\(id)", method: "GET", body: nil))
            guard generation == run, selection == request, selectedID == id, !Task.isCancelled else { return }
            guard result.id == id, result.original.headers.allSatisfy({ $0.count == 2 }),
                  result.original.headers.count <= 200, result.original.bodyBase64.utf8.count <= 349528,
                  pending.contains(where: { $0.id == id && $0.revision == result.revision && $0.state == "paused" }) else {
                throw BreakpointFailure("stage_ended")
            }
            detail = result; draft = BreakpointDraft(original: result.original); issue = nil; message = nil
        } catch { if generation == run && selection == request { issue = BreakpointCopy.issue(error) } }
    }

    func resolve(_ action: String) async {
        guard canEdit, let target, let detail else { return }
        struct Payload: Encodable { let operationId: String; let expectedRevision: Int; let action: String; let patch: BreakpointPatch? }
        await mutate {
            let patch = action == "apply" ? try self.draft?.patch(stage: detail.stage, original: detail.original) : nil
            let payload = Payload(operationId: detail.id + "." + UUID().uuidString, expectedRevision: detail.revision, action: action, patch: patch)
            _ = try await self.api.call(target, path: "/pending/\(detail.id)/resolve", method: "POST", body: BreakpointWire.encode(payload))
            self.detail = nil; self.draft = nil; self.selectedID = nil
            self.message = action == "abort" ? BreakpointCopy.abortAccepted : BreakpointCopy.accepted
        }
        await poll()
    }

    func seed(url: String, method: String) {
        do { ruleSeed = try BreakpointRuleSpec.seed(url: url, method: method); panelTab = "rules"; showsPanel = true }
        catch { issue = BreakpointCopy.issue(error) }
    }

    private func mutate(_ operation: () async throws -> Void) async {
        guard !busy else { return }
        busy = true; generation = UUID(); issue = nil; message = nil
        defer { busy = false }
        do { try await operation() }
        catch { issue = BreakpointCopy.issue(error) }
    }
}

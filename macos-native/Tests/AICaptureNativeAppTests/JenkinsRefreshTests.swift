import Foundation
import Testing
@testable import AICaptureNativeApp

private actor DeferredJenkinsAPI: JenkinsPackageAPI {
    private var pending: CheckedContinuation<JenkinsPackagesResponse, any Error>?
    private var waiter: CheckedContinuation<Void, Never>?
    private(set) var calls = 0

    func getJenkinsPackages() async throws -> JenkinsPackagesResponse {
        calls += 1
        return try await withCheckedThrowingContinuation {
            pending = $0
            waiter?.resume()
            waiter = nil
        }
    }

    func waitForRequest() async {
        if pending == nil {
            await withCheckedContinuation { waiter = $0 }
        }
    }

    func finish(_ result: Result<JenkinsPackagesResponse, any Error>) {
        pending?.resume(with: result)
        pending = nil
    }
}

@MainActor
struct JenkinsRefreshTests {
    private func response(_ packages: String, source: String = "{}") throws -> JenkinsPackagesResponse {
        try JSONDecoder().decode(JenkinsPackagesResponse.self, from: Data(
            "{\"source\":\(source),\"packages\":\(packages)}".utf8
        ))
    }

    @Test
    func retainsListDuringRefreshAndIgnoresDuplicateRequest() async throws {
        let api = DeferredJenkinsAPI()
        let state = AppState(jenkinsAPI: api)
        state.jenkinsPackages = try response("[{\"id\":\"old\",\"job_name\":\"music\"}]").packages
        let refresh = Task { await state.refreshJenkinsPackages() }
        await api.waitForRequest()
        #expect(state.jenkinsLoadState == .loading)
        #expect(state.jenkinsPackages.map(\.id) == ["old"])
        await state.refreshJenkinsPackages()
        #expect(await api.calls == 1)
        await api.finish(.success(try response("[{\"id\":\"new\",\"job_name\":\"music\"}]")))
        await refresh.value
        #expect(state.jenkinsLoadState == .loaded)
        #expect(state.jenkinsPackages.map(\.id) == ["new"])
        #expect(state.jenkinsRefreshWarning.isEmpty)
    }

    @Test
    func failureRetainsPreviousPackagesAndCanRetry() async throws {
        let api = DeferredJenkinsAPI()
        let state = AppState(jenkinsAPI: api)
        state.jenkinsPackages = try response("[{\"id\":\"old\"}]").packages
        let first = Task { await state.refreshJenkinsPackages() }
        await api.waitForRequest()
        await api.finish(.failure(URLError(.notConnectedToInternet)))
        await first.value
        #expect(state.jenkinsPackages.map(\.id) == ["old"])
        #expect(state.jenkinsLoadState == .failed(AppCopy.Install.jenkinsUnavailable))
        let retry = Task { await state.refreshJenkinsPackages() }
        await api.waitForRequest()
        await api.finish(.success(try response("[]")))
        await retry.value
        #expect(state.jenkinsLoadState == .loaded)
        #expect(state.jenkinsPackages.isEmpty)
    }

    @Test
    func partialRefreshKeepsOnlyFailedJobsOldPackages() async throws {
        let api = DeferredJenkinsAPI()
        let state = AppState(jenkinsAPI: api)
        state.jenkinsPackages = try response("""
        [{"id":"old-music","job_name":"music"},
         {"id":"old-poke","job_name":"poke"},
         {"id":"removed","job_name":"removed"}]
        """).packages
        let refresh = Task { await state.refreshJenkinsPackages() }
        await api.waitForRequest()
        await api.finish(.success(try response(
            "[{\"id\":\"new-music\",\"job_name\":\"music\"}]",
            source: "{\"errors\":[\"poke: HTTP 403\"],\"failed_jobs\":[\"poke\"]}"
        )))
        await refresh.value
        #expect(state.jenkinsPackages.map(\.id) == ["new-music", "old-poke"])
        #expect(state.jenkinsRefreshWarning == AppCopy.Install.partialRefresh)
    }

    @Test
    func olderBackendPartialErrorStillWarnsWithoutShowingRawDetails() async throws {
        let api = DeferredJenkinsAPI()
        let state = AppState(jenkinsAPI: api)
        let refresh = Task { await state.refreshJenkinsPackages() }
        await api.waitForRequest()
        await api.finish(.success(try response("[]", source: "{\"errors\":[\"HTTP 403 raw details\"]}")))
        await refresh.value
        #expect(state.jenkinsRefreshWarning == AppCopy.Install.partialRefresh)
    }
}

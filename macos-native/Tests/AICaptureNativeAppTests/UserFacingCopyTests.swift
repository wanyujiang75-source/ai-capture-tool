import Foundation
import Testing
@testable import AICaptureNativeApp

private actor FailingLogcatAPI: LogcatAPI {
    func startLogcat(
        deviceID: String,
        source: LogcatSource,
        packageName: String
    ) async throws -> LogcatActionResponse {
        throw APIClientError.httpStatus(
            409,
            #"{"detail":{"code":"logcat_offline","user_message":"raw backend message","technical_detail":"adb device offline"}}"#
        )
    }

    func pollLogcat(deviceID: String, after: Int64, limit: Int) async throws -> LogcatPollResponse {
        throw APIClientError.httpStatus(409, #"{"detail":"raw poll failure"}"#)
    }

    func clearLogcat(deviceID: String) async throws -> LogcatActionResponse {
        throw APIClientError.httpStatus(409, #"{"detail":"raw clear failure"}"#)
    }

    func stopLogcat(deviceID: String) async throws -> LogcatActionResponse {
        throw APIClientError.httpStatus(409, #"{"detail":"raw stop failure"}"#)
    }
}

@Suite(.serialized)
@MainActor
struct UserFacingCopyTests {
    @Test
    func structuredBackendErrorSeparatesUserMessageFromTechnicalDetail() {
        let error = APIClientError.httpStatus(
            409,
            #"{"detail":{"code":"capture_active","title":"其他应用正在抓包","user_message":"请先停止当前抓包。","recovery_action":"停止抓包","technical_detail":"another capture session is active"}}"#
        )

        #expect(
            error.userFacingIssue == UserFacingIssue(
                code: "capture_active",
                title: "其他应用正在抓包",
                message: "请先停止当前抓包。",
                recoveryAction: "停止抓包",
                technicalDetail: "another capture session is active"
            )
        )
        #expect(error.localizedDescription == "请先停止当前抓包。")
        #expect(!error.localizedDescription.contains("HTTP 409"))
        #expect(!error.localizedDescription.contains("another capture session"))
    }

    @Test
    func legacyBackendConflictDoesNotExposeRawJSON() {
        let error = APIClientError.httpStatus(
            409,
            #"{"detail":"another capture session is active; stop or cleanup first"}"#
        )

        #expect(error.userFacingIssue.title == "当前操作暂时无法完成")
        #expect(error.userFacingIssue.message == "当前操作与正在进行的任务冲突，请结束当前任务后重试。")
        #expect(error.userFacingIssue.technicalDetail?.contains("another capture session") == true)
        #expect(!error.localizedDescription.contains("another capture session"))
    }

    @Test
    func flowCopyDistinguishesNoRequestNoResponseAndEmptySuccessfulResponse() throws {
        let emptyResponse = try flowDetail(status: "200")
        let noResponse = try flowDetail(status: "NO_RESPONSE")

        #expect(FlowListPresentation.statusLabel("NO_RESPONSE") == AppCopy.Flow.noResponse)
        #expect(FlowListPresentation.requestBodyText(emptyResponse) == AppCopy.Flow.noRequestBody)
        #expect(
            FlowListPresentation.responseBodyText(emptyResponse)
                == "已捕获 HTTP 200，但没有可展示的响应正文。"
        )
        #expect(FlowListPresentation.responseBodyText(noResponse) == AppCopy.Flow.responsePending)
    }

    @Test
    func logcatUsesStableUserCopyForOfflineWaitingAndConnectionFailure() async {
        let controller = LogcatController(
            api: FailingLogcatAPI(),
            sleep: { _ in try await Task.sleep(for: .seconds(60)) }
        )

        await controller.configure(deviceID: nil, packageName: nil)
        #expect(controller.message == AppCopy.Log.deviceOffline)

        await controller.configure(deviceID: "device-1", packageName: nil)
        #expect(controller.message == AppCopy.Log.waitingForApp)

        await controller.configure(deviceID: "device-1", packageName: "com.example.app")
        #expect(controller.message == AppCopy.Log.disconnected)
        #expect(!controller.message.contains("HTTP 409"))
        #expect(!controller.message.contains("adb"))
    }

    @Test
    func transientNoticeDurationMatchesSuccessAndFailurePolicy() {
        #expect(UserNotice.success(title: "成功", message: "完成").duration == .seconds(3))
        #expect(UserNotice.failure(title: "失败", message: "重试").duration == .seconds(4))
    }

    private func flowDetail(status: String) throws -> FlowDetail {
        try JSONDecoder().decode(
            FlowDetail.self,
            from: Data(
                """
                {
                  "id": "flow-1",
                  "method": "GET",
                  "status": "\(status)",
                  "url": "https://example.com/user"
                }
                """.utf8
            )
        )
    }
}

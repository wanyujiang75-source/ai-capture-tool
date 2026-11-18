import SwiftUI

struct DesktopUpdateView: View {
    private enum UpdateState {
        case loading, available(DesktopRelease), unavailable, failed
    }

    let supportsInstallation: Bool
    let install: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var state: UpdateState = .loading
    @State private var retryCount = 0

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("软件更新")
                .font(.title2.bold())
                .accessibilityAddTraits(.isHeader)

            statusContent
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)

            Divider()
            HStack(spacing: 12) {
                Link("GitHub 发布页", destination: DesktopReleaseCatalog.releasesPage)
                if case let .available(release) = state, let checksum = release.checksumURL {
                    Link("SHA-256 校验文件", destination: checksum)
                }
                Spacer()
                Button("关闭") { dismiss() }
                    .keyboardShortcut(.cancelAction)

                if case let .available(release) = state {
                    if supportsInstallation {
                        Link("下载 ZIP", destination: release.downloadURL)
                            .buttonStyle(.bordered)
                    } else {
                        Link("下载 ZIP", destination: release.downloadURL)
                            .buttonStyle(.borderedProminent)
                    }
                }
                if supportsInstallation {
                    Button("应用内安装…", action: install)
                        .buttonStyle(.borderedProminent)
                }
            }
        }
        .padding(24)
        .frame(width: 600, height: 400)
        .task(id: retryCount) {
            state = .loading
            do {
                let release = try await DesktopReleaseCatalog().latest(includePreview: !supportsInstallation)
                guard !Task.isCancelled else { return }
                state = release.map(UpdateState.available) ?? .unavailable
            } catch {
                guard !Task.isCancelled else { return }
                state = .failed
            }
        }
    }

    @ViewBuilder private var statusContent: some View {
        switch state {
        case .loading:
            ProgressView("正在获取版本…")
        case .unavailable:
            Text("当前没有可下载的 macOS Apple Silicon 安装包。")
                .foregroundStyle(.secondary)
        case .failed:
            VStack(alignment: .leading, spacing: 12) {
                Text("暂时无法获取版本。请检查网络后重试。")
                Button("重试") { retryCount += 1 }
            }
        case let .available(release):
            VStack(alignment: .leading, spacing: 10) {
                Text(verbatim: release.title)
                    .font(.headline)
                HStack {
                    Text(release.isPreview ? "预览版" : "正式版")
                    Text(release.publishedAt, format: .dateTime.year().month().day())
                }
                .font(.caption)
                .foregroundStyle(.secondary)

                ScrollView {
                    Text(verbatim: release.notes.isEmpty ? "此版本暂无更新说明。" : release.notes)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }
}

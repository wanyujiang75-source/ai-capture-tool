import SwiftUI

struct DesktopUpdateView: View {
    private enum UpdateState {
        case loading, available(DesktopRelease), current, unknownVersion, unavailable, failed
    }

    let supportsInstallation: Bool
    let install: () -> Void
    private let installedVersion = InstalledDesktopVersion.read()

    @Environment(\.dismiss) private var dismiss
    @State private var state: UpdateState = .loading
    @State private var retryCount = 0

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text("软件更新")
                    .font(.title2.bold())
                    .accessibilityAddTraits(.isHeader)
                if let version = installedVersion.version {
                    Text("当前版本 \(version.description)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

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
                    if supportsInstallation {
                        Button("应用内安装…", action: install)
                            .buttonStyle(.borderedProminent)
                    }
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
                guard let release else {
                    state = .unavailable
                    return
                }
                switch installedVersion.availability(for: release) {
                case .newer: state = .available(release)
                case .current: state = .current
                case .unknown: state = .unknownVersion
                }
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
        case .current:
            Label("已是最新版", systemImage: "checkmark.circle")
                .font(.headline)
        case .unknownVersion:
            Text("暂时无法比较版本，请查看 GitHub 发布页。")
                .foregroundStyle(.secondary)
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

# Jenkins Package Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Jenkins package source so users can choose latest enterprise build APKs from the macOS desktop app and install them to the selected emulator.

**Architecture:** Backend owns Jenkins API access, artifact download, proxy bypass, and installation. The macOS native app only displays package metadata and calls install APIs. Installation reuses existing package parsing and install helpers.

**Tech Stack:** FastAPI, Python standard library `urllib`, SwiftUI, URLSession.

---

### Task 1: Backend Jenkins Service

**Files:**
- Create: `capture_console/jenkins_source.py`
- Modify: `capture_console/app.py`

- [x] Add a focused Jenkins service that lists jobs, filters enterprise builds, resolves latest installable artifacts, rewrites Jenkins URLs to the configured base URL, downloads artifacts, and bypasses system proxy.
- [x] Add `GET /api/package-sources/jenkins/packages`.
- [x] Add `POST /api/package-sources/jenkins/install`.
- [x] Reuse `collect_uploaded_apks`, `select_base_apk`, and `install_uploaded_package_for_app`.

### Task 2: Native Jenkins UI

**Files:**
- Modify: `macos-native/Sources/AICaptureNativeApp/Models.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/APIClient.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/AppState.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/DeviceAppView.swift`

- [x] Add decodable Jenkins package models.
- [x] Add API client methods for package list and install.
- [x] Add app state for Jenkins loading/installing.
- [x] Add Jenkins package list UI and install buttons.

### Task 3: Verification

**Commands:**
- `python3 -m compileall capture_console`
- `npm --prefix web test`
- `cd macos-native && swift build`
- `curl --noproxy '*' http://127.0.0.1:7001/api/package-sources/jenkins/packages`

- [x] Backend Python compiles.
- [x] Existing frontend tests pass.
- [x] Native app builds.
- [x] Jenkins package API returns installable packages.

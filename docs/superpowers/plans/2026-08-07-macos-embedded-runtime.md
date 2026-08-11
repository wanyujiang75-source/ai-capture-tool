# macOS Embedded Runtime Implementation Plan

**Goal:** Make the desktop App start and run its FastAPI, mitmproxy and Frida client stack without system Python, Node, npm, mitmproxy or Frida CLI.

**Architecture:** Build a relocatable arm64 CPython 3.12 runtime with `uv`, install pinned console dependencies into that interpreter, and copy it under `Contents/Resources/runtime`. Runtime wrappers resolve Python relative to their own bundle path. Swift launches the embedded backend with an explicit environment; source-mode development retains the existing venv path.

## Task 1: Build and embed a relocatable runtime

**Files:**
- Create: `macos-native/scripts/build-runtime.sh`
- Modify: `macos-native/scripts/build-app.sh`
- Modify: `tests/test_native_app_packaging.py`

Acceptance:
- The built App contains `Contents/Resources/runtime/bin/python3`, `uvicorn`, `mitmweb`, `frida`, and `frida-ps`.
- The embedded Python imports `fastapi`, `uvicorn`, `mitmproxy`, and `frida` after the App is copied to a different directory.
- The runtime manifest records Python version, architecture and requirements SHA-256.

## Task 2: Launch the backend without a venv or npm

**Files:**
- Modify: `scripts/start_console.sh`
- Modify: `macos-native/Sources/AICaptureNativeApp/RuntimeManager.swift`
- Modify: `tests/test_console_core.py`
- Modify: `tests/test_native_app_packaging.py`

Acceptance:
- Embedded mode sets `CONSOLE_PYTHON`, `CONSOLE_SKIP_INSTALL=1`, `CONSOLE_USE_EMBEDDED_RUNTIME=1`, `TRACEDECK_RUNTIME_BIN`, `FRIDA_PYTHON_BIN`, and `MITMWEB_BIN`.
- Embedded mode never creates a venv and never invokes pip/npm.
- With a restricted system PATH, the App-bundled backend starts and `/api/status` returns HTTP 200.

## Task 3: Make Environment Doctor reflect desktop dependencies

**Files:**
- Modify: `capture_console/runner.py`
- Modify: `scripts/start_frida_server.sh`
- Modify: `tests/test_console_core.py`
- Modify: `tests/test_console_api.py`

Acceptance:
- Desktop mode treats embedded Python/mitmweb/Frida as required and does not require Node/npm.
- Frida server extraction falls back to Python `lzma`, so Homebrew `xz` is not a desktop blocker.
- Android SDK commands remain external required dependencies.

## Task 4: Own and stop the backend process

**Files:**
- Modify: `macos-native/Sources/AICaptureNativeApp/RuntimeManager.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/AICaptureNativeApp.swift`
- Add/modify native tests as needed under `macos-native/Tests/`

Acceptance:
- RuntimeManager retains the process it starts and writes a project-owned PID record.
- Normal App termination stops only that owned backend process and removes its PID record.
- An already-running external backend is probed but never claimed or killed.

## Phase Verification

```bash
./.venv-console/bin/python -m unittest discover tests
npm --prefix web run build
./macos-native/scripts/build-app.sh
env -i HOME="$HOME" PATH="/usr/bin:/bin" <embedded-runtime-smoke-command>
codesign --verify --deep --strict --verbose=2 "macos-native/build/AI抓包工具.app"
```

Real Apple notarization remains an external credential gate and is not weakened by this phase.

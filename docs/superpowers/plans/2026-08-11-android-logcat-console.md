# Android Logcat Desktop Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the native desktop “日志” placeholder with an automatically managed Android Logcat console covering app, system, and crash logs.

**Architecture:** A new backend `LogcatService` owns one bounded, cursor-based Logcat session per capture device and exposes incremental polling APIs. A dedicated Swift `LogcatController` polls those APIs and drives a three-source `LogsView`; process cleanup is enforced by source switching, device release, backend shutdown, and an inactivity TTL.

**Tech Stack:** Python 3, FastAPI, `subprocess.Popen`, ADB Logcat, Swift 6.2, SwiftUI, URLSession, Python `unittest`, Swift Testing.

---

## File Map

- Create `capture_console/logcat.py`: Logcat parsing, bounded buffers, per-device session state, process supervision, PID reattachment, cleanup.
- Modify `capture_console/runner.py`: expose a safe ADB command prefix and process environment for supervised Logcat processes.
- Modify `capture_console/app.py`: request models, Logcat endpoints, release/shutdown cleanup.
- Create `tests/test_logcat_service.py`: parser, command, cursor, limits, reattachment, isolation and TTL tests.
- Modify `tests/test_console_api.py`: endpoint validation and cleanup integration tests.
- Modify `macos-native/Sources/AICaptureNativeApp/Models.swift`: Logcat request/response models and source/level enums.
- Modify `macos-native/Sources/AICaptureNativeApp/APIClient.swift`: start, poll, clear and stop methods.
- Create `macos-native/Sources/AICaptureNativeApp/LogcatController.swift`: polling lifecycle, pause/resume, filters and bounded client buffer.
- Create `macos-native/Sources/AICaptureNativeApp/LogsView.swift`: native three-source log console.
- Modify `macos-native/Sources/AICaptureNativeApp/ContentView.swift`: route the existing sidebar logs case to `LogsView`.
- Create `macos-native/Tests/AICaptureNativeAppTests/LogcatControllerTests.swift`: decoding, filtering, cursor and cancellation tests.
- Modify `macos-native/Tests/AICaptureNativeAppTests/APIClientTests.swift`: verify Logcat endpoint requests.
- Modify `progress.md`: record task evidence after each acceptance gate.

### Task 1: Logcat parser and bounded session core

**Files:**
- Create: `capture_console/logcat.py`
- Create: `tests/test_logcat_service.py`

- [ ] **Step 1: Write failing parser and bounded-buffer tests**

Create tests for a standard `threadtime` line, a continuation/raw line, cursor ordering, count truncation and byte truncation:

```python
import unittest

from capture_console.logcat import BoundedLogBuffer, parse_threadtime_line


class LogcatParserTests(unittest.TestCase):
    def test_parses_threadtime_entry(self) -> None:
        entry = parse_threadtime_line(
            "08-11 15:24:01.337  2468  2501 E flutter : example message"
        )
        self.assertEqual(
            {
                "timestamp": "08-11 15:24:01.337",
                "pid": 2468,
                "tid": 2501,
                "level": "E",
                "tag": "flutter",
                "message": "example message",
                "raw": "",
            },
            entry,
        )

    def test_buffer_reports_truncation_for_old_cursor(self) -> None:
        buffer = BoundedLogBuffer(max_entries=2, max_bytes=1024)
        for index in range(3):
            buffer.append({"message": f"line-{index}"})
        snapshot = buffer.snapshot(after=0, limit=50)
        self.assertTrue(snapshot["truncated"])
        self.assertEqual([2, 3], [entry["cursor"] for entry in snapshot["entries"]])
        self.assertEqual(3, snapshot["next_cursor"])
```

- [ ] **Step 2: Run the tests and confirm the red state**

Run:

```bash
python -m unittest -v tests.test_logcat_service
```

Expected: import failure because `capture_console.logcat` does not exist.

- [ ] **Step 3: Implement the parser and buffer**

Define these public units in `capture_console/logcat.py`:

```python
THREADTIME_PATTERN = re.compile(
    r"^(?P<timestamp>\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d+)\s+"
    r"(?P<pid>\d+)\s+(?P<tid>\d+)\s+(?P<level>[VDIWEF])\s+"
    r"(?P<tag>.*?)\s*:\s(?P<message>.*)$"
)


def parse_threadtime_line(line: str) -> dict[str, object]:
    match = THREADTIME_PATTERN.match(line.rstrip("\n"))
    if match is None:
        return {
            "timestamp": "",
            "pid": None,
            "tid": None,
            "level": "",
            "tag": "",
            "message": line.rstrip("\n"),
            "raw": line.rstrip("\n"),
        }
    values = match.groupdict()
    return {
        "timestamp": values["timestamp"],
        "pid": int(values["pid"]),
        "tid": int(values["tid"]),
        "level": values["level"],
        "tag": values["tag"].strip(),
        "message": values["message"],
        "raw": "",
    }
```

Implement `BoundedLogBuffer(max_entries=5000, max_bytes=2 * 1024 * 1024)` with a `deque`, monotonic cursor, UTF-8 byte accounting, `append`, `snapshot`, and `clear`. `clear` removes retained entries but never resets the next cursor.

- [ ] **Step 4: Run parser and buffer tests**

Run:

```bash
python -m unittest -v tests.test_logcat_service
```

Expected: parser and buffer tests pass.

- [ ] **Step 5: Commit the core**

```bash
git add capture_console/logcat.py tests/test_logcat_service.py
git commit -m "feat: add bounded logcat stream core"
```

### Task 2: Per-device Logcat process supervision

**Files:**
- Modify: `capture_console/logcat.py`
- Modify: `capture_console/runner.py`
- Modify: `tests/test_logcat_service.py`

- [ ] **Step 1: Add failing command and lifecycle tests**

Use injected `process_factory`, `clock`, and `pid_resolver` fakes. Cover the exact command arrays:

```python
self.assertEqual(
    ["adb", "-s", "emulator-5554", "logcat", "--pid", "2468", "-v", "threadtime"],
    app_command,
)
self.assertEqual(
    ["adb", "-s", "emulator-5554", "logcat", "-v", "threadtime"],
    system_command,
)
self.assertEqual(
    ["adb", "-s", "emulator-5554", "logcat", "-b", "crash", "-v", "threadtime"],
    crash_command,
)
```

Also test:

- starting a second source on `device-1` terminates only the previous `device-1` process;
- `device-2` remains active;
- missing app PID returns `waiting_app` and retries;
- a changed PID creates a replacement app command;
- `reap_idle(now)` stops sessions whose `last_polled_at` exceeds 30 seconds.

- [ ] **Step 2: Run the lifecycle tests and confirm failures**

Run:

```bash
python -m unittest -v tests.test_logcat_service
```

Expected: failures for missing `LogcatService` supervision methods.

- [ ] **Step 3: Implement `LogcatService`**

Use these externally visible methods:

```python
class LogcatService:
    def start(
        self,
        *,
        device_id: str,
        adb_command: list[str],
        process_environment: dict[str, str],
        source: str,
        package_name: str = "",
        pid_resolver: Callable[[str], int | None] | None = None,
    ) -> dict[str, object]: ...

    def poll(self, device_id: str, *, after: int, limit: int) -> dict[str, object]: ...
    def clear(self, device_id: str) -> dict[str, object]: ...
    def stop(self, device_id: str) -> dict[str, object]: ...
    def stop_all(self) -> None: ...
    def reap_idle(self, *, now: float | None = None) -> list[str]: ...
```

Represent sessions with a private dataclass containing source, package, process, reader thread, stop event, buffer, state and last poll time. Termination sequence is `terminate()`, bounded wait, then `kill()` only for the owned child. Reader threads are daemon threads and must stop when their session token is replaced.

Add safe runner accessors:

```python
def adb_command_prefix(self) -> list[str]:
    return [str(self.adb_bin), "-s", self.adb_serial]

def process_environment(self) -> dict[str, str]:
    return self._env()
```

The service receives a complete ADB prefix and process environment and never interpolates package names into a shell command.

- [ ] **Step 4: Verify service isolation and cleanup**

Run:

```bash
python -m unittest -v tests.test_logcat_service
```

Expected: all parser, buffer, command, reattachment, isolation and TTL tests pass.

- [ ] **Step 5: Commit supervision**

```bash
git add capture_console/logcat.py capture_console/runner.py tests/test_logcat_service.py
git commit -m "feat: supervise per-device logcat sessions"
```

### Task 3: FastAPI Logcat API and resource cleanup

**Files:**
- Modify: `capture_console/app.py`
- Modify: `tests/test_console_api.py`

- [ ] **Step 1: Write failing API contract tests**

Cover:

- app source requires `package_name`;
- package validation rejects shell metacharacters;
- offline devices return `409`;
- start/poll/clear/stop return the specified response shape;
- `release_device_runtime(device_id)` calls `logcat_service.stop(device_id)`;
- FastAPI shutdown calls `logcat_service.stop_all()`.

Use a fake service that records full calls, then compare complete dictionaries rather than individual fields.

- [ ] **Step 2: Run focused API tests and confirm failures**

Run:

```bash
python -m unittest -v \
  tests.test_console_api.ConsoleApiTests.test_logcat_app_source_requires_package \
  tests.test_console_api.ConsoleApiTests.test_logcat_lifecycle_is_device_scoped
```

Expected: `404` because the Logcat routes do not exist.

- [ ] **Step 3: Add payload validation and routes**

Add:

```python
class LogcatStartPayload(BaseModel):
    source: str = "app"
    package_name: str = ""
```

Validate sources with `LOGCAT_SOURCES = {"app", "system", "crash"}` and package names with `re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", package_name)`.

Expose:

```python
@app.post("/api/devices/{device_id}/logcat/start")
def api_start_logcat(device_id: str, payload: LogcatStartPayload) -> Dict[str, Any]: ...

@app.get("/api/devices/{device_id}/logcat")
def api_poll_logcat(device_id: str, after: int = 0, limit: int = 500) -> Dict[str, Any]: ...

@app.post("/api/devices/{device_id}/logcat/clear")
def api_clear_logcat(device_id: str) -> Dict[str, Any]: ...

@app.post("/api/devices/{device_id}/logcat/stop")
def api_stop_logcat(device_id: str) -> Dict[str, Any]: ...
```

Clamp `limit` to `1...1000`. Before start, require `emulator_status()["adb_online"]`. Use the selected device runner’s `adb_command_prefix()` and a PID resolver based on `runner.adb(["shell", "pidof", "-s", package_name])`.

Call `logcat_service.stop(device_id)` at the beginning of `release_device_runtime`, and `stop_all()` in the shutdown event. Start one daemon reaper thread at startup that calls `reap_idle()` every five seconds and exits through a shared shutdown event.

- [ ] **Step 4: Run backend tests**

Run:

```bash
python -m unittest -v tests.test_logcat_service tests.test_console_api
```

Expected: all Logcat and existing API tests pass.

- [ ] **Step 5: Commit the API**

```bash
git add capture_console/app.py tests/test_console_api.py
git commit -m "feat: expose device logcat APIs"
```

### Task 4: Native models and API client

**Files:**
- Modify: `macos-native/Sources/AICaptureNativeApp/Models.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/APIClient.swift`
- Modify: `macos-native/Tests/AICaptureNativeAppTests/APIClientTests.swift`

- [ ] **Step 1: Add failing request and decoding tests**

Extend the capturing URL protocol to record method, URL and body. Verify:

```swift
#expect(observedRequest?.httpMethod == "POST")
#expect(observedRequest?.url?.path == "/api/devices/device-1/logcat/start")
#expect(decodedBody.source == "app")
#expect(decodedBody.packageName == "com.example.app")
```

Decode a poll response containing a structured line and assert equality of the complete `LogcatEntry` value.

- [ ] **Step 2: Run Swift tests and confirm failures**

Run:

```bash
swift test --package-path macos-native --filter APIClientTests
```

Expected: compile failures for missing Logcat models and client methods.

- [ ] **Step 3: Add models and client methods**

Define:

```swift
enum LogcatSource: String, Codable, CaseIterable, Identifiable {
    case app
    case system
    case crash
    var id: String { rawValue }
}

struct LogcatEntry: Decodable, Identifiable, Equatable {
    let cursor: Int64
    let timestamp: String
    let pid: Int?
    let tid: Int?
    let level: String
    let tag: String
    let message: String
    let raw: String
    var id: Int64 { cursor }
}
```

Add `LogcatStartPayload`, `LogcatActionResponse` and `LogcatPollResponse` with snake-case coding keys. Add API methods `startLogcat`, `pollLogcat`, `clearLogcat`, and `stopLogcat`; polling uses a 10-second request timeout and URL query items `after` and `limit`.

- [ ] **Step 4: Run native API tests**

Run:

```bash
swift test --package-path macos-native --filter APIClientTests
```

Expected: all API client tests pass.

- [ ] **Step 5: Commit native contracts**

```bash
git add \
  macos-native/Sources/AICaptureNativeApp/Models.swift \
  macos-native/Sources/AICaptureNativeApp/APIClient.swift \
  macos-native/Tests/AICaptureNativeAppTests/APIClientTests.swift
git commit -m "feat: add native logcat API contracts"
```

### Task 5: Native Logcat controller

**Files:**
- Create: `macos-native/Sources/AICaptureNativeApp/LogcatController.swift`
- Create: `macos-native/Tests/AICaptureNativeAppTests/LogcatControllerTests.swift`

- [ ] **Step 1: Write failing controller tests**

Use an actor-backed fake API and Swift’s `Clock` injection. Cover:

- configure starts app logs with the selected package;
- source switch stops the previous stream before starting the next;
- pause keeps a five-second heartbeat, buffers entries without changing the visible list, and resume merges the pending entries while preserving cursor order;
- clear removes displayed entries and adopts the returned cursor;
- minimum level and text search filter correctly;
- stop cancels the polling task.

Compare complete call arrays such as:

```swift
#expect(await fake.calls == [
    .start(deviceID: "device-1", source: .app, packageName: "com.example.app"),
    .poll(deviceID: "device-1", after: 0, limit: 500),
])
```

- [ ] **Step 2: Run the controller tests and confirm the red state**

Run:

```bash
swift test --package-path macos-native --filter LogcatControllerTests
```

Expected: compile failure because `LogcatController` is missing.

- [ ] **Step 3: Implement the controller**

Create a `@MainActor final class LogcatController: ObservableObject` with published `entries`, `source`, `state`, `searchText`, `minimumLevel`, `isPaused`, `autoScroll`, `truncated`, and `message` properties. Keep `pollingTask: Task<Void, Never>?`, `cursor: Int64`, and the current device/package key private.

Use a narrow `LogcatAPI` protocol implemented by `APIClient`, so tests do not need a live backend. Poll every 750 milliseconds while active. While paused, poll every five seconds, advance the cursor, and append to a bounded private `pendingEntries` buffer without changing the visible list; resume merges pending entries in cursor order. Keep at most 5,000 visible plus pending entries client-side. `deinit` cancels the task; explicit `stop()` also calls the backend stop endpoint.

- [ ] **Step 4: Run controller tests**

Run:

```bash
swift test --package-path macos-native --filter LogcatControllerTests
```

Expected: all controller lifecycle and filtering tests pass.

- [ ] **Step 5: Commit the controller**

```bash
git add \
  macos-native/Sources/AICaptureNativeApp/LogcatController.swift \
  macos-native/Tests/AICaptureNativeAppTests/LogcatControllerTests.swift
git commit -m "feat: manage native logcat polling"
```

### Task 6: Build the native Logs tab

**Files:**
- Create: `macos-native/Sources/AICaptureNativeApp/LogsView.swift`
- Modify: `macos-native/Sources/AICaptureNativeApp/ContentView.swift`

- [ ] **Step 1: Replace the placeholder route**

Change only the existing `.logs` route:

```swift
case .logs:
    LogsView()
```

Do not add another sidebar item. Remove `placeholderView` because no navigation case uses it after this change. When the view first appears and the application list is empty, call `appState.refreshDeviceAndApps()` before configuring the controller.

- [ ] **Step 2: Implement the three-source console**

`LogsView` must include:

- device and app pickers bound to `AppState` selections;
- segmented `Picker` for `.app`, `.system`, `.crash`;
- status dot and concise waiting/offline/error copy;
- pause/resume and clear buttons;
- search field, minimum-level menu and auto-scroll toggle;
- a monospaced `LazyVStack` of timestamp, level, PID/TID, tag and message;
- `ScrollViewReader` that follows the newest cursor only when `autoScroll` is enabled and the stream is not paused;
- a local-only sensitive-log notice.

Use `.task(id: selectionKey)` to call controller configuration whenever device, package or source changes. Use `.onDisappear` to cancel client polling; the backend TTL remains the cleanup fallback.

- [ ] **Step 3: Compile and run all Swift tests**

Run:

```bash
swift test --package-path macos-native
```

Expected: all native tests pass and the view compiles under macOS 14.

- [ ] **Step 4: Build the signed app bundle**

Run:

```bash
macos-native/scripts/build-app.sh
codesign --verify --deep --strict --verbose=2 macos-native/build/AI抓包工具.app
```

Expected: build exits zero and code signing reports a valid bundle.

- [ ] **Step 5: Commit the UI**

```bash
git add \
  macos-native/Sources/AICaptureNativeApp/LogsView.swift \
  macos-native/Sources/AICaptureNativeApp/ContentView.swift
git commit -m "feat: add native Android log console"
```

### Task 7: Real-device acceptance and regression

**Files:**
- Modify: `progress.md`

- [ ] **Step 1: Run backend regression**

Run:

```bash
python -m unittest discover -v tests
```

Expected: zero failures.

- [ ] **Step 2: Run native regression and final build**

Run:

```bash
swift test --package-path macos-native
macos-native/scripts/build-app.sh
```

Expected: all Swift tests and the final app build pass.

- [ ] **Step 3: Perform desktop-only functional acceptance**

Using the built `.app`:

1. Start one configured emulator from the desktop UI.
2. Select and launch an installed test App.
3. Open the left “日志” Tab and confirm app entries appear within two seconds.
4. Restart the target App and confirm the log state moves through `waiting_app` and resumes with the new PID.
5. Switch to system and crash sources and verify the backend reports the matching source without duplicate `adb logcat` children.
6. Verify pause/resume, clear, search, level filtering and auto-scroll.
7. Leave the Log tab for more than 30 seconds and confirm the owned Logcat child exits.
8. Start logs again, release the device, and confirm that only that device’s child exits.

- [ ] **Step 4: Record evidence**

Update `progress.md`: set L1, L2 and L3 to `DONE` only when their exact acceptance criteria have passed. Record test counts, tested device serial/package, PID reattachment evidence and post-cleanup process evidence.

- [ ] **Step 5: Commit acceptance evidence**

```bash
git add progress.md
git commit -m "test: verify desktop logcat console"
```

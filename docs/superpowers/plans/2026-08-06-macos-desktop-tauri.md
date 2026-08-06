# macOS Desktop Tauri Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable macOS desktop app for AI抓包工具 using Tauri while reusing the existing React, FastAPI, and capture scripts.

**Architecture:** Tauri owns the native macOS app lifecycle and starts the FastAPI console as a local sidecar on `127.0.0.1`. FastAPI continues to serve the existing React build and execute the existing adb/Frida/mitmproxy scripts. Runtime data moves to macOS Application Support for desktop launches while `./start.sh` remains available for browser mode.

**Tech Stack:** Tauri v2, Rust, React/Vite, FastAPI/uvicorn, Python 3.12+, existing shell/Python capture scripts.

---

## File Structure

- Create `src-tauri/Cargo.toml`: Rust package metadata and Tauri dependencies.
- Create `src-tauri/build.rs`: Tauri build script.
- Create `src-tauri/tauri.conf.json`: macOS app metadata, bundle resources, window, and build config.
- Create `src-tauri/capabilities/default.json`: minimal default capability for the main window.
- Create `src-tauri/src/main.rs`: Tauri app lifecycle, backend process manager, health polling, window navigation, and shutdown cleanup.
- Create `desktop/ui/index.html`: small loading/error page shown while the backend starts.
- Create `desktop/start-backend.sh`: controlled backend launcher used by Tauri and local smoke tests.
- Create `desktop/package-desktop.sh`: repeatable desktop build entrypoint.
- Create `desktop/smoke-backend.sh`: local smoke test for the desktop backend launcher.
- Modify `package.json`: add desktop scripts and Tauri dev dependency.
- Modify `README.md`: document desktop app usage while preserving browser mode.

## Task 1: Desktop Backend Launcher

**Files:**
- Create: `desktop/start-backend.sh`
- Create: `desktop/smoke-backend.sh`

- [ ] **Step 1: Create `desktop/start-backend.sh`**

Create an executable script that accepts `TRACEDECK_ROOT`, `CAPTURE_RUNTIME_DIR`, `TRACEDECK_CONFIG`, `CONSOLE_HOST`, and `CONSOLE_PORT`. It must create a venv under `$CAPTURE_RUNTIME_DIR/desktop-venv`, install `requirements-console.txt` if needed, build `web/dist` if missing, and exec uvicorn:

```bash
exec "$VENV_DIR/bin/uvicorn" capture_console.app:app --host "$CONSOLE_HOST" --port "$CONSOLE_PORT"
```

- [ ] **Step 2: Create `desktop/smoke-backend.sh`**

Create a script that starts `desktop/start-backend.sh` against a temporary runtime directory, waits for `/api/status`, prints the URL, and then kills only the spawned backend pid.

- [ ] **Step 3: Verify launcher**

Run:

```bash
desktop/smoke-backend.sh
```

Expected: prints a `desktop backend smoke ok` line and exits 0.

- [ ] **Step 4: Commit launcher**

```bash
git add desktop/start-backend.sh desktop/smoke-backend.sh
git commit -m "feat: add desktop backend launcher"
```

## Task 2: Tauri Shell

**Files:**
- Create: `src-tauri/Cargo.toml`
- Create: `src-tauri/build.rs`
- Create: `src-tauri/tauri.conf.json`
- Create: `src-tauri/capabilities/default.json`
- Create: `src-tauri/src/main.rs`
- Create: `desktop/ui/index.html`
- Modify: `package.json`

- [ ] **Step 1: Add root `package.json` desktop scripts**

Create or update root `package.json` with scripts:

```json
{
  "scripts": {
    "desktop:dev": "tauri dev",
    "desktop:build": "tauri build -- --bundles app",
    "desktop:smoke-backend": "desktop/smoke-backend.sh"
  },
  "devDependencies": {
    "@tauri-apps/cli": "^2.0.0"
  }
}
```

Preserve existing fields if root `package.json` already exists.

- [ ] **Step 2: Add Tauri config**

Create `src-tauri/tauri.conf.json` with product name `AI抓包工具`, bundle identifier `com.local.ai-capture-tool`, `frontendDist` set to `../desktop/ui`, and bundle resources for `../capture_console`, `../scripts`, `../requirements-console.txt`, `../web/dist`, and `../desktop/start-backend.sh`.

- [ ] **Step 3: Add Rust lifecycle**

Create `src-tauri/src/main.rs` with:

- a `BackendProcess` state containing `child`, `port`, `url`, and `log_path`;
- port selection from `7001..7099`;
- Application Support runtime path creation;
- `desktop/start-backend.sh` spawning with controlled env;
- `/api/status` polling before navigation;
- `main` window navigation to `http://127.0.0.1:<port>/`;
- shutdown that kills only the stored child pid.

- [ ] **Step 4: Add loading UI**

Create `desktop/ui/index.html` with a minimal white loading screen saying the desktop app is starting the local capture service.

- [ ] **Step 5: Verify Tauri compile**

Run:

```bash
npm install
npm run desktop:build
```

Expected: Tauri builds an app bundle or fails only on external macOS signing/notarization constraints. Rust compile errors must be fixed before continuing.

- [ ] **Step 6: Commit Tauri shell**

```bash
git add package.json package-lock.json src-tauri desktop/ui
git commit -m "feat: add tauri desktop shell"
```

## Task 3: Desktop Runtime and Web Compatibility

**Files:**
- Modify: `capture_console/app.py`
- Modify: `capture_console/local_config.py`
- Modify: `web/src/appEnvironment.js` or `web/src/main.jsx`
- Test: `tests/test_console_core.py`
- Test: `tests/test_console_api.py`
- Test: `web/tests/appEnvironment.test.mjs` or a new focused test file

- [ ] **Step 1: Add tests for desktop runtime env**

Add tests proving:

- `TRACEDECK_CONFIG` can point outside the repo.
- `CAPTURE_RUNTIME_DIR` can point outside the repo.
- `/api/status` exposes enough runtime info to tell desktop and browser modes apart.

- [ ] **Step 2: Implement minimal backend runtime metadata**

Add `desktop_mode` and `runtime_dir` metadata to `/api/status` when `TRACEDECK_DESKTOP=1` is present. Do not change existing API fields that current UI depends on.

- [ ] **Step 3: Add desktop UI hint**

Show a compact “桌面端运行” hint when `/api/status` reports desktop mode. Keep browser mode unchanged.

- [ ] **Step 4: Verify compatibility**

Run:

```bash
python -m unittest tests.test_console_core tests.test_console_api
node --test web/tests/*.test.mjs
```

Expected: all tests pass.

- [ ] **Step 5: Commit runtime compatibility**

```bash
git add capture_console web tests
git commit -m "feat: expose desktop runtime status"
```

## Task 4: Desktop Packaging Script and Docs

**Files:**
- Create: `desktop/package-desktop.sh`
- Modify: `README.md`
- Modify: `release/package.sh`

- [ ] **Step 1: Add desktop package script**

Create `desktop/package-desktop.sh` that runs:

```bash
npm --prefix web install
npm --prefix web run build
npm install
npm run desktop:build
```

It must print the generated `.app` path.

- [ ] **Step 2: Update release packaging**

Update `release/package.sh` so desktop source files are included in source releases but runtime data, `target/`, and desktop build artifacts are excluded.

- [ ] **Step 3: Update README**

Document:

- desktop mode: `desktop/package-desktop.sh`;
- browser mode: `./start.sh`;
- where desktop runtime data is stored;
- that Android Studio/SDK/AVD are prerequisites and not bundled;
- that unsigned local builds may require Gatekeeper handling.

- [ ] **Step 4: Verify scripts**

Run:

```bash
bash -n desktop/package-desktop.sh
bash -n release/package.sh
```

Expected: both shell scripts parse cleanly.

- [ ] **Step 5: Commit packaging docs**

```bash
git add desktop/package-desktop.sh README.md release/package.sh
git commit -m "docs: add desktop packaging workflow"
```

## Task 5: Full Verification

**Files:**
- No new files unless a failing test requires a focused fix in a previous scope file.

- [ ] **Step 1: Run backend tests**

```bash
python -m unittest discover tests
```

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend tests**

```bash
node --test web/tests/*.test.mjs
```

Expected: all frontend tests pass.

- [ ] **Step 3: Run frontend build**

```bash
npm --prefix web run build
```

Expected: Vite build succeeds and `web/dist/index.html` exists.

- [ ] **Step 4: Run desktop backend smoke**

```bash
desktop/smoke-backend.sh
```

Expected: `/api/status` responds through a temp desktop runtime.

- [ ] **Step 5: Run desktop build**

```bash
npm run desktop:build
```

Expected: `src-tauri/target/release/bundle/macos/AI抓包工具.app` exists.

- [ ] **Step 6: Inspect git status**

```bash
git status --short
```

Expected: only pre-existing unrelated dirty files remain, or no dirty files if all implementation changes were committed.

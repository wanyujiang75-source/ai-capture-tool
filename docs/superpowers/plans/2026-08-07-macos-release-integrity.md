# macOS Release Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a structurally valid signed development App and a strict Developer ID/notarization pipeline that cannot mislabel an unnotarized build as distributable.

**Architecture:** Assemble all bundle files before signing. `build-app.sh` owns bundle signing and structural verification; `release/package.sh` owns release-kind validation and archive naming; `release/notarize-app.sh` owns Apple notarization and Gatekeeper verification. Development and distribution outputs use distinct names and gates.

**Tech Stack:** Bash, SwiftPM, macOS `codesign`, `security`, `xcrun notarytool`, `stapler`, `spctl`, `ditto`, Python unittest.

---

## Task 1: Sign the complete App bundle

**Files:**
- Modify: `macos-native/scripts/build-app.sh`
- Test: `tests/test_native_app_packaging.py`

- [x] **Step 1: Keep the existing failing integration test**

The test builds the real App and runs:

```python
subprocess.run(
    ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(APP_PATH)],
    capture_output=True,
    text=True,
)
```

The observed failure is `code has no resources but signature indicates they must be present`.

- [x] **Step 2: Sign after all Resources and Info.plist are written**

Append this behavior to `build-app.sh` after `PkgInfo` creation:

```bash
SIGN_IDENTITY="${MACOS_SIGN_IDENTITY:--}"
if [[ "$SIGN_IDENTITY" == "-" ]]; then
  codesign --force --sign - "$APP_DIR"
else
  codesign --force --options runtime --timestamp --sign "$SIGN_IDENTITY" "$APP_DIR"
fi
codesign --verify --deep --strict --verbose=2 "$APP_DIR"
```

- [x] **Step 3: Run the focused test**

Run:

```bash
./.venv-console/bin/python -m unittest tests.test_native_app_packaging
```

Expected: one test passes and `codesign --verify` exits 0.

## Task 2: Add strict release-mode preflight

**Files:**
- Modify: `tests/test_native_app_packaging.py`
- Modify: `release/package.sh`

- [x] **Step 1: Add failing tests for release labels and missing credentials**

Add tests that execute `release/package.sh` with:

```python
env = {**os.environ, "TRACEDECK_RELEASE_KIND": "distribution"}
result = subprocess.run([str(PACKAGE_SCRIPT)], cwd=ROOT, env=env, capture_output=True, text=True)
self.assertNotEqual(0, result.returncode)
self.assertIn("Developer ID Application", result.stderr)
```

Add a development packaging test asserting the resulting archive name contains `development-arm64.zip` and contains `AI抓包工具.app/Contents/MacOS/AI抓包工具`.

- [x] **Step 2: Verify the new tests fail for the intended reasons**

Run:

```bash
./.venv-console/bin/python -m unittest tests.test_native_app_packaging
```

Expected: missing distribution preflight and missing development zip assertions fail.

- [x] **Step 3: Implement release-kind validation before npm/Swift builds**

`release/package.sh` must accept only `development` or `distribution`. Distribution mode requires:

```bash
[[ "$MACOS_SIGN_IDENTITY" == Developer\ ID\ Application:* ]]
[[ -n "$MACOS_NOTARY_PROFILE" ]]
security find-identity -v -p codesigning | grep -F "$MACOS_SIGN_IDENTITY"
```

If any check fails, exit before installing dependencies or writing an archive.

- [x] **Step 4: Generate a distinct development desktop zip**

After building and verifying the App, create:

```bash
ditto -c -k --sequesterRsrc --keepParent \
  "$ROOT_DIR/macos-native/build/AI抓包工具.app" \
  "$ROOT_DIR/release/AI-Capture-Desktop-$VERSION-development-arm64.zip"
```

Keep the existing source tar for compatibility, but print the desktop zip path first.

- [x] **Step 5: Run focused tests**

Expected: development archive test passes; distribution without credentials fails before build with the required message.

## Task 3: Implement notarization as a separate release boundary

**Files:**
- Create: `release/notarize-app.sh`
- Modify: `release/package.sh`
- Modify: `tests/test_native_app_packaging.py`

- [x] **Step 1: Add a failing notary-profile test**

Run `release/notarize-app.sh` without `MACOS_NOTARY_PROFILE` and assert a non-zero result containing `MACOS_NOTARY_PROFILE`.

- [x] **Step 2: Implement the notarization script**

The script must:

1. Verify `MACOS_SIGN_IDENTITY` starts with `Developer ID Application:`.
2. Verify `MACOS_NOTARY_PROFILE` is non-empty.
3. Run `codesign --verify --deep --strict` on the App.
4. Create a temporary submission zip with `ditto`.
5. Run `xcrun notarytool submit ... --keychain-profile "$MACOS_NOTARY_PROFILE" --wait`.
6. Run `xcrun stapler staple` and `xcrun stapler validate` on the App.
7. Run `spctl --assess --type execute --verbose=4`.
8. Create the final distribution zip only after all checks pass.

- [x] **Step 3: Wire distribution packaging**

`release/package.sh` passes the built App, version and output path to `notarize-app.sh`. It must never fall back to development naming after a distribution failure.

- [x] **Step 4: Run focused tests**

Expected: all local tests pass. Real notarization remains skipped until a valid Developer ID identity and Keychain profile exist.

## Task 4: Document and verify release boundaries

**Files:**
- Modify: `README.md`
- Modify: `macos-native/README.md`
- Modify: `tests/test_console_core.py`

- [x] **Step 1: Add script contract assertions**

Assert that source packaging still excludes `runtime`, `config/local.json`, `web/node_modules`, venvs, APKs and capture results. Assert that distribution mode references Developer ID, notarytool, stapler and spctl.

- [x] **Step 2: Document exact commands**

Development:

```bash
TRACEDECK_RELEASE_KIND=development ./release/package.sh
```

Distribution:

```bash
TRACEDECK_RELEASE_KIND=distribution \
MACOS_SIGN_IDENTITY="Developer ID Application: Company Name (TEAMID)" \
MACOS_NOTARY_PROFILE="ai-capture-notary" \
./release/package.sh
```

- [x] **Step 3: Run phase verification**

Run:

```bash
./.venv-console/bin/python -m unittest discover tests
npm --prefix web run build
./macos-native/scripts/build-app.sh
codesign --verify --deep --strict --verbose=2 "macos-native/build/AI抓包工具.app"
TRACEDECK_RELEASE_KIND=development ./release/package.sh
```

Expected: all local commands exit 0; development archive is explicitly labeled; distribution preflight remains intentionally blocked until Developer ID credentials are installed.

## Self-Review

- Spec coverage: complete-bundle signing, development labeling, distribution preflight, notarization, Gatekeeper validation, exclusions and documentation are covered.
- Scope: embedded Python and clean-Mac runtime are intentionally separate implementation plans because they affect runtime execution rather than release integrity.
- Type consistency: environment variables are consistently named `TRACEDECK_RELEASE_KIND`, `MACOS_SIGN_IDENTITY` and `MACOS_NOTARY_PROFILE`.
- Placeholder scan: no unspecified implementation steps remain in this phase.

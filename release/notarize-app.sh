#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${1:-}"
OUTPUT_PATH="${2:-}"
SIGN_IDENTITY="${MACOS_SIGN_IDENTITY:-}"
NOTARY_PROFILE="${MACOS_NOTARY_PROFILE:-}"

fail() {
  echo "$1" >&2
  exit 1
}

[[ "$SIGN_IDENTITY" == Developer\ ID\ Application:* ]] || \
  fail 'notarization requires MACOS_SIGN_IDENTITY="Developer ID Application: Company Name (TEAMID)"'
[[ -n "$NOTARY_PROFILE" ]] || \
  fail "notarization requires MACOS_NOTARY_PROFILE configured with xcrun notarytool store-credentials"
[[ -n "$APP_PATH" && -d "$APP_PATH" ]] || fail "signed App bundle not found: $APP_PATH"
[[ -n "$OUTPUT_PATH" ]] || fail "distribution output path is required"

if ! security find-identity -v -p codesigning | grep -F "$SIGN_IDENTITY" >/dev/null; then
  fail "Developer ID Application identity is not available in the current Keychain: $SIGN_IDENTITY"
fi

codesign --verify --deep --strict --verbose=2 "$APP_PATH"
if ! codesign -d --verbose=4 "$APP_PATH" 2>&1 | grep -F "Authority=$SIGN_IDENTITY" >/dev/null; then
  fail "App bundle is not signed with the configured Developer ID identity: $SIGN_IDENTITY"
fi

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT
SUBMISSION_ZIP="$TEMP_DIR/notary-submission.zip"
FINAL_ZIP="$TEMP_DIR/distribution.zip"
FINAL_CHECKSUM="$TEMP_DIR/distribution.zip.sha256"

ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$SUBMISSION_ZIP"
xcrun notarytool submit "$SUBMISSION_ZIP" \
  --keychain-profile "$NOTARY_PROFILE" \
  --wait
xcrun stapler staple "$APP_PATH"
xcrun stapler validate "$APP_PATH"
codesign --verify --deep --strict --verbose=2 "$APP_PATH"
spctl --assess --type execute --verbose=4 "$APP_PATH"

ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$FINAL_ZIP"
shasum -a 256 "$FINAL_ZIP" >"$FINAL_CHECKSUM"
mkdir -p "$(dirname "$OUTPUT_PATH")"
mv "$FINAL_ZIP" "$OUTPUT_PATH"
mv "$FINAL_CHECKSUM" "$OUTPUT_PATH.sha256"

echo "$OUTPUT_PATH"

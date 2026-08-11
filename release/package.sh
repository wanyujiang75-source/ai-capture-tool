#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${TRACEDECK_VERSION:-$(date +%Y%m%d-%H%M%S)}"
RELEASE_KIND="${TRACEDECK_RELEASE_KIND:-development}"
HOST_ARCH="$(uname -m)"
SIGN_IDENTITY="${MACOS_SIGN_IDENTITY:--}"
NOTARY_PROFILE="${MACOS_NOTARY_PROFILE:-}"
ARCHIVE_NAME="TraceDeck-$VERSION.tar.gz"
ARCHIVE_PATH="$ROOT_DIR/release/$ARCHIVE_NAME"
if [[ "$RELEASE_KIND" == "distribution" ]]; then
  DESKTOP_ARCHIVE_NAME="AI-Capture-Desktop-$VERSION-$HOST_ARCH.zip"
else
  DESKTOP_ARCHIVE_NAME="AI-Capture-Desktop-$VERSION-development-$HOST_ARCH.zip"
fi
DESKTOP_ARCHIVE_PATH="$ROOT_DIR/release/$DESKTOP_ARCHIVE_NAME"

case "$RELEASE_KIND" in
  development)
    ;;
  distribution)
    if [[ "$SIGN_IDENTITY" != Developer\ ID\ Application:* ]]; then
      echo "distribution release requires MACOS_SIGN_IDENTITY=\"Developer ID Application: Company Name (TEAMID)\"" >&2
      exit 1
    fi
    if [[ -z "$NOTARY_PROFILE" ]]; then
      echo "distribution release requires MACOS_NOTARY_PROFILE configured with xcrun notarytool store-credentials" >&2
      exit 1
    fi
    if ! security find-identity -v -p codesigning | grep -F "$SIGN_IDENTITY" >/dev/null; then
      echo "Developer ID Application identity is not available in the current Keychain: $SIGN_IDENTITY" >&2
      exit 1
    fi
    ;;
  *)
    echo "invalid TRACEDECK_RELEASE_KIND: $RELEASE_KIND (expected development or distribution)" >&2
    exit 1
    ;;
esac

if [[ "$HOST_ARCH" != "arm64" ]]; then
  echo "AI抓包工具 V1 desktop release requires Apple Silicon arm64; current architecture: $HOST_ARCH" >&2
  exit 1
fi

if command -v npm >/dev/null 2>&1; then
  (cd "$ROOT_DIR/web" && npm install && npm run build)
fi

if [[ ! -f "$ROOT_DIR/web/dist/index.html" ]]; then
  echo "web/dist is missing; install npm and run npm --prefix web run build before packaging." >&2
  exit 1
fi

if command -v swift >/dev/null 2>&1; then
  (cd "$ROOT_DIR/macos-native" && MACOS_SIGN_IDENTITY="$SIGN_IDENTITY" ./scripts/build-app.sh >/dev/null)
fi

if [[ ! -d "$ROOT_DIR/macos-native/build/AI抓包工具.app" ]]; then
  echo "native macOS app is missing; install Xcode command line tools and run macos-native/scripts/build-app.sh before packaging." >&2
  exit 1
fi

rm -f "$DESKTOP_ARCHIVE_PATH" "$DESKTOP_ARCHIVE_PATH.sha256"
if [[ "$RELEASE_KIND" == "distribution" ]]; then
  "$ROOT_DIR/release/notarize-app.sh" \
    "$ROOT_DIR/macos-native/build/AI抓包工具.app" \
    "$DESKTOP_ARCHIVE_PATH"
else
  ditto -c -k --sequesterRsrc --keepParent \
    "$ROOT_DIR/macos-native/build/AI抓包工具.app" \
    "$DESKTOP_ARCHIVE_PATH"
  shasum -a 256 "$DESKTOP_ARCHIVE_PATH" >"$DESKTOP_ARCHIVE_PATH.sha256"
fi

(
  cd "$ROOT_DIR"
  tar -czf "$ARCHIVE_PATH" \
    --exclude=.git \
    --exclude=.DS_Store \
    --exclude=runtime \
    --exclude=.venv \
    --exclude='.venv-*' \
    --exclude=.venv-console \
    --exclude=.venv-console312 \
    --exclude=web/node_modules \
    --exclude=node_modules \
    --exclude=src-tauri/target \
    --exclude=src-tauri/gen \
    --exclude=macos-native/.build \
    --exclude=macos-native/.swiftpm \
    --exclude=macos-native/build \
    --exclude=config/local.json \
    --exclude='release/*.tar.gz' \
    --exclude='release/*.zip' \
    --exclude='release/*.sha256' \
    README.md \
    setup.sh \
    start.sh \
    start_capture.sh \
    release/package.sh \
    release/notarize-app.sh \
    package.json \
    package-lock.json \
    requirements-console.txt \
    capture_console \
    desktop \
    macos-native \
    scripts \
    src-tauri \
    tools \
    web \
    config/local.example.json \
    config/devices.macmini.json.example \
    docs
)

shasum -a 256 "$ARCHIVE_PATH" >"$ARCHIVE_PATH.sha256"
echo "$DESKTOP_ARCHIVE_PATH"
echo "$ARCHIVE_PATH"

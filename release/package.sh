#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${TRACEDECK_VERSION:-$(date +%Y%m%d-%H%M%S)}"
RELEASE_KIND="${TRACEDECK_RELEASE_KIND:-development}"
HOST_ARCH="$(uname -m)"
SIGN_IDENTITY="${MACOS_SIGN_IDENTITY:--}"
NOTARY_PROFILE="${MACOS_NOTARY_PROFILE:-}"
UPDATE_RELEASES_URL="https://github.com/wanyujiang75-source/ai-capture-tool/releases"
UPDATE_OUTPUT_DIR="$ROOT_DIR/release/.updates/$VERSION"
ARCHIVE_NAME="TraceDeck-$VERSION.tar.gz"
ARCHIVE_PATH="$ROOT_DIR/release/$ARCHIVE_NAME"
if [[ "$RELEASE_KIND" == "distribution" ]]; then
  DESKTOP_ARCHIVE_NAME="AI-Capture-Desktop-$VERSION-$HOST_ARCH.zip"
else
  DESKTOP_ARCHIVE_NAME="AI-Capture-Desktop-$VERSION-development-$HOST_ARCH.zip"
fi
DESKTOP_ARCHIVE_PATH="$ROOT_DIR/release/$DESKTOP_ARCHIVE_NAME"
NATIVE_APP_PATH="$ROOT_DIR/macos-native/build/抓包工具.app"
INSTALL_GUIDE_PATH="$ROOT_DIR/release/安装说明.md"
BREAKPOINT_GUIDE_PATH="$ROOT_DIR/docs/breakpoint-user-guide.md"
USER_GUIDE_PATH="$ROOT_DIR/docs/desktop-user-guide.md"

write_checksum() {
  local target_path="$1"
  local target_dir
  local target_name
  target_dir="$(dirname "$target_path")"
  target_name="$(basename "$target_path")"
  (cd "$target_dir" && shasum -a 256 "$target_name" >"$target_name.sha256")
}

case "$RELEASE_KIND" in
  development)
    ;;
  distribution)
    if [[ -n "${SPARKLE_PRIVATE_ED_KEY_FILE:-}" ]]; then
      if [[ ! -f "$SPARKLE_PRIVATE_ED_KEY_FILE" ]]; then
        echo "Sparkle private key file is missing" >&2
        exit 1
      fi
      private_key_path="$(realpath "$SPARKLE_PRIVATE_ED_KEY_FILE")"
      if [[ "$private_key_path" == "$(cd "$ROOT_DIR" && pwd -P)/"* ]]; then
        echo "Sparkle private key file must be outside the source checkout" >&2
        exit 1
      fi
    fi
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
    if [[ ! "${TRACEDECK_VERSION:-}" =~ ^[0-9]+[.][0-9]+[.][0-9]+$ ||
          ! "${TRACEDECK_BUILD_NUMBER:-}" =~ ^[1-9][0-9]*$ || "$TRACEDECK_BUILD_NUMBER" == "1" ]]; then
      echo "distribution release requires TRACEDECK_VERSION=major.minor.patch and TRACEDECK_BUILD_NUMBER greater than 1" >&2
      exit 1
    fi
    if [[ ! "${SPARKLE_PUBLIC_ED_KEY:-}" =~ ^[a-zA-Z0-9+/]{43}=$ ]]; then
      echo "distribution release requires SPARKLE_PUBLIC_ED_KEY for the Sparkle signing key" >&2
      exit 1
    fi
    if [[ -e "$UPDATE_OUTPUT_DIR" ]]; then
      echo "Update output already exists for this version: $UPDATE_OUTPUT_DIR" >&2
      exit 1
    fi
    ;;
  *)
    echo "invalid TRACEDECK_RELEASE_KIND: $RELEASE_KIND (expected development or distribution)" >&2
    exit 1
    ;;
esac

if [[ "$HOST_ARCH" != "arm64" ]]; then
  echo "抓包工具 V1 desktop release requires Apple Silicon arm64; current architecture: $HOST_ARCH" >&2
  exit 1
fi

if [[ ! -f "$INSTALL_GUIDE_PATH" ]]; then
  echo "desktop install guide is missing: $INSTALL_GUIDE_PATH" >&2
  exit 1
fi
if [[ ! -f "$BREAKPOINT_GUIDE_PATH" ]]; then
  echo "desktop breakpoint guide is missing: $BREAKPOINT_GUIDE_PATH" >&2
  exit 1
fi
if [[ ! -f "$USER_GUIDE_PATH" ]]; then
  echo "desktop user guide is missing: $USER_GUIDE_PATH" >&2
  exit 1
fi

PACKAGE_TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$PACKAGE_TEMP_DIR"' EXIT
PORTABLE_INSTALL_GUIDE_PATH="$PACKAGE_TEMP_DIR/INSTALL.md"
cp "$INSTALL_GUIDE_PATH" "$PORTABLE_INSTALL_GUIDE_PATH"
PORTABLE_BREAKPOINT_GUIDE_PATH="$PACKAGE_TEMP_DIR/BREAKPOINTS.md"
cp "$BREAKPOINT_GUIDE_PATH" "$PORTABLE_BREAKPOINT_GUIDE_PATH"
PORTABLE_USER_GUIDE_PATH="$PACKAGE_TEMP_DIR/USER_GUIDE.md"
cp "$USER_GUIDE_PATH" "$PORTABLE_USER_GUIDE_PATH"

if command -v npm >/dev/null 2>&1; then
  (cd "$ROOT_DIR/web" && npm ci && npm run build)
fi

if [[ ! -f "$ROOT_DIR/web/dist/index.html" ]]; then
  echo "web/dist is missing; install npm and run npm --prefix web run build before packaging." >&2
  exit 1
fi

if [[ "$RELEASE_KIND" == "distribution" ]]; then
  AI_CAPTURE_APP_VERSION="$VERSION" SPARKLE_FEED_URL="$UPDATE_RELEASES_URL/latest/download/appcast.xml" \
    MACOS_SIGN_IDENTITY="$SIGN_IDENTITY" "$ROOT_DIR/macos-native/scripts/build-app.sh" >/dev/null
else
  SPARKLE_FEED_URL="" SPARKLE_PUBLIC_ED_KEY="" \
    MACOS_SIGN_IDENTITY="$SIGN_IDENTITY" "$ROOT_DIR/macos-native/scripts/build-app.sh" >/dev/null
fi

if [[ ! -d "$NATIVE_APP_PATH" ]]; then
  echo "native macOS app is missing; install Xcode command line tools and run macos-native/scripts/build-app.sh before packaging." >&2
  exit 1
fi

rm -f "$DESKTOP_ARCHIVE_PATH" "$DESKTOP_ARCHIVE_PATH.sha256"
if [[ "$RELEASE_KIND" == "distribution" ]]; then
  "$ROOT_DIR/release/notarize-app.sh" \
    "$NATIVE_APP_PATH" \
    "$DESKTOP_ARCHIVE_PATH"
  "$ROOT_DIR/release/build-appcast.sh" "$NATIVE_APP_PATH" "$UPDATE_OUTPUT_DIR" \
    "$UPDATE_RELEASES_URL/download/v$VERSION/"
else
  ditto -c -k --sequesterRsrc --keepParent \
    "$NATIVE_APP_PATH" \
    "$DESKTOP_ARCHIVE_PATH"
fi

/usr/bin/zip -q -j \
  "$DESKTOP_ARCHIVE_PATH" \
  "$INSTALL_GUIDE_PATH" \
  "$PORTABLE_INSTALL_GUIDE_PATH" \
    "$PORTABLE_BREAKPOINT_GUIDE_PATH" \
    "$PORTABLE_USER_GUIDE_PATH"
write_checksum "$DESKTOP_ARCHIVE_PATH"

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
    --exclude=android-bridge/.gradle \
    --exclude=android-bridge/build \
    --exclude=android-bridge/app/build \
    --exclude=android-bridge/local.properties \
    --exclude=config/local.json \
    --exclude='release/*.tar.gz' \
    --exclude='release/*.zip' \
    --exclude='release/*.sha256' \
    README.md \
    INSTALL.md \
    setup.sh \
    start.sh \
    start_capture.sh \
    release/安装说明.md \
    release/package.sh \
    release/notarize-app.sh \
    release/build-appcast.sh \
    release/desktop-preview-ci.py \
    package.json \
    package-lock.json \
    requirements-console.txt \
    requirements-android-physical.txt \
    android-bridge \
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

write_checksum "$ARCHIVE_PATH"
echo "$DESKTOP_ARCHIVE_PATH"
echo "$ARCHIVE_PATH"
if [[ "$RELEASE_KIND" == "distribution" ]]; then
  echo "$UPDATE_OUTPUT_DIR/AI-Capture-Update-$VERSION-arm64.zip"
  echo "$UPDATE_OUTPUT_DIR/appcast.xml"
fi

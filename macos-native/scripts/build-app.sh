#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
APP_NAME="${APP_NAME:-抓包工具}"
CONFIGURATION="${CONFIGURATION:-debug}"
APP_DIR="$ROOT_DIR/build/$APP_NAME.app"
LEGACY_APP_DIR="$ROOT_DIR/build/AI抓包工具.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
BACKEND_DIR="$RESOURCES_DIR/backend"
EMBED_RUNTIME="${EMBED_RUNTIME:-1}"
BUILD_ID="${AI_CAPTURE_BUILD_ID:-}"
APP_VERSION="${AI_CAPTURE_APP_VERSION:-0.1.0}"
APP_BUILD_NUMBER="${TRACEDECK_BUILD_NUMBER:-1}"
SPARKLE_FEED_URL="${SPARKLE_FEED_URL:-}"
SPARKLE_PUBLIC_ED_KEY="${SPARKLE_PUBLIC_ED_KEY:-}"
SPARKLE_ARTIFACTS="$ROOT_DIR/.build/artifacts/sparkle/Sparkle"
ICON_SOURCE="$ROOT_DIR/Resources/AppIcon.png"
ICONSET_DIR="$ROOT_DIR/build/AppIcon.iconset"
ICON_OUTPUT="$RESOURCES_DIR/AppIcon.icns"

if [[ ! -f "$PROJECT_ROOT/web/dist/index.html" ]]; then
  echo "desktop web assets are missing: $PROJECT_ROOT/web/dist/index.html" >&2
  echo "From the project root, run: npm --prefix web ci && npm --prefix web run build" >&2
  exit 1
fi

if [[ ! "$APP_VERSION" =~ ^[0-9]+[.][0-9]+[.][0-9]+$ || ! "$APP_BUILD_NUMBER" =~ ^[1-9][0-9]*$ ]]; then
  echo "App version must be major.minor.patch and build number must be a positive integer" >&2
  exit 1
fi
if [[ -n "$SPARKLE_FEED_URL" || -n "$SPARKLE_PUBLIC_ED_KEY" ]]; then
  if [[ ! "$SPARKLE_FEED_URL" =~ ^https://[a-zA-Z0-9.-]+(:[0-9]+)?/[^[:space:]]+$ ||
        ! "$SPARKLE_PUBLIC_ED_KEY" =~ ^[a-zA-Z0-9+/]{43}=$ ]]; then
    echo "Sparkle requires an HTTPS feed URL and a valid EdDSA public key" >&2
    exit 1
  fi
fi

if [[ -z "$BUILD_ID" ]]; then
  BUILD_ID="$(git -C "$PROJECT_ROOT" rev-parse --short=12 HEAD 2>/dev/null || date +%Y%m%d%H%M%S)"
fi

cd "$ROOT_DIR"
swift build -c "$CONFIGURATION" >/dev/null
BIN_DIR="$(swift build -c "$CONFIGURATION" --show-bin-path)"
EXECUTABLE="$BIN_DIR/$APP_NAME"

SPARKLE_FRAMEWORK_SOURCE="$SPARKLE_ARTIFACTS/Sparkle.xcframework/macos-arm64_x86_64/Sparkle.framework"
if [[ ! -d "$SPARKLE_FRAMEWORK_SOURCE" ]]; then
  echo "Sparkle framework is missing after SwiftPM build" >&2
  exit 1
fi
if [[ ! -x "$EXECUTABLE" ]]; then
  echo "executable not found: $EXECUTABLE" >&2
  exit 1
fi

rm -rf "$APP_DIR"
if [[ "$APP_NAME" == "抓包工具" ]]; then
  rm -rf "$LEGACY_APP_DIR"
fi
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"
cp "$EXECUTABLE" "$MACOS_DIR/$APP_NAME"
SPARKLE_FRAMEWORK="$CONTENTS_DIR/Frameworks/Sparkle.framework"
ditto "$SPARKLE_FRAMEWORK_SOURCE" "$SPARKLE_FRAMEWORK"
cp "$SPARKLE_ARTIFACTS/LICENSE" "$RESOURCES_DIR/Sparkle-LICENSE.txt"
printf '%s\n' "$BUILD_ID" >"$RESOURCES_DIR/backend-build-id.txt"

if [[ ! -f "$ICON_SOURCE" ]]; then
  echo "macOS app icon source not found: $ICON_SOURCE" >&2
  exit 1
fi
for command in sips iconutil; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "required macOS icon tool not found: $command" >&2
    exit 1
  fi
done

rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"
while read -r filename pixels; do
  sips -z "$pixels" "$pixels" "$ICON_SOURCE" \
    --out "$ICONSET_DIR/$filename" >/dev/null
done <<'ICON_SIZES'
icon_16x16.png 16
icon_16x16@2x.png 32
icon_32x32.png 32
icon_32x32@2x.png 64
icon_128x128.png 128
icon_128x128@2x.png 256
icon_256x256.png 256
icon_256x256@2x.png 512
icon_512x512.png 512
icon_512x512@2x.png 1024
ICON_SIZES
iconutil -c icns "$ICONSET_DIR" -o "$ICON_OUTPUT"
rm -rf "$ICONSET_DIR"

mkdir -p "$BACKEND_DIR"
cp -R "$PROJECT_ROOT/capture_console" "$BACKEND_DIR/capture_console"
cp -R "$PROJECT_ROOT/scripts" "$BACKEND_DIR/scripts"
mkdir -p "$BACKEND_DIR/tools"
cp -R "$PROJECT_ROOT/tools/rootAVD" "$BACKEND_DIR/tools/rootAVD"
cp -R "$PROJECT_ROOT/tools/httptoolkit-frida" "$BACKEND_DIR/tools/httptoolkit-frida"
cp "$PROJECT_ROOT/requirements-console.txt" "$BACKEND_DIR/requirements-console.txt"
mkdir -p "$BACKEND_DIR/config" "$BACKEND_DIR/web"
cp "$PROJECT_ROOT/config/local.example.json" "$BACKEND_DIR/config/local.example.json"
cp -R "$PROJECT_ROOT/web/dist" "$BACKEND_DIR/web/dist"
find "$BACKEND_DIR" -name __pycache__ -type d -prune -exec rm -rf {} +
find "$BACKEND_DIR" -name '*.pyc' -delete

if [[ "$EMBED_RUNTIME" == "1" ]]; then
  "$ROOT_DIR/scripts/build-runtime.sh" "$RESOURCES_DIR/runtime" >/dev/null
  EMBEDDED_REQUIREMENTS_FILE="$PROJECT_ROOT/requirements-android-physical.txt" \
    EMBEDDED_RUNTIME_CACHE_DIR="$ROOT_DIR/.build/physical-runtime-cache" \
    "$ROOT_DIR/scripts/build-runtime.sh" "$RESOURCES_DIR/physical-runtime" >/dev/null
  if [[ -n "${ANDROID_BRIDGE_APK_PATH:-}" ]]; then
    cp "$ANDROID_BRIDGE_APK_PATH" "$RESOURCES_DIR/android-bridge.apk"
  else
    bash "$PROJECT_ROOT/android-bridge/build.sh" >/dev/null
    cp "$PROJECT_ROOT/android-bridge/app/build/outputs/apk/debug/app-debug.apk" "$RESOURCES_DIR/android-bridge.apk"
  fi
  cp "$PROJECT_ROOT/android-bridge/README.md" "$RESOURCES_DIR/android-bridge-NOTICE.md"
  cp "$PROJECT_ROOT/android-bridge/LICENSE-Apache-2.0.txt" "$RESOURCES_DIR/android-bridge-LICENSE.txt"
fi

cat >"$CONTENTS_DIR/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>zh_CN</string>
  <key>CFBundleExecutable</key>
  <string>$APP_NAME</string>
  <key>CFBundleIdentifier</key>
  <string>com.local.ai-capture-tool.native</string>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundleDisplayName</key>
  <string>$APP_NAME</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>$APP_VERSION</string>
  <key>CFBundleVersion</key>
  <string>$APP_BUILD_NUMBER</string>
  <key>LSMinimumSystemVersion</key>
  <string>14.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
</dict>
</plist>
PLIST

if [[ -n "$SPARKLE_FEED_URL" ]]; then
  plutil -insert SUFeedURL -string "$SPARKLE_FEED_URL" "$CONTENTS_DIR/Info.plist"
  plutil -insert SUPublicEDKey -string "$SPARKLE_PUBLIC_ED_KEY" "$CONTENTS_DIR/Info.plist"
  plutil -insert SUEnableAutomaticChecks -bool NO "$CONTENTS_DIR/Info.plist"
  plutil -insert SUAllowsAutomaticUpdates -bool NO "$CONTENTS_DIR/Info.plist"
  plutil -insert SUVerifyUpdateBeforeExtraction -bool YES "$CONTENTS_DIR/Info.plist"
  plutil -insert SURequireSignedFeed -bool YES "$CONTENTS_DIR/Info.plist"
fi

printf 'APPL????' >"$CONTENTS_DIR/PkgInfo"

SIGN_IDENTITY="${MACOS_SIGN_IDENTITY:--}"
SIGN_ARGS=(--force --sign "$SIGN_IDENTITY")
if [[ "$SIGN_IDENTITY" != "-" ]]; then
  SIGN_ARGS+=(--options runtime --timestamp)
  if [[ "$EMBED_RUNTIME" == "1" ]]; then
    # Notarization inspects the Mach-O executables and libraries inside Resources too.
    while IFS= read -r -d '' component; do
      if [[ "$(file -b "$component")" == Mach-O* ]]; then
        codesign "${SIGN_ARGS[@]}" --preserve-metadata=identifier,entitlements "$component"
      fi
    done < <(find "$RESOURCES_DIR/runtime" "$RESOURCES_DIR/physical-runtime" -type f \
      \( -perm -111 -o -name '*.so' -o -name '*.dylib' \) -print0)
  fi
fi
SPARKLE_VERSION_DIR="$SPARKLE_FRAMEWORK/Versions/Current"
for component in "$SPARKLE_VERSION_DIR/Autoupdate" "$SPARKLE_VERSION_DIR/Updater.app" "$SPARKLE_VERSION_DIR"/XPCServices/*.xpc; do
  codesign "${SIGN_ARGS[@]}" --preserve-metadata=identifier,entitlements "$component"
done
codesign "${SIGN_ARGS[@]}" "$SPARKLE_FRAMEWORK"
codesign "${SIGN_ARGS[@]}" "$APP_DIR"
codesign --verify --deep --strict --verbose=2 "$APP_DIR"

echo "$APP_DIR"

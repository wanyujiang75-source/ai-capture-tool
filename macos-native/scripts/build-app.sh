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
ICON_SOURCE="$ROOT_DIR/Resources/AppIcon.png"
ICONSET_DIR="$ROOT_DIR/build/AppIcon.iconset"
ICON_OUTPUT="$RESOURCES_DIR/AppIcon.icns"

cd "$ROOT_DIR"
swift build -c "$CONFIGURATION" >/dev/null
BIN_DIR="$(swift build -c "$CONFIGURATION" --show-bin-path)"
EXECUTABLE="$BIN_DIR/$APP_NAME"

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
if [[ -d "$PROJECT_ROOT/web/dist" ]]; then
  cp -R "$PROJECT_ROOT/web/dist" "$BACKEND_DIR/web/dist"
fi
find "$BACKEND_DIR" -name __pycache__ -type d -prune -exec rm -rf {} +
find "$BACKEND_DIR" -name '*.pyc' -delete

if [[ "$EMBED_RUNTIME" == "1" ]]; then
  "$ROOT_DIR/scripts/build-runtime.sh" "$RESOURCES_DIR/runtime" >/dev/null
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
  <string>0.1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>14.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
</dict>
</plist>
PLIST

printf 'APPL????' >"$CONTENTS_DIR/PkgInfo"

SIGN_IDENTITY="${MACOS_SIGN_IDENTITY:--}"
if [[ "$SIGN_IDENTITY" == "-" ]]; then
  codesign --force --sign - "$APP_DIR"
else
  codesign --force --options runtime --timestamp --sign "$SIGN_IDENTITY" "$APP_DIR"
fi
codesign --verify --deep --strict --verbose=2 "$APP_DIR"

echo "$APP_DIR"

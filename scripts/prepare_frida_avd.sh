#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}"
AVD_HOME="${ANDROID_AVD_HOME:-$HOME/.android/avd}"
AVD_NAME="${ANDROID_CAPTURE_AVD:?ANDROID_CAPTURE_AVD is required}"
ADB_SERIAL="${ADB_SERIAL:?ADB_SERIAL is required}"
RUNTIME_DIR="${RUNTIME_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)/runtime}"
PYTHON_BIN="${FRIDA_PYTHON_BIN:-$(command -v python3 || true)}"
ROOTAVD_SOURCE="$SCRIPT_DIR/../tools/rootAVD"
TOOLS_ROOT="$(dirname "$RUNTIME_DIR")/tools"
DOWNLOAD_DIR="$TOOLS_ROOT/downloads"
AVD_CONFIG="$AVD_HOME/$AVD_NAME.avd/config.ini"
SAFE_AVD_NAME="$(printf '%s' "$AVD_NAME" | tr -c 'A-Za-z0-9_.-' '_')"
OVERLAY_REL=".ai-capture/system-images/$SAFE_AVD_NAME"
OVERLAY_DIR="$SDK_ROOT/$OVERLAY_REL"
MARKER_FILE="$OVERLAY_DIR/.frida-bootstrap"
MAGISK_VERSION="30.7"
MAGISK_URL="https://github.com/topjohnwu/Magisk/releases/download/v${MAGISK_VERSION}/Magisk-v${MAGISK_VERSION}.apk"
MAGISK_SHA256="e0d32d2123532860f97123d927b1bb86c4e08e6fd8a48bfc6b5bee0afae9ebd5"
MAGISK_APK="$DOWNLOAD_DIR/Magisk-v${MAGISK_VERSION}.apk"
ROOTAVD_BOOTSTRAP_VERSION="2"

require_command "$ADB_BIN"
require_command curl
if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "embedded Python is unavailable for Frida ramdisk bootstrap" >&2
  exit 1
fi
if [[ ! -f "$AVD_CONFIG" ]]; then
  echo "AVD config not found: $AVD_CONFIG" >&2
  exit 1
fi
if [[ ! -f "$ROOTAVD_SOURCE/rootAVD.sh" || ! -f "$ROOTAVD_SOURCE/frida.rc" || ! -f "$ROOTAVD_SOURCE/sbin/ai-capture-root-grant.sh" ]]; then
  echo "rootAVD bootstrap assets are missing from the desktop application" >&2
  exit 1
fi

read_config_value() {
  "$PYTHON_BIN" - "$AVD_CONFIG" "$1" <<'PY'
import sys

path, wanted = sys.argv[1:]
for line in open(path, encoding="utf-8"):
    key, separator, value = line.partition("=")
    if separator and key.strip() == wanted:
        print(value.strip())
        break
PY
}

write_image_sysdir() {
  "$PYTHON_BIN" - "$AVD_CONFIG" "$OVERLAY_REL/" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
value = sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines()
updated = []
written = False
for line in lines:
    if line.partition("=")[0].strip() == "image.sysdir.1":
        if not written:
            updated.append(f"image.sysdir.1={value}")
            written = True
    else:
        updated.append(line)
if not written:
    updated.append(f"image.sysdir.1={value}")
path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
}

CURRENT_SYS_DIR="$(read_config_value image.sysdir.1)"
if [[ -z "$CURRENT_SYS_DIR" ]]; then
  echo "image.sysdir.1 is missing from $AVD_CONFIG" >&2
  exit 1
fi
if [[ "$CURRENT_SYS_DIR" == "$OVERLAY_REL/" && -f "$OVERLAY_DIR/.source-sysdir" ]]; then
  SOURCE_SYS_DIR="$(cat "$OVERLAY_DIR/.source-sysdir")"
else
  SOURCE_SYS_DIR="${CURRENT_SYS_DIR%/}"
fi
SOURCE_DIR="$SDK_ROOT/$SOURCE_SYS_DIR"
if [[ ! -f "$SOURCE_DIR/ramdisk.img" ]]; then
  echo "source system image ramdisk not found: $SOURCE_DIR/ramdisk.img" >&2
  exit 1
fi

RC_SHA256="$(shasum -a 256 "$ROOTAVD_SOURCE/frida.rc" | awk '{print $1}')"
ROOT_GRANT_SHA256="$(shasum -a 256 "$ROOTAVD_SOURCE/sbin/ai-capture-root-grant.sh" | awk '{print $1}')"
EXPECTED_MARKER="bootstrap=$ROOTAVD_BOOTSTRAP_VERSION rc=$RC_SHA256 root_grant=$ROOT_GRANT_SHA256 magisk=$MAGISK_VERSION"
if [[ -f "$MARKER_FILE" ]] && grep -Fx "$EXPECTED_MARKER" "$MARKER_FILE" >/dev/null 2>&1; then
  write_image_sysdir
  echo "isolated Frida ramdisk already prepared: $OVERLAY_DIR/ramdisk.img"
  exit 0
fi

mkdir -p "$DOWNLOAD_DIR"
if [[ ! -f "$MAGISK_APK" ]] || ! echo "$MAGISK_SHA256  $MAGISK_APK" | shasum -a 256 -c - >/dev/null 2>&1; then
  rm -f "$MAGISK_APK"
  curl -fL --retry 3 "$MAGISK_URL" -o "$MAGISK_APK"
  echo "$MAGISK_SHA256  $MAGISK_APK" | shasum -a 256 -c - >/dev/null
fi

ROOTAVD_TEMP_ROOT="${TMPDIR:-/tmp}"
case "$ROOTAVD_TEMP_ROOT" in
  *[[:space:]]*) ROOTAVD_TEMP_ROOT="/tmp" ;;
esac
ROOTAVD_WORK="$(mktemp -d "$ROOTAVD_TEMP_ROOT/ai-capture-rootavd.XXXXXX")"
trap 'rm -rf "$ROOTAVD_WORK"' EXIT
mkdir -p "$ROOTAVD_WORK/Apps" "$ROOTAVD_WORK/sbin" "$ROOTAVD_WORK/bin"
cp "$ROOTAVD_SOURCE/rootAVD.sh" "$ROOTAVD_WORK/rootAVD.sh"
cp "$ROOTAVD_SOURCE/frida.rc" "$ROOTAVD_WORK/frida.rc"
cp "$ROOTAVD_SOURCE/sbin/ai-capture-root-grant.sh" "$ROOTAVD_WORK/sbin/ai-capture-root-grant.sh"
cp "$MAGISK_APK" "$ROOTAVD_WORK/Magisk.zip"
chmod 755 "$ROOTAVD_WORK/rootAVD.sh" "$ROOTAVD_WORK/sbin/ai-capture-root-grant.sh"

cat >"$ROOTAVD_WORK/bin/adb" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  devices|start-server|kill-server|version)
    exec "$AI_CAPTURE_REAL_ADB" "$@"
    ;;
  *)
    exec "$AI_CAPTURE_REAL_ADB" -s "$AI_CAPTURE_ADB_SERIAL" "$@"
    ;;
esac
SH
chmod 755 "$ROOTAVD_WORK/bin/adb"

rm -rf "$OVERLAY_DIR"
mkdir -p "$OVERLAY_DIR"
for source_file in "$SOURCE_DIR"/*; do
  filename="$(basename "$source_file")"
  case "$filename" in
    ramdisk.img|ramdisk.img.backup)
      continue
      ;;
  esac
  ln -s "$source_file" "$OVERLAY_DIR/$filename"
done
cp "$SOURCE_DIR/ramdisk.img" "$OVERLAY_DIR/ramdisk.img"
printf '%s\n' "$SOURCE_SYS_DIR" >"$OVERLAY_DIR/.source-sysdir"

export ANDROID_HOME="$SDK_ROOT"
export AI_CAPTURE_REAL_ADB="$ADB_BIN"
export AI_CAPTURE_ADB_SERIAL="$ADB_SERIAL"
export PATH="$ROOTAVD_WORK/bin:$PATH"
printf '1\n' | "$ROOTAVD_WORK/rootAVD.sh" "$OVERLAY_REL/ramdisk.img" AddRCscripts

if [[ ! -f "$OVERLAY_DIR/ramdisk.img" ]]; then
  echo "rootAVD did not produce the isolated ramdisk" >&2
  exit 1
fi
printf '%s\n' "$EXPECTED_MARKER" >"$MARKER_FILE"
write_image_sysdir
echo "prepared isolated Frida ramdisk: $OVERLAY_DIR/ramdisk.img"

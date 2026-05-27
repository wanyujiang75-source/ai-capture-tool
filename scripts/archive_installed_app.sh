#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

PACKAGE_NAME="${1:-}"
ARCHIVE_NAME="${2:-}"
RUNTIME_DIR="${RUNTIME_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)/runtime}"
ARCHIVE_ROOT="${ARCHIVE_ROOT:-$RUNTIME_DIR/apks}"

require_command "$ADB_BIN"

if [[ -z "$PACKAGE_NAME" ]]; then
  echo "usage: $0 <package-name> [archive-name]" >&2
  exit 1
fi

resolve_adb_serial

if [[ -z "$ARCHIVE_NAME" ]]; then
  ARCHIVE_NAME="${PACKAGE_NAME##*.}"
fi

DEST_DIR="$ARCHIVE_ROOT/$ARCHIVE_NAME"
TMP_DIR="$DEST_DIR.tmp"
META_FILE="$DEST_DIR/metadata.txt"

PACKAGE_PATHS=()
while IFS= read -r package_path; do
  [[ -n "$package_path" ]] || continue
  PACKAGE_PATHS+=("$package_path")
done < <(
  adb_cmd shell pm path "$PACKAGE_NAME" 2>/dev/null \
    | tr -d '\r' \
    | sed -n 's/^package://p'
)

if (( ${#PACKAGE_PATHS[@]} == 0 )); then
  echo "package not found on device: $PACKAGE_NAME" >&2
  exit 1
fi

mkdir -p "$ARCHIVE_ROOT"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

for apk_path in "${PACKAGE_PATHS[@]}"; do
  apk_name="$(basename "$apk_path")"
  adb_cmd pull "$apk_path" "$TMP_DIR/$apk_name" >/dev/null
done

VERSION_NAME="$(
  adb_cmd shell dumpsys package "$PACKAGE_NAME" 2>/dev/null \
    | tr -d '\r' \
    | sed -n 's/^[[:space:]]*versionName=//p' \
    | head -n 1
)"
VERSION_CODE="$(
  adb_cmd shell dumpsys package "$PACKAGE_NAME" 2>/dev/null \
    | tr -d '\r' \
    | sed -n 's/^[[:space:]]*versionCode=\([0-9][0-9]*\).*/\1/p' \
    | head -n 1
)"
MAIN_ACTIVITY="$(
  adb_cmd shell cmd package resolve-activity --brief "$PACKAGE_NAME" 2>/dev/null \
    | tr -d '\r' \
    | tail -n 1
)"
ARCHIVED_AT="$(date '+%Y-%m-%d %H:%M:%S %Z')"

{
  printf 'archive_name=%s\n' "$ARCHIVE_NAME"
  printf 'package_name=%s\n' "$PACKAGE_NAME"
  printf 'adb_serial=%s\n' "$ADB_SERIAL"
  printf 'archived_at=%s\n' "$ARCHIVED_AT"
  printf 'version_name=%s\n' "$VERSION_NAME"
  printf 'version_code=%s\n' "$VERSION_CODE"
  printf 'main_activity=%s\n' "$MAIN_ACTIVITY"
  printf 'apk_count=%s\n' "${#PACKAGE_PATHS[@]}"
  printf 'apk_files='
  printf '%s ' "$(cd "$TMP_DIR" && ls -1 *.apk | LC_ALL=C sort)"
  printf '\n'
} >"$TMP_DIR/metadata.txt"

rm -rf "$DEST_DIR"
mv "$TMP_DIR" "$DEST_DIR"

echo "archived $PACKAGE_NAME to $DEST_DIR"
echo "apk count: ${#PACKAGE_PATHS[@]}"
if [[ -n "$VERSION_NAME" || -n "$VERSION_CODE" ]]; then
  echo "version: ${VERSION_NAME:-unknown} (${VERSION_CODE:-unknown})"
fi
if [[ -n "$MAIN_ACTIVITY" ]]; then
  echo "activity: $MAIN_ACTIVITY"
fi
echo "metadata: $META_FILE"

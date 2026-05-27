#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

ARCHIVE_NAME="${1:-}"
RUNTIME_DIR="${RUNTIME_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)/runtime}"
ARCHIVE_ROOT="${ARCHIVE_ROOT:-$RUNTIME_DIR/apks}"

require_command "$ADB_BIN"

if [[ -z "$ARCHIVE_NAME" ]]; then
  echo "usage: $0 <archive-name>" >&2
  exit 1
fi

ARCHIVE_DIR="$ARCHIVE_ROOT/$ARCHIVE_NAME"
if [[ ! -d "$ARCHIVE_DIR" ]]; then
  echo "archive not found: $ARCHIVE_DIR" >&2
  exit 1
fi

resolve_adb_serial
adb_wait_for_device 120

APK_FILES=()
while IFS= read -r apk_file; do
  [[ -n "$apk_file" ]] || continue
  APK_FILES+=("$apk_file")
done < <(
  find "$ARCHIVE_DIR" -maxdepth 1 -type f -name '*.apk' -print \
    | LC_ALL=C sort
)

if (( ${#APK_FILES[@]} == 0 )); then
  echo "no apk files found in archive: $ARCHIVE_DIR" >&2
  exit 1
fi

if [[ -f "$ARCHIVE_DIR/base.apk" ]]; then
  ORDERED_APKS=("$ARCHIVE_DIR/base.apk")
  for apk_file in "${APK_FILES[@]}"; do
    [[ "$apk_file" == "$ARCHIVE_DIR/base.apk" ]] && continue
    ORDERED_APKS+=("$apk_file")
  done
else
  ORDERED_APKS=("${APK_FILES[@]}")
fi

adb_cmd install-multiple -r "${ORDERED_APKS[@]}"

META_FILE="$ARCHIVE_DIR/metadata.txt"
if [[ -f "$META_FILE" ]]; then
  PACKAGE_NAME="$(
    sed -n 's/^package_name=//p' "$META_FILE" | head -n 1
  )"
  MAIN_ACTIVITY="$(
    sed -n 's/^main_activity=//p' "$META_FILE" | head -n 1
  )"
  [[ -n "$PACKAGE_NAME" ]] && echo "installed package: $PACKAGE_NAME"
  [[ -n "$MAIN_ACTIVITY" ]] && echo "activity: $MAIN_ACTIVITY"
fi

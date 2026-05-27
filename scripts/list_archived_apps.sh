#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_DIR="${RUNTIME_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)/runtime}"
ARCHIVE_ROOT="${ARCHIVE_ROOT:-$RUNTIME_DIR/apks}"

if [[ ! -d "$ARCHIVE_ROOT" ]]; then
  echo "no archived apps under $ARCHIVE_ROOT"
  exit 0
fi

found=0
for archive_dir in "$ARCHIVE_ROOT"/*; do
  [[ -d "$archive_dir" ]] || continue
  found=1
  archive_name="$(basename "$archive_dir")"
  meta_file="$archive_dir/metadata.txt"
  if [[ -f "$meta_file" ]]; then
    package_name="$(sed -n 's/^package_name=//p' "$meta_file" | head -n 1)"
    version_name="$(sed -n 's/^version_name=//p' "$meta_file" | head -n 1)"
    version_code="$(sed -n 's/^version_code=//p' "$meta_file" | head -n 1)"
    archived_at="$(sed -n 's/^archived_at=//p' "$meta_file" | head -n 1)"
    apk_count="$(sed -n 's/^apk_count=//p' "$meta_file" | head -n 1)"
    printf '%s\t%s\t%s (%s)\t%s apks\t%s\n' \
      "$archive_name" \
      "${package_name:-unknown}" \
      "${version_name:-unknown}" \
      "${version_code:-unknown}" \
      "${apk_count:-0}" \
      "${archived_at:-unknown}"
  else
    apk_count="$(find "$archive_dir" -maxdepth 1 -type f -name '*.apk' | wc -l | tr -d ' ')"
    printf '%s\t%s\t%s\n' "$archive_name" "metadata-missing" "${apk_count} apks"
  fi
done

if [[ "$found" == 0 ]]; then
  echo "no archived apps under $ARCHIVE_ROOT"
fi

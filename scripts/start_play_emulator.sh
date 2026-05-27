#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

AVD_NAME="${1:-${PLAY_AVD_NAME:-$ANDROID_CAPTURE_AVD}}"

echo "start_play_emulator.sh is a compatibility entrypoint."
echo "using retained Android capture AVD: $AVD_NAME"
echo

"$SCRIPT_DIR/start_lab_emulator.sh" "$AVD_NAME"

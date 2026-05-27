#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

AVD_NAME="${1:-$ANDROID_CAPTURE_AVD}"

"$SCRIPT_DIR/start_lab_emulator.sh" "$AVD_NAME"

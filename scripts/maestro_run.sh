#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

AVD_NAME="${AVD_NAME:-$ANDROID_CAPTURE_AVD}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-240}"
FLOW="${1:-$ROOT_DIR/maestro/flows/open-chrome-example.yaml}"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export MAESTRO_CLI_NO_ANALYTICS="${MAESTRO_CLI_NO_ANALYTICS:-1}"
export MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED="${MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED:-true}"

require_command maestro
require_command "$ADB_BIN"

if [[ ! -f "$FLOW" && ! -d "$FLOW" ]]; then
  echo "Maestro flow not found: $FLOW" >&2
  exit 1
fi

if ! pgrep -af "emulator.*-avd ${AVD_NAME}" >/dev/null 2>&1; then
  "$SCRIPT_DIR/start_android_emulator.sh" "$AVD_NAME"
fi

wait_for_adb_serial_for_avd "$AVD_NAME" "$BOOT_TIMEOUT"
adb_cmd wait-for-device
wait_for_property sys.boot_completed 1 "$BOOT_TIMEOUT"

echo "maestro device: $ADB_SERIAL"
echo "maestro flow: $FLOW"
maestro test --device "$ADB_SERIAL" "$FLOW"

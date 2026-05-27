#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

AVD_NAME="${1:-${PLAY_AVD_NAME:-$ANDROID_CAPTURE_AVD}}"
PROXY_PORT="${PROXY_PORT:-9090}"
WEB_PORT="${WEB_PORT:-9091}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-240}"
OPEN_UI="${OPEN_UI:-0}"

echo "play_capture_up.sh is a compatibility entrypoint."
echo "using retained Android capture AVD: $AVD_NAME"
echo

require_command "$ADB_BIN"
require_command lsof

if ! pgrep -af "emulator.*-avd ${AVD_NAME}" >/dev/null 2>&1; then
  "$SCRIPT_DIR/start_lab_emulator.sh" "$AVD_NAME"
fi

if ! lsof -iTCP:"$PROXY_PORT" -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  PROXY_PORT="$PROXY_PORT" WEB_PORT="$WEB_PORT" "$SCRIPT_DIR/start_mitm_stack.sh"
fi

wait_for_adb_serial_for_avd "$AVD_NAME" "$BOOT_TIMEOUT"
adb_cmd wait-for-device
wait_for_property sys.boot_completed 1 "$BOOT_TIMEOUT"
wait_for_listen_port "$PROXY_PORT" 30
wait_for_listen_port "$WEB_PORT" 30

PROXY_PORT="$PROXY_PORT" "$SCRIPT_DIR/apply_android_proxy.sh"
if [[ "$OPEN_UI" == "1" ]]; then
  "$SCRIPT_DIR/open_proxy_ui.sh"
fi

echo
echo "android serial: $ADB_SERIAL"
echo "proxy ui: http://127.0.0.1:$WEB_PORT/?token=${MITMWEB_PASSWORD:-android-capture}"
echo "note: Google Play AVDs are non-root production builds; HTTPS decryption may require installing the mitmproxy user CA in Android Settings."

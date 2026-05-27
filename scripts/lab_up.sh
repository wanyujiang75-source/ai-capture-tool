#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

AVD_NAME="${1:-${AVD_NAME:-$ANDROID_CAPTURE_AVD}}"
PROXY_PORT="${PROXY_PORT:-9090}"
WEB_PORT="${WEB_PORT:-9091}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-240}"

require_command "$ADB_BIN"
require_command lsof

if ! pgrep -af "emulator.*-avd ${AVD_NAME}" >/dev/null 2>&1; then
  "$SCRIPT_DIR/start_lab_emulator.sh" "$AVD_NAME"
fi

if ! lsof -iTCP:"$PROXY_PORT" -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  "$SCRIPT_DIR/start_mitm_stack.sh"
fi

if [[ -z "${ADB_SERIAL:-}" ]]; then
  wait_for_adb_serial_for_avd "$AVD_NAME" "$BOOT_TIMEOUT"
fi

wait_for_listen_port "$PROXY_PORT" 30
wait_for_listen_port "$WEB_PORT" 30
wait_for_boot_completed "$BOOT_TIMEOUT"

echo "android serial: $(adb_get_serial)"

PROXY_PORT="$PROXY_PORT" "$SCRIPT_DIR/apply_android_proxy.sh"
root_output="$(adb_cmd root 2>&1 || true)"
if [[ "$root_output" == *"cannot run as root"* ]]; then
  echo "system CA skipped: $AVD_NAME is a non-root Google Play build"
  echo "install user CA manually if HTTPS decryption is required:"
  echo "  $SCRIPT_DIR/install_play_user_ca.sh"
else
  wait_for_adb_serial_for_avd "$AVD_NAME" "$BOOT_TIMEOUT"
  "$SCRIPT_DIR/install_mitm_system_ca.sh"
  PROXY_PORT="$PROXY_PORT" WEB_PORT="$WEB_PORT" "$SCRIPT_DIR/verify_lab.sh"
fi

echo
echo "lab is ready"
echo "proxy ui: http://127.0.0.1:$WEB_PORT/?token=${MITMWEB_PASSWORD:-android-capture}"

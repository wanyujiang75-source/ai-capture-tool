#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

FORWARD_PORT="${FORWARD_PORT:-27042}"
DEVICE_BIN="/data/local/tmp/frida-server"
SCREEN_SESSION="frida-server"

require_command "$ADB_BIN"

adb_root_wait
screen -S "$SCREEN_SESSION" -X quit >/dev/null 2>&1 || true
if adb_cmd shell "su -c id" 2>/dev/null | tr -d '\r' | grep -q 'uid=0'; then
  adb_cmd shell "su -c \"pkill -f '/data/local/tmp/[f]rida-server' >/dev/null 2>&1 || true\""
else
  adb_cmd shell "pkill -f '/data/local/tmp/[f]rida-server' >/dev/null 2>&1 || true"
fi
adb_cmd forward --remove "tcp:${FORWARD_PORT}" >/dev/null 2>&1 || true

echo "stopped frida server on: $(adb_get_serial)"

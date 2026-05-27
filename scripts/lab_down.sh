#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

PROXY_PORT="${PROXY_PORT:-9090}"
STOP_EMULATOR="${STOP_EMULATOR:-0}"
SCREEN_SESSION="mitmweb-${PROXY_PORT}"
FRIDA_SCREEN_SESSION="frida-server"

require_command "$ADB_BIN"

if "$ADB_BIN" devices | awk 'NR > 1 && $2 == "device" { found = 1 } END { exit(found ? 0 : 1) }'; then
  resolve_adb_serial
  adb_cmd shell settings put global http_proxy :0 >/dev/null
  adb_cmd shell "pkill -f '/data/local/tmp/[f]rida-server' >/dev/null 2>&1 || true"
  adb_cmd forward --remove tcp:27042 >/dev/null 2>&1 || true
  echo "cleared Android proxy on: $(adb_get_serial)"
  if [[ "$STOP_EMULATOR" == "1" ]]; then
    adb_cmd emu kill >/dev/null || true
    echo "requested emulator shutdown"
  fi
else
  echo "no online adb device found; skipped Android cleanup"
fi

if lsof -iTCP:"$PROXY_PORT" -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  lsof -tiTCP:"$PROXY_PORT" -sTCP:LISTEN -n -P | xargs kill >/dev/null 2>&1 || true
  screen -S "$SCREEN_SESSION" -X quit >/dev/null 2>&1 || true
  screen -S "$FRIDA_SCREEN_SESSION" -X quit >/dev/null 2>&1 || true
  echo "stopped mitmweb on port $PROXY_PORT"
else
  screen -S "$SCREEN_SESSION" -X quit >/dev/null 2>&1 || true
  screen -S "$FRIDA_SCREEN_SESSION" -X quit >/dev/null 2>&1 || true
  echo "mitmweb not listening on port $PROXY_PORT"
fi

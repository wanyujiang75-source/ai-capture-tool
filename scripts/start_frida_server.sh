#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

RUNTIME_DIR="${RUNTIME_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)/runtime}"
DEFAULT_TOOLS_DIR="$(dirname "$RUNTIME_DIR")/tools/frida"
TOOLS_DIR="${TOOLS_DIR:-$DEFAULT_TOOLS_DIR}"
FRIDA_VERSION="${FRIDA_VERSION:-$(frida --version)}"
FRIDA_ARCH="${FRIDA_ARCH:-android-arm64}"
FRIDA_ASSET="frida-server-${FRIDA_VERSION}-${FRIDA_ARCH}.xz"
FRIDA_URL="https://github.com/frida/frida/releases/download/${FRIDA_VERSION}/${FRIDA_ASSET}"
FRIDA_XZ="$TOOLS_DIR/$FRIDA_ASSET"
FRIDA_BIN="$TOOLS_DIR/frida-server-${FRIDA_VERSION}-${FRIDA_ARCH}"
DEVICE_BIN="/data/local/tmp/frida-server"
FORWARD_PORT="${FORWARD_PORT:-27042}"
CAPTURE_INSTANCE="${CAPTURE_INSTANCE:-${ADB_SERIAL:-device-1}}"
CAPTURE_INSTANCE_SAFE="$(printf '%s' "$CAPTURE_INSTANCE" | tr -c 'A-Za-z0-9_.-' '_')"
SCREEN_SESSION="frida-server-$CAPTURE_INSTANCE_SAFE"
LOG_FILE="$RUNTIME_DIR/frida-server-${FORWARD_PORT}.log"
LAUNCHER_FILE="$RUNTIME_DIR/launch-frida-server-${FORWARD_PORT}.sh"
FRIDA_LD_LIBRARY_PATH="${FRIDA_LD_LIBRARY_PATH:-/apex/com.android.os.statsd/lib64:/apex/com.android.art/lib64:/apex/com.android.runtime/lib64}"

require_command "$ADB_BIN"
require_command curl
require_command xz
require_command frida
require_command frida-ps
require_command screen

mkdir -p "$TOOLS_DIR"
mkdir -p "$RUNTIME_DIR"

if [[ ! -f "$FRIDA_XZ" ]]; then
  echo "downloading $FRIDA_ASSET"
  curl -L "$FRIDA_URL" -o "$FRIDA_XZ"
fi

if [[ ! -x "$FRIDA_BIN" ]]; then
  xz -dc "$FRIDA_XZ" >"$FRIDA_BIN"
  chmod +x "$FRIDA_BIN"
fi

adb_root_wait
adb_cmd push "$FRIDA_BIN" "$DEVICE_BIN" >/dev/null
adb_cmd shell "chmod 755 '$DEVICE_BIN'"
REMOTE_CMD="env LD_LIBRARY_PATH=$FRIDA_LD_LIBRARY_PATH $DEVICE_BIN"

USE_SU=0
if adb_cmd shell "id" 2>/dev/null | tr -d '\r' | grep -q 'uid=0'; then
  USE_SU=0
elif adb_cmd shell "su -c id" 2>/dev/null | tr -d '\r' | grep -q 'uid=0'; then
  USE_SU=1
fi

if [[ "$USE_SU" == "1" ]]; then
  adb_cmd shell "su -c \"pkill -f '/data/local/tmp/[f]rida-server' >/dev/null 2>&1 || true; pidof frida-server >/dev/null 2>&1 && kill \$(pidof frida-server) >/dev/null 2>&1 || true\""
else
  adb_cmd shell "pkill -f '/data/local/tmp/[f]rida-server' >/dev/null 2>&1 || true; pidof frida-server >/dev/null 2>&1 && kill \$(pidof frida-server) >/dev/null 2>&1 || true"
fi
adb_cmd forward --remove "tcp:${FORWARD_PORT}" >/dev/null 2>&1 || true

: >"$LOG_FILE"
{
  printf '#!/usr/bin/env bash\n'
  printf 'exec '
  if [[ -n "${ADB_SERIAL:-}" ]]; then
    if [[ "$USE_SU" == "1" ]]; then
      printf '%q ' "$ADB_BIN" -s "$ADB_SERIAL" shell su -c "$REMOTE_CMD"
    else
      printf '%q ' "$ADB_BIN" -s "$ADB_SERIAL" shell "$REMOTE_CMD"
    fi
  else
    if [[ "$USE_SU" == "1" ]]; then
      printf '%q ' "$ADB_BIN" shell su -c "$REMOTE_CMD"
    else
      printf '%q ' "$ADB_BIN" shell "$REMOTE_CMD"
    fi
  fi
  printf '>>"%s" 2>&1\n' "$LOG_FILE"
} >"$LAUNCHER_FILE"
chmod +x "$LAUNCHER_FILE"

screen -S "$SCREEN_SESSION" -X quit >/dev/null 2>&1 || true
screen -dmS "$SCREEN_SESSION" "$LAUNCHER_FILE"
adb_cmd forward "tcp:${FORWARD_PORT}" "tcp:27042" >/dev/null

sleep 2

echo "android serial: $(adb_get_serial)"
echo "frida server: $DEVICE_BIN"
if [[ "$USE_SU" == "1" ]]; then
  echo "frida privilege: magisk su"
else
  echo "frida privilege: adb shell"
fi
for attempt in 1 2 3 4 5; do
  if frida-ps -H "127.0.0.1:${FORWARD_PORT}" | sed -n '1,12p'; then
    exit 0
  fi
  sleep 1
done

echo "frida server started but process enumeration is not ready" >&2
exit 1

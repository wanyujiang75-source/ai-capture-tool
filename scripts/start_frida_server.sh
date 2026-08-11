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
require_command frida
require_command frida-ps
require_command screen

decompress_frida_archive() {
  local archive_path="$1"
  local output_path="$2"
  if command -v xz >/dev/null 2>&1; then
    xz -dc "$archive_path" >"$output_path"
    return 0
  fi

  local python_bin="${FRIDA_PYTHON_BIN:-$(command -v python3 || true)}"
  if [[ -z "$python_bin" || ! -x "$python_bin" ]]; then
    echo "unable to decompress Frida server: neither xz nor embedded Python is available" >&2
    return 1
  fi
  "$python_bin" - "$archive_path" "$output_path" <<'PY'
import lzma
import shutil
import sys

with lzma.open(sys.argv[1], "rb") as source, open(sys.argv[2], "wb") as target:
    shutil.copyfileobj(source, target)
PY
}

mkdir -p "$TOOLS_DIR"
mkdir -p "$RUNTIME_DIR"

if [[ ! -f "$FRIDA_XZ" ]]; then
  echo "downloading $FRIDA_ASSET"
  curl -L "$FRIDA_URL" -o "$FRIDA_XZ"
fi

if [[ ! -x "$FRIDA_BIN" ]]; then
  FRIDA_TEMP_BIN="${FRIDA_BIN}.tmp.$$"
  trap 'rm -f "$FRIDA_TEMP_BIN"' EXIT
  decompress_frida_archive "$FRIDA_XZ" "$FRIDA_TEMP_BIN"
  chmod +x "$FRIDA_TEMP_BIN"
  mv "$FRIDA_TEMP_BIN" "$FRIDA_BIN"
  trap - EXIT
fi

adb_wait_for_device
USE_SU=0
ROOT_AVAILABLE=0
ROOT_SHELL_PREFIX=""
if adb_cmd shell "id" 2>/dev/null | tr -d '\r' | grep -q 'uid=0'; then
  ROOT_AVAILABLE=1
  USE_SU=0
elif adb_cmd shell "su -c id" 2>/dev/null | tr -d '\r' | grep -q 'uid=0'; then
  ROOT_AVAILABLE=1
  USE_SU=1
  ROOT_SHELL_PREFIX="su"
elif adb_cmd shell "/debug_ramdisk/magisk su -c id" 2>/dev/null | tr -d '\r' | grep -q 'uid=0'; then
  ROOT_AVAILABLE=1
  USE_SU=1
  ROOT_SHELL_PREFIX="/debug_ramdisk/magisk su"
fi
if [[ "$ROOT_AVAILABLE" != "1" ]]; then
  echo "no root-capable Frida launch path; the AVD ramdisk bootstrap is required" >&2
  exit 2
fi

adb_cmd push "$FRIDA_BIN" "$DEVICE_BIN" >/dev/null
adb_cmd shell "chmod 755 '$DEVICE_BIN'"
REMOTE_CMD="env LD_LIBRARY_PATH=$FRIDA_LD_LIBRARY_PATH $DEVICE_BIN"

if [[ "$USE_SU" == "1" ]]; then
  adb_cmd shell "$ROOT_SHELL_PREFIX -c \"pkill -f '/data/local/tmp/[f]rida-server' >/dev/null 2>&1 || true; pidof frida-server >/dev/null 2>&1 && kill \$(pidof frida-server) >/dev/null 2>&1 || true\""
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
      printf '%q ' "$ADB_BIN" -s "$ADB_SERIAL" shell "$ROOT_SHELL_PREFIX -c \"$REMOTE_CMD\""
    else
      printf '%q ' "$ADB_BIN" -s "$ADB_SERIAL" shell "$REMOTE_CMD"
    fi
  else
    if [[ "$USE_SU" == "1" ]]; then
      printf '%q ' "$ADB_BIN" shell "$ROOT_SHELL_PREFIX -c \"$REMOTE_CMD\""
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

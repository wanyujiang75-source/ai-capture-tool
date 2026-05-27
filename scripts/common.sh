#!/usr/bin/env bash

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

COMMON_ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
RUNTIME_DIR="${CAPTURE_RUNTIME_DIR:-${RUNTIME_DIR:-$COMMON_ROOT_DIR/runtime}}"
export RUNTIME_DIR

ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}"
ANDROID_CAPTURE_AVD="${ANDROID_CAPTURE_AVD:-Medium_Phone_API_36.1}"
export ANDROID_CAPTURE_AVD

if [[ -z "${ADB_BIN:-}" ]]; then
  if [[ -x "$ANDROID_SDK_ROOT/platform-tools/adb" ]]; then
    ADB_BIN="$ANDROID_SDK_ROOT/platform-tools/adb"
  else
    ADB_BIN="adb"
  fi
fi
ADB_SERIAL="${ADB_SERIAL:-}"

require_command() {
  if [[ "$1" == */* ]]; then
    if [[ ! -x "$1" ]]; then
      echo "$1 not found or not executable" >&2
      exit 1
    fi
    return 0
  fi

  if ! command -v "$1" >/dev/null 2>&1; then
    echo "$1 not found in PATH" >&2
    exit 1
  fi
}

adb_cmd() {
  if [[ -n "${ADB_SERIAL:-}" ]]; then
    "$ADB_BIN" -s "$ADB_SERIAL" "$@"
  else
    "$ADB_BIN" "$@"
  fi
}

detect_adb_serial() {
  local devices=()
  local emulators=()
  local serial
  local state
  local extra

  if [[ -n "${ADB_SERIAL:-}" ]]; then
    return 0
  fi

  while read -r serial state extra; do
    [[ -z "$serial" || "$serial" == "List" ]] && continue
    [[ "$state" == "device" ]] || continue
    devices+=("$serial")
    if [[ "$serial" == emulator-* ]]; then
      emulators+=("$serial")
    fi
  done < <("$ADB_BIN" devices)

  if (( ${#emulators[@]} == 1 )); then
    ADB_SERIAL="${emulators[0]}"
    return 0
  fi

  if (( ${#devices[@]} == 1 )); then
    ADB_SERIAL="${devices[0]}"
    return 0
  fi

  return 1
}

resolve_adb_serial() {
  local devices=()
  local serial
  local state
  local extra

  if detect_adb_serial; then
    export ADB_SERIAL
    return 0
  fi

  while read -r serial state extra; do
    [[ -z "$serial" || "$serial" == "List" ]] && continue
    [[ "$state" == "device" ]] || continue
    devices+=("$serial")
  done < <("$ADB_BIN" devices)

  if (( ${#devices[@]} == 0 )); then
    echo "no online adb device found; start the emulator first" >&2
  else
    printf 'multiple adb devices online: %s\n' "${devices[*]}" >&2
    echo "set ADB_SERIAL to the target serial" >&2
  fi
  exit 1
}

wait_for_adb_serial() {
  local timeout="${1:-120}"
  local deadline=$((SECONDS + timeout))

  while (( SECONDS < deadline )); do
    if detect_adb_serial; then
      export ADB_SERIAL
      return 0
    fi
    sleep 2
  done

  echo "timed out waiting for an adb device to appear" >&2
  exit 1
}

adb_wait_for_device() {
  wait_for_adb_serial "${1:-120}"
  adb_cmd wait-for-device
}

adb_root_wait() {
  adb_wait_for_device "${1:-120}"
  adb_cmd root >/dev/null
  adb_wait_for_device "${1:-120}"
}

adb_get_serial() {
  resolve_adb_serial
  printf '%s\n' "$ADB_SERIAL"
}

wait_for_property() {
  local prop="$1"
  local expected="$2"
  local timeout="${3:-180}"
  local deadline=$((SECONDS + timeout))
  local value

  while (( SECONDS < deadline )); do
    value="$(adb_cmd shell getprop "$prop" 2>/dev/null | tr -d '\r')"
    if [[ "$value" == "$expected" ]]; then
      return 0
    fi
    sleep 2
  done

  echo "timed out waiting for Android property $prop=$expected" >&2
  exit 1
}

wait_for_boot_completed() {
  local timeout="${1:-180}"
  adb_wait_for_device "$timeout"
  wait_for_property sys.boot_completed 1 "$timeout"
}

wait_for_listen_port() {
  local port="$1"
  local timeout="${2:-30}"
  local deadline=$((SECONDS + timeout))

  while (( SECONDS < deadline )); do
    if lsof -iTCP:"$port" -sTCP:LISTEN -n -P >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "timed out waiting for host port $port to listen" >&2
  exit 1
}

pid_command_line() {
  local pid="$1"
  ps -p "$pid" -o command= 2>/dev/null || true
}

project_owns_pid() {
  local pid="$1"
  local command_line
  command_line="$(pid_command_line "$pid")"
  [[ -n "$command_line" ]] || return 1

  case "$command_line" in
    *"$COMMON_ROOT_DIR"*|*"$RUNTIME_DIR"*|*ai_capture*|*capture_console*|*flutter_proxy_unpin_capture.py*|*mitmweb-socks*|*launch-mitmweb*|*web_password=android-capture*)
      return 0
      ;;
  esac
  return 1
}

stop_owned_port_listeners() {
  local port="$1"
  local label="${2:-port $port}"
  local pid

  while read -r pid; do
    [[ -n "$pid" ]] || continue
    if project_owns_pid "$pid"; then
      kill "$pid" >/dev/null 2>&1 || true
      echo "stopped owned $label listener pid=$pid"
    else
      echo "refusing to stop foreign $label listener pid=$pid command=$(pid_command_line "$pid")" >&2
      return 1
    fi
  done < <(lsof -tiTCP:"$port" -sTCP:LISTEN -n -P 2>/dev/null || true)
}

refuse_foreign_port_owner() {
  local port="$1"
  local label="${2:-port $port}"
  local pid

  while read -r pid; do
    [[ -n "$pid" ]] || continue
    if ! project_owns_pid "$pid"; then
      echo "port $port for $label is occupied by another process: pid=$pid command=$(pid_command_line "$pid")" >&2
      echo "stop that service manually or change this capture device port before starting AI capture." >&2
      return 1
    fi
  done < <(lsof -tiTCP:"$port" -sTCP:LISTEN -n -P 2>/dev/null || true)
}

detect_adb_serial_for_avd() {
  local avd_name="$1"
  local serial
  local state
  local extra
  local current_avd

  while read -r serial state extra; do
    [[ -z "$serial" || "$serial" == "List" ]] && continue
    [[ "$state" == "device" ]] || continue
    current_avd="$("$ADB_BIN" -s "$serial" emu avd name 2>/dev/null | tr -d '\r' | sed -n '1p')"
    if [[ "$current_avd" == "$avd_name" ]]; then
      ADB_SERIAL="$serial"
      return 0
    fi
  done < <("$ADB_BIN" devices)

  return 1
}

wait_for_adb_serial_for_avd() {
  local avd_name="$1"
  local timeout="${2:-180}"
  local deadline=$((SECONDS + timeout))

  while (( SECONDS < deadline )); do
    if detect_adb_serial_for_avd "$avd_name"; then
      export ADB_SERIAL
      return 0
    fi
    sleep 2
  done

  echo "timed out waiting for adb device for AVD $avd_name" >&2
  exit 1
}

open_url() {
  local url="$1"

  if [[ "$(uname -s)" == "Darwin" ]]; then
    open "$url" >/dev/null 2>&1
    return 0
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 &
    return 0
  fi

  echo "open this URL manually: $url"
}

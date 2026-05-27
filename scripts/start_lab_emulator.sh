#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}"
AVD_NAME="${1:-$ANDROID_CAPTURE_AVD}"
RUNTIME_DIR="${RUNTIME_DIR:-$(cd "$(dirname "$0")/.." && pwd)/runtime}"
EMULATOR_BIN="$SDK_ROOT/emulator/emulator"
EMULATOR_ARGS="${EMULATOR_ARGS:-}"
EMULATOR_PORT="${EMULATOR_PORT:-}"
EMULATOR_LAUNCH_MODE="${EMULATOR_LAUNCH_MODE:-background}"
LOG_FILE="$RUNTIME_DIR/emulator-${AVD_NAME}.log"
LAUNCHER_FILE="$RUNTIME_DIR/launch-emulator-${AVD_NAME}.sh"

mkdir -p "$RUNTIME_DIR"
: >"$LOG_FILE"

if [[ ! -x "$EMULATOR_BIN" ]]; then
  echo "emulator binary not found: $EMULATOR_BIN" >&2
  exit 1
fi

if pgrep -af "emulator.*-avd ${AVD_NAME}" >/dev/null 2>&1; then
  echo "emulator already running: $AVD_NAME"
  exit 0
fi

emulator_supports_arg() {
  local arg="$1"
  "$EMULATOR_BIN" -help 2>&1 | grep -Fq -- "$arg"
}

maybe_add_emulator_arg() {
  local arg="$1"
  shift || true
  if emulator_supports_arg "$arg"; then
    EXTRA_ARGS+=("$arg" "$@")
  else
    echo "skip unsupported emulator arg: $arg" >>"$LOG_FILE"
  fi
}

EXTRA_ARGS=()
if [[ -n "$EMULATOR_ARGS" ]]; then
  read -r -a EXTRA_ARGS <<< "$EMULATOR_ARGS"
else
  maybe_add_emulator_arg -no-snapshot-load
  maybe_add_emulator_arg -crash-report-mode never
fi

PORT_ARGS=()
if [[ -n "$EMULATOR_PORT" && " ${EXTRA_ARGS[*]} " != *" -port "* && " ${EXTRA_ARGS[*]} " != *" -ports "* ]]; then
  PORT_ARGS=(-port "$EMULATOR_PORT")
fi

{
  printf '#!/usr/bin/env bash\n'
  printf 'exec '
  printf '%q ' "$EMULATOR_BIN" -avd "$AVD_NAME" "${PORT_ARGS[@]}" "${EXTRA_ARGS[@]}"
  printf '>>"%s" 2>&1\n' "$LOG_FILE"
} >"$LAUNCHER_FILE"

chmod +x "$LAUNCHER_FILE"

if [[ "$(uname -s)" == "Darwin" && "$EMULATOR_LAUNCH_MODE" == "terminal" ]]; then
  open -a Terminal "$LAUNCHER_FILE" >/dev/null
  echo "started emulator $AVD_NAME in a new Terminal window"
else
  nohup "$LAUNCHER_FILE" >/dev/null 2>&1 < /dev/null &
  echo "started emulator $AVD_NAME in background"
fi

echo "args: ${EXTRA_ARGS[*]}"
if [[ -n "$EMULATOR_PORT" ]]; then
  echo "emulator port: $EMULATOR_PORT"
fi
echo "log: $LOG_FILE"

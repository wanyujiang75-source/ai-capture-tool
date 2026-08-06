#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="${DESKTOP_SMOKE_RUNTIME_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/tracedeck-desktop-smoke.XXXXXX")}"
VENV_DIR="${CONSOLE_VENV_DIR:-$ROOT_DIR/.venv-console}"
HOST="127.0.0.1"
PORT="$(
  python3 - <<'PY'
import socket

with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
LOG_FILE="$RUNTIME_DIR/logs/backend.log"
PID_FILE="$RUNTIME_DIR/backend.pid"

cleanup() {
  if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE")"
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" >/dev/null 2>&1 || true
    fi
  fi
  if [[ -z "${DESKTOP_SMOKE_RUNTIME_DIR:-}" ]]; then
    rm -rf "$RUNTIME_DIR"
  fi
}
trap cleanup EXIT

mkdir -p "$RUNTIME_DIR/logs"

TRACEDECK_ROOT="$ROOT_DIR" \
CAPTURE_RUNTIME_DIR="$RUNTIME_DIR" \
CONSOLE_VENV_DIR="$VENV_DIR" \
CONSOLE_HOST="$HOST" \
CONSOLE_PORT="$PORT" \
"$ROOT_DIR/desktop/start-backend.sh" >"$LOG_FILE" 2>&1 &
echo "$!" >"$PID_FILE"

timeout_seconds="${DESKTOP_SMOKE_TIMEOUT_SECONDS:-180}"
deadline=$((SECONDS + timeout_seconds))
while (( SECONDS < deadline )); do
  if curl --noproxy "*" -fsS "http://$HOST:$PORT/api/status" >/dev/null 2>&1; then
    echo "desktop backend smoke ok: http://$HOST:$PORT"
    exit 0
  fi
  if ! kill -0 "$(cat "$PID_FILE")" >/dev/null 2>&1; then
    echo "desktop backend exited before becoming ready" >&2
    cat "$LOG_FILE" >&2 || true
    exit 1
  fi
  sleep 1
done

echo "timed out waiting for desktop backend: http://$HOST:$PORT/api/status" >&2
cat "$LOG_FILE" >&2 || true
exit 1

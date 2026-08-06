#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="${TRACEDECK_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
RUNTIME_DIR="${CAPTURE_RUNTIME_DIR:-$ROOT_DIR/runtime}"
VENV_DIR="${CONSOLE_VENV_DIR:-$RUNTIME_DIR/desktop-venv}"
HOST="${CONSOLE_HOST:-127.0.0.1}"
PORT="${CONSOLE_PORT:-7001}"
CONFIG_PATH="${TRACEDECK_CONFIG:-$RUNTIME_DIR/config/local.json}"
DEVICES_CONFIG_PATH="${CAPTURE_DEVICES_CONFIG:-$RUNTIME_DIR/config/devices.json}"
CONSOLE_PYTHON="${CONSOLE_PYTHON:-}"

source "$ROOT_DIR/scripts/console_python.sh"

mkdir -p "$RUNTIME_DIR" "$RUNTIME_DIR/config" "$RUNTIME_DIR/logs"

if [[ -z "${CAPTURE_DEVICES_CONFIG:-}" && ! -f "$DEVICES_CONFIG_PATH" && -f "$ROOT_DIR/config/devices.macmini.json.example" ]]; then
  cp "$ROOT_DIR/config/devices.macmini.json.example" "$DEVICES_CONFIG_PATH"
fi

ensure_console_venv

if [[ "${CONSOLE_SKIP_INSTALL:-0}" != "1" ]]; then
  requirements_hash="$(shasum -a 256 "$ROOT_DIR/requirements-console.txt" | awk '{print $1}')"
  install_marker="$VENV_DIR/.requirements-$requirements_hash.installed"
  if [[ ! -f "$install_marker" ]]; then
    "$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
    "$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements-console.txt" >/dev/null
    rm -f "$VENV_DIR"/.requirements-*.installed
    touch "$install_marker"
  fi
fi

if [[ ! -f "$ROOT_DIR/web/dist/index.html" ]]; then
  if command -v npm >/dev/null 2>&1 && [[ -f "$ROOT_DIR/web/package.json" ]]; then
    if [[ ! -d "$ROOT_DIR/web/node_modules" ]]; then
      (cd "$ROOT_DIR/web" && npm install)
    fi
    (cd "$ROOT_DIR/web" && npm run build)
  else
    echo "web/dist is missing and npm is not available; desktop backend will serve fallback UI." >&2
  fi
fi

cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR"
export CAPTURE_RUNTIME_DIR="$RUNTIME_DIR"
export TRACEDECK_CONFIG="$CONFIG_PATH"
export CAPTURE_DEVICES_CONFIG="$DEVICES_CONFIG_PATH"
export TRACEDECK_DESKTOP=1
export CONSOLE_HOST="$HOST"
export CONSOLE_PORT="$PORT"

exec "$VENV_DIR/bin/uvicorn" capture_console.app:app --host "$HOST" --port "$PORT"

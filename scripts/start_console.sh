#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${CONSOLE_VENV_DIR:-$ROOT_DIR/.venv-console}"
HOST="${CONSOLE_HOST:-127.0.0.1}"
PORT="${CONSOLE_PORT:-7001}"
CONSOLE_PYTHON="${CONSOLE_PYTHON:-}"
USE_EMBEDDED_RUNTIME="${CONSOLE_USE_EMBEDDED_RUNTIME:-0}"
source "$ROOT_DIR/scripts/console_python.sh"

if [[ "$USE_EMBEDDED_RUNTIME" == "1" ]]; then
  if [[ -z "$CONSOLE_PYTHON" || ! -x "$CONSOLE_PYTHON" ]]; then
    echo "embedded console Python is unavailable: ${CONSOLE_PYTHON:-not configured}" >&2
    exit 1
  fi
  if [[ -z "${TRACEDECK_RUNTIME_BIN:-}" || ! -d "$TRACEDECK_RUNTIME_BIN" ]]; then
    echo "embedded runtime bin directory is unavailable: ${TRACEDECK_RUNTIME_BIN:-not configured}" >&2
    exit 1
  fi
  python_supports_console_requirements "$CONSOLE_PYTHON" || {
    echo "embedded console Python must be Python ${CONSOLE_MIN_PYTHON_MAJOR}.${CONSOLE_MIN_PYTHON_MINOR}+" >&2
    exit 1
  }
  export PATH="$TRACEDECK_RUNTIME_BIN:${PATH:-/usr/bin:/bin}"
  SERVER_PYTHON="$CONSOLE_PYTHON"
else
  ensure_console_venv
  if [[ "${CONSOLE_SKIP_INSTALL:-0}" != "1" ]]; then
    "$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
    "$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements-console.txt" >/dev/null
  fi
  SERVER_PYTHON="$VENV_DIR/bin/python"
fi

if [[ -f "$ROOT_DIR/web/dist/index.html" ]]; then
  :
elif [[ "${TRACEDECK_DESKTOP:-0}" == "1" ]]; then
  echo "desktop web assets are missing: $ROOT_DIR/web/dist/index.html" >&2
  exit 1
elif command -v npm >/dev/null 2>&1 && [[ -f "$ROOT_DIR/web/package.json" ]]; then
  if [[ ! -d "$ROOT_DIR/web/node_modules" ]]; then
    (cd "$ROOT_DIR/web" && npm install)
  fi
  (cd "$ROOT_DIR/web" && npm run build)
else
  echo "npm not found; serving built-in fallback UI instead of React/Vite build" >&2
fi

cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR"
exec "$SERVER_PYTHON" -m uvicorn capture_console.app:app --host "$HOST" --port "$PORT"

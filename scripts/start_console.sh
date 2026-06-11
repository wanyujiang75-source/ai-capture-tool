#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${CONSOLE_VENV_DIR:-$ROOT_DIR/.venv-console}"
HOST="${CONSOLE_HOST:-127.0.0.1}"
PORT="${CONSOLE_PORT:-7001}"
CONSOLE_PYTHON="${CONSOLE_PYTHON:-}"
source "$ROOT_DIR/scripts/console_python.sh"

ensure_console_venv

if [[ "${CONSOLE_SKIP_INSTALL:-0}" != "1" ]]; then
  "$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
  "$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements-console.txt" >/dev/null
fi

if command -v npm >/dev/null 2>&1 && [[ -f "$ROOT_DIR/web/package.json" ]]; then
  if [[ ! -d "$ROOT_DIR/web/node_modules" ]]; then
    (cd "$ROOT_DIR/web" && npm install)
  fi
  if [[ ! -f "$ROOT_DIR/web/dist/index.html" ]]; then
    (cd "$ROOT_DIR/web" && npm run build)
  fi
else
  echo "npm not found; serving built-in fallback UI instead of React/Vite build" >&2
fi

cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR"
exec "$VENV_DIR/bin/uvicorn" capture_console.app:app --host "$HOST" --port "$PORT"

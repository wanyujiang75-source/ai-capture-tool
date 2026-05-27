#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${CONSOLE_VENV_DIR:-$ROOT_DIR/.venv-console}"
HOST="${CONSOLE_HOST:-127.0.0.1}"
PORT="${CONSOLE_PORT:-7001}"
CONSOLE_PYTHON="${CONSOLE_PYTHON:-}"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  if [[ -z "$CONSOLE_PYTHON" ]]; then
    for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
      if command -v "$candidate" >/dev/null 2>&1; then
        CONSOLE_PYTHON="$(command -v "$candidate")"
        break
      fi
    done
  fi
  "${CONSOLE_PYTHON:-python3}" -m venv "$VENV_DIR"
fi

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

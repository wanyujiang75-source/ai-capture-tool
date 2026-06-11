#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${CONSOLE_VENV_DIR:-$ROOT_DIR/.venv-console}"
CONFIG_FILE="$ROOT_DIR/config/local.json"
CONFIG_EXAMPLE="$ROOT_DIR/config/local.example.json"
CONSOLE_PYTHON="${CONSOLE_PYTHON:-}"
source "$ROOT_DIR/scripts/console_python.sh"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "TraceDeck 首版仅支持 macOS。" >&2
  exit 1
fi

find_command() {
  command -v "$1" >/dev/null 2>&1
}

echo "TraceDeck setup: macOS 本机环境检查"
for command_name in python3 node npm adb emulator mitmweb frida frida-ps; do
  if find_command "$command_name"; then
    echo "ok    $command_name"
  else
    echo "miss  $command_name"
  fi
done

mkdir -p "$ROOT_DIR/config"
if [[ ! -f "$CONFIG_FILE" ]]; then
  cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
  echo "created $CONFIG_FILE"
else
  echo "kept existing $CONFIG_FILE"
fi

ensure_console_venv
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements-console.txt"

if find_command npm; then
  (cd "$ROOT_DIR/web" && npm install && npm run build)
else
  echo "npm 未安装，跳过 React 前端构建；后端会提供静态兜底页。" >&2
fi

cat <<EOF

setup complete.
Run:
  ./start.sh

Open:
  http://127.0.0.1:7001
EOF

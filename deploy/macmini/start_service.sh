#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${AI_CAPTURE_ENV_FILE:-$HOME/ai-capture-tool/shared/config/.env.macmini}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

export CONSOLE_HOST="${CONSOLE_HOST:-0.0.0.0}"
export CONSOLE_PORT="${CONSOLE_PORT:-7001}"
export OPEN_WEB="${OPEN_WEB:-0}"
export START_FRONTEND_DEV="${START_FRONTEND_DEV:-0}"
export CAPTURE_RUNTIME_DIR="${CAPTURE_RUNTIME_DIR:-$HOME/ai-capture-tool/shared/runtime}"
export CAPTURE_DEVICES_CONFIG="${CAPTURE_DEVICES_CONFIG:-$HOME/ai-capture-tool/shared/config/devices.macmini.json}"
export PATH="$ROOT_DIR/.venv-console/bin:$HOME/.local/bin:$HOME/Library/Python/3.12/bin:$HOME/Library/Python/3.11/bin:$HOME/Library/Python/3.10/bin:$HOME/Library/Python/3.9/bin:${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}/cmdline-tools/latest/bin:${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}/platform-tools:${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}/emulator:/opt/homebrew/bin:/usr/local/bin:$PATH"

if [[ "${1:-}" == "--foreground" ]]; then
  exec "$ROOT_DIR/scripts/start_console.sh"
fi

exec "$ROOT_DIR/scripts/start_web_services.sh"

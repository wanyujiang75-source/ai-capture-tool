#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="${CAPTURE_RUNTIME_DIR:-$ROOT_DIR/runtime}"
source "$ROOT_DIR/scripts/common.sh"
BACKEND_PORT="${CONSOLE_PORT:-7001}"
FRONTEND_PORT="${FRONTEND_PORT:-7002}"
BACKEND_SCREEN_SESSION="ai-capture-web-backend"
FRONTEND_SCREEN_SESSION="ai-capture-web-frontend"

stop_screen() {
  local session="$1"
  local label="$2"
  if screen -ls 2>/dev/null | awk '{print $1}' | grep -Eq "^[0-9]+[.]${session}$"; then
    screen -S "$session" -X quit >/dev/null 2>&1 || true
    echo "stopped $label screen=$session"
  fi
}

stop_pid_file() {
  local pid_file="$1"
  local label="$2"
  if [[ ! -f "$pid_file" ]]; then
    return 0
  fi

  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" >/dev/null 2>&1; then
    if project_owns_pid "$pid"; then
      kill "$pid" >/dev/null 2>&1 || true
      echo "stopped $label pid=$pid"
    else
      echo "skipped foreign $label pid=$pid command=$(pid_command_line "$pid")"
    fi
  fi
  rm -f "$pid_file"
}

stop_port() {
  local port="$1"
  local label="$2"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi
  while read -r pid; do
    [[ -n "$pid" ]] || continue
    if project_owns_pid "$pid"; then
      kill "$pid" >/dev/null 2>&1 || true
      echo "stopped $label port=$port pid=$pid"
    else
      echo "skipped foreign $label port=$port pid=$pid command=$(pid_command_line "$pid")"
    fi
  done <<< "$pids"
}

stop_screen "$BACKEND_SCREEN_SESSION" "backend"
stop_screen "$FRONTEND_SCREEN_SESSION" "frontend"
stop_pid_file "$RUNTIME_DIR/web-backend.pid" "backend"
stop_pid_file "$RUNTIME_DIR/web-frontend.pid" "frontend"
stop_port "$BACKEND_PORT" "backend"
stop_port "$FRONTEND_PORT" "frontend"

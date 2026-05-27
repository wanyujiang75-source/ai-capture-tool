#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/scripts/common.sh"
CAPTURE_INSTANCE="${CAPTURE_INSTANCE:-device-1}"
CAPTURE_INSTANCE_SAFE="$(printf '%s' "$CAPTURE_INSTANCE" | tr -c 'A-Za-z0-9_.-' '_')"
INSTANCE_DIR="$RUNTIME_DIR/capture_instances/$CAPTURE_INSTANCE_SAFE"
EXPORTER_PID_FILE="$INSTANCE_DIR/ai_capture_export.pid"
FRIDA_PID_FILE="$INSTANCE_DIR/ai_capture_frida.pid"
ENV_FILE="$INSTANCE_DIR/ai_capture.env"
EXPORTER_SCREEN_SESSION="ai-capture-export-$CAPTURE_INSTANCE_SAFE"
FRIDA_SCREEN_SESSION="ai-capture-frida-$CAPTURE_INSTANCE_SAFE"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

PROXY_PORT="${PROXY_PORT:-9090}"
WEB_PORT="${WEB_PORT:-9091}"

if command -v screen >/dev/null 2>&1; then
  screen -S "$EXPORTER_SCREEN_SESSION" -X quit >/dev/null 2>&1 || true
  screen -S "$FRIDA_SCREEN_SESSION" -X quit >/dev/null 2>&1 || true
  if [[ "$CAPTURE_INSTANCE" == "device-1" ]]; then
    screen -S "ai-capture-export" -X quit >/dev/null 2>&1 || true
    screen -S "ai-capture-frida" -X quit >/dev/null 2>&1 || true
  fi
fi

stop_pid_file() {
  local label="$1"
  local pid_file="$2"

  if [[ ! -f "$pid_file" ]]; then
    echo "$label is not running"
    return 0
  fi

  local pid
  pid="$(sed -n '1p' "$pid_file")"
  if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    echo "stopped $label: $pid"
  else
    echo "$label already stopped"
  fi

  rm -f "$pid_file"
}

stop_pid_file "AI capture exporter" "$EXPORTER_PID_FILE"
stop_pid_file "AI capture Frida hook" "$FRIDA_PID_FILE"

stop_mitmweb() {
  local proxy_port="$1"
  local web_port="$2"

  if command -v screen >/dev/null 2>&1; then
    screen -S "mitmweb-socks-$proxy_port" -X quit >/dev/null 2>&1 || true
    screen -S "mitmweb-$proxy_port" -X quit >/dev/null 2>&1 || true
  fi

  rm -f "$RUNTIME_DIR/mitmweb-socks-$proxy_port.pid" "$RUNTIME_DIR/mitmweb-$proxy_port.pid"
  stop_owned_port_listeners "$proxy_port" "mitmweb proxy" || true
  stop_owned_port_listeners "$web_port" "mitmweb web" || true
}

stop_mitmweb "$PROXY_PORT" "$WEB_PORT"

if [[ "$CAPTURE_INSTANCE" == "device-1" ]]; then
  stop_pid_file "legacy AI capture exporter" "$RUNTIME_DIR/ai_capture_export.pid"
  stop_pid_file "legacy AI capture Frida hook" "$RUNTIME_DIR/ai_capture_frida.pid"
fi

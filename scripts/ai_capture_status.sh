#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

CAPTURE_INSTANCE="${CAPTURE_INSTANCE:-device-1}"
CAPTURE_INSTANCE_SAFE="$(printf '%s' "$CAPTURE_INSTANCE" | tr -c 'A-Za-z0-9_.-' '_')"
INSTANCE_DIR="$RUNTIME_DIR/capture_instances/$CAPTURE_INSTANCE_SAFE"
ENV_FILE="$INSTANCE_DIR/ai_capture.env"
EXPORTER_PID_FILE="$INSTANCE_DIR/ai_capture_export.pid"
FRIDA_PID_FILE="$INSTANCE_DIR/ai_capture_frida.pid"

if [[ "$CAPTURE_INSTANCE" == "device-1" && ! -f "$ENV_FILE" && -f "$RUNTIME_DIR/ai_capture.env" ]]; then
  ENV_FILE="$RUNTIME_DIR/ai_capture.env"
fi
if [[ "$CAPTURE_INSTANCE" == "device-1" && ! -f "$EXPORTER_PID_FILE" && -f "$RUNTIME_DIR/ai_capture_export.pid" ]]; then
  EXPORTER_PID_FILE="$RUNTIME_DIR/ai_capture_export.pid"
fi
if [[ "$CAPTURE_INSTANCE" == "device-1" && ! -f "$FRIDA_PID_FILE" && -f "$RUNTIME_DIR/ai_capture_frida.pid" ]]; then
  FRIDA_PID_FILE="$RUNTIME_DIR/ai_capture_frida.pid"
fi

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
else
  OUTDIR="$(sed -n '1p' "$INSTANCE_DIR/last-ai-capture-dir.txt" 2>/dev/null || true)"
  if [[ "$CAPTURE_INSTANCE" == "device-1" && -z "$OUTDIR" ]]; then
    OUTDIR="$(sed -n '1p' "$RUNTIME_DIR/last-ai-capture-dir.txt" 2>/dev/null || true)"
  fi
  WEB_PORT="${WEB_PORT:-9091}"
  PROXY_PORT="${PROXY_PORT:-9090}"
  FRIDA_PORT="${FRIDA_PORT:-27042}"
  MITMWEB_PASSWORD="${MITMWEB_PASSWORD:-android-capture}"
fi

echo "AI capture status"
echo "instance: ${CAPTURE_INSTANCE:-device-1}"
echo "web: http://127.0.0.1:${WEB_PORT:-9091}/?token=${MITMWEB_PASSWORD:-android-capture}"
echo "outdir: ${OUTDIR:-none}"
echo "mode: ${CAPTURE_MODE:-unknown}"
echo "frida host: 127.0.0.1:${FRIDA_PORT:-27042}"
if [[ -n "${APP_PACKAGE:-}" ]]; then
  echo "package: $APP_PACKAGE"
fi

if lsof -iTCP:"${PROXY_PORT:-9090}" -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  echo "proxy: listening on ${PROXY_PORT:-9090}"
else
  echo "proxy: not listening on ${PROXY_PORT:-9090}"
fi

if [[ -f "$EXPORTER_PID_FILE" ]]; then
  pid="$(sed -n '1p' "$EXPORTER_PID_FILE")"
  if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    echo "exporter: running pid=$pid"
  else
    echo "exporter: stopped"
  fi
else
  echo "exporter: no pid file"
fi

if [[ -f "$FRIDA_PID_FILE" ]]; then
  pid="$(sed -n '1p' "$FRIDA_PID_FILE")"
  if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    echo "frida hook: running pid=$pid"
  else
    echo "frida hook: stopped"
  fi
else
  echo "frida hook: no pid file"
fi

echo
echo "adb devices:"
"$ADB_BIN" devices

if [[ -n "${ADB_SERIAL:-}" ]]; then
  echo
  echo "android serial: $ADB_SERIAL"
  echo "android proxy: $(adb_cmd shell settings get global http_proxy 2>/dev/null | tr -d '\r' || true)"
  echo "foreground: $(adb_cmd shell dumpsys window 2>/dev/null | awk -F'[ /}]' '/mCurrentFocus|topResumedActivity/ {print; exit}' | tr -d '\r' || true)"
fi

if [[ -n "${OUTDIR:-}" && -f "$OUTDIR/summary.md" ]]; then
  echo
  sed -n '1,80p' "$OUTDIR/summary.md"
fi

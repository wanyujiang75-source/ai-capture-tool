#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

PROXY_HOST="${PROXY_HOST:-10.0.2.2}"
PROXY_PORT="${PROXY_PORT:-9090}"
PROXY_VALUE="${PROXY_HOST}:${PROXY_PORT}"

require_command "$ADB_BIN"

adb_wait_for_device
adb_cmd shell settings put global http_proxy "$PROXY_VALUE"
adb_cmd shell svc wifi enable >/dev/null 2>&1 || true
adb_cmd shell svc data enable >/dev/null 2>&1 || true

echo "android serial: $(adb_get_serial)"
echo "android global proxy set to: $(adb_cmd shell settings get global http_proxy | tr -d '\r')"

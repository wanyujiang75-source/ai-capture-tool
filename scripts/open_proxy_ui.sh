#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

WEB_PORT="${WEB_PORT:-9091}"
MITMWEB_PASSWORD="${MITMWEB_PASSWORD:-android-capture}"
PROXY_UI_URL="${PROXY_UI_URL:-http://127.0.0.1:$WEB_PORT/?token=$MITMWEB_PASSWORD}"

open_url "$PROXY_UI_URL"
echo "proxy ui: $PROXY_UI_URL"

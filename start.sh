#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
export OPEN_WEB="${OPEN_WEB:-1}"

exec "$ROOT_DIR/scripts/start_web_services.sh"

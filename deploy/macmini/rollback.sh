#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${AI_CAPTURE_HOME:-$HOME/ai-capture-tool}"
TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  TARGET="$(find "$BASE_DIR/releases" -maxdepth 1 -mindepth 1 -type d | sort | tail -2 | head -1)"
fi
[[ -n "$TARGET" && -d "$TARGET" ]] || { echo "no rollback target found" >&2; exit 1; }

ln -sfn "$TARGET" "$BASE_DIR/current"
if [[ -f "$HOME/Library/LaunchAgents/com.ai-capture-tool.console.plist" ]]; then
  "$BASE_DIR/current/deploy/macmini/install_launchd.sh"
else
  echo "launchd service is not installed; start manually with:"
  echo "$BASE_DIR/current/deploy/macmini/start_service.sh"
fi

echo "rolled back to $TARGET"

#!/usr/bin/env bash
set -euo pipefail

PACKAGE="${1:?usage: upgrade.sh /path/to/ai-capture-tool-version.tar.gz}"
BASE_DIR="${AI_CAPTURE_HOME:-$HOME/ai-capture-tool}"
VERSION="$(basename "$PACKAGE" .tar.gz | sed 's/^ai-capture-tool-//')"
TARGET="$BASE_DIR/releases/$VERSION"

mkdir -p "$TARGET" "$BASE_DIR/releases"
tar -xzf "$PACKAGE" -C "$TARGET"
ln -sfn "$TARGET" "$BASE_DIR/current"

cd "$BASE_DIR/current"
"$BASE_DIR/current/deploy/macmini/bootstrap.sh"
if [[ -f "$HOME/Library/LaunchAgents/com.ai-capture-tool.console.plist" ]]; then
  "$BASE_DIR/current/deploy/macmini/install_launchd.sh"
else
  echo "launchd service is not installed; start manually with:"
  echo "$BASE_DIR/current/deploy/macmini/start_service.sh"
fi

echo "upgraded to $VERSION"

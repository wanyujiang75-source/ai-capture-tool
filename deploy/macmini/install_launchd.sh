#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.ai-capture-tool.console.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/ai-capture-tool/shared/runtime"

cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.ai-capture-tool.console</string>
  <key>ProgramArguments</key>
  <array>
    <string>$ROOT_DIR/deploy/macmini/start_service.sh</string>
    <string>--foreground</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT_DIR</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$HOME/ai-capture-tool/shared/runtime/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$HOME/ai-capture-tool/shared/runtime/launchd.err.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/com.ai-capture-tool.console"

echo "installed launchd service: $PLIST"

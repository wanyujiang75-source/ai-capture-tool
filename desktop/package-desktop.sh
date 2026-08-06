#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_PATH="$ROOT_DIR/src-tauri/target/release/bundle/macos/AI抓包工具.app"

cd "$ROOT_DIR"

npm --prefix web install
npm --prefix web run build
npm install
npm run desktop:build

if [[ ! -d "$APP_PATH" ]]; then
  echo "desktop app bundle was not generated: $APP_PATH" >&2
  exit 1
fi

echo "$APP_PATH"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${TRACEDECK_VERSION:-$(date +%Y%m%d-%H%M%S)}"
ARCHIVE_NAME="TraceDeck-$VERSION.tar.gz"
ARCHIVE_PATH="$ROOT_DIR/release/$ARCHIVE_NAME"

if command -v npm >/dev/null 2>&1; then
  (cd "$ROOT_DIR/web" && npm install && npm run build)
fi

if [[ ! -f "$ROOT_DIR/web/dist/index.html" ]]; then
  echo "web/dist is missing; install npm and run npm --prefix web run build before packaging." >&2
  exit 1
fi

(
  cd "$ROOT_DIR"
  tar -czf "$ARCHIVE_PATH" \
    --exclude=.git \
    --exclude=.DS_Store \
    --exclude=runtime \
    --exclude=.venv \
    --exclude='.venv-*' \
    --exclude=.venv-console \
    --exclude=.venv-console312 \
    --exclude=web/node_modules \
    --exclude=config/local.json \
    --exclude='release/*.tar.gz' \
    --exclude='release/*.zip' \
    --exclude='release/*.sha256' \
    README.md \
    setup.sh \
    start.sh \
    start_capture.sh \
    requirements-console.txt \
    capture_console \
    scripts \
    tools \
    web \
    config/local.example.json \
    config/devices.macmini.json.example \
    docs
)

shasum -a 256 "$ARCHIVE_PATH" >"$ARCHIVE_PATH.sha256"
echo "$ARCHIVE_PATH"

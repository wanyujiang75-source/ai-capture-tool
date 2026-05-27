#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="${1:-$(date +%Y%m%d-%H%M%S)}"
RELEASE_DIR="$ROOT_DIR/release"
PACKAGE="$RELEASE_DIR/ai-capture-tool-$VERSION.tar.gz"

mkdir -p "$RELEASE_DIR"

(
  cd "$ROOT_DIR/web"
  npm ci
  npm run build
)

tar \
  --exclude='.venv-console' \
  --exclude='web/node_modules' \
  --exclude='runtime/captures' \
  --exclude='runtime/capture_instances' \
  --exclude='runtime/uploads' \
  --exclude='runtime/*.log' \
  --exclude='runtime/*.pid' \
  --exclude='release' \
  --exclude='.pytest_cache' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  --exclude='tools/httptoolkit-frida/.git' \
  --exclude='tools/httptoolkit-frida/.github' \
  --exclude='tools/httptoolkit-frida/test' \
  -czf "$PACKAGE" \
  -C "$ROOT_DIR" \
  capture_console scripts web/dist web/package.json web/package-lock.json web/vite.config.js \
  config deploy docs tools/frida tools/httptoolkit-frida requirements-console.txt README.md start_capture.sh

shasum -a 256 "$PACKAGE" >"$PACKAGE.sha256"

echo "package: $PACKAGE"
echo "sha256 : $PACKAGE.sha256"

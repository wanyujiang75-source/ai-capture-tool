#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
OUTPUT_DIR="${1:-$ROOT_DIR/build/embedded-runtime}"
CACHE_DIR="${EMBEDDED_RUNTIME_CACHE_DIR:-$ROOT_DIR/.build/embedded-runtime-cache}"
PYTHON_VERSION="${EMBEDDED_PYTHON_VERSION:-3.12}"
REQUIREMENTS_FILE="$PROJECT_ROOT/requirements-console.txt"
HOST_ARCH="$(uname -m)"
UV_BIN="${UV_BIN:-$(command -v uv || true)}"
RUNTIME_SCHEMA_VERSION="2"

if [[ "$(uname -s)" != "Darwin" || "$HOST_ARCH" != "arm64" ]]; then
  echo "embedded runtime V1 requires macOS arm64" >&2
  exit 1
fi
if [[ -z "$UV_BIN" || ! -x "$UV_BIN" ]]; then
  echo "uv is required to build the embedded Python runtime: https://docs.astral.sh/uv/" >&2
  exit 1
fi
if [[ ! -f "$REQUIREMENTS_FILE" ]]; then
  echo "requirements file not found: $REQUIREMENTS_FILE" >&2
  exit 1
fi

REQUIREMENTS_SHA256="$(shasum -a 256 "$REQUIREMENTS_FILE" | awk '{print $1}')"
CACHE_KEY="$(printf '%s\n' "$RUNTIME_SCHEMA_VERSION" "$PYTHON_VERSION" "$HOST_ARCH" "$REQUIREMENTS_SHA256" | shasum -a 256 | awk '{print $1}')"
CACHED_RUNTIME="$CACHE_DIR/runtime"
MANIFEST="$CACHED_RUNTIME/manifest.json"

if [[ ! -f "$MANIFEST" ]] || ! grep -F "\"cache_key\": \"$CACHE_KEY\"" "$MANIFEST" >/dev/null; then
  mkdir -p "$CACHE_DIR"
  STAGE_DIR="$(mktemp -d "$CACHE_DIR/stage.XXXXXX")"
  trap 'rm -rf "$STAGE_DIR"' EXIT
  RUNTIME_DIR="$STAGE_DIR/runtime"
  PYTHON_ROOT="$RUNTIME_DIR/python"
  BIN_DIR="$RUNTIME_DIR/bin"

  mkdir -p "$PYTHON_ROOT" "$BIN_DIR"
  "$UV_BIN" python install "$PYTHON_VERSION" \
    --install-dir "$PYTHON_ROOT" \
    --no-bin \
    --no-progress

  # uv adds a convenience alias that points back to its install-time absolute path.
  # The concrete version directory is relocatable; the alias is redundant and breaks App copying.
  find "$PYTHON_ROOT" -mindepth 1 -maxdepth 1 -type l -delete

  PYTHON_BIN="$(find "$PYTHON_ROOT" -path '*/bin/python3' | head -n 1)"
  if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
    echo "uv did not create an executable Python runtime" >&2
    exit 1
  fi

  "$UV_BIN" pip install \
    --python "$PYTHON_BIN" \
    --system \
    --break-system-packages \
    --strict \
    --link-mode copy \
    --no-progress \
    --requirements "$REQUIREMENTS_FILE"

  PYTHON_HOME="$(cd "$(dirname "$PYTHON_BIN")/.." && pwd)"
  PYTHON_HOME_NAME="$(basename "$PYTHON_HOME")"
  ln -s "../python/$PYTHON_HOME_NAME/bin/python3" "$BIN_DIR/python3"

  cat >"$RUNTIME_DIR/console_entrypoint.py" <<'PY'
import sys
from importlib.metadata import entry_points


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("console entry point name is required")
    name = sys.argv[1]
    sys.argv = [name, *sys.argv[2:]]
    matches = [entry for entry in entry_points(group="console_scripts") if entry.name == name]
    if len(matches) != 1:
        raise SystemExit(f"console entry point is unavailable: {name}")
    result = matches[0].load()()
    raise SystemExit(result)


if __name__ == "__main__":
    main()
PY

  for command_name in uvicorn mitmweb frida frida-ps; do
    cat >"$BIN_DIR/$command_name" <<WRAPPER
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
exec "\$SCRIPT_DIR/python3" "\$SCRIPT_DIR/../console_entrypoint.py" "$command_name" "\$@"
WRAPPER
    chmod +x "$BIN_DIR/$command_name"
  done

  PYTHON_FULL_VERSION="$($PYTHON_BIN -c 'import platform; print(platform.python_version())')"
  cat >"$RUNTIME_DIR/manifest.json" <<JSON
{
  "schema_version": $RUNTIME_SCHEMA_VERSION,
  "cache_key": "$CACHE_KEY",
  "python_version": "$PYTHON_FULL_VERSION",
  "architecture": "$HOST_ARCH",
  "requirements_sha256": "$REQUIREMENTS_SHA256"
}
JSON

  "$BIN_DIR/python3" -c 'import fastapi, frida, mitmproxy, uvicorn'
  while IFS= read -r -d '' runtime_link; do
    link_target="$(readlink "$runtime_link")"
    if [[ "$link_target" == /* ]]; then
      echo "embedded runtime contains an absolute symlink: $runtime_link -> $link_target" >&2
      exit 1
    fi
  done < <(find "$RUNTIME_DIR" -type l -print0)
  rm -rf "$CACHED_RUNTIME"
  mv "$RUNTIME_DIR" "$CACHED_RUNTIME"
fi

rm -rf "$OUTPUT_DIR"
mkdir -p "$(dirname "$OUTPUT_DIR")"
ditto "$CACHED_RUNTIME" "$OUTPUT_DIR"
"$OUTPUT_DIR/bin/python3" -c 'import fastapi, frida, mitmproxy, uvicorn'
echo "$OUTPUT_DIR"

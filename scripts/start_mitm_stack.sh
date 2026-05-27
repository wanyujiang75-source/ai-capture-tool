#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

PROXY_PORT="${PROXY_PORT:-9090}"
WEB_PORT="${WEB_PORT:-9091}"
MITMWEB_PASSWORD="${MITMWEB_PASSWORD:-android-capture}"
MITMPROXY_IGNORE_HOSTS="${MITMPROXY_IGNORE_HOSTS:-}"
RUNTIME_DIR="${RUNTIME_DIR:-$(cd "$(dirname "$0")/.." && pwd)/runtime}"
LOG_FILE="$RUNTIME_DIR/mitmweb-${PROXY_PORT}.log"
PID_FILE="$RUNTIME_DIR/mitmweb-${PROXY_PORT}.pid"
LAUNCHER_FILE="$RUNTIME_DIR/launch-mitmweb-${PROXY_PORT}.sh"
SCREEN_SESSION="mitmweb-${PROXY_PORT}"
MITMWEB_BIN="${MITMWEB_BIN:-}"

mkdir -p "$RUNTIME_DIR"
: >"$LOG_FILE"

if [[ -z "$MITMWEB_BIN" ]]; then
  MITMWEB_BIN="$(command -v mitmweb || true)"
fi

if [[ -z "$MITMWEB_BIN" || ! -x "$MITMWEB_BIN" ]]; then
  echo "mitmweb not found in PATH" >&2
  exit 1
fi

MITMWEB_ARGS=(
  --no-web-open-browser
  --listen-host 0.0.0.0
  --listen-port "$PROXY_PORT"
  --web-host 127.0.0.1
  --web-port "$WEB_PORT"
  --set "web_password=$MITMWEB_PASSWORD"
)

if [[ -n "$MITMPROXY_IGNORE_HOSTS" ]]; then
  IFS=',' read -r -a ignore_hosts <<< "$MITMPROXY_IGNORE_HOSTS"
  for ignore_host in "${ignore_hosts[@]}"; do
    [[ -n "$ignore_host" ]] || continue
    MITMWEB_ARGS+=(--ignore-hosts "$ignore_host")
  done
fi

if lsof -iTCP:"$PROXY_PORT" -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  echo "proxy port already in use: $PROXY_PORT" >&2
  exit 1
fi

if lsof -iTCP:"$WEB_PORT" -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  echo "web port already in use: $WEB_PORT" >&2
  exit 1
fi

{
  printf '#!/usr/bin/env bash\n'
  printf 'exec '
  printf '%q ' "$MITMWEB_BIN" "${MITMWEB_ARGS[@]}"
  printf '>>"%s" 2>&1\n' "$LOG_FILE"
} >"$LAUNCHER_FILE"

chmod +x "$LAUNCHER_FILE"

if [[ "$(uname -s)" == "Darwin" ]]; then
  if command -v screen >/dev/null 2>&1; then
    screen -S "$SCREEN_SESSION" -X quit >/dev/null 2>&1 || true
    screen -dmS "$SCREEN_SESSION" "$LAUNCHER_FILE"
    echo "screen:$SCREEN_SESSION" >"$PID_FILE"
  else
    open -a Terminal "$LAUNCHER_FILE" >/dev/null
    echo "terminal-launch" >"$PID_FILE"
  fi
else
  nohup "$LAUNCHER_FILE" >/dev/null 2>&1 < /dev/null &
  echo $! >"$PID_FILE"
fi

sleep 2

if ! lsof -iTCP:"$PROXY_PORT" -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  echo "mitmweb failed to bind to port $PROXY_PORT" >&2
  tail -n 20 "$LOG_FILE" 2>/dev/null >&2 || true
  exit 1
fi

echo "mitmweb started"
echo "proxy: 0.0.0.0:$PROXY_PORT"
echo "web:   http://127.0.0.1:$WEB_PORT"
echo "web with token: http://127.0.0.1:$WEB_PORT/?token=$MITMWEB_PASSWORD"
if [[ -n "$MITMPROXY_IGNORE_HOSTS" ]]; then
  echo "ignore hosts: $MITMPROXY_IGNORE_HOSTS"
fi
echo "log:   $LOG_FILE"
tail -n 5 "$LOG_FILE" 2>/dev/null || true

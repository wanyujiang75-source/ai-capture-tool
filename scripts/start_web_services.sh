#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="${CAPTURE_RUNTIME_DIR:-$ROOT_DIR/runtime}"
VENV_DIR="${CONSOLE_VENV_DIR:-$ROOT_DIR/.venv-console}"
CONSOLE_PYTHON="${CONSOLE_PYTHON:-}"
BACKEND_HOST="${CONSOLE_HOST:-127.0.0.1}"
BACKEND_PORT="${CONSOLE_PORT:-7001}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-7002}"
START_FRONTEND_DEV="${START_FRONTEND_DEV:-0}"
OPEN_WEB="${OPEN_WEB:-1}"

BACKEND_PID_FILE="$RUNTIME_DIR/web-backend.pid"
FRONTEND_PID_FILE="$RUNTIME_DIR/web-frontend.pid"
BACKEND_LOG="$RUNTIME_DIR/web-backend.log"
FRONTEND_LOG="$RUNTIME_DIR/web-frontend.log"
BACKEND_LAUNCHER_FILE="$RUNTIME_DIR/launch-web-backend.sh"
FRONTEND_LAUNCHER_FILE="$RUNTIME_DIR/launch-web-frontend.sh"
BACKEND_SCREEN_SESSION="ai-capture-web-backend"
FRONTEND_SCREEN_SESSION="ai-capture-web-frontend"

mkdir -p "$RUNTIME_DIR"

is_port_listening() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

ensure_backend_env() {
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    if [[ -z "$CONSOLE_PYTHON" ]]; then
      for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
          CONSOLE_PYTHON="$(command -v "$candidate")"
          break
        fi
      done
    fi
    "${CONSOLE_PYTHON:-python3}" -m venv "$VENV_DIR"
  fi

  if [[ "${CONSOLE_SKIP_INSTALL:-0}" != "1" ]]; then
    "$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements-console.txt" >/dev/null
  fi
}

ensure_frontend_env() {
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm not found; frontend dev server cannot be started" >&2
    exit 1
  fi

  if [[ ! -d "$ROOT_DIR/web/node_modules" ]]; then
    (cd "$ROOT_DIR/web" && npm install)
  fi
}

start_backend() {
  if is_port_listening "$BACKEND_PORT"; then
    echo "backend already listening: http://$BACKEND_HOST:$BACKEND_PORT"
    return 0
  fi

  ensure_backend_env
  : >"$BACKEND_LOG"
  {
    printf '#!/usr/bin/env bash\n'
    printf 'cd %q\n' "$ROOT_DIR"
    printf 'export PYTHONPATH=%q\n' "$ROOT_DIR"
    printf 'exec %q capture_console.app:app --host %q --port %q >>%q 2>&1\n' \
      "$VENV_DIR/bin/uvicorn" "$BACKEND_HOST" "$BACKEND_PORT" "$BACKEND_LOG"
  } >"$BACKEND_LAUNCHER_FILE"
  chmod +x "$BACKEND_LAUNCHER_FILE"

  if command -v screen >/dev/null 2>&1; then
    screen -S "$BACKEND_SCREEN_SESSION" -X quit >/dev/null 2>&1 || true
    screen -dmS "$BACKEND_SCREEN_SESSION" "$BACKEND_LAUNCHER_FILE"
    echo "$BACKEND_SCREEN_SESSION" >"$BACKEND_PID_FILE"
  else
    nohup "$BACKEND_LAUNCHER_FILE" >/dev/null 2>&1 &
    echo "$!" >"$BACKEND_PID_FILE"
  fi
  echo "started backend: http://$BACKEND_HOST:$BACKEND_PORT"
}

start_frontend() {
  if is_port_listening "$FRONTEND_PORT"; then
    echo "frontend already listening: http://$FRONTEND_HOST:$FRONTEND_PORT"
    return 0
  fi

  ensure_frontend_env
  : >"$FRONTEND_LOG"
  {
    printf '#!/usr/bin/env bash\n'
    printf 'cd %q\n' "$ROOT_DIR/web"
    printf 'exec npm run dev -- --host %q --port %q >>%q 2>&1\n' "$FRONTEND_HOST" "$FRONTEND_PORT" "$FRONTEND_LOG"
  } >"$FRONTEND_LAUNCHER_FILE"
  chmod +x "$FRONTEND_LAUNCHER_FILE"

  if command -v screen >/dev/null 2>&1; then
    screen -S "$FRONTEND_SCREEN_SESSION" -X quit >/dev/null 2>&1 || true
    screen -dmS "$FRONTEND_SCREEN_SESSION" "$FRONTEND_LAUNCHER_FILE"
    echo "$FRONTEND_SCREEN_SESSION" >"$FRONTEND_PID_FILE"
  else
    nohup "$FRONTEND_LAUNCHER_FILE" >/dev/null 2>&1 &
    echo "$!" >"$FRONTEND_PID_FILE"
  fi
  echo "started frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
}

build_frontend() {
  ensure_frontend_env
  (
    cd "$ROOT_DIR/web"
    npm run build
  ) >>"$FRONTEND_LOG" 2>&1
  echo "built frontend assets for backend serving"
}

wait_for_url() {
  local url="$1"
  local timeout="${2:-20}"
  local deadline=$((SECONDS + timeout))
  while (( SECONDS < deadline )); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "timed out waiting for $url" >&2
  return 1
}

open_url() {
  local url="$1"
  if [[ "$OPEN_WEB" != "1" ]]; then
    return 0
  fi
  if [[ "$(uname -s)" == "Darwin" ]]; then
    open "$url" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || true
  fi
}

start_backend
if [[ "$START_FRONTEND_DEV" == "1" ]]; then
  start_frontend
else
  build_frontend
fi

wait_for_url "http://$BACKEND_HOST:$BACKEND_PORT/api/status" 30
if [[ "$START_FRONTEND_DEV" == "1" ]]; then
  wait_for_url "http://$FRONTEND_HOST:$FRONTEND_PORT/" 30
fi

echo
echo "AI抓包工具已启动："
echo "- 页面入口: http://$BACKEND_HOST:$BACKEND_PORT"
echo "- 后端 API : http://$BACKEND_HOST:$BACKEND_PORT"
if [[ "$START_FRONTEND_DEV" == "1" ]]; then
  echo "- 前端开发服务: http://$FRONTEND_HOST:$FRONTEND_PORT"
fi
echo
echo "后续操作全部在 Web 页面完成："
echo "1. 点击“启动模拟器”启动保留 AVD"
echo "2. 选择应用并启动抓包"
echo "3. 在模拟器里手动操作 App"
echo "4. 在页面接口分析区查看请求和响应"
echo
echo "logs:"
echo "- $BACKEND_LOG"
echo "- $FRONTEND_LOG"

open_url "http://$BACKEND_HOST:$BACKEND_PORT"

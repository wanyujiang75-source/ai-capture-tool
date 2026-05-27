#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BASE_DIR="${AI_CAPTURE_HOME:-$HOME/ai-capture-tool}"
SHARED_DIR="$BASE_DIR/shared"
CONFIG_DIR="$SHARED_DIR/config"
RUNTIME_DIR="$SHARED_DIR/runtime"
ENV_FILE="$CONFIG_DIR/.env.macmini"
CONSOLE_PYTHON="${CONSOLE_PYTHON:-}"
INSTALL_DEPS=0
CREATE_AVDS=0
INSTALL_SERVICE=0

for arg in "$@"; do
  case "$arg" in
    --install-deps) INSTALL_DEPS=1 ;;
    --create-avds) CREATE_AVDS=1 ;;
    --install-service) INSTALL_SERVICE=1 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

mkdir -p "$CONFIG_DIR" "$RUNTIME_DIR" "$SHARED_DIR/releases"

if [[ ! -f "$CONFIG_DIR/devices.macmini.json" ]]; then
  cp "$ROOT_DIR/config/devices.macmini.json.example" "$CONFIG_DIR/devices.macmini.json"
fi

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -z "$CONSOLE_PYTHON" ]]; then
    for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
      if command -v "$candidate" >/dev/null 2>&1; then
        CONSOLE_PYTHON="$(command -v "$candidate")"
        break
      fi
    done
  fi
  cat >"$ENV_FILE" <<EOF
CONSOLE_HOST=0.0.0.0
CONSOLE_PORT=7001
OPEN_WEB=0
START_FRONTEND_DEV=0
CONSOLE_PYTHON=${CONSOLE_PYTHON:-python3}
CAPTURE_RUNTIME_DIR=$RUNTIME_DIR
CAPTURE_DEVICES_CONFIG=$CONFIG_DIR/devices.macmini.json
ANDROID_SDK_ROOT=\${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}
JAVA_HOME=\${JAVA_HOME:-/opt/homebrew/opt/openjdk@21}
EOF
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

if [[ "$INSTALL_DEPS" == "1" ]]; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew not found. Install Homebrew first, then rerun bootstrap." >&2
    exit 1
  fi
  brew install python@3.14 node mitmproxy screen xz android-platform-tools openjdk@21 || true
  python3 -m pip install --user frida-tools
fi

"${CONSOLE_PYTHON:-python3}" -m venv "$ROOT_DIR/.venv-console"
"$ROOT_DIR/.venv-console/bin/python" -m pip install --upgrade pip >/dev/null
"$ROOT_DIR/.venv-console/bin/python" -m pip install -r "$ROOT_DIR/requirements-console.txt"
if [[ "${CONSOLE_INSTALL_CAPTURE_DEPS:-1}" != "0" ]]; then
  "$ROOT_DIR/.venv-console/bin/python" -m pip install frida-tools mitmproxy
fi

if [[ ! -f "$ROOT_DIR/web/dist/index.html" ]]; then
  (cd "$ROOT_DIR/web" && npm ci && npm run build)
fi

if [[ "$CREATE_AVDS" == "1" ]]; then
  "$ROOT_DIR/deploy/macmini/create_avds.sh"
fi

if [[ "$INSTALL_SERVICE" == "1" ]]; then
  "$ROOT_DIR/deploy/macmini/install_launchd.sh"
fi

"$ROOT_DIR/deploy/macmini/check_env.sh" || true

echo
echo "Mac mini 初始化完成。"
echo "环境文件: $ENV_FILE"
echo "运行目录: $RUNTIME_DIR"
echo "启动服务: $ROOT_DIR/deploy/macmini/start_service.sh"
echo "首次访问: http://<mac-mini-ip>:7001"
echo "首次访问后请按页面初始化向导完成 Google 登录、Frida 准入和抓包冒烟。"

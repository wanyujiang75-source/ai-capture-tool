#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

TARGET="${1:-}"
if [[ -n "$TARGET" && "$TARGET" != android && "$TARGET" != ios && "$TARGET" != "-h" && "$TARGET" != "--help" ]]; then
  echo "first argument must be android or ios" >&2
  echo "usage: $0 [android|ios] [--avd NAME] [--serial SERIAL] [--mode system|flutter-socks] [--package PACKAGE] [--no-clear] [--restart-mitm] [--open-ui]" >&2
  exit 1
fi
if [[ "$TARGET" == "-h" || "$TARGET" == "--help" ]]; then
  cat <<'USAGE'
usage: scripts/ai_capture.sh [android|ios] [options]

Starts a generic discovery capture. Do not pass the target URL here.
Operate any app on the emulator; the exporter finds likely business APIs
from captured traffic and writes request/response artifacts.

Options:
  --avd NAME          Android AVD to use. Defaults to ANDROID_CAPTURE_AVD.
  --serial SERIAL     adb serial to use. Avoids device auto-selection.
  --mode MODE         Android mode: system or flutter-socks. Default: system.
  --flutter-socks     Shortcut for --mode flutter-socks.
  --package PACKAGE   Android app package to launch/hook in flutter-socks mode.
  --activity COMP     Android activity component. Defaults to launcher activity.
  --no-clear          Do not clear existing mitmweb flows at startup.
  --restart-mitm      Restart mitmweb before capture.
  --open-ui           Open the mitmweb browser UI. Default: disabled.
  --no-open-ui        Keep the mitmweb browser UI closed.
  --interval SECONDS  Polling interval. Default: 2.
  --capture-noise     Also export Google/ad/analytics noise content.
USAGE
  exit 0
fi

if [[ -z "$TARGET" ]]; then
  echo "Select capture target:"
  echo "1) Android"
  echo "2) iOS"
  printf '> '
  read -r choice
  case "$choice" in
    1|android|Android) TARGET="android" ;;
    2|ios|iOS|IOS) TARGET="ios" ;;
    *) echo "invalid selection: $choice" >&2; exit 1 ;;
  esac
else
  shift
fi

AVD_NAME="${AVD_NAME:-$ANDROID_CAPTURE_AVD}"
PROXY_PORT="${PROXY_PORT:-9090}"
WEB_PORT="${WEB_PORT:-9091}"
FRIDA_PORT="${FRIDA_PORT:-27042}"
FRIDA_HOST="${FRIDA_HOST:-127.0.0.1:$FRIDA_PORT}"
FRIDA_PID_TIMEOUT="${FRIDA_PID_TIMEOUT:-60}"
MITMWEB_PASSWORD="${MITMWEB_PASSWORD:-android-capture}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-240}"
RUN_TS="${RUN_TS:-$(date +%Y%m%d-%H%M%S)}"
OUTDIR="${OUTDIR:-$RUNTIME_DIR/captures/ai-discover-$RUN_TS}"
CLEAR_FLOWS=1
OPEN_UI="${OPEN_UI:-0}"
RESTART_MITM=0
INTERVAL=2
CAPTURE_NOISE=0
CAPTURE_MODE="${CAPTURE_MODE:-system}"
APP_PACKAGE="${APP_PACKAGE:-}"
APP_ACTIVITY="${APP_ACTIVITY:-}"
CAPTURE_INSTANCE="${CAPTURE_INSTANCE:-device-1}"
CAPTURE_INSTANCE_SAFE="$(printf '%s' "$CAPTURE_INSTANCE" | tr -c 'A-Za-z0-9_.-' '_')"
INSTANCE_DIR="$RUNTIME_DIR/capture_instances/$CAPTURE_INSTANCE_SAFE"
COOKIE_FILE="${COOKIE_FILE:-$INSTANCE_DIR/mitmweb.cookies}"
EXPORTER_PID_FILE="$INSTANCE_DIR/ai_capture_export.pid"
EXPORTER_LAUNCHER_FILE="$INSTANCE_DIR/launch-ai-capture-export.sh"
EXPORTER_SCREEN_SESSION="ai-capture-export-$CAPTURE_INSTANCE_SAFE"
FRIDA_PID_FILE="$INSTANCE_DIR/ai_capture_frida.pid"
FRIDA_LAUNCHER_FILE="$INSTANCE_DIR/launch-ai-capture-frida.sh"
FRIDA_SCREEN_SESSION="ai-capture-frida-$CAPTURE_INSTANCE_SAFE"

while (($#)); do
  case "$1" in
    --avd)
      AVD_NAME="${2:?missing value for --avd}"
      shift 2
      ;;
    --serial)
      ADB_SERIAL="${2:?missing value for --serial}"
      export ADB_SERIAL
      shift 2
      ;;
    --mode)
      CAPTURE_MODE="${2:?missing value for --mode}"
      shift 2
      ;;
    --flutter-socks)
      CAPTURE_MODE="flutter-socks"
      shift
      ;;
    --package)
      APP_PACKAGE="${2:?missing value for --package}"
      shift 2
      ;;
    --activity)
      APP_ACTIVITY="${2:?missing value for --activity}"
      shift 2
      ;;
    --no-clear)
      CLEAR_FLOWS=0
      shift
      ;;
    --restart-mitm)
      RESTART_MITM=1
      shift
      ;;
    --no-open-ui)
      OPEN_UI=0
      shift
      ;;
    --open-ui)
      OPEN_UI=1
      shift
      ;;
    --interval)
      INTERVAL="${2:?missing value for --interval}"
      shift 2
      ;;
    --capture-noise)
      CAPTURE_NOISE=1
      shift
      ;;
    http://*|https://*)
      echo "URL is not an input for discovery capture." >&2
      echo "Start capture first, operate the app, then read summary.md for discovered URLs." >&2
      exit 1
      ;;
    *)
      echo "unknown option: $1" >&2
      exit 1
      ;;
esac
done

if [[ "$CAPTURE_MODE" != "system" && "$CAPTURE_MODE" != "flutter-socks" ]]; then
  echo "invalid --mode: $CAPTURE_MODE" >&2
  echo "valid modes: system, flutter-socks" >&2
  exit 1
fi

GOOGLE_PASSTHROUGH_HOSTS="${GOOGLE_PASSTHROUGH_HOSTS:-android\\.googleapis\\.com,android\\.apis\\.googleapis\\.com,geller-pa\\.googleapis\\.com,auditrecording-pa\\.googleapis\\.com,digitalassetlinks\\.googleapis\\.com,play\\.googleapis\\.com,voilatile-pa\\.googleapis\\.com,remoteprovisioning\\.googleapis\\.com,infinitedata-pa\\.googleapis\\.com,www\\.google\\.com,accounts\\.google\\.com,oauth2\\.googleapis\\.com}"
SDK_NOISE_PASSTHROUGH_HOSTS="${SDK_NOISE_PASSTHROUGH_HOSTS:-applovin\\.com,applvn\\.com,unityads\\.unity3d\\.com,doubleclick\\.net,googlesyndication\\.com,googleads\\.g\\.doubleclick\\.net,fundingchoicesmessages\\.google\\.com,app\\.adjust\\.com,axon\\.ai,crashlyticsreports-pa\\.googleapis\\.com,firebaselogging(-pa)?\\.googleapis\\.com,firebaseinstallations\\.googleapis\\.com,firebaseremoteconfigrealtime\\.googleapis\\.com,connectivitycheck\\.gstatic\\.com}"
MITMPROXY_IGNORE_HOSTS="${MITMPROXY_IGNORE_HOSTS:-$GOOGLE_PASSTHROUGH_HOSTS,$SDK_NOISE_PASSTHROUGH_HOSTS}"
export MITMPROXY_IGNORE_HOSTS

require_command "$ADB_BIN"
require_command curl
require_command lsof
require_command python3

mkdir -p "$OUTDIR"
mkdir -p "$INSTANCE_DIR"

stop_existing_exporter() {
  if command -v screen >/dev/null 2>&1; then
    screen -S "$EXPORTER_SCREEN_SESSION" -X quit >/dev/null 2>&1 || true
  fi
  if [[ -f "$EXPORTER_PID_FILE" ]]; then
    local old_pid
    old_pid="$(sed -n '1p' "$EXPORTER_PID_FILE")"
    if [[ -n "$old_pid" ]] && kill -0 "$old_pid" >/dev/null 2>&1; then
      kill "$old_pid" >/dev/null 2>&1 || true
      sleep 1
    fi
	    rm -f "$EXPORTER_PID_FILE"
	  fi
	  if [[ "$CAPTURE_INSTANCE" == "device-1" && -f "$RUNTIME_DIR/ai_capture_export.pid" ]]; then
	    local legacy_pid
	    legacy_pid="$(sed -n '1p' "$RUNTIME_DIR/ai_capture_export.pid")"
	    if [[ -n "$legacy_pid" ]] && kill -0 "$legacy_pid" >/dev/null 2>&1; then
	      kill "$legacy_pid" >/dev/null 2>&1 || true
	      sleep 1
	    fi
	    rm -f "$RUNTIME_DIR/ai_capture_export.pid"
	  fi
	}

stop_existing_frida() {
  if command -v screen >/dev/null 2>&1; then
    screen -S "$FRIDA_SCREEN_SESSION" -X quit >/dev/null 2>&1 || true
  fi
  if [[ -f "$FRIDA_PID_FILE" ]]; then
    local old_pid
    old_pid="$(sed -n '1p' "$FRIDA_PID_FILE")"
    if [[ -n "$old_pid" ]] && kill -0 "$old_pid" >/dev/null 2>&1; then
      kill "$old_pid" >/dev/null 2>&1 || true
      sleep 1
    fi
	    rm -f "$FRIDA_PID_FILE"
	  fi
	  if [[ "$CAPTURE_INSTANCE" == "device-1" && -f "$RUNTIME_DIR/ai_capture_frida.pid" ]]; then
	    local legacy_pid
	    legacy_pid="$(sed -n '1p' "$RUNTIME_DIR/ai_capture_frida.pid")"
	    if [[ -n "$legacy_pid" ]] && kill -0 "$legacy_pid" >/dev/null 2>&1; then
	      kill "$legacy_pid" >/dev/null 2>&1 || true
	      sleep 1
	    fi
	    rm -f "$RUNTIME_DIR/ai_capture_frida.pid"
	  fi
	}

ensure_mitmweb() {
  if [[ "$CAPTURE_MODE" == "flutter-socks" ]]; then
    PROXY_PORT="$PROXY_PORT" WEB_PORT="$WEB_PORT" MITMWEB_PASSWORD="$MITMWEB_PASSWORD" "$SCRIPT_DIR/start_mitm_socks_stack.sh" >/dev/null
    wait_for_listen_port "$PROXY_PORT" 30
    wait_for_listen_port "$WEB_PORT" 30
    return 0
  fi

  if [[ "$RESTART_MITM" == "1" ]]; then
    if command -v screen >/dev/null 2>&1; then
      screen -S "mitmweb-$PROXY_PORT" -X quit >/dev/null 2>&1 || true
    fi
    stop_owned_port_listeners "$PROXY_PORT" "mitmweb proxy"
    stop_owned_port_listeners "$WEB_PORT" "mitmweb web"
    refuse_foreign_port_owner "$PROXY_PORT" "mitmweb proxy"
    refuse_foreign_port_owner "$WEB_PORT" "mitmweb web"
    sleep 1
  fi

  refuse_foreign_port_owner "$PROXY_PORT" "mitmweb proxy"
  refuse_foreign_port_owner "$WEB_PORT" "mitmweb web"
  if ! lsof -iTCP:"$PROXY_PORT" -sTCP:LISTEN -n -P >/dev/null 2>&1; then
    PROXY_PORT="$PROXY_PORT" WEB_PORT="$WEB_PORT" MITMWEB_PASSWORD="$MITMWEB_PASSWORD" "$SCRIPT_DIR/start_mitm_stack.sh"
  fi
  wait_for_listen_port "$PROXY_PORT" 30
  wait_for_listen_port "$WEB_PORT" 30
}

online_devices() {
  "$ADB_BIN" devices | awk 'NR > 1 && $2 == "device" { print $1 }'
}

select_android_device() {
  if [[ -n "${ADB_SERIAL:-}" ]]; then
    adb_cmd wait-for-device
    return 0
  fi

  if detect_adb_serial_for_avd "$AVD_NAME"; then
    export ADB_SERIAL
    return 0
  fi

  devices=()
  while IFS= read -r device; do
    [[ -n "$device" ]] && devices+=("$device")
  done < <(online_devices)
  if (( ${#devices[@]} > 0 )); then
    echo "online adb devices exist, but retained target AVD is not online: $AVD_NAME" >&2
    echo "devices: ${devices[*]}" >&2
    echo "To avoid using the wrong emulator, close the other emulator or pass --serial SERIAL." >&2
    exit 1
  fi

  "$SCRIPT_DIR/start_play_emulator.sh" "$AVD_NAME"
  wait_for_adb_serial_for_avd "$AVD_NAME" "$BOOT_TIMEOUT"
  export ADB_SERIAL
}

start_exporter() {
  local args=(
    python3
    "$SCRIPT_DIR/ai_capture_export.py"
    --web-port "$WEB_PORT"
    --password "$MITMWEB_PASSWORD"
    --cookie-file "$COOKIE_FILE"
    --outdir "$OUTDIR"
    --interval "$INTERVAL"
  )
  if [[ "$CLEAR_FLOWS" == "1" ]]; then
    args+=(--clear)
  fi
  if [[ "$CAPTURE_NOISE" == "1" ]]; then
    args+=(--capture-noise)
  fi

  {
    printf '#!/usr/bin/env bash\n'
    printf 'echo $$ > %q\n' "$EXPORTER_PID_FILE"
    printf 'exec '
    printf '%q ' "${args[@]}"
    printf '>> %q 2>&1\n' "$OUTDIR/exporter.log"
  } > "$EXPORTER_LAUNCHER_FILE"
  chmod +x "$EXPORTER_LAUNCHER_FILE"

  if command -v screen >/dev/null 2>&1; then
    screen -S "$EXPORTER_SCREEN_SESSION" -X quit >/dev/null 2>&1 || true
    screen -dmS "$EXPORTER_SCREEN_SESSION" "$EXPORTER_LAUNCHER_FILE"
  else
    nohup "$EXPORTER_LAUNCHER_FILE" >/dev/null 2>&1 < /dev/null &
  fi
  sleep 1
}

clear_android_http_proxy() {
  adb_cmd shell settings put global http_proxy :0 >/dev/null 2>&1 || true
  adb_cmd shell settings delete global http_proxy >/dev/null 2>&1 || true
}

resolve_app_activity() {
  if [[ -n "$APP_ACTIVITY" ]]; then
    return 0
  fi
  APP_ACTIVITY="$(adb_cmd shell cmd package resolve-activity --brief "$APP_PACKAGE" | tr -d '\r' | tail -n 1)"
  if [[ -z "$APP_ACTIVITY" || "$APP_ACTIVITY" == "No activity found" ]]; then
    echo "unable to resolve launcher activity for package: $APP_PACKAGE" >&2
    exit 1
  fi
}

python_can_import_frida() {
  local candidate="${1:-}"
  local resolved=""

  [[ -n "$candidate" ]] || return 1
  if [[ "$candidate" == */* ]]; then
    [[ -x "$candidate" ]] || return 1
    resolved="$candidate"
  else
    resolved="$(command -v "$candidate" 2>/dev/null || true)"
    [[ -n "$resolved" ]] || return 1
  fi

  "$resolved" -c 'import frida' >/dev/null 2>&1
}

select_frida_python() {
  local candidate
  local resolved
  for candidate in \
    "${FRIDA_PYTHON_BIN:-}" \
    "python3" \
    "$ROOT_DIR/.venv-console/bin/python3" \
    "$ROOT_DIR/.venv-console/bin/python" \
    "$ROOT_DIR/.venv/bin/python3" \
    "$ROOT_DIR/.venv/bin/python" \
    "/Applications/Xcode.app/Contents/Developer/usr/bin/python3"; do
    if python_can_import_frida "$candidate"; then
      if [[ "$candidate" == */* ]]; then
        printf '%s\n' "$candidate"
      else
        resolved="$(command -v "$candidate")"
        printf '%s\n' "$resolved"
      fi
      return 0
    fi
  done
  return 1
}

start_flutter_socks_hook() {
  if [[ -z "$APP_PACKAGE" ]]; then
    echo "--package is required with --mode flutter-socks" >&2
    exit 1
  fi
  resolve_app_activity

  local frida_python=""
  if ! frida_python="$(select_frida_python)"; then
    cat >&2 <<EOF
unable to find a Python interpreter with the frida package installed.
Install console dependencies first:
  python3 -m venv .venv-console
  .venv-console/bin/pip install -r requirements-console.txt
Or set FRIDA_PYTHON_BIN to a Python executable that can import frida.
EOF
    exit 1
  fi
  local hook_path="$ROOT_DIR/.venv-console/bin:$ROOT_DIR/.venv/bin:$HOME/Library/Python/3.9/bin:$ANDROID_SDK_ROOT/platform-tools:/opt/homebrew/bin:/usr/local/bin"

  {
    printf '#!/usr/bin/env bash\n'
    printf 'echo $$ > %q\n' "$FRIDA_PID_FILE"
    printf 'cd %q\n' "$ROOT_DIR"
    printf 'export PATH=%q:"$PATH"\n' "$hook_path"
    printf 'exec %q %q ' "$frida_python" "$SCRIPT_DIR/flutter_proxy_unpin_capture.py"
    printf '%q ' \
      --serial "$ADB_SERIAL" \
      --package "$APP_PACKAGE" \
      --activity "$APP_ACTIVITY" \
	      --proxy-host 10.0.2.2 \
	      --proxy-port "$PROXY_PORT" \
	      --frida-host "$FRIDA_HOST" \
      --native-connect-hook \
      --socks5 \
      --no-proxy-env \
      --flutter-verify-success-value 1 \
      --no-force-stop \
      --pid-timeout "$FRIDA_PID_TIMEOUT" \
      --duration 0
    printf '>> %q 2>&1\n' "$OUTDIR/frida.log"
  } > "$FRIDA_LAUNCHER_FILE"
  chmod +x "$FRIDA_LAUNCHER_FILE"

  if command -v screen >/dev/null 2>&1; then
    screen -S "$FRIDA_SCREEN_SESSION" -X quit >/dev/null 2>&1 || true
    screen -dmS "$FRIDA_SCREEN_SESSION" "$FRIDA_LAUNCHER_FILE"
  else
    nohup "$FRIDA_LAUNCHER_FILE" >/dev/null 2>&1 < /dev/null &
  fi
  sleep 1
}

write_env_file() {
  {
	    printf 'TARGET=%q\n' "$TARGET"
	    printf 'CAPTURE_INSTANCE=%q\n' "$CAPTURE_INSTANCE"
	    printf 'AVD_NAME=%q\n' "$AVD_NAME"
	    printf 'ADB_SERIAL=%q\n' "${ADB_SERIAL:-}"
	    printf 'PROXY_PORT=%q\n' "$PROXY_PORT"
	    printf 'WEB_PORT=%q\n' "$WEB_PORT"
	    printf 'FRIDA_PORT=%q\n' "$FRIDA_PORT"
	    printf 'FRIDA_HOST=%q\n' "$FRIDA_HOST"
	    printf 'FRIDA_PID_TIMEOUT=%q\n' "$FRIDA_PID_TIMEOUT"
	    printf 'MITMWEB_PASSWORD=%q\n' "$MITMWEB_PASSWORD"
	    printf 'CAPTURE_MODE=%q\n' "$CAPTURE_MODE"
	    printf 'APP_PACKAGE=%q\n' "$APP_PACKAGE"
	    printf 'APP_ACTIVITY=%q\n' "$APP_ACTIVITY"
	    printf 'OUTDIR=%q\n' "$OUTDIR"
	  } > "$INSTANCE_DIR/ai_capture.env"
	  printf '%s\n' "$OUTDIR" > "$INSTANCE_DIR/last-ai-capture-dir.txt"
	  if [[ "$CAPTURE_INSTANCE" == "device-1" ]]; then
	    cp "$INSTANCE_DIR/ai_capture.env" "$RUNTIME_DIR/ai_capture.env"
	    printf '%s\n' "$OUTDIR" > "$RUNTIME_DIR/last-ai-capture-dir.txt"
	  fi
	}

case "$TARGET" in
  android)
    stop_existing_exporter
    stop_existing_frida
    ensure_mitmweb
    select_android_device
    wait_for_property sys.boot_completed 1 "$BOOT_TIMEOUT"
    if [[ "$CAPTURE_MODE" == "flutter-socks" ]]; then
      clear_android_http_proxy
    else
      ADB_SERIAL="$ADB_SERIAL" PROXY_PORT="$PROXY_PORT" "$SCRIPT_DIR/apply_android_proxy.sh" >/dev/null
    fi
    start_exporter
    if [[ "$CAPTURE_MODE" == "flutter-socks" ]]; then
      start_flutter_socks_hook
    fi
    write_env_file
    if [[ "$OPEN_UI" == "1" ]]; then
      WEB_PORT="$WEB_PORT" MITMWEB_PASSWORD="$MITMWEB_PASSWORD" "$SCRIPT_DIR/open_proxy_ui.sh" >/dev/null
    fi
    echo "AI capture discovery started"
    echo "target: Android"
    echo "mode: $CAPTURE_MODE"
    echo "avd: $AVD_NAME"
	    echo "serial: $ADB_SERIAL"
	    echo "instance: $CAPTURE_INSTANCE"
	    echo "proxy: 10.0.2.2:$PROXY_PORT"
    if [[ "$CAPTURE_MODE" == "flutter-socks" ]]; then
      echo "package: $APP_PACKAGE"
      echo "activity: $APP_ACTIVITY"
      echo "frida: $OUTDIR/frida.log"
    fi
    echo "web: http://127.0.0.1:$WEB_PORT/?token=$MITMWEB_PASSWORD"
    echo "outdir: $OUTDIR"
    echo "summary: $OUTDIR/summary.md"
    echo "operate any app now; discovered business APIs will appear in candidates.tsv and summary.md"
    ;;
  ios)
    ensure_mitmweb
    if [[ "$OPEN_UI" == "1" ]]; then
      WEB_PORT="$WEB_PORT" MITMWEB_PASSWORD="$MITMWEB_PASSWORD" "$SCRIPT_DIR/open_proxy_ui.sh" >/dev/null
    fi
    echo "AI capture discovery started"
    echo "target: iOS"
    echo "status: reserved for future extension; Android capture is implemented now"
    echo "web: http://127.0.0.1:$WEB_PORT/?token=$MITMWEB_PASSWORD"
    ;;
esac

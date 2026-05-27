#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${AI_CAPTURE_ENV_FILE:-$HOME/ai-capture-tool/shared/config/.env.macmini}"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}"
DEVICE_CONFIG="${CAPTURE_DEVICES_CONFIG:-$ROOT_DIR/config/devices.macmini.json.example}"
CONSOLE_PORT="${CONSOLE_PORT:-7001}"

if [[ -z "${JAVA_HOME:-}" ]]; then
  for candidate in \
    /opt/homebrew/opt/openjdk@21 \
    /opt/homebrew/opt/openjdk@17 \
    /opt/homebrew/opt/openjdk \
    /Library/Java/JavaVirtualMachines/*/Contents/Home; do
    if [[ -x "$candidate/bin/java" ]]; then
      export JAVA_HOME="$candidate"
      break
    fi
  done
fi

export PATH="$ROOT_DIR/.venv-console/bin:${JAVA_HOME:+$JAVA_HOME/bin:}$HOME/.local/bin:$HOME/Library/Python/3.12/bin:$HOME/Library/Python/3.11/bin:$HOME/Library/Python/3.10/bin:$HOME/Library/Python/3.9/bin:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/emulator:/opt/homebrew/bin:/usr/local/bin:$PATH"

JSON=0
if [[ "${1:-}" == "--json" ]]; then
  JSON=1
fi

if ! command -v python3 >/dev/null 2>&1; then
  if [[ "$JSON" == "1" ]]; then
    printf '{"ok":false,"checks":[{"name":"python3","ok":false,"detail":"not found","fix":"brew install python@3.14"}]}\n'
  else
    echo "AI抓包工具 Mac mini 环境检查"
    echo "FAIL  python3        not found"
    echo "fix: brew install python@3.14"
  fi
  exit 1
fi

JSON="$JSON" \
ANDROID_SDK_ROOT="$ANDROID_SDK_ROOT" \
DEVICE_CONFIG="$DEVICE_CONFIG" \
CONSOLE_PORT="$CONSOLE_PORT" \
python3 - <<'PY'
import json
import os
import shutil
import socket
import subprocess
from pathlib import Path

json_mode = os.environ.get("JSON") == "1"
sdk_root = Path(os.environ["ANDROID_SDK_ROOT"]).expanduser()
device_config = Path(os.environ["DEVICE_CONFIG"]).expanduser()
console_port = int(os.environ.get("CONSOLE_PORT") or 7001)

COMMANDS = [
    ("python3", "brew install python@3.14"),
    ("node", "brew install node"),
    ("npm", "brew install node"),
    ("adb", "安装 Android SDK platform-tools，并确认 adb 在 PATH 中。"),
    ("emulator", "安装 Android SDK emulator，并确认 emulator 在 PATH 中。"),
    ("sdkmanager", "安装 Android command line tools。"),
    ("avdmanager", "安装 Android command line tools。"),
    ("java", "brew install openjdk@21，并设置 JAVA_HOME=/opt/homebrew/opt/openjdk@21。"),
    ("mitmweb", "brew install mitmproxy"),
    ("frida", "python3 -m pip install frida-tools"),
    ("frida-ps", "python3 -m pip install frida-tools"),
    ("screen", "brew install screen"),
    ("xz", "brew install xz"),
]


def add(checks, name, ok, detail, fix="", category="env"):
    checks.append({
        "name": name,
        "ok": bool(ok),
        "detail": str(detail),
        "fix": "" if ok else fix,
        "category": category,
    })


def run_text(args):
    try:
        return subprocess.run(args, check=False, capture_output=True, text=True, timeout=12).stdout
    except Exception:
        return ""


def load_devices(checks):
    if not device_config.is_file():
        return []
    try:
        data = json.loads(device_config.read_text())
        devices = data.get("devices", data if isinstance(data, list) else [])
        return devices if isinstance(devices, list) else []
    except Exception as exc:
        add(checks, "devices_config_parse", False, f"{device_config}: {exc}", "修复设备配置 JSON 格式。", "devices")
        return []


def port_listeners(port):
    output = run_text(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"])
    lines = [line for line in output.splitlines()[1:] if line.strip()]
    return lines


checks = []
for command, fix in COMMANDS:
    found = shutil.which(command)
    add(checks, command, bool(found), found or "not found", fix)

add(checks, "android_sdk", sdk_root.is_dir(), sdk_root, "安装 Android Studio 或 Android command line tools，并设置 ANDROID_SDK_ROOT。")
add(checks, "devices_config", device_config.is_file(), device_config, "复制 config/devices.macmini.json.example 到共享配置目录。", "devices")

devices = load_devices(checks)
avd_names = set()
if shutil.which("emulator"):
    avd_names = {line.strip() for line in run_text(["emulator", "-list-avds"]).splitlines() if line.strip()}

for device in devices:
    if not int(device.get("enabled", 1)):
        continue
    avd = str(device.get("avd_name") or "")
    add(checks, f"avd:{avd}", avd in avd_names, avd or "missing avd_name", f"运行 deploy/macmini/create_avds.sh 创建 {avd}。", "devices")

ports = {console_port: "console"}
for device in devices:
    if not int(device.get("enabled", 1)):
        continue
    for key in ("proxy_port", "web_port", "frida_port"):
        value = device.get(key)
        if value:
            ports[int(value)] = f"{device.get('device_id')}:{key}"

for port, label in sorted(ports.items()):
    listeners = port_listeners(port)
    # 7001 在服务已启动时会被本工具占用；这里展示状态但不把它作为失败。
    ok = not listeners or port == console_port
    detail = "available" if not listeners else "listening: " + " | ".join(line.strip() for line in listeners[:2])
    add(checks, f"port:{port}", ok, f"{label} {detail}", f"释放端口 {port} 后重试。", "ports")

payload = {"ok": all(item["ok"] for item in checks), "checks": checks}
if json_mode:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
else:
    print("AI抓包工具 Mac mini 环境检查")
    for item in checks:
        state = "OK" if item["ok"] else "FAIL"
        print(f"{state:<5} {item['name']:<22} {item['detail']}")
        if item.get("fix"):
            print(f"      fix: {item['fix']}")
raise SystemExit(0 if payload["ok"] else 1)
PY

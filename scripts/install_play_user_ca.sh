#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

PLAY_AVD_NAME="${PLAY_AVD_NAME:-$ANDROID_CAPTURE_AVD}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-240}"
PIN="${PLAY_CA_PIN:-0000}"
PIN_HINT="your current device PIN"
CERT_SOURCE="${CERT_SOURCE:-$HOME/.mitmproxy/mitmproxy-ca-cert.cer}"
DEVICE_CERT_NAME="${DEVICE_CERT_NAME:-mitmproxy-ca-cert.cer.crt}"
DEVICE_CERT_PATH="/sdcard/Download/$DEVICE_CERT_NAME"

require_command "$ADB_BIN"

if [[ ! -f "$CERT_SOURCE" ]]; then
  echo "mitmproxy user CA not found: $CERT_SOURCE" >&2
  echo "start mitmweb once first so it can generate ~/.mitmproxy certificates" >&2
  exit 1
fi

wait_for_adb_serial_for_avd "$PLAY_AVD_NAME" "$BOOT_TIMEOUT"
adb_cmd wait-for-device
wait_for_property sys.boot_completed 1 "$BOOT_TIMEOUT"

adb_cmd shell mkdir -p /sdcard/Download >/dev/null
adb_cmd push "$CERT_SOURCE" "$DEVICE_CERT_PATH" >/dev/null

if adb_cmd shell locksettings verify --old "$PIN" >/dev/null 2>&1; then
  pin_status="verified existing PIN"
  PIN_HINT="$PIN"
elif adb_cmd shell locksettings set-pin "$PIN" >/dev/null 2>&1; then
  pin_status="set PIN to $PIN"
  PIN_HINT="$PIN"
else
  pin_status="could not set or verify PIN automatically"
fi

adb_cmd shell am start -a com.android.settings.MORE_SECURITY_PRIVACY_SETTINGS >/dev/null 2>&1 || true

echo "android serial: $ADB_SERIAL"
echo "android avd: $PLAY_AVD_NAME"
echo "copied CA to: $DEVICE_CERT_PATH"
echo "device PIN: $pin_status"
echo
echo "finish on the emulator:"
echo "1. More security & privacy -> Encryption & credentials"
echo "2. Install a certificate -> CA certificate"
echo "3. INSTALL ANYWAY"
echo "4. Enter PIN: $PIN_HINT"
echo "5. Downloads -> $DEVICE_CERT_NAME"
echo
echo "verify after installation:"
echo "Settings -> Trusted credentials -> User should list mitmproxy"

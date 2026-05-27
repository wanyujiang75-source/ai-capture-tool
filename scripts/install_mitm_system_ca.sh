#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

CERT_PEM="${CERT_PEM:-$HOME/.mitmproxy/mitmproxy-ca-cert.pem}"
DEVICE_CERT_DIR="/data/local/tmp/mitm-cacerts"

require_command "$ADB_BIN"
require_command openssl

if [[ ! -f "$CERT_PEM" ]]; then
  echo "mitmproxy CA not found: $CERT_PEM" >&2
  exit 1
fi

HASH="$(openssl x509 -inform PEM -subject_hash_old -in "$CERT_PEM" | head -1)"
TMP_CERT="$(mktemp "/tmp/${HASH}.XXXXXX.0")"
CERT_NAME="${HASH}.0"
cp "$CERT_PEM" "$TMP_CERT"

cleanup() {
  rm -f "$TMP_CERT"
}
trap cleanup EXIT

adb_root_wait
adb_cmd push "$TMP_CERT" "/data/local/tmp/$CERT_NAME" >/dev/null

adb_cmd shell "
set -e
mkdir -p '$DEVICE_CERT_DIR'
cp /apex/com.android.conscrypt/cacerts/* '$DEVICE_CERT_DIR'/ 2>/dev/null || true
cp '/data/local/tmp/$CERT_NAME' '$DEVICE_CERT_DIR/$CERT_NAME'
chmod 755 '$DEVICE_CERT_DIR'
chmod 644 '$DEVICE_CERT_DIR'/*
chown root:root '$DEVICE_CERT_DIR' '$DEVICE_CERT_DIR'/*
chcon u:object_r:system_security_cacerts_file:s0 '$DEVICE_CERT_DIR'
chcon u:object_r:system_security_cacerts_file:s0 '$DEVICE_CERT_DIR'/*
mount --bind '$DEVICE_CERT_DIR' /system/etc/security/cacerts
mount --bind '$DEVICE_CERT_DIR' /apex/com.android.conscrypt/cacerts
for proc_name in zygote64 zygote webview_zygote com.android.chrome_zygote com.android.networkstack.process; do
  for pid in \$(pidof \$proc_name 2>/dev/null); do
    nsenter --mount=/proc/\$pid/ns/mnt -- mount --bind '$DEVICE_CERT_DIR' /system/etc/security/cacerts || true
    nsenter --mount=/proc/\$pid/ns/mnt -- mount --bind '$DEVICE_CERT_DIR' /apex/com.android.conscrypt/cacerts || true
  done
done
am force-stop com.android.chrome >/dev/null 2>&1 || true
am force-stop com.google.android.webview >/dev/null 2>&1 || true
ls -Z /apex/com.android.conscrypt/cacerts/$CERT_NAME
"

echo "android serial: $(adb_get_serial)"
echo "installed mitmproxy CA as temporary system CA: $CERT_NAME"
echo "rerun this script after each emulator reboot"

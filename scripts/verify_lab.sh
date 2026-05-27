#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

PROXY_PORT="${PROXY_PORT:-9090}"
WEB_PORT="${WEB_PORT:-9091}"
CERT_PEM="${CERT_PEM:-$HOME/.mitmproxy/mitmproxy-ca-cert.pem}"

require_command "$ADB_BIN"
require_command openssl

HASH="$(openssl x509 -inform PEM -subject_hash_old -in "$CERT_PEM" | head -1)"
CERT_NAME="${HASH}.0"

echo "[host] ports"
lsof -iTCP:"$PROXY_PORT" -sTCP:LISTEN -n -P 2>/dev/null || true
lsof -iTCP:"$WEB_PORT" -sTCP:LISTEN -n -P 2>/dev/null || true

echo
echo "[android] devices"
adb_cmd devices -l

echo
echo "[android] root"
adb_root_wait
adb_cmd shell id

echo
echo "[android] proxy"
adb_cmd shell settings get global http_proxy

echo
echo "[android] mounted CA"
adb_cmd shell "ls -Z /apex/com.android.conscrypt/cacerts/$CERT_NAME /system/etc/security/cacerts/$CERT_NAME"

echo
echo "[zygote namespace]"
adb_cmd shell "for p in \$(pidof zygote64 zygote webview_zygote com.android.chrome_zygote 2>/dev/null); do echo PID:\$p; nsenter --mount=/proc/\$p/ns/mnt -- ls /apex/com.android.conscrypt/cacerts/$CERT_NAME; done"

echo
echo "[networkstack namespace]"
adb_cmd shell "for p in \$(pidof com.android.networkstack.process 2>/dev/null); do echo PID:\$p; nsenter --mount=/proc/\$p/ns/mnt -- ls /apex/com.android.conscrypt/cacerts/$CERT_NAME; done"

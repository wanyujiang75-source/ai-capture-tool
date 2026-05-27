#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

AVD_NAME="${AVD_NAME:-lab-android35-gapi}"
ARCHIVE_NAME="${ARCHIVE_NAME:-pokehub}"
PACKAGE="${PACKAGE:-com.mi.poketrade}"
ACTIVITY="${ACTIVITY:-com.mi.poketrade.MainActivity}"
PROXY_PORT="${PROXY_PORT:-9090}"
WEB_PORT="${WEB_PORT:-9091}"
MITMWEB_PASSWORD="${MITMWEB_PASSWORD:-android-capture}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-240}"
RUN_TS="${RUN_TS:-$(date +%Y%m%d-%H%M%S)}"
OUTDIR="${OUTDIR:-$ROOT_DIR/runtime/captures/pokehub-functional-$RUN_TS}"
COOKIE_FILE="${COOKIE_FILE:-/tmp/mitmweb-pokehub-functional.cookies}"
AUTO_GOOGLE_ACCOUNT="${AUTO_GOOGLE_ACCOUNT:-1}"
RESTART_MITM="${RESTART_MITM:-0}"
RESET_APP="${RESET_APP:-1}"
CAPTURE_MARKET_CARD="${CAPTURE_MARKET_CARD:-0}"
GOOGLE_PASSTHROUGH_HOSTS="${GOOGLE_PASSTHROUGH_HOSTS:-android\\.googleapis\\.com,android\\.apis\\.googleapis\\.com,geller-pa\\.googleapis\\.com,auditrecording-pa\\.googleapis\\.com,digitalassetlinks\\.googleapis\\.com,play\\.googleapis\\.com,voilatile-pa\\.googleapis\\.com,remoteprovisioning\\.googleapis\\.com,infinitedata-pa\\.googleapis\\.com,www\\.google\\.com,accounts\\.google\\.com,oauth2\\.googleapis\\.com}"
SDK_NOISE_PASSTHROUGH_HOSTS="${SDK_NOISE_PASSTHROUGH_HOSTS:-applovin\\.com,applvn\\.com,unityads\\.unity3d\\.com,facebook\\.com,doubleclick\\.net,googlesyndication\\.com,googleads\\.g\\.doubleclick\\.net,fundingchoicesmessages\\.google\\.com,app\\.adjust\\.com,axon\\.ai,crashlyticsreports-pa\\.googleapis\\.com,firebaselogging(-pa)?\\.googleapis\\.com,firebaseinappmessaging\\.googleapis\\.com,firebaseinstallations\\.googleapis\\.com,firebaseremoteconfigrealtime\\.googleapis\\.com,connectivitycheck\\.gstatic\\.com}"
MITMPROXY_IGNORE_HOSTS="${MITMPROXY_IGNORE_HOSTS:-$GOOGLE_PASSTHROUGH_HOSTS,$SDK_NOISE_PASSTHROUGH_HOSTS}"
export MITMPROXY_IGNORE_HOSTS

mkdir -p "$OUTDIR"

require_command "$ADB_BIN"
require_command curl
require_command jq
require_command lsof
require_command openssl
require_command python3
require_command rg

log() {
  printf '%s\n' "$*" | tee -a "$OUTDIR/run.log"
}

ensure_mitmweb() {
  if [[ "$RESTART_MITM" == "1" ]]; then
    if command -v screen >/dev/null 2>&1; then
      screen -S "mitmweb-$PROXY_PORT" -X quit >/dev/null 2>&1 || true
    fi
    while read -r pid; do
      [[ -n "$pid" ]] && kill "$pid" >/dev/null 2>&1 || true
    done < <(lsof -tiTCP:"$PROXY_PORT" -sTCP:LISTEN -n -P 2>/dev/null || true)
    while read -r pid; do
      [[ -n "$pid" ]] && kill "$pid" >/dev/null 2>&1 || true
    done < <(lsof -tiTCP:"$WEB_PORT" -sTCP:LISTEN -n -P 2>/dev/null || true)
    sleep 1
  fi

  if ! lsof -iTCP:"$PROXY_PORT" -sTCP:LISTEN -n -P >/dev/null 2>&1; then
    PROXY_PORT="$PROXY_PORT" WEB_PORT="$WEB_PORT" MITMWEB_PASSWORD="$MITMWEB_PASSWORD" "$SCRIPT_DIR/start_mitm_stack.sh"
  fi
  wait_for_listen_port "$PROXY_PORT" 30
  wait_for_listen_port "$WEB_PORT" 30
}

ensure_device() {
  if ! detect_adb_serial_for_avd "$AVD_NAME"; then
    "$SCRIPT_DIR/start_lab_emulator.sh" "$AVD_NAME"
    wait_for_adb_serial_for_avd "$AVD_NAME" "$BOOT_TIMEOUT"
  fi
  export ADB_SERIAL
  adb_cmd wait-for-device
  wait_for_property sys.boot_completed 1 "$BOOT_TIMEOUT"
}

ensure_app_installed() {
  if adb_cmd shell pm path "$PACKAGE" >/dev/null 2>&1; then
    return 0
  fi

  log "installing archived app: $ARCHIVE_NAME"
  ADB_SERIAL="$ADB_SERIAL" "$SCRIPT_DIR/install_archived_app.sh" "$ARCHIVE_NAME" | tee -a "$OUTDIR/run.log"
}

ensure_proxy_and_ca() {
  local root_output
  local cert_hash

  root_output="$(adb_cmd root 2>&1 || true)"
  if [[ "$root_output" == *"cannot run as root"* ]]; then
    echo "AVD is not rootable: $AVD_NAME" >&2
    echo "方案1 requires a rootable Google APIs emulator, not a Google Play production image." >&2
    exit 1
  fi

  wait_for_adb_serial_for_avd "$AVD_NAME" "$BOOT_TIMEOUT"
  cert_hash="$(openssl x509 -inform PEM -subject_hash_old -in "$HOME/.mitmproxy/mitmproxy-ca-cert.pem" | head -1)"
  if ! adb_cmd shell "ls /apex/com.android.conscrypt/cacerts/$cert_hash.0 /system/etc/security/cacerts/$cert_hash.0 >/dev/null 2>&1"; then
    ADB_SERIAL="$ADB_SERIAL" "$SCRIPT_DIR/install_mitm_system_ca.sh" >/dev/null
  fi

  ADB_SERIAL="$ADB_SERIAL" PROXY_PORT="$PROXY_PORT" "$SCRIPT_DIR/apply_android_proxy.sh" >/dev/null
}

disable_android_proxy() {
  adb_cmd shell settings put global http_proxy :0
}

enable_android_proxy() {
  ADB_SERIAL="$ADB_SERIAL" PROXY_PORT="$PROXY_PORT" "$SCRIPT_DIR/apply_android_proxy.sh" >/dev/null
}

dump_ui() {
  local file="$1"
  local attempt

  for attempt in 1 2 3 4 5; do
    adb_cmd exec-out uiautomator dump /dev/tty > "$file" 2>/dev/null || true
    if rg -q '</hierarchy>' "$file"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

pick_text_center() {
  local xml_file="$1"
  local target="$2"

  python3 - "$xml_file" "$target" <<'PY'
import re
import sys
import xml.etree.ElementTree as ET

path, target = sys.argv[1:3]
data = open(path, encoding="utf-8", errors="replace").read()
end = data.find("</hierarchy>")
if end != -1:
    data = data[: end + len("</hierarchy>")]
root = ET.fromstring(data)
for node in root.iter():
    if node.attrib.get("text") == target or node.attrib.get("content-desc") == target:
        match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.attrib.get("bounds", ""))
        if match:
            x1, y1, x2, y2 = map(int, match.groups())
            print((x1 + x2) // 2, (y1 + y2) // 2)
            raise SystemExit(0)
raise SystemExit(2)
PY
}

tap_text_if_present() {
  local xml_file="$1"
  local target="$2"
  local coords

  coords="$(pick_text_center "$xml_file" "$target" 2>/dev/null || true)"
  if [[ -n "$coords" ]]; then
    adb_cmd shell input tap $coords
    return 0
  fi
  return 1
}

launch_app() {
  adb_cmd shell am start -n "$PACKAGE/$ACTIVITY" >/dev/null
}

login_if_needed() {
  local xml_file="$OUTDIR/login-check.xml"

  dump_ui "$xml_file"
  if ! rg -q 'Continue with Google' "$xml_file"; then
    return 0
  fi

  log "login screen detected; disabling proxy for Google OAuth"
  disable_android_proxy
  adb_cmd shell input tap 540 1820
  sleep 8

  dump_ui "$OUTDIR/google-account-picker.xml"
  if rg -q 'Choose an account' "$OUTDIR/google-account-picker.xml"; then
    if [[ "$AUTO_GOOGLE_ACCOUNT" != "1" ]]; then
      echo "Google account picker is open; choose an account on the emulator, then rerun this script." >&2
      exit 1
    fi
    adb_cmd shell input tap 540 1298
    sleep 30
  else
    sleep 20
  fi

  dump_ui "$OUTDIR/login-after-direct.xml"
  if rg -q 'Continue with Google' "$OUTDIR/login-after-direct.xml"; then
    echo "PokeHub is still on the login screen." >&2
    echo "Use the emulator UI to finish Google login while proxy is off, then rerun this script." >&2
    exit 1
  fi

  log "Google login completed with proxy disabled"
  enable_android_proxy
}

dismiss_guides() {
  local xml_file

  for i in $(seq 1 14); do
    xml_file="$OUTDIR/guide-$i.xml"
    dump_ui "$xml_file"
    if ! rg -q 'Next|OK|Dismiss|Previous|Introducing|feedback|Brand New|guide|friend id|Match' "$xml_file"; then
      return 0
    fi
    if tap_text_if_present "$xml_file" "OK"; then
      sleep 2
      continue
    fi
    if tap_text_if_present "$xml_file" "Next"; then
      sleep 2
      continue
    fi
    if tap_text_if_present "$xml_file" "Dismiss"; then
      sleep 2
      continue
    fi
    adb_cmd shell input tap 740 1657
    sleep 2
  done
}

mitm_clear() {
  WEB_PORT="$WEB_PORT" MITMWEB_PASSWORD="$MITMWEB_PASSWORD" COOKIE_FILE="$COOKIE_FILE" "$SCRIPT_DIR/mitmweb_clear.sh" >/dev/null
}

fetch_flows() {
  local output_json="$1"
  curl -sS -b "$COOKIE_FILE" "http://127.0.0.1:$WEB_PORT/flows" > "$output_json"
}

summarize_flows() {
  local operation="$1"
  local json_file="$OUTDIR/$operation.flows.json"
  local csv_file="$OUTDIR/$operation.flows.csv"
  local summary_file="$OUTDIR/$operation.summary.txt"
  local ids_file="$OUTDIR/$operation.flow-ids.tsv"
  local content_dir="$OUTDIR/$operation-content"

  mkdir -p "$content_dir"
  fetch_flows "$json_file"

  python3 - "$json_file" "$csv_file" "$summary_file" "$ids_file" <<'PY'
import collections
import csv
import json
import sys

src, csv_dst, summary_dst, ids_dst = sys.argv[1:5]
flows = json.load(open(src))

sdk_noise = (
    "applovin",
    "applvn",
    "app-measurement",
    "adjust.com",
    "bidease",
    "connectivitycheck",
    "doubleclick",
    "facebook.com",
    "fundingchoicesmessages",
    "googleads",
    "googlesyndication",
    "gstatic",
    "impression.link",
    "liftoff",
    "unityads",
    "vungle",
)

auth_config = (
    "clientauthconfig.googleapis.com",
    "firebaseappcheck.googleapis.com",
    "firebaseinappmessaging.googleapis.com",
    "firebaseinstallations.googleapis.com",
    "firebaselogging.googleapis.com",
    "identitytoolkit.googleapis.com",
    "oauth2.googleapis.com",
    "securetoken.googleapis.com",
)

business_markers = (
    "cloudfunctions.net",
    "firebasedatabase.app",
    "firebaseio.com",
    "firestore.googleapis.com",
    "pokehub",
    "poketrade",
    "supabase.co",
)


def build_url(req):
    scheme = req.get("scheme") or "http"
    host = req.get("host") or req.get("pretty_host") or ""
    port = req.get("port")
    endpoint_path = req.get("path") or "/"
    default_port = 443 if scheme == "https" else 80
    netloc = host if not port or port == default_port else f"{host}:{port}"
    return f"{scheme}://{netloc}{endpoint_path}"


def header(headers, name):
    for key, value in headers or []:
        if key.lower() == name.lower():
            return value
    return ""


def classify(host, endpoint_path, url):
    low = f"{host}{endpoint_path}{url}".lower()
    if any(marker in low for marker in business_markers):
        return "BUSINESS_CANDIDATE"
    if host in auth_config:
        return "AUTH_OR_CONFIG"
    if "googleapis.com" in host and ("/google.firestore." in endpoint_path or "firestore" in low):
        return "BUSINESS_CANDIDATE"
    if any(marker in low for marker in sdk_noise):
        return "SDK_NOISE"
    if "googleapis.com" in host or "google.com" in host:
        return "GOOGLE_OTHER"
    return "OTHER"


rows = []
by_host = collections.Counter()
by_kind = collections.Counter()
by_status = collections.Counter()
extract_ids = []

for flow in flows:
    if flow.get("type") != "http":
        continue
    req = flow.get("request") or {}
    resp = flow.get("response") or {}
    endpoint_path = req.get("path") or ""
    url = build_url(req)
    host = req.get("host") or req.get("pretty_host") or ""
    kind = classify(host, endpoint_path, url)
    status = resp.get("status_code", "NO_RESPONSE")
    row = [
        kind,
        flow.get("id", ""),
        req.get("method", ""),
        status,
        host,
        endpoint_path,
        url,
        header(req.get("headers"), "content-type"),
        header(resp.get("headers"), "content-type"),
        req.get("contentLength", ""),
        resp.get("contentLength", ""),
        req.get("timestamp_start", ""),
        flow.get("error", {}).get("msg", ""),
    ]
    rows.append(row)
    by_host[host] += 1
    by_kind[kind] += 1
    by_status[str(status)] += 1
    if kind in {"BUSINESS_CANDIDATE", "AUTH_OR_CONFIG", "OTHER"}:
        extract_ids.append(row)

with open(csv_dst, "w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(
        [
            "kind",
            "id",
            "method",
            "status",
            "host",
            "path",
            "url",
            "request_content_type",
            "response_content_type",
            "req_bytes",
            "resp_bytes",
            "timestamp_start",
            "error",
        ]
    )
    writer.writerows(rows)

with open(summary_dst, "w") as file:
    file.write(f"flows_total={len(flows)}\nhttp_flows={len(rows)}\n")
    file.write("kind_counts:\n")
    for key, value in by_kind.most_common():
        file.write(f"  {key}: {value}\n")
    file.write("status_counts:\n")
    for key, value in by_status.most_common():
        file.write(f"  {key}: {value}\n")
    file.write("top_hosts:\n")
    for host, count in by_host.most_common(50):
        file.write(f"  {count} {host}\n")
    file.write("interface_candidates:\n")
    for row in extract_ids:
        file.write("  " + " | ".join(map(str, [row[0], row[2], row[3], row[4], row[5], row[12]])) + "\n")

with open(ids_dst, "w") as file:
    for row in extract_ids:
        file.write("\t".join(map(str, [row[1], row[0], row[2], row[4], row[5]])) + "\n")
PY

  while IFS=$'\t' read -r flow_id kind method host endpoint_path; do
    [[ -z "${flow_id:-}" ]] && continue
    local safe
    safe="${kind}_${method}_${host}_${endpoint_path}"
    safe="$(printf '%s' "$safe" | tr '/:?=&' '_____' | tr -cd '[:alnum:]_.-')"
    safe="${safe:0:180}"
    curl -sS -b "$COOKIE_FILE" "http://127.0.0.1:$WEB_PORT/flows/$flow_id/request/content.data" -o "$content_dir/$safe.request.bin" || true
    curl -sS -b "$COOKIE_FILE" "http://127.0.0.1:$WEB_PORT/flows/$flow_id/response/content.data" -o "$content_dir/$safe.response.bin" || true
  done < "$ids_file"
}

capture_op() {
  local operation="$1"
  local description="$2"
  shift 2

  log ""
  log "=== $operation: $description ==="
  mitm_clear
  adb_cmd logcat -c || true
  "$@"
  sleep 8
  dismiss_guides
  adb_cmd exec-out screencap -p > "$OUTDIR/$operation.png"
  dump_ui "$OUTDIR/$operation.xml"
  python3 /Users/wan/.codex/plugins/cache/openai-curated/test-android-apps/82fd64bc/skills/android-emulator-qa/scripts/ui_tree_summarize.py "$OUTDIR/$operation.xml" "$OUTDIR/$operation.ui-summary.txt" || true
  adb_cmd logcat -d > "$OUTDIR/$operation.logcat.txt" || true
  summarize_flows "$operation"
  log "$OUTDIR/$operation.summary.txt"
}

tap() {
  adb_cmd shell input tap "$1" "$2"
}

tap_node() {
  local target="$1"
  local xml_file="$OUTDIR/tap-node.xml"
  local coords

  dump_ui "$xml_file"
  coords="$(pick_text_center "$xml_file" "$target" 2>/dev/null || true)"
  if [[ -z "$coords" ]]; then
    echo "node not found in UI tree: $target" >&2
    return 1
  fi
  adb_cmd shell input tap $coords
}

key_back() {
  adb_cmd shell input keyevent 4 || true
}

build_interface_map() {
  python3 - "$OUTDIR" <<'PY'
import csv
import glob
import os
import sys

outdir = sys.argv[1]
rows = []
for csv_path in sorted(glob.glob(os.path.join(outdir, "*.flows.csv"))):
    operation = os.path.basename(csv_path).replace(".flows.csv", "")
    with open(csv_path, newline="") as file:
        for row in csv.DictReader(file):
            if row["kind"] in {"BUSINESS_CANDIDATE", "AUTH_OR_CONFIG", "OTHER"}:
                rows.append({"operation": operation, **row})

output = os.path.join(outdir, "operation-interface-map.csv")
fieldnames = [
    "operation",
    "kind",
    "id",
    "method",
    "status",
    "host",
    "path",
    "url",
    "request_content_type",
    "response_content_type",
    "req_bytes",
    "resp_bytes",
    "timestamp_start",
    "error",
]
with open(output, "w", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"OUTDIR={outdir}")
print(f"INTERFACE_MAP={output}")
print(f"ROWS={len(rows)}")
for row in rows[:160]:
    print(f"{row['operation']} | {row['kind']} | {row['method']} {row['status']} | {row['url']} | {row['error']}")
PY
}

ensure_mitmweb
ensure_device
ensure_app_installed
ensure_proxy_and_ca

log "android serial: $ADB_SERIAL"
log "android avd: $AVD_NAME"
log "package: $PACKAGE"
log "output: $OUTDIR"
log "proxy ui: http://127.0.0.1:$WEB_PORT/?token=$MITMWEB_PASSWORD"

if [[ "$RESET_APP" == "1" ]]; then
  adb_cmd shell am force-stop "$PACKAGE" >/dev/null 2>&1 || true
fi
launch_app
sleep 8
login_if_needed
sleep 3
dismiss_guides

capture_op market_tab "Bottom tab: Market" tap_node "Market"
capture_op exchange_tab "Bottom tab: Exchange" tap_node "Exchange"
capture_op message_tab "Bottom tab: Message" tap_node "Message"
capture_op hub_tab "Bottom tab: Hub" tap_node "Hub"
capture_op me_tab "Bottom tab: Me/Profile" tap_node "Me"
capture_op me_inventory "Me: Inventory tab" tap_node "Inventory"
capture_op me_wishlist "Me: Wishlist tab" tap_node "Wishlist"
capture_op me_posts "Me: Posts tab" tap_node "Posts"
capture_op me_seeking "Me: Seeking tab" tap 345 699

if [[ "$CAPTURE_MARKET_CARD" == "1" ]]; then
  tap_node "Market"
  sleep 2
  capture_op market_card_first "Market: first visible card detail" tap 192 947
  key_back
fi

build_interface_map | tee -a "$OUTDIR/run.log"

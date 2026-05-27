#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

AVD_NAME="${AVD_NAME:-$ANDROID_CAPTURE_AVD}"
PACKAGE="${PACKAGE:-com.meta.inno.sticker}"
ACTIVITY="${ACTIVITY:-com.meta.inno.monopoly_sticker.MainActivity}"
PROXY_PORT="${PROXY_PORT:-9090}"
WEB_PORT="${WEB_PORT:-9091}"
MITMWEB_PASSWORD="${MITMWEB_PASSWORD:-android-capture}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-240}"
RUN_TS="${RUN_TS:-$(date +%Y%m%d-%H%M%S)}"
OUTDIR="${OUTDIR:-$ROOT_DIR/runtime/captures/functional-$RUN_TS}"
COOKIE_FILE="${COOKIE_FILE:-/tmp/mitmweb-functional.cookies}"

mkdir -p "$OUTDIR"

require_command "$ADB_BIN"
require_command curl
require_command lsof
require_command rg

log() {
  printf '%s\n' "$*" | tee -a "$OUTDIR/run.log"
}

ensure_mitmweb() {
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

ensure_proxy_and_ca() {
  PROXY_PORT="$PROXY_PORT" "$SCRIPT_DIR/apply_android_proxy.sh" >/dev/null

  local cert_hash
  cert_hash="$(openssl x509 -inform PEM -subject_hash_old -in "$HOME/.mitmproxy/mitmproxy-ca-cert.pem" | head -1)"
  if ! adb_cmd shell "ls /apex/com.android.conscrypt/cacerts/$cert_hash.0 /system/etc/security/cacerts/$cert_hash.0 >/dev/null 2>&1"; then
    local root_output
    root_output="$(adb_cmd root 2>&1 || true)"
    if [[ "$root_output" == *"cannot run as root"* ]]; then
      log "system CA skipped: $AVD_NAME is a non-root Google Play build"
      log "HTTPS decryption depends on the user CA being installed and trusted by the app"
    else
      wait_for_adb_serial_for_avd "$AVD_NAME" "$BOOT_TIMEOUT"
      ADB_SERIAL="$ADB_SERIAL" "$SCRIPT_DIR/install_mitm_system_ca.sh" >/dev/null
    fi
  fi
}

mitm_clear() {
  WEB_PORT="$WEB_PORT" MITMWEB_PASSWORD="$MITMWEB_PASSWORD" COOKIE_FILE="$COOKIE_FILE" "$SCRIPT_DIR/mitmweb_clear.sh" >/dev/null
}

fetch_flows() {
  local output_json="$1"
  curl -sS -b "$COOKIE_FILE" "http://127.0.0.1:$WEB_PORT/flows" > "$output_json"
}

close_popups() {
  local tmpxml="$1"
  adb_cmd exec-out uiautomator dump /dev/tty > "$tmpxml" 2>/dev/null || true
  if rg -q 'Ad-Free Mode|Watch Ads|Scrim' "$tmpxml"; then
    adb_cmd shell input tap 1006 1450
    sleep 2
  fi
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

  /opt/homebrew/bin/python3 - "$json_file" "$csv_file" "$summary_file" "$ids_file" <<'PY'
import collections
import csv
import json
import sys

src, csv_dst, summary_dst, ids_dst = sys.argv[1:5]
flows = json.load(open(src))
noise = (
    "googleads",
    "googlesyndication",
    "doubleclick",
    "gstatic",
    "googleapis",
    "connectivitycheck",
    "vungle",
    "bidease",
    "adjust.com",
    "app-measurement",
    "firebase",
    "intercom",
    "nexus-websocket",
    "google.com",
    "liftoff",
    "app-install.bid",
    "tobsnssdk",
    "facebook.com",
)
app_hosts = {"app.stickerhub.io", "pbzhiqxtoqqgizddjblb.supabase.co"}
page_paths = {"/app/events", "/activity", "/free-mini-game"}


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
    low = url.lower()
    if host == "pbzhiqxtoqqgizddjblb.supabase.co" and endpoint_path.startswith("/functions/v1/"):
        return "API"
    if host == "app.stickerhub.io" and endpoint_path in page_paths:
        return "H5_PAGE"
    if host in app_hosts and (
        endpoint_path.startswith("/assets/")
        or endpoint_path.startswith("/storage/")
        or endpoint_path in {"/loading.css", "/favicon.png"}
    ):
        return "STATIC_RESOURCE"
    if host in app_hosts:
        return "APP_RELATED"
    if any(item in low for item in noise):
        return "SDK_NOISE"
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
        header(resp.get("headers"), "content-type"),
        req.get("contentLength", ""),
        resp.get("contentLength", ""),
        req.get("timestamp_start", ""),
    ]
    rows.append(row)
    by_host[host] += 1
    by_kind[kind] += 1
    by_status[str(status)] += 1
    if kind in {"API", "H5_PAGE", "APP_RELATED"}:
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
            "content_type",
            "req_bytes",
            "resp_bytes",
            "timestamp_start",
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
    for host, count in by_host.most_common(40):
        file.write(f"  {count} {host}\n")
    file.write("app_business_candidates:\n")
    for row in extract_ids:
        file.write("  " + " | ".join(map(str, [row[0], row[2], row[3], row[4], row[5], row[6]])) + "\n")

with open(ids_dst, "w") as file:
    for row in extract_ids:
        file.write("\t".join(map(str, [row[1], row[0], row[2], row[4], row[5]])) + "\n")
PY

  while IFS=$'\t' read -r flow_id kind method host endpoint_path; do
    [[ -z "${flow_id:-}" ]] && continue
    local safe
    safe="${kind}_${method}_${host}_${endpoint_path}"
    safe="$(printf '%s' "$safe" | tr '/:?=&' '_____' | tr -cd '[:alnum:]_.-')"
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
  close_popups "/tmp/$operation-before.xml"
  mitm_clear
  fetch_flows "/tmp/$operation-after-clear.json"
  /opt/homebrew/bin/python3 - "$operation" "/tmp/$operation-after-clear.json" <<'PY' | tee -a "$OUTDIR/run.log"
import json
import sys

operation, path = sys.argv[1:3]
print(f"{operation} flows_after_clear={len(json.load(open(path)))}")
PY
  adb_cmd logcat -c
  "$@"
  sleep 7
  close_popups "/tmp/$operation-after-popup.xml"
  adb_cmd exec-out screencap -p > "$OUTDIR/$operation.png"
  adb_cmd exec-out uiautomator dump /dev/tty > "$OUTDIR/$operation.xml"
  adb_cmd logcat -d > "$OUTDIR/$operation.logcat.txt"
  summarize_flows "$operation"
  log "$OUTDIR/$operation.summary.txt"
}

tap() {
  adb_cmd shell input tap "$1" "$2"
}

back_to_bonus() {
  adb_cmd shell input keyevent 4 || true
  sleep 2
  tap 756 2142
  sleep 2
}

build_interface_map() {
  /opt/homebrew/bin/python3 - "$OUTDIR" <<'PY'
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
            if row["kind"] in {"API", "H5_PAGE", "APP_RELATED"}:
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
    "content_type",
    "req_bytes",
    "resp_bytes",
    "timestamp_start",
]
with open(output, "w", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"OUTDIR={outdir}")
print(f"INTERFACE_MAP={output}")
print(f"ROWS={len(rows)}")
for row in rows[:120]:
    print(f"{row['operation']} | {row['kind']} | {row['method']} {row['status']} | {row['url']}")
PY
}

ensure_mitmweb
ensure_device
ensure_proxy_and_ca

log "android serial: $ADB_SERIAL"
log "android avd: $AVD_NAME"
log "output: $OUTDIR"

adb_cmd shell am force-stop "$PACKAGE" >/dev/null 2>&1 || true
adb_cmd shell am start -n "$PACKAGE/$ACTIVITY" >/dev/null
sleep 10
close_popups /tmp/stickerhub-functional-launch.xml
tap 108 2142
sleep 2
close_popups /tmp/stickerhub-functional-launch2.xml

capture_op album_missing "Album: Missing tab" tap 510 325
capture_op album_duplicate "Album: Duplicate tab" tap 824 325
capture_op proposals_tab "Bottom tab: Proposals" tap 324 2142
capture_op message_tab "Bottom tab: Message" tap 540 2142
capture_op profile_tab "Bottom tab: Profile" tap 972 2142
capture_op bonus_tab "Bottom tab: Bonus" tap 756 2142

tap 756 2142
sleep 2
capture_op bonus_events_card "Bonus card: Events" tap 540 424
back_to_bonus
capture_op bonus_invitation_rewards_card "Bonus card: Invitation Rewards" tap 540 677
back_to_bonus
capture_op bonus_lucky_draw_card "Bonus card: Lucky Draw" tap 540 930
back_to_bonus
capture_op bonus_free_mini_game_card "Bonus card: Free Mini Game" tap 540 1183
back_to_bonus
capture_op bonus_partner_events_card "Bonus card: Partner Events" tap 540 1436

build_interface_map | tee -a "$OUTDIR/run.log"

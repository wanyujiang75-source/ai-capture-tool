#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

IOS_DEVICE_UDID="${IOS_DEVICE_UDID:-}"
IOS_DEVICE_NAME="${IOS_DEVICE_NAME:-}"
OPEN_MITMIT="${OPEN_MITMIT:-1}"

require_command xcrun
require_command /usr/bin/python3

DEVICE_JSON="$(
  xcrun simctl list devices available -j | /usr/bin/python3 - "$IOS_DEVICE_UDID" "$IOS_DEVICE_NAME" <<'PY'
import json
import sys

target_udid = sys.argv[1].strip()
target_name = sys.argv[2].strip().lower()
devices = json.load(sys.stdin)["devices"]
candidates = []

for runtime, entries in devices.items():
    for entry in entries:
        if not entry.get("isAvailable"):
            continue
        name = entry.get("name", "")
        if not name.startswith("iPhone"):
            continue
        if target_udid and entry.get("udid") != target_udid:
            continue
        if target_name and target_name not in name.lower():
            continue
        candidates.append(
            {
                "runtime": runtime.replace("com.apple.CoreSimulator.SimRuntime.", ""),
                "name": name,
                "udid": entry["udid"],
                "state": entry["state"],
            }
        )

if not candidates:
    raise SystemExit("no available iPhone simulator matched the requested filter")

candidates.sort(
    key=lambda item: (
        item["state"] == "Booted",
        item["runtime"],
        item["name"],
    ),
    reverse=True,
)

print(json.dumps(candidates[0]))
PY
)"

IOS_UDID="$(
  printf '%s' "$DEVICE_JSON" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["udid"])'
)"
IOS_NAME="$(
  printf '%s' "$DEVICE_JSON" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])'
)"
IOS_RUNTIME="$(
  printf '%s' "$DEVICE_JSON" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["runtime"])'
)"
IOS_STATE="$(
  printf '%s' "$DEVICE_JSON" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])'
)"

open -a Simulator >/dev/null 2>&1

if [[ "$IOS_STATE" != "Booted" ]]; then
  xcrun simctl boot "$IOS_UDID" >/dev/null 2>&1 || true
fi

xcrun simctl bootstatus "$IOS_UDID" -b >/dev/null 2>&1 || true

FINAL_STATE="$(
  xcrun simctl list devices available -j | /usr/bin/python3 - "$IOS_UDID" <<'PY'
import json
import sys

target_udid = sys.argv[1]
devices = json.load(sys.stdin)["devices"]

for entries in devices.values():
    for entry in entries:
        if entry.get("udid") == target_udid:
            print(entry.get("state", "Unknown"))
            raise SystemExit(0)

raise SystemExit("simulator disappeared while checking boot state")
PY
)"

if [[ "$FINAL_STATE" != "Booted" ]]; then
  echo "failed to boot iOS simulator: $IOS_NAME ($IOS_UDID)" >&2
  exit 1
fi

if [[ "$OPEN_MITMIT" == "1" ]]; then
  xcrun simctl openurl "$IOS_UDID" "http://mitm.it" >/dev/null 2>&1 || true
fi

echo "ios simulator: $IOS_NAME"
echo "runtime: $IOS_RUNTIME"
echo "udid: $IOS_UDID"
echo "state: $FINAL_STATE"
if [[ "$OPEN_MITMIT" == "1" ]]; then
  echo "opened: http://mitm.it"
fi

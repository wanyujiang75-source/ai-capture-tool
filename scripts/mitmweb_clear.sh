#!/usr/bin/env bash
set -euo pipefail

WEB_PORT="${WEB_PORT:-9091}"
MITMWEB_PASSWORD="${MITMWEB_PASSWORD:-android-capture}"
COOKIE_FILE="${COOKIE_FILE:-/tmp/mitmweb-auth.cookies}"
BASE_URL="http://127.0.0.1:$WEB_PORT"

require_tool() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "$1 not found in PATH" >&2
    exit 1
  fi
}

require_tool curl
require_tool python3

tmp_login="$(mktemp)"
tmp_headers="$(mktemp)"
tmp_body="$(mktemp)"
trap 'rm -f "$tmp_login" "$tmp_headers" "$tmp_body"' EXIT

rm -f "$COOKIE_FILE"

curl -sS -c "$COOKIE_FILE" "$BASE_URL/" -o "$tmp_login"
xsrf="$(
  python3 - "$tmp_login" <<'PY'
import re
import sys

html = open(sys.argv[1], encoding="utf-8", errors="replace").read()
match = re.search(r'name="_xsrf" value="([^"]+)"', html)
print(match.group(1) if match else "")
PY
)"

if [[ -z "$xsrf" ]]; then
  echo "failed to read mitmweb _xsrf token from $BASE_URL/" >&2
  exit 1
fi

curl -sS \
  -b "$COOKIE_FILE" \
  -c "$COOKIE_FILE" \
  -X POST "$BASE_URL/" \
  --data-urlencode "token=$MITMWEB_PASSWORD" \
  --data-urlencode "_xsrf=$xsrf" \
  -o "$tmp_body" \
  -D "$tmp_headers"

if ! awk 'NR == 1 && $2 ~ /^2/ { ok=1 } END { exit ok ? 0 : 1 }' "$tmp_headers"; then
  echo "mitmweb token login failed" >&2
  cat "$tmp_headers" >&2
  exit 1
fi

xsrf_cookie="$(awk '$6 == "_xsrf" { print $7 }' "$COOKIE_FILE" | tail -1)"
if [[ -z "$xsrf_cookie" ]]; then
  echo "failed to read mitmweb _xsrf cookie" >&2
  exit 1
fi

curl -sS \
  -b "$COOKIE_FILE" \
  -H "X-XSRFToken: $xsrf_cookie" \
  -X POST "$BASE_URL/clear" \
  -o "$tmp_body" \
  -D "$tmp_headers"

if ! awk 'NR == 1 && $2 ~ /^2/ { ok=1 } END { exit ok ? 0 : 1 }' "$tmp_headers"; then
  echo "mitmweb clear failed" >&2
  cat "$tmp_headers" >&2
  cat "$tmp_body" >&2
  exit 1
fi

echo "mitmweb cleared: $BASE_URL"

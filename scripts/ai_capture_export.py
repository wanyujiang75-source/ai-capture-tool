#!/usr/bin/env python3
import argparse
import base64
import collections
import datetime as dt
import gzip
import html
import json
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import MozillaCookieJar


NOISE_HOST_RE = re.compile(
    r"("
    r"(^|\.)connectivitycheck\.gstatic\.com$|"
    r"(^|\.)gstatic\.com$|"
    r"(^|\.)google\.com$|"
    r"(^|\.)googleapis\.com$|"
    r"(^|\.)googleusercontent\.com$|"
    r"(^|\.)googlevideo\.com$|"
    r"(^|\.)android\.com$|"
    r"(^|\.)doubleclick\.net$|"
    r"(^|\.)googlesyndication\.com$|"
    r"(^|\.)googleadservices\.com$|"
    r"(^|\.)unity3d\.com$|"
    r"(^|\.)unityads\.unity3d\.com$|"
    r"(^|\.)applovin\.com$|"
    r"(^|\.)applvn\.com$|"
    r"(^|\.)facebook\.com$|"
    r"(^|\.)fbcdn\.net$|"
    r"(^|\.)adjust\.com$|"
    r"(^|\.)appsflyer\.com$|"
    r"(^|\.)branch\.io$|"
    r"(^|\.)sentry\.io$|"
    r"(^|\.)crashlytics\.com$|"
    r"(^|\.)app-measurement\.com$|"
    r"(^|\.)amplitude\.com$|"
    r"(^|\.)mixpanel\.com$"
    r")",
    re.I,
)

NOISE_URL_RE = re.compile(
    r"("
    r"/generate_204$|"
    r"/gen_204$|"
    r"/favicon\.ico$|"
    r"connectivity|"
    r"crashlytics|"
    r"firebaseinstallations|"
    r"firebaseremoteconfig|"
    r"firebaselogging|"
    r"app-measurement|"
    r"googleads|"
    r"doubleclick|"
    r"adservice|"
    r"adserver|"
    r"applovin|"
    r"unityads|"
    r"adjust|"
    r"appsflyer|"
    r"sentry"
    r")",
    re.I,
)

API_HINT_RE = re.compile(
    r"("
    r"/api/|"
    r"/apis/|"
    r"/v[0-9]+/|"
    r"/graphql|"
    r"/rpc|"
    r"/rest/|"
    r"/portal/|"
    r"/user|"
    r"/profile|"
    r"/account|"
    r"/auth|"
    r"/login|"
    r"/create|"
    r"/order|"
    r"/task|"
    r"/bonus|"
    r"/wallet|"
    r"/feed|"
    r"/home"
    r")",
    re.I,
)

SENSITIVE_HEADER_RE = re.compile(r"authorization|cookie|token|secret|session|apikey|api-key", re.I)

stop_requested = False


def now_iso():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def epoch_iso(value):
    if value is None or value == "":
        return ""
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return ""
    return dt.datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="milliseconds")


def duration_ms(start, end):
    if start is None or end is None or start == "" or end == "":
        return None
    try:
        start_value = float(start)
        end_value = float(end)
    except (TypeError, ValueError):
        return None
    if end_value < start_value:
        return None
    return int(round((end_value - start_value) * 1000))


def flow_timing(flow):
    req = flow.get("request") or {}
    resp = flow.get("response") if isinstance(flow.get("response"), dict) else {}
    request_start = req.get("timestamp_start")
    request_end = req.get("timestamp_end")
    response_start = resp.get("timestamp_start")
    response_end = resp.get("timestamp_end")
    return {
        "request_started_at": epoch_iso(request_start),
        "request_finished_at": epoch_iso(request_end),
        "response_started_at": epoch_iso(response_start),
        "response_finished_at": epoch_iso(response_end),
        "request_duration_ms": duration_ms(request_start, request_end),
        "wait_duration_ms": duration_ms(request_end, response_start),
        "response_duration_ms": duration_ms(response_start, response_end),
        "total_duration_ms": duration_ms(request_start, response_end),
    }


def safe_name(value, max_len=140):
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    value = value.strip("._")
    return (value or "flow")[:max_len]


def header_items(headers):
    if not headers:
        return []
    if isinstance(headers, dict):
        return [(str(k), str(v)) for k, v in headers.items()]
    if isinstance(headers, list):
        items = []
        for item in headers:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                items.append((str(item[0]), str(item[1])))
        return items
    return []


def header_dict(headers):
    return {k.lower(): v for k, v in header_items(headers)}


def redact_headers(headers):
    redacted = []
    for key, value in header_items(headers):
        if SENSITIVE_HEADER_RE.search(key):
            redacted.append((key, "<redacted>"))
        else:
            redacted.append((key, value))
    return redacted


def get_header(headers, name):
    return header_dict(headers).get(name.lower(), "")


def parse_url_from_request(req):
    url = req.get("pretty_url") or req.get("url") or ""
    if url:
        return url
    scheme = req.get("scheme") or "https"
    host = req.get("pretty_host") or req.get("host") or ""
    path = req.get("path") or "/"
    return urllib.parse.urlunsplit((scheme, host, path, "", ""))


def normalize_segment(segment):
    if not segment:
        return segment
    if re.fullmatch(r"\d+", segment):
        return "{num}"
    if re.fullmatch(r"[0-9a-f]{8,}", segment, re.I):
        return "{hex}"
    if re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        segment,
        re.I,
    ):
        return "{uuid}"
    if len(segment) >= 28 and re.fullmatch(r"[A-Za-z0-9_-]+", segment):
        return "{token}"
    return segment


def url_pattern(url):
    parsed = urllib.parse.urlsplit(url)
    parts = [normalize_segment(urllib.parse.unquote(p)) for p in parsed.path.split("/")]
    path = "/".join(parts) or "/"
    if not path.startswith("/"):
        path = "/" + path
    query_keys = sorted(urllib.parse.parse_qs(parsed.query, keep_blank_values=True).keys())
    query = ""
    if query_keys:
        query = "?" + "&".join(query_keys)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, query, ""))


def flow_summary(flow):
    req = flow.get("request") or {}
    resp = flow.get("response") or {}
    url = parse_url_from_request(req)
    parsed = urllib.parse.urlsplit(url)
    host = req.get("pretty_host") or req.get("host") or parsed.netloc
    path = req.get("path") or parsed.path or "/"
    method = req.get("method") or ""
    status = resp.get("status_code") if isinstance(resp, dict) else None
    return {
        "id": flow.get("id") or "",
        "method": method,
        "status": status if status is not None else "NO_RESPONSE",
        "host": host,
        "path": path,
        "url": url,
        "pattern": url_pattern(url) if url else "",
        "request_content_type": get_header(req.get("headers"), "content-type"),
        "response_content_type": get_header(resp.get("headers"), "content-type") if isinstance(resp, dict) else "",
        "request_headers": header_items(req.get("headers")),
        "response_headers": header_items(resp.get("headers")) if isinstance(resp, dict) else [],
        **flow_timing(flow),
    }


def noise_reason(summary):
    host = summary["host"] or ""
    url = summary["url"] or ""
    if NOISE_HOST_RE.search(host):
        return "noise-host"
    if NOISE_URL_RE.search(url):
        return "noise-url"
    return ""


def score_candidate(summary, request_len=0, response_len=0):
    score = 10
    method = summary["method"].upper()
    url = summary["url"]
    ctype_req = summary["request_content_type"].lower()
    ctype_resp = summary["response_content_type"].lower()
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        score += 35
    if API_HINT_RE.search(url):
        score += 30
    if "json" in ctype_req or "json" in ctype_resp:
        score += 25
    if request_len > 0:
        score += 15
    if response_len > 0:
        score += 10
    status = str(summary["status"])
    if status.startswith("2"):
        score += 8
    if status.startswith("4") or status.startswith("5"):
        score += 3
    return score


def maybe_decode_content(data):
    if not data:
        return b""
    if data[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(data)
        except OSError:
            return data
    return data


TEXT_CONTENT_TYPES = {
    "application/graphql",
    "application/javascript",
    "application/json",
    "application/ld+json",
    "application/x-ndjson",
    "application/x-www-form-urlencoded",
    "application/xml",
    "application/yaml",
    "image/svg+xml",
}
BINARY_CONTENT_PREFIXES = ("audio/", "font/", "image/", "video/")
BINARY_CONTENT_TYPES = {
    "application/gzip",
    "application/octet-stream",
    "application/pdf",
    "application/zip",
}


def normalized_content_type(value):
    return (value or "").split(";", 1)[0].strip().lower()


def content_type_is_text(value):
    normalized = normalized_content_type(value)
    if not normalized:
        return True
    if normalized.startswith("text/") or normalized in TEXT_CONTENT_TYPES:
        return True
    if normalized.endswith("+json") or normalized.endswith("+xml"):
        return True
    if normalized.startswith(BINARY_CONTENT_PREFIXES) or normalized in BINARY_CONTENT_TYPES:
        return False
    return True


def render_text_content(data, content_type):
    data = maybe_decode_content(data)
    if not data:
        return ""
    if not content_type_is_text(content_type):
        return ""
    text = None
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return ""
    stripped = text.strip()
    if "json" in (content_type or "").lower() or stripped.startswith(("{", "[")):
        try:
            return json.dumps(json.loads(stripped), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return text
    return text


class MitmWeb:
    def __init__(self, web_port, password, cookie_file):
        self.base_url = f"http://127.0.0.1:{web_port}"
        self.password = password
        self.cookie_file = cookie_file
        self.cookiejar = MozillaCookieJar(cookie_file)
        if os.path.exists(cookie_file):
            try:
                self.cookiejar.load(ignore_discard=True, ignore_expires=True)
            except Exception:
                pass
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookiejar))

    def request(self, method, path, data=None, headers=None):
        url = self.base_url + path
        req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        try:
            with self.opener.open(req, timeout=20) as resp:
                body = resp.read()
                return resp.status, resp.headers, body
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                return exc.code, exc.headers, exc.read()
            raise

    def login(self):
        status, _, body = self.request("GET", "/")
        text = body.decode("utf-8", errors="replace")
        if status == 200 and "mitmproxy" in text and "Authentication Required" not in text:
            self.cookiejar.save(ignore_discard=True, ignore_expires=True)
            return
        match = re.search(r'name="_xsrf" value="([^"]+)"', text)
        if not match:
            raise RuntimeError("failed to read mitmweb _xsrf token")
        form = urllib.parse.urlencode({"token": self.password, "_xsrf": html.unescape(match.group(1))}).encode()
        self.request("POST", "/", form, {"Content-Type": "application/x-www-form-urlencoded"})
        self.cookiejar.save(ignore_discard=True, ignore_expires=True)

    def xsrf_cookie(self):
        for cookie in self.cookiejar:
            if cookie.name == "_xsrf":
                return cookie.value
        return ""

    def clear(self):
        token = self.xsrf_cookie()
        if not token:
            self.login()
            token = self.xsrf_cookie()
        self.request("POST", "/clear", b"", {"X-XSRFToken": token})

    def flows(self):
        _, _, body = self.request("GET", "/flows")
        return json.loads(body.decode("utf-8", errors="replace") or "[]")

    def flow_content(self, flow_id, part):
        encoded = urllib.parse.quote(flow_id, safe="")
        try:
            _, _, body = self.request("GET", f"/flows/{encoded}/{part}/content.data")
            return body
        except urllib.error.HTTPError as exc:
            if exc.code in {400, 404, 409, 500}:
                return b""
            raise


def write_bytes_and_text(outdir, prefix, suffix, data, content_type):
    bin_path = os.path.join(outdir, f"{prefix}.{suffix}.bin")
    with open(bin_path, "wb") as fh:
        fh.write(data)

    text = render_text_content(data, content_type)
    if text:
        ext = "json" if text.lstrip().startswith(("{", "[")) else "txt"
        with open(os.path.join(outdir, f"{prefix}.{suffix}.{ext}"), "w", encoding="utf-8") as fh:
            fh.write(text)
            if not text.endswith("\n"):
                fh.write("\n")
    elif data:
        with open(os.path.join(outdir, f"{prefix}.{suffix}.base64.txt"), "w", encoding="ascii") as fh:
            fh.write(base64.b64encode(data).decode("ascii"))
            fh.write("\n")
    return bin_path


def append_tsv(path, values):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\t".join(str(v).replace("\t", " ") for v in values))
        fh.write("\n")


def write_json(path, value):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(value, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def write_summary(outdir, stats, patterns, recent, web_url):
    lines = [
        "# AI Capture Discovery",
        "",
        f"- updated: {now_iso()}",
        f"- web UI: {web_url}",
        f"- output: {outdir}",
        f"- total flows seen: {stats['total']}",
        f"- candidates exported: {stats['candidates']}",
        f"- noise ignored: {stats['noise']}",
        "",
        "## Top Candidate URL Patterns",
        "",
    ]
    if patterns:
        sorted_patterns = sorted(
            patterns.items(),
            key=lambda pair: (pair[1]["max_score"], pair[1]["count"], pair[0]),
            reverse=True,
        )
        for pattern, item in sorted_patterns[:30]:
            methods = ",".join(sorted(item["methods"]))
            statuses = ",".join(sorted(item["statuses"]))
            lines.append(f"- score={item['max_score']} count={item['count']} methods={methods} status={statuses} `{pattern}`")
            lines.append(f"  sample: {item['sample']}")
    else:
        lines.append("- no candidate business requests yet")

    lines.extend(["", "## Top Hosts", ""])
    for host, count in stats["hosts"].most_common(30):
        lines.append(f"- {count} `{host}`")

    lines.extend(["", "## Recent Candidates", ""])
    if recent:
        for item in recent[-30:]:
            lines.append(
                f"- {item['time']} score={item['score']} {item['method']} {item['status']} `{item['url']}`"
            )
    else:
        lines.append("- no candidate business requests yet")

    tmp = os.path.join(outdir, "summary.md.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
        fh.write("\n")
    os.replace(tmp, os.path.join(outdir, "summary.md"))


def load_seen(path):
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8", errors="replace") as fh:
        return {line.strip() for line in fh if line.strip()}


def save_seen(path, seen):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for item in sorted(seen):
            fh.write(item)
            fh.write("\n")
    os.replace(tmp, path)


def handle_signal(signum, frame):
    del signum, frame
    global stop_requested
    stop_requested = True


def export_flow(client, outdir, flow, summary, stats, patterns, recent, capture_noise):
    flow_id = summary["id"]
    reason = noise_reason(summary)
    request_data = client.flow_content(flow_id, "request")
    response_data = client.flow_content(flow_id, "response")

    score = score_candidate(summary, len(request_data), len(response_data))
    prefix = safe_name(
        f"{time.strftime('%Y%m%d-%H%M%S')}_{summary['method']}_{summary['status']}_{summary['host']}_{summary['path']}_{flow_id}"
    )
    meta = {
        "captured_at": now_iso(),
        "kind": "noise" if reason else "candidate",
        "score": score,
        "noise_reason": reason,
        "summary": summary,
        "mitm_flow": flow,
    }
    meta_name = f"{prefix}.meta.json"
    request_name = f"{prefix}.request.bin"
    response_name = f"{prefix}.response.bin"
    write_json(os.path.join(outdir, meta_name), meta)
    write_bytes_and_text(outdir, prefix, "request", request_data, summary["request_content_type"])
    write_bytes_and_text(outdir, prefix, "response", response_data, summary["response_content_type"])

    row = [
        now_iso(),
        "noise" if reason else "candidate",
        score,
        summary["method"],
        summary["status"],
        summary["host"],
        summary["pattern"],
        summary["url"],
        reason,
        meta_name,
        request_name,
        response_name,
    ]
    append_tsv(os.path.join(outdir, "all-flows.tsv"), row)

    if reason:
        stats["noise"] += 1
        return

    stats["candidates"] += 1

    append_tsv(
        os.path.join(outdir, "candidates.tsv"),
        [
            now_iso(),
            score,
            summary["method"],
            summary["status"],
            summary["host"],
            summary["pattern"],
            summary["url"],
            meta_name,
            request_name,
            response_name,
        ],
    )

    item = patterns[summary["pattern"]]
    item["count"] += 1
    item["max_score"] = max(item["max_score"], score)
    item["methods"].add(summary["method"])
    item["statuses"].add(str(summary["status"]))
    item["sample"] = item["sample"] or summary["url"]
    recent.append(
        {
            "time": now_iso(),
            "score": score,
            "method": summary["method"],
            "status": summary["status"],
            "url": summary["url"],
        }
    )


def main():
    parser = argparse.ArgumentParser(description="Discover likely app business APIs from mitmweb flows.")
    parser.add_argument("--web-port", type=int, default=9091)
    parser.add_argument("--password", default="android-capture")
    parser.add_argument("--cookie-file", default="/tmp/mitmweb-ai-capture.cookies")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--capture-noise", action="store_true")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    for signal_name in ("SIGINT", "SIGTERM"):
        signal.signal(getattr(signal, signal_name), handle_signal)

    client = MitmWeb(args.web_port, args.password, args.cookie_file)
    client.login()
    if args.clear:
        client.clear()

    web_url = f"http://127.0.0.1:{args.web_port}/?token={urllib.parse.quote(args.password)}"
    stats = {
        "total": 0,
        "candidates": 0,
        "noise": 0,
        "hosts": collections.Counter(),
    }
    patterns = collections.defaultdict(lambda: {"count": 0, "max_score": 0, "methods": set(), "statuses": set(), "sample": ""})
    recent = []
    seen_path = os.path.join(args.outdir, "seen-flow-ids.txt")
    seen = load_seen(seen_path)

    headers = [
        "time",
        "kind",
        "score",
        "method",
        "status",
        "host",
        "pattern",
        "url",
        "noise_reason",
        "meta",
        "request_bin",
        "response_bin",
    ]
    if not os.path.exists(os.path.join(args.outdir, "all-flows.tsv")):
        append_tsv(os.path.join(args.outdir, "all-flows.tsv"), headers)
    if not os.path.exists(os.path.join(args.outdir, "candidates.tsv")):
        append_tsv(
            os.path.join(args.outdir, "candidates.tsv"),
            ["time", "score", "method", "status", "host", "pattern", "url", "meta", "request_bin", "response_bin"],
        )

    while not stop_requested:
        try:
            flows = client.flows()
            write_json(os.path.join(args.outdir, "flows-current.json"), flows)
            for flow in flows:
                summary = flow_summary(flow)
                flow_id = summary["id"]
                if not flow_id or flow_id in seen:
                    continue
                seen.add(flow_id)
                stats["total"] += 1
                stats["hosts"][summary["host"]] += 1
                export_flow(client, args.outdir, flow, summary, stats, patterns, recent, args.capture_noise)
            save_seen(seen_path, seen)
            serializable_patterns = {
                pattern: {
                    "count": item["count"],
                    "max_score": item["max_score"],
                    "methods": sorted(item["methods"]),
                    "statuses": sorted(item["statuses"]),
                    "sample": item["sample"],
                }
                for pattern, item in patterns.items()
            }
            write_json(os.path.join(args.outdir, "url-patterns.json"), serializable_patterns)
            write_summary(args.outdir, stats, patterns, recent, web_url)
        except Exception as exc:
            append_tsv(os.path.join(args.outdir, "errors.tsv"), [now_iso(), type(exc).__name__, str(exc)])

        if args.once:
            break
        time.sleep(max(args.interval, 0.5))

    write_summary(args.outdir, stats, patterns, recent, web_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

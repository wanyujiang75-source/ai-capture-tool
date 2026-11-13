"""Opt-in, bounded GMA correlation diagnostics; never used by capture workers."""

import argparse
import hashlib
import json
import os
import re
import selectors
import subprocess
import time
from urllib.parse import urlsplit


class TraceParser:
    def __init__(self, max_block=262144, max_buffers=8, max_records=512):
        self.max_block = max_block
        self.max_buffers = max_buffers
        self.max_records = max_records
        self.buffers = {}
        self.records = 0
        self.dropped = 0
        self.drop_reasons = {}
        self.salt = os.urandom(32)

    def drop(self, reason):
        self.dropped += 1
        self.drop_reasons[reason] = self.drop_reasons.get(reason, 0) + 1

    def feed(self, thread, message):
        if message == "GMA Debug BEGIN":
            if thread in self.buffers or len(self.buffers) < self.max_buffers:
                if thread in self.buffers:
                    self.drop("restarted_block")
                self.buffers[thread] = ""
            else:
                self.drop("buffer_limit")
            return None
        if thread not in self.buffers:
            return None
        if message.startswith("GMA Debug CONTENT "):
            chunk = message.removeprefix("GMA Debug CONTENT ")
            if len(self.buffers[thread].encode()) + len(chunk.encode()) > self.max_block:
                del self.buffers[thread]
                self.drop("block_limit")
            else:
                self.buffers[thread] += chunk
            return None
        if message != "GMA Debug FINISH":
            return None
        raw = self.buffers.pop(thread)
        if self.records >= self.max_records:
            self.drop("record_limit")
            return None
        try:
            data = json.loads(raw)
        except (ValueError, RecursionError):
            self.drop("invalid_json")
            return None
        if not isinstance(data, dict) or data.get("event") not in (
            "onNetworkRequest", "onNetworkResponse", "onNetworkResponseBody", "onNetworkError",
            "onNetworkRequestError",
        ):
            self.drop("unsupported_event")
            return None
        result = {"event": data["event"]}
        timestamp = data.get("timestamp")
        if type(timestamp) in (int, float) and 0 <= timestamp < 1e15:
            result["timestamp"] = timestamp
        components = data.get("components")
        if isinstance(components, list):
            ids = [value.split("_request_", 1)[0] + ":" + hashlib.sha256(self.salt + value.encode()).hexdigest()[:16]
                   for value in components[:8] if isinstance(value, str)
                   and len(value) <= 256 and value.startswith(("ad_request_", "network_request_"))]
            if ids:
                result["components"] = ids
        params = data.get("params")
        if isinstance(params, dict):
            first = params.get("firstline")
            if isinstance(first, dict):
                uri = first.get("uri")
                try:
                    parsed = urlsplit(uri) if isinstance(uri, str) else None
                    host = parsed.hostname if parsed else None
                    if (data["event"] == "onNetworkRequest" and parsed is not None
                            and parsed.scheme in ("http", "https") and parsed.username is None
                            and host and re.fullmatch(r"[a-zA-Z0-9.-]+", host)
                            and parsed.port in (None, 80, 443)):
                        # A suffix is only a resource hint, not proof of media content or playback.
                        if parsed.path.lower().endswith((".mp4", ".webm")):
                            result["resource"] = "video_file_hint"
                        elif parsed.path.lower().endswith((".m3u8", ".mpd")):
                            result["resource"] = "video_manifest_hint"
                    if (data["event"] == "onNetworkRequest" and parsed is not None
                            and parsed.scheme == "https" and host == "googleads.g.doubleclick.net"
                            and parsed.port in (None, 443) and parsed.username is None
                            and parsed.path == "/mads/static/mad/sdk/native/sdk-core-v40-loader.html"):
                        result["resource"] = "gma_js_loader"
                except ValueError:
                    host = None
                if host and len(host) <= 253 and re.fullmatch(r"[a-zA-Z0-9.-]+", host):
                    result["host"] = host.lower()
                if first.get("verb") in ("GET", "POST", "HEAD", "PUT", "DELETE", "OPTIONS", "PATCH"):
                    result["method"] = first["verb"]
                if type(first.get("code")) is int and 100 <= first["code"] <= 599:
                    result["status"] = first["code"]
            if type(params.get("bodylength")) is int and 0 <= params["bodylength"] < 2**63:
                result["body_length"] = params["bodylength"]
            if data["event"] == "onNetworkResponseBody":
                result["body_visibility"] = ("inline" if isinstance(params.get("body"), str)
                    else "digest_only" if isinstance(params.get("bodydigest"), str) else "absent")
        self.records += 1
        return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--adb", required=True)
    cli.add_argument("--serial", required=True)
    cli.add_argument("--uid", type=int, required=True)
    cli.add_argument("--seconds", type=int, default=120, choices=range(1, 181))
    cli.add_argument("--output", required=True)
    args = cli.parse_args()
    if args.uid < 10000:
        cli.error("An application UID is required; system-wide collection is not allowed")
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    parser = TraceParser()
    records = []
    total = 0
    pending = b""
    line_pattern = re.compile(r"^\s*\S+\s+\S+\s+(\d+)\s+(\d+)\s+[VDIWEF]\s+Ads(?:-cont)?\s*:\s?(.*)$")
    process = None
    try:
        process = subprocess.Popen(
            [args.adb, "-s", args.serial, "logcat", "--uid=" + str(args.uid),
             "-T", "1", "-v", "threadtime", "*:S", "Ads:I", "Ads-cont:I"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + args.seconds
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while time.monotonic() < deadline and total < 32 * 1024 * 1024:
                if not selector.select(timeout=0.25):
                    if process.poll() is not None:
                        break
                    continue
                chunk = os.read(process.stdout.fileno(), 16384)
                if not chunk:
                    break
                total += len(chunk)
                pending += chunk
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    if len(line) > 16384:
                        parser.buffers.clear()
                        parser.drop("line_limit")
                        continue
                    match = line_pattern.match(line.decode("utf-8", errors="replace"))
                    if match:
                        result = parser.feed((match[1], match[2]), match[3])
                        if result is not None:
                            records.append(result)
                if len(pending) > 16384:
                    pending = b""
                    parser.buffers.clear()
                    parser.drop("line_limit")
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process.stdout.close()
        report = {"records": records, "dropped": parser.dropped, "drop_reasons": parser.drop_reasons,
                  "incomplete_blocks": len(parser.buffers), "input_bytes": total,
                  "logcat_exit": process.returncode if process else None}
        with os.fdopen(fd, "w") as output:
            json.dump(report, output, ensure_ascii=True)
        print(json.dumps({"records": len(records), "dropped": parser.dropped,
                          "incomplete_blocks": len(parser.buffers)}))


if __name__ == "__main__":
    main()

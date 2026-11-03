"""Temporary LAN delivery of one inert Shadowrocket compatibility probe."""

import argparse
import ipaddress
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROBE = (
    b"#!name=Capture-A1-Import-Probe\n"
    b"#!desc=Compatibility probe only. No nodes, rules, DNS, scripts, or certificates.\n"
)


def validate_probe(body):
    if body != PROBE:
        raise ValueError("Only the fixed, metadata-only probe may be served")
    return body


def validate_host(host):
    address = ipaddress.IPv4Address(host)
    allowed = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8")
    if not any(address in ipaddress.IPv4Network(network) for network in allowed):
        raise ValueError("Bind to one private LAN or loopback IPv4 address")
    return str(address)


class ProbeHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(3)

    def log_message(self, format, *args):
        pass

    def respond(self, include_body):
        filenames = {"/a1.module": "a1.module", "/a1.sgmodule": "a1.sgmodule"}
        if self.path not in filenames:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filenames[self.path]}"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(self.server.body)))
        self.end_headers()
        if include_body:
            self.wfile.write(self.server.body)
            with self.server.counter_lock:
                self.server.downloads += 1
                print(f"probe_downloads={self.server.downloads}", flush=True)

    def do_GET(self):
        self.respond(include_body=True)

    def do_HEAD(self):
        self.respond(include_body=False)

    def do_POST(self):
        self.send_error(405)


class ProbeServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, body):
        self.body = validate_probe(body)
        self.downloads = 0
        self.counter_lock = threading.Lock()
        super().__init__((validate_host(address[0]), address[1]), ProbeHandler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, type=validate_host)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ttl", type=int, default=900)
    args = parser.parse_args()
    if not 1 <= args.ttl <= 900:
        parser.error("ttl must be 1..900 seconds")
    if not 0 <= args.port <= 65535:
        parser.error("port must be 0..65535")
    body = (Path(__file__).parent / "fixtures/ios_setup_import/empty.module").read_bytes()
    with ProbeServer((args.host, args.port), body) as server:
        host, port = server.server_address
        print(f"http://{host}:{port}/a1.module", flush=True)
        print(f"metadata_only=true expires_in_seconds={args.ttl}", flush=True)
        timer = threading.Timer(args.ttl, server.shutdown)
        timer.daemon = True
        timer.start()
        try:
            server.serve_forever(poll_interval=0.1)
        except KeyboardInterrupt:
            pass
        finally:
            timer.cancel()
    print("probe_closed=true", flush=True)


if __name__ == "__main__":
    main()

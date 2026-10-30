"""Opt-in loopback-only visual fixture. No proxy, ADB, APK, phone, or real traffic.

Stop the real desktop first. Run with a disposable --runtime-dir and matching
--build-id, then launch the desktop with AI_CAPTURE_NATIVE_RUNTIME_DIR pointing
there. PUT /__scenario sets mode to normal/empty/loading/failed. This fixture
must never be packaged or treated as evidence of a working iPhone connection.
"""

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlparse


class Fixture:
    def __init__(self, build_id, runtime):
        self.build_id, self.runtime = build_id, Path(runtime)
        self.mode = "normal"
        self.recording = False
        self.session = None
        self.connected = True
        self.flows = []
        self.lock = threading.RLock()
        self.project = {"id": "visual-only", "name": "[合成验收] 示例项目", "domains": ["example.test"]}

    def status(self):
        return {"phase": "capturing" if self.recording else ("ready" if self.connected else "stopped"),
                "connection_state": "ready" if self.connected else "idle",
                "recording_state": "recording" if self.recording else "stopped" if self.session else "idle",
                "session_id": self.session, "flow_count": len(self.flows), "flows": [],
                "project": self.project if self.session else None}

    def reply(self, method, path, body):
        if path == "/__scenario" and method == "PUT":
            if body.get("mode") not in {"normal", "empty", "loading", "failed"}:
                return 400, {}
            self.mode = body["mode"]
            return 200, {"mode": self.mode, "synthetic": True}
        if path == "/api/status":
            return 200, {"desktop": {"enabled": True, "build_id": self.build_id}}
        if self.mode == "loading":
            time.sleep(8)
        if self.mode == "failed":
            return 503, {"detail": {"user_message": "synthetic private error HTTP 409"}}
        if path == "/api/ios-setup":
            return 200, self.status()
        if path == "/api/ios-setup/projects":
            return 200, {"projects": [] if self.mode == "empty" else [self.project]}
        if path == "/api/ios-setup/recording/start" and method == "POST":
            with self.lock:
                self.session = (self.session or 9000) + 1
                self.recording = True
                stamp = datetime.now(timezone.utc).isoformat()
                self.flows = [{"id": "visual-1", "method": "POST", "status": "200", "time": stamp,
                               "url": "https://example.test/visual/response?source=synthetic", "host": "example.test",
                               "path": "/visual/response?source=synthetic", "total_duration_ms": "35"}]
            return 200, self.status()
        if path == "/api/ios-setup/recording/stop" and method == "POST":
            self.recording = False
            return 200, self.status()
        if path == "/api/ios-setup/stop" and method == "POST":
            if body.get("phone_configuration_removed") is not True:
                return 409, {}
            self.connected = self.recording = False
            self.runtime.joinpath("ios-setup/cleanup-required").unlink(missing_ok=True)
            return 200, self.status()
        if path == "/api/captures":
            sessions = [] if self.session is None else [{"id": self.session, "platform": "ios",
                "mode": "ios-http-proxy", "status": "running" if self.recording else "stopped",
                "app_name": self.project["name"]}]
            return 200, {"sessions": sessions}
        if path.startswith("/api/captures/"):
            if path.endswith("/flows"):
                flows = [] if self.mode == "empty" else self.flows
                return 200, {"flows": flows, "total": len(flows), "cursor": 1, "next_cursor": None}
            if path.endswith("/curl"):
                return 200, "curl 'https://example.test/visual/response?source=synthetic'"
            return 200, {"id": "visual-1", "url": self.flows[0]["url"], "method": "POST", "status": "200",
                         "request_body_kind": "json", "response_body_kind": "json",
                         "request_text": '{"fixture": "request"}', "response_text": '{"synthetic": true, "result": "ok"}'}
        if path == "/api/package-sources/jenkins/packages":
            return 200, {"packages": [] if self.mode == "empty" else [{"job_name": "[合成验收] Example",
                "build_number": 1, "artifact_file_name": "Example_1.apk", "artifact_relative_path": "Example_1.apk"}]}
        if path == "/api/apps":
            return 200, {"apps": []}
        if path in {"/api/devices", "/api/log-devices/discover"}:
            return 200, {"devices": [], "blocked_devices": [], "count": 0}
        return 404, {"detail": "visual fixture has no such operation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--port", type=int, default=7001)
    args = parser.parse_args()
    fixture = Fixture(args.build_id, args.runtime_dir)
    if fixture.runtime.exists():
        parser.error("runtime-dir must be a new disposable directory")
    fixture.runtime.mkdir(parents=True, mode=0o700)
    # Simulates recovery only; no configuration/certificate was generated or installed.
    marker = fixture.runtime / "ios-setup/cleanup-required"
    marker.parent.mkdir()
    marker.write_text("synthetic visual fixture: no phone configuration exists\n")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def handle_request(self):
            size = min(4096, int(self.headers.get("Content-Length", 0)))
            data = json.loads(self.rfile.read(size)) if size else {}
            code, result = fixture.reply(self.command, urlparse(self.path).path, data)
            raw = result.encode() if isinstance(result, str) else json.dumps(result).encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/plain" if isinstance(result, str) else "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except BrokenPipeError:
                pass

        do_GET = do_POST = do_PUT = handle_request

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("SYNTHETIC UI ONLY: no proxy, device, or real traffic", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

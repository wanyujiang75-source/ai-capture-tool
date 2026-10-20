"""Opt-in real-device measurement; always restore this run's shaping and probe file."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import urlopen
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from capture_console.runner import ConsoleRunner
from capture_console.weak_network import NetworkProfile, WeakNetworkService
from capture_console.weak_network_device import EmulatorNetworkDevice


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"x" * min(int(self.path[1:]), 524288)
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.rfile.read(min(int(self.headers["Content-Length"]), 524288))
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *_):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", required=True)
    parser.add_argument("--avd", required=True)
    parser.add_argument("--socks-port", type=int)
    parser.add_argument("--latency-ms", type=int, default=200)
    options = parser.parse_args()
    sdk = Path(os.environ.get("ANDROID_SDK_ROOT", Path.home() / "Library/Android/sdk"))
    runner = ConsoleRunner(ROOT, adb_serial=options.serial, avd_name=options.avd)
    service = WeakNetworkService(ROOT / "runtime/weak-network-qa", lambda _: EmulatorNetworkDevice(runner),
                                 lambda _: EmulatorNetworkDevice(runner))
    service.recover()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    remote = f"/data/local/tmp/ai-capture-weak-probe-{os.getpid()}.dex"
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["javac", "-source", "8", "-target", "8", "-d", tmp,
                        str(ROOT / "tests/fixtures/WeakNetworkProbe.java")], check=True)
        build_tools = sorted((sdk / "build-tools").iterdir())[-1]
        subprocess.run([str(build_tools / "d8"), "--output", tmp,
                        str(Path(tmp) / "WeakNetworkProbe.class")], check=True)
        pushed = runner.adb(["push", str(Path(tmp) / "classes.dex"), remote])
        if not pushed.ok:
            raise RuntimeError(pushed.text)

        def measure():
            results = {}
            for kind, size in (("latency", 1), ("download", 524288), ("upload", 524288)):
                args = ["shell", f"CLASSPATH={remote}", "app_process", "/", "WeakNetworkProbe",
                        "127.0.0.1" if options.socks_port else "10.0.2.2", str(server.server_port),
                        str(size), "upload" if kind == "upload" else "download"]
                if options.socks_port:
                    args.append(str(options.socks_port))
                result = runner.adb(args, timeout=60)
                if not result.ok:
                    raise RuntimeError(result.text)
                results[kind] = json.loads(result.stdout.strip().splitlines()[-1])
            return results

        try:
            baseline = measure()
            state = service.apply("qa", NetworkProfile(512, 1024, options.latency_ms))
            if not state["enabled"]:
                raise RuntimeError(state)
            shaped = measure()
            started = time.monotonic()
            with urlopen(f"http://127.0.0.1:{server.server_port}/524288", timeout=5) as response:
                assert len(response.read()) == 524288
            host_ms = (time.monotonic() - started) * 1000
            restored = service.restore("qa")
            if restored["pending_restore"]:
                raise RuntimeError(restored)
            after = measure()
            print(json.dumps({"baseline": baseline, "weak": shaped, "host_download_ms_during_weak": host_ms,
                              "restored": after}, indent=2), flush=True)
            if options.latency_ms:
                assert shaped["latency"]["elapsed_ms"] > baseline["latency"]["elapsed_ms"] + options.latency_ms * 0.6
            assert host_ms < shaped["download"]["elapsed_ms"] / 2
            for kind in ("upload", "download"):
                assert shaped[kind]["status"] == 200
                if kind == "download":
                    assert shaped[kind]["received"] >= 524288
                assert shaped[kind]["elapsed_ms"] > baseline[kind]["elapsed_ms"] * 3
                assert after[kind]["elapsed_ms"] < shaped[kind]["elapsed_ms"] / 2
        finally:
            print(json.dumps({"cleanup": service.restore("qa")}, ensure_ascii=False), flush=True)
            runner.adb(["shell", "rm", "-f", remote])
            server.shutdown()


if __name__ == "__main__":
    main()

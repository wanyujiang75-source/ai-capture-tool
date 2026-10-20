"""Exercise the real packaged API lifecycle on an explicitly selected emulator."""

import argparse
import json
import os
import socket
import subprocess
import sys
from contextlib import nullcontext
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from capture_console.runner import ConsoleRunner
from capture_console.weak_network import WeakNetworkService
from capture_console.weak_network_device import EmulatorNetworkDevice


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", required=True)
    parser.add_argument("--avd", required=True)
    parser.add_argument("--backend-root", type=Path, default=ROOT,
                        help="Source root or the built app's Contents/Resources/backend directory")
    options = parser.parse_args()
    backend_root = options.backend_root.resolve()
    if not (backend_root / "capture_console/app.py").is_file():
        parser.error("backend root must contain capture_console/app.py")
    process = None
    # Preserve journals even if the device disconnects during the QA cleanup.
    directory = ROOT / "runtime/weak-network-lifecycle-qa"
    directory.mkdir(parents=True, exist_ok=True)
    with nullcontext(directory) as tmp:
        root = Path(tmp)
        config = root / "devices.json"
        config.write_text(json.dumps([{
            "device_id": "device-1", "name": "Weak network QA", "avd_name": options.avd,
            "adb_serial": options.serial, "proxy_port": 29090, "web_port": 29091,
            "frida_port": 29042, "resident": 0, "idle_release_minutes": 0,
        }]))
        env = {**os.environ, "CAPTURE_RUNTIME_DIR": str(root), "CAPTURE_DEVICES_CONFIG": str(config),
               "TRACEDECK_DESKTOP": "1", "PYTHONPATH": str(backend_root), "PYTHONDONTWRITEBYTECODE": "1"}
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        runner = ConsoleRunner(backend_root, adb_serial=options.serial, avd_name=options.avd)

        def request(method="GET", path="/api/devices/device-1/weak-network", payload=None):
            req = Request(f"http://127.0.0.1:{port}{path}", method=method,
                          data=json.dumps(payload).encode() if payload is not None else None,
                          headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=30) as response:
                return json.load(response)

        with (root / "server.log").open("w") as log:
            def start():
                child = subprocess.Popen([sys.executable, "-m", "uvicorn", "capture_console.app:app",
                                          "--fd", str(listener.fileno()), "--log-level", "warning"],
                                         cwd=backend_root, env=env, stdout=log, stderr=log,
                                         pass_fds=(listener.fileno(),))
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if child.poll() is not None:
                        raise RuntimeError((root / "server.log").read_text())
                    try:
                        request()
                        return child
                    except (OSError, ValueError):
                        time.sleep(0.1)
                raise RuntimeError("isolated API did not start")

            profile = {"upload_kbps": 512, "download_kbps": 1024, "latency_ms": 200}
            try:
                process = start()
                assert request("PUT", payload=profile)["enabled"]
                started = time.monotonic()
                request("POST", "/api/desktop/stop-captures")
                elapsed = time.monotonic() - started
                assert not request()["enabled"]
                assert elapsed < 15, "desktop cleanup exceeds current native timeout"
                assert "9c01:" not in runner.adb(["shell", "tc qdisc show"]).stdout
                print(json.dumps({"desktop_cleanup_seconds": elapsed}), flush=True)

                assert request("PUT", payload=profile)["enabled"]
                assert request("POST", "/api/desktop/recover-weak-network")["ok"]
                assert not request()["enabled"]
                print("orphan backend adoption: restored without stopping captures", flush=True)

                assert request("PUT", payload=profile)["enabled"]
                process.kill()  # Only this isolated child, never the user's desktop backend.
                process.wait(timeout=10)
                process = start()
                deadline = time.monotonic() + 20
                state = request()
                while state["pending_restore"] and time.monotonic() < deadline:
                    time.sleep(0.2)
                    state = request()
                assert state["available"] and not state["enabled"] and not state["pending_restore"]
                print(json.dumps({"crash_recovery": state}, ensure_ascii=False), flush=True)

                assert request("PUT", payload=profile)["enabled"]
                process.terminate()
                process.wait(timeout=15)
                assert "9c01:" not in runner.adb(["shell", "tc qdisc show"]).stdout
                assert not list((root / "weak-network").glob("*.json"))
                print("graceful shutdown: restored", flush=True)
            finally:
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=15)
                recovery = WeakNetworkService(root / "weak-network", lambda _: EmulatorNetworkDevice(runner),
                                              lambda _: EmulatorNetworkDevice(runner))
                recovery.recover()
                if recovery.records:
                    raise RuntimeError(f"recovery still pending: {recovery.records}")
                listener.close()


if __name__ == "__main__":
    main()

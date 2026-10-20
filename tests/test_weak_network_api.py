import tempfile
import unittest
import json
import socket
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path

from fastapi import FastAPI, HTTPException
import uvicorn

from capture_console.weak_network import WeakNetworkService
from capture_console.weak_network_api import weak_network_router
from tests.test_weak_network import FakeDevice


class WeakNetworkApiTests(unittest.TestCase):
    def test_apply_read_restore_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            device = FakeDevice()
            service = WeakNetworkService(Path(tmp), lambda _: device, lambda _: device)
            app = FastAPI()

            def validate(device_id):
                if device_id != "one":
                    raise HTTPException(404)

            app.include_router(weak_network_router(service, validate))
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
            thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            thread.start()
            deadline = time.monotonic() + 5
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(server.started)

            def request(method, path, body=None):
                req = Request(f"http://127.0.0.1:{port}{path}", method=method,
                              data=json.dumps(body).encode() if body is not None else None,
                              headers={"Content-Type": "application/json"})
                try:
                    with urlopen(req, timeout=5) as response:
                        return response.status, json.load(response)
                except HTTPError as exc:
                    return exc.code, json.load(exc)

            def stop():
                server.should_exit = True
                thread.join(timeout=5)
                listener.close()

            self.addCleanup(stop)
            path = "/api/devices/one/weak-network"
            profile = {"upload_kbps": 512, "download_kbps": 1024, "latency_ms": 200}
            for invalid in (0, True, "512", 100001):
                self.assertEqual(request("PUT", path, {**profile, "upload_kbps": invalid})[0], 422)
                self.assertFalse(device.rules)
            self.assertEqual(request("PUT", "/api/devices/missing/weak-network", profile)[0], 404)
            self.assertTrue(request("PUT", path, profile)[1]["enabled"])
            self.assertEqual(request("GET", path)[1]["profile"], profile)
            self.assertFalse(request("DELETE", path)[1]["enabled"])
            self.assertFalse(device.rules)
            self.assertTrue(request("PUT", path, profile)[1]["enabled"])
            self.assertEqual(request("POST", "/api/desktop/recover-weak-network")[1],
                             {"ok": True, "pending_devices": []})
            self.assertFalse(device.rules)

    def test_runtime_shutdown_and_desktop_cleanup_restore_weak_network(self):
        from unittest.mock import patch
        from capture_console import app as module

        with patch.object(module.weak_network_service, "restore_all") as restore, \
             patch.object(module, "stop_all_active_captures", return_value={"ok": True}), \
             patch.object(module, "stop_logcat_reaper"), \
             patch.object(module.logcat_service, "stop_all"), \
             patch.object(module, "clear_project_capture_records"):
            module.api_desktop_stop_captures()
            restore.assert_called_once()
            module.shutdown()
            self.assertEqual(restore.call_count, 2)

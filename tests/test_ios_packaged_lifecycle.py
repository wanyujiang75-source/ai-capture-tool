"""Opt-in relocated bundle checks; synthetic archives, no phone or LAN proxy."""

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request


SEED_ARCHIVE = """
import json, os
from pathlib import Path
from mitmproxy import connection, http
from capture_console.store import CaptureStore
from capture_console.ios_results import IOSCaptureArchive
root = Path(os.environ['CAPTURE_RUNTIME_DIR'])
store = CaptureStore(root / 'console.db')
saved = store.create_ios_session(connection_id='synthetic', project_name='Synthetic archive', outdir=str(root / 'archive'))
saved = store.update_session_status(saved['id'], 'stopped')
abandoned = store.create_ios_session(connection_id='abandoned', project_name='Abandoned synthetic', outdir=str(root / 'abandoned'))
android = store.create_session(app_id=None, device_id='device-1', mode='flutter-socks', outdir=str(root / 'android'))
flow = http.HTTPFlow(connection.Client(peername=('192.0.2.2', 1234), sockname=('192.0.2.1', 9180)),
                     connection.Server(address=('api.example.test', 443)))
flow.request = http.Request.make('POST', 'https://api.example.test/items?synthetic=true', b'{"request":1}', {'content-type': 'application/json'})
flow.response = http.Response.make(200, b'{"response":true}', {'content-type': 'application/json'})
archive = IOSCaptureArchive(root / 'archive')
archive.begin(flow)
archive.append_body(flow.id, 'request', flow.request.raw_content)
archive.request_complete(flow)
archive.append_body(flow.id, 'response', flow.response.raw_content)
archive.finish(flow)
archive.close()
print(json.dumps({'saved': saved, 'abandoned': abandoned['id'], 'android': android['id'], 'flow': flow.id}))
"""


@unittest.skipUnless(os.environ.get("CAPTURE_TEST_IOS_APP_PATH"), "requires an extracted macOS app")
class IOSPackagedLifecycleTests(unittest.TestCase):
    def test_relocated_backend_keeps_archive_across_normal_and_abnormal_restarts(self):
        app = Path(os.environ["CAPTURE_TEST_IOS_APP_PATH"]).resolve()
        backend = app / "Contents/Resources/backend"
        runtime_bin = app / "Contents/Resources/runtime/bin"
        with tempfile.TemporaryDirectory(prefix="ios-package-lifecycle-") as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            with socket.socket() as port_socket:
                port_socket.bind(("127.0.0.1", 0))
                port = port_socket.getsockname()[1]
            env = {
                "HOME": str(home), "PATH": f"{runtime_bin}:/usr/bin:/bin", "LANG": "en_US.UTF-8",
                "CAPTURE_RUNTIME_DIR": str(root / "data"), "TRACEDECK_DESKTOP": "1",
                "CONSOLE_HOST": "127.0.0.1", "CONSOLE_PORT": str(port),
                "CONSOLE_PYTHON": str(runtime_bin / "python3"), "CONSOLE_SKIP_INSTALL": "1",
                "CONSOLE_USE_EMBEDDED_RUNTIME": "1", "TRACEDECK_RUNTIME_BIN": str(runtime_bin),
                "FRIDA_PYTHON_BIN": str(runtime_bin / "python3"), "MITMWEB_BIN": str(runtime_bin / "mitmweb"),
                "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(backend),
                "PYTHONPYCACHEPREFIX": str(root / "pycache"),
            }
            seed = subprocess.run([str(runtime_bin / "python3"), "-c", SEED_ARCHIVE],
                                  cwd=backend, env=env, check=True, capture_output=True, text=True)
            ids = json.loads(seed.stdout)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

            def request(path, payload=None):
                data = None if payload is None else json.dumps(payload).encode()
                req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data,
                                             headers={"Content-Type": "application/json"})
                with opener.open(req, timeout=5) as response:
                    body = response.read()
                    return json.loads(body) if "application/json" in response.headers.get("Content-Type", "") else body.decode()

            interrupted = None
            project = None
            for turn in range(3):
                with self.subTest(restart=turn), (root / f"backend-{turn}.log").open("w+") as log:
                    process = subprocess.Popen(["/bin/bash", str(backend / "scripts/start_console.sh")],
                                               cwd=backend, env=env, stdout=log, stderr=subprocess.STDOUT,
                                               start_new_session=True)
                    try:
                        deadline = time.monotonic() + 30
                        while True:
                            if process.poll() is not None:
                                log.seek(0)
                                self.fail(f"packaged backend exited: {log.read()[-5000:]}")
                            try:
                                state = request("/api/ios-setup")
                                break
                            except (urllib.error.URLError, TimeoutError):
                                if time.monotonic() >= deadline:
                                    self.fail("packaged backend did not become ready")
                                time.sleep(0.2)
                        self.assertEqual((state["connection_state"], state["recording_state"], state["session_id"]),
                                         ("idle", "idle", None))
                        rows = {row["id"]: row for row in request("/api/captures")["sessions"]}
                        self.assertEqual(set(rows), {ids["saved"]["id"], ids["abandoned"]})
                        self.assertEqual(rows[ids["saved"]["id"]], ids["saved"])
                        if interrupted is None:
                            interrupted = rows[ids["abandoned"]]
                            self.assertEqual(interrupted["status"], "failed")
                            self.assertTrue(interrupted["stopped_at"])
                            self.assertTrue(interrupted["error"])
                        self.assertEqual(rows[ids["abandoned"]], interrupted)
                        base = f'/api/captures/{ids["saved"]["id"]}/flows'
                        self.assertEqual([row["id"] for row in request(base)["flows"]], [ids["flow"]])
                        detail = request(base + "/" + ids["flow"])
                        self.assertEqual((detail["request_text"], detail["response_text"]),
                                         ('{"request":1}', '{"response":true}'))
                        self.assertIn("synthetic=true", request(base + "/" + ids["flow"] + "/curl"))
                        if project is None:
                            project = request("/api/ios-setup/projects", {"name": "Synthetic", "domains": ["example.com"]})
                        self.assertIn(project, request("/api/ios-setup/projects")["projects"])
                        with self.assertRaises(urllib.error.HTTPError) as denied:
                            request("/api/ios-setup/recording/start", {"project_id": project["id"]})
                        self.assertEqual(denied.exception.code, 400)
                        denied.exception.close()
                    finally:
                        if process.poll() is None:
                            os.killpg(process.pid, signal.SIGKILL if turn == 1 else signal.SIGTERM)
                            try:
                                process.wait(timeout=20)
                            except subprocess.TimeoutExpired:
                                os.killpg(process.pid, signal.SIGKILL)
                                process.wait(timeout=5)
                                self.fail("packaged backend did not finish normal cleanup")
                    self.assertEqual(process.returncode, -signal.SIGKILL if turn == 1 else -signal.SIGTERM)

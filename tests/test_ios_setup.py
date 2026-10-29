import json
import asyncio
import gzip
import os
import plistlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mitmproxy import connection, http

from capture_console.ios_setup import IOSSetupService, make_profile, validate_ssid
from capture_console.ios_pairing_proxy import PairingMonitor, owner_is_alive, run


def config(root):
    return {
        "ssid": "Office & Test", "host": "192.168.1.10", "port": 9190,
        "username": "ios", "password": "test-proxy-secret", "check_token": "check-secret",
        "state_path": str(root / "state.json"), "profile_path": str(root / "iPhone.mobileconfig"),
        "confdir": str(root / "ca"),
        "hosts": ["poke.example"],
    }


class IOSProfileTests(unittest.TestCase):
    def test_profile_prepopulates_only_wifi_proxy_public_ca_and_check_shortcut(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = config(Path(tmp))
            profile = plistlib.loads(make_profile(cfg, b"public-der-certificate"))
        self.assertFalse(profile["PayloadRemovalDisallowed"])
        self.assertEqual(profile["DurationUntilRemoval"], 86400)
        wifi, ca, shortcut = profile["PayloadContent"]
        self.assertEqual(wifi["SSID_STR"], cfg["ssid"])
        self.assertEqual(wifi["ProxyServer"], cfg["host"])
        self.assertEqual(wifi["ProxyServerPort"], cfg["port"])
        self.assertEqual(wifi["ProxyUsername"], cfg["username"])
        self.assertEqual(wifi["ProxyPassword"], cfg["password"])
        self.assertNotIn("Password", wifi)
        self.assertEqual(ca["PayloadContent"], b"public-der-certificate")
        self.assertEqual(shortcut["URL"], "https://capture-check.invalid/check-secret")
        self.assertEqual([x["PayloadType"] for x in profile["PayloadContent"]],
                         ["com.apple.wifi.managed", "com.apple.security.root", "com.apple.webClip.managed"])

    def test_ssid_validates_bytes_without_changing_significant_spaces(self):
        self.assertEqual(validate_ssid(" Office "), " Office ")
        for name in ["", "x" * 33, "测" * 11, "bad\nssid"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_ssid(name)


class IOSMonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = config(Path(self.tmp.name))
        self.monitor = PairingMonitor(self.cfg)

    def flow(self, host="poke.example", client="192.168.1.11", auth=True, path="/api"):
        flow = http.HTTPFlow(connection.Client(peername=(client, 2222), sockname=(self.cfg["host"], 9190)),
                             connection.Server(address=(host, 443)))
        flow.client_conn.tls = True
        flow.request = http.Request.make("POST", f"https://{host}{path}", b'{"hello":1}')
        flow.response = http.Response.make(200, b'{"ok":true}', {"content-type": "application/json"})
        if auth:
            flow.metadata["proxyauth"] = ("ios", "test-proxy-secret")
        return flow

    def state(self):
        self.monitor.flush()
        return json.loads(Path(self.cfg["state_path"]).read_text())

    def test_mac_selfcheck_and_unauthenticated_client_do_not_mark_phone_ready(self):
        for flow in [self.flow(client="192.168.1.10"), self.flow(client="127.0.0.1"), self.flow(auth=False)]:
            self.monitor.response(flow)
        self.assertEqual(self.state()["phase"], "waiting_phone")
        self.assertEqual(self.state()["flow_count"], 0)

    def test_probe_auth_token_and_tls_are_required_and_not_counted_as_app(self):
        flow = self.flow(host="capture-check.invalid", path="/check-secret")
        self.monitor.request(flow)
        self.assertEqual(flow.response.status_code, 200)
        self.monitor.response(flow)
        self.assertEqual((self.state()["phase"], self.state()["flow_count"]), ("ready", 0))
        self.assertEqual(self.state()["client_ip"], "192.168.1.11")

    def test_invalid_probe_does_not_mark_ready(self):
        for auth, path, tls in [(False, "/check-secret", True), (True, "/wrong", True), (True, "/check-secret", False)]:
            flow = self.flow(host="capture-check.invalid", path=path, auth=auth)
            flow.client_conn.tls = tls
            self.monitor.request(flow)
            self.monitor.response(flow)
        self.assertEqual(self.state()["phase"], "waiting_phone")

    def test_target_responses_bounded_and_unrelated_hosts_are_not_recorded(self):
        self.monitor.response(self.flow(host="unrelated.example"))
        for _ in range(25):
            flow = self.flow()
            flow.response.content = b"x" * 32768
            self.monitor.response(flow)
        state = self.state()
        self.assertEqual((state["phase"], state["flow_count"], len(state["flows"])), ("capturing", 25, 20))
        self.assertLessEqual(len(state["flows"][0]["response_body"].encode()), 16384)
        self.assertTrue(state["flows"][0]["truncated"])
        self.assertNotIn("password", state)
        self.assertNotIn("request_headers", state["flows"][0])

    def test_non_utf8_preview_still_respects_byte_budget(self):
        flow = self.flow()
        flow.response.content = b"\xff" * 16384
        self.monitor.response(flow)
        self.assertLessEqual(len(self.state()["flows"][0]["response_body"].encode()), 16384)

    def test_connect_only_reports_waiting_for_trust(self):
        self.monitor.http_connect(self.flow())
        self.assertEqual((self.state()["phase"], self.state()["flow_count"]), ("waiting_trust", 0))

    def test_gzip_response_is_readable_and_decompression_is_bounded(self):
        flow = self.flow()
        flow.response.headers["content-encoding"] = "gzip"
        flow.response.raw_content = gzip.compress(b'{"value":"' + b"a" * 200000 + b'"}')
        self.monitor.response(flow)
        preview = self.state()["flows"][0]
        self.assertTrue(preview["response_body"].startswith('{"value":"'))
        self.assertLessEqual(len(preview["response_body"].encode()), 16384)
        self.assertTrue(preview["truncated"])

    def test_serialized_state_stays_bounded_for_control_bytes_and_long_urls(self):
        for _ in range(25):
            flow = self.flow(path="/" + "x" * 65536)
            flow.request.content = b"\x00" * 16384
            flow.response.content = b"\x00" * 16384
            self.monitor.response(flow)
        state = self.state()
        self.assertEqual(state["flow_count"], 25)
        self.assertLess(Path(self.cfg["state_path"]).stat().st_size, 1_500_000)
        self.assertLessEqual(len(state["flows"][-1]["url"].encode()), 2048)

    def test_unsupported_upgrades_do_not_retain_tcp_message_history(self):
        flow = SimpleNamespace(messages=[SimpleNamespace(content=b"hello")])
        self.monitor.tcp_message(flow)
        self.assertEqual(flow.messages, [])

    def test_owner_pid_reuse_or_exit_stops_capture_even_if_backend_is_alive(self):
        cfg = {"owner_pid": 42, "owner_identity": "original"}
        with patch("capture_console.ios_pairing_proxy.process_identity", return_value="original"):
            self.assertTrue(owner_is_alive(cfg))
        for identity in [None, "reused PID"]:
            with patch("capture_console.ios_pairing_proxy.process_identity", return_value=identity):
                self.assertFalse(owner_is_alive(cfg))


class IOSWorkerTests(unittest.TestCase):
    def test_state_write_failure_stops_proxy_and_still_deletes_secrets(self):
        original_mask = os.umask(0o077)
        self.addCleanup(os.umask, original_mask)
        class Master:
            def __init__(self, *args, **kwargs):
                self.done = asyncio.Event()
                self.addons = Mock()
            async def run(self):
                await self.done.wait()
            def shutdown(self):
                self.done.set()

        with tempfile.TemporaryDirectory() as tmp:
            cfg = config(Path(tmp))
            cfg["parent_pid"] = os.getppid()
            (Path(tmp) / "config.json").write_text("secret")
            async def exercise():
                await asyncio.wait_for(run(cfg), timeout=3)
            with patch("capture_console.ios_pairing_proxy.DumpMaster", Master), \
                    patch("capture_console.ios_pairing_proxy.options.Options", return_value=Mock()), \
                    patch("capture_console.ios_pairing_proxy.owner_is_alive", return_value=True), \
                    patch.object(PairingMonitor, "flush", side_effect=OSError("disk full")):
                asyncio.run(exercise())
            for name in ["ca", "config.json", "iPhone.mobileconfig"]:
                self.assertFalse((Path(tmp) / name).exists(), name)


class IOSServiceTests(unittest.TestCase):
    def setUp(self):
        identity = patch("capture_console.ios_setup.process_identity", return_value="test desktop identity")
        identity.start()
        self.addCleanup(identity.stop)

    def test_restart_requires_phone_cleanup_and_keeps_marker_on_shutdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "session-test"
            directory.mkdir()
            (root / "cleanup-required").write_text(directory.name)
            service = IOSSetupService(root)
            self.assertEqual(service.status()["phase"], "failed")
            with self.assertRaises(ValueError):
                service.prepare("Office")
            service.shutdown()
            self.assertTrue((root / "cleanup-required").exists())
            service.stop()
            self.assertFalse((root / "cleanup-required").exists())
            self.assertFalse(directory.exists())

    def test_unreadable_status_is_failure_not_stale_capture_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = IOSSetupService(Path(tmp))
            service.process = Mock()
            service.process.poll.return_value = None
            path = Path(tmp) / "state.json"
            path.write_text("x" * 2_000_001)
            service.config = {"state_path": str(path)}
            service.last = {"phase": "capturing", "flow_count": 2, "flows": []}
            self.assertEqual(service.status()["phase"], "failed")

    def test_start_is_idempotent_and_stop_only_terminates_owned_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            process = Mock()
            process.poll.return_value = None
            def spawn(args, **kwargs):
                cfg = json.loads(Path(args[-1]).read_text())
                Path(cfg["state_path"]).write_text(json.dumps({"phase": "waiting_phone", "flow_count": 0, "flows": []}))
                return process
            service = IOSSetupService(Path(tmp), host_provider=lambda: "192.168.1.10")
            with patch("capture_console.ios_setup.subprocess.Popen", side_effect=spawn) as popen, \
                    patch("capture_console.ios_setup.socket.socket") as sock:
                sock.return_value.__enter__.return_value.getsockname.return_value = ("192.168.1.10", 9190)
                first = service.prepare("Office")
                self.assertEqual(service.prepare("Office"), first)
                with self.assertRaises(ValueError):
                    service.prepare("Another Wi-Fi")
                self.assertEqual(popen.call_count, 1)
                service.stop()
                process.terminate.assert_called_once()
                process.wait.assert_called_once()
                self.assertEqual(service.status()["phase"], "stopped")

    def test_missing_lan_fails_before_spawning_and_does_not_touch_other_ports(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = IOSSetupService(Path(tmp), host_provider=lambda: "127.0.0.1")
            with patch("capture_console.ios_setup.subprocess.Popen") as popen, self.assertRaises(ValueError):
                service.prepare("Office")
            popen.assert_not_called()

    def test_worker_exit_is_not_reported_as_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = IOSSetupService(Path(tmp), host_provider=lambda: "192.168.1.10")
            process = Mock()
            process.poll.return_value = 1
            with patch("capture_console.ios_setup.subprocess.Popen", return_value=process), \
                    patch("capture_console.ios_setup.socket.socket") as sock, self.assertRaises(RuntimeError):
                sock.return_value.__enter__.return_value.getsockname.return_value = ("192.168.1.10", 9190)
                service.prepare("Office")
            self.assertEqual(service.status()["phase"], "failed")


class IOSAPITests(unittest.TestCase):
    def test_ios_cleanup_failure_does_not_skip_android_shutdown(self):
        from capture_console import app as module
        with patch.object(module.ios_setup_service, "shutdown", side_effect=OSError("cleanup failed")), \
                patch.object(module, "stop_logcat_reaper"), \
                patch.object(module.logcat_service, "stop_all") as logcat, \
                patch.object(module.weak_network_service, "restore_all") as restore, \
                patch.object(module, "desktop_runtime_metadata", return_value={"enabled": True}), \
                patch.object(module, "stop_all_active_captures") as captures, \
                patch.object(module, "clear_project_capture_records") as records:
            with self.assertRaises(OSError):
                module.shutdown()
            logcat.assert_called_once()
            restore.assert_called_once()
            captures.assert_called_once()
            records.assert_called_once()

    def setUp(self):
        from fastapi import FastAPI
        from capture_console.ios_setup_api import ios_setup_router
        self.service = Mock()
        self.service.status.return_value = {"phase": "idle", "flow_count": 0, "flows": []}
        self.app = FastAPI()
        self.app.include_router(ios_setup_router(self.service))

    def post(self, path, json):
        body = __import__("json").dumps(json).encode()
        messages = []
        async def request():
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}
            async def send(message):
                messages.append(message)
            await self.app({"type": "http", "http_version": "1.1", "asgi": {"version": "3.0"},
                            "method": "POST", "scheme": "http", "path": path, "query_string": b"",
                            "headers": [(b"content-type", b"application/json")],
                            "client": ("127.0.0.1", 1), "server": ("127.0.0.1", 7001)}, receive, send)
        asyncio.run(request())
        text = b"".join(x.get("body", b"") for x in messages).decode()
        return SimpleNamespace(status_code=messages[0]["status"], text=text,
                               json=lambda: __import__("json").loads(text))

    def test_stop_rejects_missing_phone_confirmation(self):
        self.assertEqual(self.post("/api/ios-setup/stop", json={}).status_code, 409)
        self.service.stop.assert_not_called()
        self.service.stop.return_value = {"phase": "stopped", "flow_count": 0, "flows": []}
        result = self.post("/api/ios-setup/stop", json={"phone_configuration_removed": True})
        self.assertEqual(result.json()["phase"], "stopped")
        self.service.stop.assert_called_once()

    def test_start_failure_never_leaks_raw_command_or_credentials(self):
        self.service.prepare.side_effect = RuntimeError("secret CLI arguments")
        result = self.post("/api/ios-setup/prepare", json={"ssid": "Office", "desktop_pid": os.getpid()})
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("secret", result.text)

    def test_prepare_payload_is_forwarded_and_unknown_fields_rejected(self):
        self.service.prepare.return_value = {"phase": "waiting_phone", "flow_count": 0, "flows": []}
        result = self.post("/api/ios-setup/prepare", json={"ssid": "Office", "desktop_pid": os.getpid()})
        self.assertEqual(result.status_code, 200)
        self.service.prepare.assert_called_once_with("Office", owner_pid=os.getpid())
        result = self.post("/api/ios-setup/prepare", json={"ssid": "Office", "password": "not-collected"})
        self.assertEqual(result.status_code, 422)


if __name__ == "__main__":
    unittest.main()

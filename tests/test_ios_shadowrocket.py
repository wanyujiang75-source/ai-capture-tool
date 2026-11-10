import base64
import asyncio
import importlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from urllib.parse import urlsplit, parse_qs

from fastapi import FastAPI
from capture_console.ios_setup import make_profile
from capture_console.ios_setup_api import ios_setup_router


def device(identifier="phone-1", name="Test iPhone", transport="wired", reality="physical"):
    return {"identifier": identifier, "hardwareProperties": {"udid": identifier}, "properties": {
        "hardware": {"udid": identifier, "reality": reality, "deviceType": "iPhone"},
        "state": {"name": name},
        "connection": {"state": "connected", "transportType": transport, "pairingState": "paired"}}}


def request(app, path, *, headers=None, body=None, client="127.0.0.1"):
    messages = []
    raw = json.dumps(body).encode() if body is not None else b""
    values = {"host": "127.0.0.1", "content-type": "application/json",
              **{k.lower(): v for k, v in (headers or {}).items()}}
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "scheme": "http",
             "method": "POST" if body is not None else "GET", "path": path, "query_string": b"",
             "headers": [(k.lower().encode(), v.encode()) for k, v in values.items()],
             "server": ("127.0.0.1", 80), "client": (client, 1234)}
    async def run():
        async def receive():
            return {"type": "http.request", "body": raw}
        async def send(message):
            messages.append(message)
        await app(scope, receive, send)
    asyncio.run(run())
    response = b"".join(m.get("body", b"") for m in messages)
    return messages[0]["status"], dict(messages[0]["headers"]), json.loads(response)


class ShadowrocketTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("capture_console.ios_shadowrocket"),
                             "节点导入适配尚未实现")
        self.module = importlib.import_module("capture_console.ios_shadowrocket")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.config = {"host": "192.168.1.10", "port": 9190, "ssid": "Office", "username": "ios",
                       "password": "fake-+/_secret-测试", "check_token": "fake-check"}
        (root / "iPhone.mobileconfig").write_bytes(make_profile(self.config, b"public-certificate"))
        self.service = SimpleNamespace(lock=threading.RLock(), directory=root, config=self.config,
            process=Mock(poll=Mock(return_value=None)), host_provider=lambda: self.config["host"],
            status=lambda: {"phase": "waiting_phone", "recording_state": "idle"})
        self.runner = Mock(side_effect=self.run_command)
        self.adapter = self.module.IOSShadowrocket(self.service, runner=self.runner)

    def run_command(self, args, **kwargs):
        if args[2:4] == ["list", "devices"]:
            path = Path(args[args.index("--json-output") + 1])
            path.write_text(json.dumps({"result": {"devices": [device(), device("remote", transport="localNetwork"),
                device("sim", reality="simulated"), device("phone-2", "Second iPhone")]}}))
        return SimpleNamespace(returncode=0)

    def test_current_connection_uri_encodes_complete_authority_without_route_actions(self):
        info = self.adapter.connection()
        parts = urlsplit(info["import_url"])
        encoded = parts.path.removeprefix("/http://")
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
        self.assertEqual(decoded, "ios:fake-+/_secret-测试@192.168.1.10:9190")
        self.assertEqual((parts.scheme, parts.netloc, parse_qs(parts.query)),
                         ("shadowrocket", "add", {"remarks": ["Capture-Mac"]}))
        self.assertEqual(info["port"], 9190)
        self.assertEqual([x["id"] for x in info["devices"]], ["phone-1", "phone-2"])

    def test_certificate_share_contains_no_wifi_proxy_or_private_credentials(self):
        original = (Path(self.tmp.name) / "iPhone.mobileconfig").read_bytes()
        path = Path(self.adapter.connection()["profile_path"])
        profile = plistlib.loads(path.read_bytes())
        self.assertEqual([p["PayloadType"] for p in profile["PayloadContent"]],
                         ["com.apple.security.root", "com.apple.webClip.managed"])
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertNotIn(self.config["password"].encode(), path.read_bytes())
        self.assertNotIn(b"ProxyPassword", path.read_bytes())
        self.assertEqual((Path(self.tmp.name) / "iPhone.mobileconfig").read_bytes(), original)

    def test_send_targets_only_explicit_current_wired_phone_and_does_not_claim_imported(self):
        result = self.adapter.send("phone-2")
        args = self.runner.call_args.args[0]
        self.assertEqual(result, {"state": "confirmation_required"})
        self.assertEqual(args[args.index("--device") + 1], "phone-2")
        self.assertEqual(args[-1], "com.liguangming.Shadowrocket")
        self.assertIn("shadowrocket://add/", args[args.index("--payload-url") + 1])
        self.assertNotIn("connect", args)
        self.assertNotIn("select", args)
        with self.assertRaises(ValueError):
            self.adapter.send("remote")

    def test_tool_failure_and_timeout_return_manual_fallback_without_raw_secret(self):
        for error in [FileNotFoundError(self.config["password"]), TimeoutError(self.config["password"]),
                      subprocess.TimeoutExpired(["fake", self.config["password"]], 1)]:
            self.runner.side_effect = error
            info = self.adapter.connection()
            self.assertEqual(info["devices"], [])
            self.assertEqual(info["host"], self.config["host"])
            self.assertNotIn(self.config["password"], str(self.adapter.send("phone-1")))
            self.assertEqual(self.adapter.send("phone-1")["state"], "manual_required")

    def test_client_launch_failure_is_manual_fallback_not_success(self):
        def failed_launch(args, **kwargs):
            if "--payload-url" in args:
                return SimpleNamespace(returncode=1)
            return self.run_command(args, **kwargs)
        self.runner.side_effect = failed_launch
        self.assertEqual(self.adapter.send("phone-1"), {"state": "manual_required"})

    def test_stopped_changed_network_and_recording_never_dispatch(self):
        for state in ["stopped", "changed", "recording"]:
            self.service.process.poll.return_value = 0 if state == "stopped" else None
            self.service.host_provider = lambda: "192.168.9.9" if state == "changed" else self.config["host"]
            self.service.status = lambda: {"phase": "ready", "recording_state": "recording" if state == "recording" else "idle"}
            self.runner.reset_mock()
            with self.assertRaises(ValueError):
                self.adapter.send("phone-1")
            self.runner.assert_not_called()

    def test_route_change_during_discovery_rejects_stale_credentials(self):
        def change(args, **kwargs):
            result = self.run_command(args, **kwargs)
            self.config["port"] += 1
            return result
        self.runner.side_effect = change
        with self.assertRaises(ValueError):
            self.adapter.send("phone-1")
        self.assertEqual(self.runner.call_count, 1)

    def test_refresh_uses_new_host_and_port_and_legacy_wifi_share_stays_unchanged(self):
        before = self.adapter.connection()
        self.config.update(host="192.168.3.4", port=22001)
        after = self.adapter.connection()
        self.assertEqual((after["host"], after["port"]), ("192.168.3.4", 22001))
        self.assertNotEqual(before["import_url"], after["import_url"])
        source = plistlib.loads((Path(self.tmp.name) / "iPhone.mobileconfig").read_bytes())
        self.assertEqual(source["PayloadContent"][0]["PayloadType"], "com.apple.wifi.managed")

    def test_remote_clients_cannot_read_credentials_or_trigger_import(self):
        app = FastAPI()
        app.include_router(ios_setup_router(self.service))
        for path, body in [("/api/ios-setup/shadowrocket", None),
                           ("/api/ios-setup/shadowrocket/import", {"device_id": "phone-1"})]:
            status, _, result = request(app, path, headers={"X-Capture-Desktop": "shadowrocket"},
                                        body=body, client="192.168.1.50")
            self.assertEqual(status, 403)
            self.assertNotIn(self.config["password"], str(result))

    def test_new_api_is_local_desktop_only_and_never_cached(self):
        app = FastAPI()
        app.include_router(ios_setup_router(self.service))
        headers = {"X-Capture-Desktop": "shadowrocket"}
        for extra in [{}, {"Origin": "https://evil.test"}, {"Host": "evil.test"}]:
            status, _, body = request(app, "/api/ios-setup/shadowrocket", headers=extra if not extra else {**headers, **extra})
            self.assertEqual(status, 403)
            self.assertNotIn(self.config["password"], str(body))
        with unittest.mock.patch.object(self.module, "IOSShadowrocket", return_value=self.adapter):
            status, response_headers, body = request(app, "/api/ios-setup/shadowrocket", headers=headers)
            self.assertEqual(status, 200)
            self.assertIn(b"no-store", response_headers[b"cache-control"])
            status, _, body = request(app, "/api/ios-setup/shadowrocket/import", headers=headers, body={"device_id": "phone-1"})
            self.assertEqual(body, {"state": "confirmation_required"})
        status, _, _ = request(app, "/api/ios-setup/shadowrocket/import", headers=headers,
                               body={"device_id": "phone-1", "url": "shadowrocket://connect"})
        self.assertEqual(status, 422)


if __name__ == "__main__":
    unittest.main()

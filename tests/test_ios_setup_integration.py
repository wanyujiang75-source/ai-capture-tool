"""Opt-in wire/lifetime checks: isolated local proxy, no phone/device changes."""

import base64
import http.client
import os
import plistlib
import ssl
import subprocess
import tempfile
import unittest
from pathlib import Path

from capture_console.ios_setup import IOSSetupService


@unittest.skipUnless(os.environ.get("CAPTURE_TEST_IOS_PROXY") == "1", "opt-in LAN proxy test")
class IOSSetupIntegrationTests(unittest.TestCase):
    def test_authenticated_tls_and_desktop_exit_cleanup(self):
        with tempfile.TemporaryDirectory(prefix="ios-setup-acceptance-") as tmp:
            # A separately owned inert process stands in for the desktop lifecycle.
            desktop = subprocess.Popen(["/bin/sleep", "60"])
            service = IOSSetupService(Path(tmp) / "ios-setup")
            try:
                state = service.prepare("Acceptance Test Only", owner_pid=desktop.pid)
                cfg = service.config
                profile = plistlib.loads(Path(state["profile_path"]).read_bytes())
                wifi, ca, _ = profile["PayloadContent"]
                self.assertEqual((wifi["ProxyServer"], wifi["ProxyServerPort"]), (cfg["host"], cfg["port"]))
                self.assertNotIn("Password", wifi)
                trust = ssl.create_default_context(cadata=ssl.DER_cert_to_PEM_cert(ca["PayloadContent"]))
                unauthenticated = http.client.HTTPSConnection(cfg["host"], cfg["port"], context=trust, timeout=5)
                unauthenticated.set_tunnel("capture-check.invalid", 443)
                try:
                    with self.assertRaisesRegex(OSError, "407"):
                        unauthenticated.connect()
                finally:
                    unauthenticated.close()
                auth = base64.b64encode(f"{cfg['username']}:{cfg['password']}".encode()).decode()
                connection = http.client.HTTPSConnection(cfg["host"], cfg["port"], context=trust, timeout=5)
                connection.set_tunnel("capture-check.invalid", 443, headers={"Proxy-Authorization": "Basic " + auth})
                try:
                    connection.request("GET", "/" + cfg["check_token"])
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertIn("HTTPS", response.read().decode())
                finally:
                    connection.close()
                self.assertEqual(service.status()["phase"], "waiting_phone")
                worker = service.process
                directory = service.directory
                desktop.terminate()
                desktop.wait(timeout=3)
                self.assertEqual(worker.wait(timeout=6), 0)
                self.assertEqual(service.status()["phase"], "failed")
                for name in ["ca", "config.json", "iPhone.mobileconfig"]:
                    self.assertFalse((directory / name).exists(), name)
                self.assertTrue(service.marker.exists())
                restarted = IOSSetupService(service.root)
                self.assertEqual(restarted.status()["phase"], "failed")
                with self.assertRaises(ValueError):
                    restarted.prepare("Other Network")
                restarted.stop()
                self.assertFalse(service.marker.exists())
                self.assertFalse(directory.exists())
            finally:
                service.stop()
                if desktop.poll() is None:
                    desktop.terminate()
                    desktop.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()

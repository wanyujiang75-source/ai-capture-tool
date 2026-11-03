import http.client
import socket
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from tests.ios_import_probe import ProbeServer, validate_probe, validate_host


class ImportProbeTests(unittest.TestCase):
    def setUp(self):
        self.body = (Path(__file__).parent / "fixtures/ios_setup_import/empty.module").read_bytes()
        self.server = ProbeServer(("127.0.0.1", 0), self.body)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path):
        client = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        try:
            client.request(method, path)
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            client.close()

    def test_only_fixed_metadata_is_downloaded_without_cache(self):
        for _ in range(3):
            status, headers, body = self.request("GET", "/a1.module")
            self.assertEqual((status, body), (200, self.body))
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertEqual(int(headers["Content-Length"]), len(body))
        self.assertEqual(self.server.downloads, 3)

    def test_head_does_not_count_as_a_download(self):
        self.assertEqual(self.request("HEAD", "/a1.module")[::2], (200, b""))
        self.assertEqual(self.server.downloads, 0)

    def test_sgmodule_alias_changes_filename_but_not_payload(self):
        status, headers, body = self.request("GET", "/a1.sgmodule")
        self.assertEqual((status, body), (200, self.body))
        self.assertEqual(headers["Content-Disposition"], 'attachment; filename="a1.sgmodule"')
        self.assertEqual(headers["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(self.request("GET", "/a1.sgmodule?x=1")[0], 404)

    def test_unknown_paths_queries_and_mutations_are_rejected(self):
        for path in ["/", "/a1.module?token=x", "/../config.json", "/%2e%2e/config.json"]:
            self.assertEqual(self.request("GET", path)[0], 404)
        self.assertEqual(self.request("POST", "/a1.module")[0], 405)
        self.assertEqual(self.server.downloads, 0)

    def test_real_settings_or_unexpected_metadata_cannot_be_served(self):
        for content in [self.body + b"[Rule]\nFINAL,DIRECT\n", self.body + b"#!password=secret\n",
                        b"[Proxy]\n", self.body * 1000, self.body + b"\x00"]:
            with self.subTest(content_length=len(content)), self.assertRaises(ValueError):
                validate_probe(content)

    def test_bind_address_must_be_one_local_unicast_ipv4_address(self):
        for host in ["0.0.0.0", "8.8.8.8", "224.0.0.1", "::", "localhost", "169.254.1.1"]:
            with self.subTest(host=host), self.assertRaises(ValueError):
                validate_host(host)
        self.assertEqual(validate_host("192.168.1.10"), "192.168.1.10")
        self.assertEqual(validate_host("127.0.0.1"), "127.0.0.1")

    def test_cli_expires_and_releases_its_ephemeral_listener(self):
        result = subprocess.run(
            [sys.executable, "-m", "tests.ios_import_probe", "--host", "127.0.0.1", "--ttl", "1"],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("probe_closed=true", result.stdout)
        endpoint = urlsplit(result.stdout.splitlines()[0])
        with self.assertRaises(OSError):
            socket.create_connection((endpoint.hostname, endpoint.port), timeout=1)

    def test_cli_does_not_replace_an_existing_listener(self):
        result = subprocess.run(
            [sys.executable, "-m", "tests.ios_import_probe", "--host", "127.0.0.1",
             "--port", str(self.server.server_port), "--ttl", "1"],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=5,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Address already in use", result.stderr)
        self.assertEqual(self.request("GET", "/a1.module")[::2], (200, self.body))


if __name__ == "__main__":
    unittest.main()

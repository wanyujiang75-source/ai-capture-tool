import importlib.util
import tempfile
import unittest
from unittest import mock
from pathlib import Path


def load_exporter():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "ai_capture_export.py"
    spec = importlib.util.spec_from_file_location("ai_capture_export", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CaptureExporterTimingTests(unittest.TestCase):
    def test_mitmweb_client_bypasses_system_proxy_for_localhost(self):
        exporter = load_exporter()
        captured_handlers = []
        original_build_opener = exporter.urllib.request.build_opener

        def capture_build_opener(*handlers):
            captured_handlers.extend(handlers)
            return original_build_opener(*handlers)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(exporter.urllib.request, "build_opener", capture_build_opener):
            exporter.MitmWeb(9101, "android-capture", str(Path(tmp) / "cookies.txt"))

        self.assertTrue(
            any(
                handler.__class__.__name__ == "ProxyHandler" and getattr(handler, "proxies", None) == {}
                for handler in captured_handlers
            )
        )

    def test_flow_summary_calculates_request_response_timing_from_mitm_timestamps(self):
        exporter = load_exporter()

        summary = exporter.flow_summary(
            {
                "id": "flow-1",
                "request": {
                    "method": "POST",
                    "scheme": "https",
                    "host": "api.example.test",
                    "port": 443,
                    "path": "/create",
                    "timestamp_start": 1779243300.100,
                    "timestamp_end": 1779243300.120,
                    "headers": [["content-type", "application/json"]],
                },
                "response": {
                    "status_code": 200,
                    "timestamp_start": 1779243300.350,
                    "timestamp_end": 1779243300.380,
                    "headers": [["content-type", "application/json"]],
                },
            }
        )

        self.assertEqual(summary["request_duration_ms"], 20)
        self.assertEqual(summary["wait_duration_ms"], 230)
        self.assertEqual(summary["response_duration_ms"], 30)
        self.assertEqual(summary["total_duration_ms"], 280)
        self.assertRegex(summary["request_started_at"], r"2026-05-\d{2}T\d{2}:\d{2}:\d{2}\.100")
        self.assertRegex(summary["response_finished_at"], r"2026-05-\d{2}T\d{2}:\d{2}:\d{2}\.380")

    def test_once_reexports_legacy_pending_flow_when_response_arrives(self):
        exporter = load_exporter()

        class FakeMitmWeb:
            def __init__(self, *_args):
                pass

            def login(self):
                pass

            def flows(self):
                return [
                    {
                        "id": "flow-1",
                        "request": {
                            "method": "GET",
                            "scheme": "https",
                            "host": "198.18.5.89",
                            "pretty_host": "api.example.test",
                            "port": 443,
                            "path": "/rest/v1/profile",
                            "headers": [["accept", "application/json"]],
                            "timestamp_start": 1779243300.100,
                            "timestamp_end": 1779243300.120,
                        },
                        "response": {
                            "status_code": 200,
                            "headers": [["content-type", "application/json"]],
                            "timestamp_start": 1779243300.350,
                            "timestamp_end": 1779243300.380,
                        },
                    }
                ]

            def flow_content(self, flow_id, part):
                if flow_id != "flow-1":
                    raise AssertionError(f"unexpected flow id: {flow_id}")
                if part == "response":
                    return b'{"ok":true}'
                return b""

        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            (outdir / "seen-flow-ids.txt").write_text("flow-1\n", encoding="utf-8")
            argv = [
                "ai_capture_export.py",
                "--outdir",
                str(outdir),
                "--once",
            ]

            with mock.patch.object(exporter, "MitmWeb", FakeMitmWeb), mock.patch.object(exporter.sys, "argv", argv):
                self.assertEqual(exporter.main(), 0)

            candidates = (outdir / "candidates.tsv").read_text(encoding="utf-8")
            self.assertIn("\t200\t", candidates)
            self.assertEqual(len(list(outdir.glob("*.response.json"))), 1)


if __name__ == "__main__":
    unittest.main()

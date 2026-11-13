import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from scripts.qa_ad_network_trace import TraceParser


class TraceParserTests(unittest.TestCase):
    def emit(self, parser, data, tid=1):
        parser.feed(tid, "GMA Debug BEGIN")
        payload = json.dumps(data)
        for offset in range(0, len(payload), 70):
            parser.feed(tid, "GMA Debug CONTENT " + payload[offset:offset + 70])
        return parser.feed(tid, "GMA Debug FINISH")

    def test_correlates_without_retaining_secrets(self):
        parser = TraceParser()
        data = {"timestamp": 123, "event": "onNetworkRequest",
                "components": ["ad_request_secret", "network_request_secret"],
                "params": {"firstline": {"uri": "https://ads.example.org/x?token=SECRET", "verb": "GET"},
                           "headers": [{"name": "Cookie", "value": "SECRET"}], "body": "SECRET"}}
        request = self.emit(parser, data)
        data.update(event="onNetworkResponse", params={"firstline": {"code": 200}})
        response = self.emit(parser, data)
        self.assertEqual(request["components"], response["components"])
        self.assertEqual(request["host"], "ads.example.org")
        self.assertEqual(response["status"], 200)
        self.assertNotIn("secret", json.dumps([request, response]).lower())
        self.assertNotIn("/x", json.dumps(request))

    def test_interleaved_and_missing_begin(self):
        parser = TraceParser()
        self.assertIsNone(parser.feed(1, 'GMA Debug CONTENT {"event":"onNetworkRequest"}'))
        parser.feed(1, "GMA Debug BEGIN")
        parser.feed(2, "GMA Debug BEGIN")
        parser.feed(1, 'GMA Debug CONTENT {"timestamp":1,"event":"onNetworkRequest"}')
        parser.feed(2, 'GMA Debug CONTENT {"timestamp":2,"event":"onNetworkResponse"}')
        self.assertEqual(parser.feed(2, "GMA Debug FINISH")["timestamp"], 2)
        self.assertEqual(parser.feed(1, "GMA Debug FINISH")["timestamp"], 1)

    def test_sdk_request_error_retains_correlation_not_description(self):
        parser = TraceParser()
        components = ["network_request_private-id"]
        request = self.emit(parser, {"event": "onNetworkRequest", "components": components})
        error = self.emit(parser, {"event": "onNetworkRequestError", "components": components,
            "params": {"error_description": "SECRET https://example.com/?token=PRIVATE"}})
        self.assertEqual(error, {"event": "onNetworkRequestError", "components": request["components"]})
        self.assertEqual(parser.dropped, 0)

    def test_known_public_loader_classification_drops_url_details(self):
        uri = "https://googleads.g.doubleclick.net/mads/static/mad/sdk/native/sdk-core-v40-loader.html?secret=PRIVATE"
        result = self.emit(TraceParser(), {"event": "onNetworkRequest",
            "params": {"firstline": {"uri": uri, "verb": "GET"}}})
        self.assertEqual(result, {"event": "onNetworkRequest", "host": "googleads.g.doubleclick.net",
                                 "method": "GET", "resource": "gma_js_loader"})
        for candidate in (uri.replace("https:", "http:"), uri.replace(".net/", ".net:8443/"),
                          uri.replace(".net/", ".net.evil/"), uri.replace("-v40-", "-v41-"),
                          uri.replace(".html?", ".html/extra?")):
            with self.subTest(uri=candidate):
                result = self.emit(TraceParser(), {"event": "onNetworkRequest",
                    "params": {"firstline": {"uri": candidate}}})
                self.assertNotIn("resource", result)
                self.assertNotIn("PRIVATE", json.dumps(result))

    def test_video_hint_requires_url_path_not_query_or_host(self):
        parser = TraceParser()
        for uri, kind in (
            ("https://cdn.example.org/private.MP4?token=SECRET", "video_file_hint"),
            ("https://cdn.example.org/private.webm", "video_file_hint"),
            ("https://cdn.example.org/private.m3u8", "video_manifest_hint"),
            ("https://cdn.example.org/private.mpd", "video_manifest_hint"),
        ):
            result = self.emit(parser, {"event": "onNetworkRequest",
                "params": {"firstline": {"uri": uri}}})
            self.assertEqual(result, {"event": "onNetworkRequest", "host": "cdn.example.org",
                                      "resource": kind})
        for uri in ("https://cdn.example.org/x?file=private.mp4", "https://cdn.example.org/x.mp4/more",
                    "file://cdn.example.org/x.mp4", "https://user:SECRET@cdn.example.org/x.mp4",
                    "https://cdn.example.org:999999/x.mp4", "https://cdn.example.org/x%2emp4"):
            result = self.emit(parser, {"event": "onNetworkRequest",
                "params": {"firstline": {"uri": uri}}})
            self.assertNotIn("resource", result)
            self.assertNotIn("SECRET", json.dumps(result))

    def test_body_visibility_never_retains_or_decodes_payload(self):
        for params, expected in (({"body": "PRIVATE", "bodylength": 7}, "inline"),
                                 ({"bodydigest": "PRIVATE", "bodylength": 12000}, "digest_only"),
                                 ({"bodylength": 0}, "absent")):
            result = self.emit(TraceParser(), {"event": "onNetworkResponseBody", "params": params})
            self.assertEqual(result, {"event": "onNetworkResponseBody", "body_length": params["bodylength"],
                                      "body_visibility": expected})

    def test_dropped_reason_counts_are_fixed_and_bounded(self):
        parser = TraceParser(max_block=100, max_buffers=1, max_records=1)
        parser.feed(1, "GMA Debug BEGIN")
        parser.feed(2, "GMA Debug BEGIN")
        parser.feed(1, "GMA Debug CONTENT " + "x" * 101)
        parser.feed(1, "GMA Debug BEGIN")
        parser.feed(1, "GMA Debug CONTENT invalid")
        parser.feed(1, "GMA Debug FINISH")
        self.emit(parser, {"event": "SECRET"})
        self.emit(parser, {"event": "onNetworkRequest"})
        self.emit(parser, {"event": "onNetworkRequest"})
        self.assertEqual(getattr(parser, "drop_reasons", {}), {
            "buffer_limit": 1, "block_limit": 1, "invalid_json": 1,
            "unsupported_event": 1, "record_limit": 1})
        self.assertEqual(parser.dropped, 5)

    def test_bounds_and_malformed(self):
        parser = TraceParser(max_block=120, max_buffers=2, max_records=2)
        for tid in range(3):
            parser.feed(tid, "GMA Debug BEGIN")
        self.assertLessEqual(len(parser.buffers), 2)
        parser.feed(0, "GMA Debug CONTENT " + "x" * 121)
        self.assertIsNone(parser.feed(0, "GMA Debug FINISH"))
        self.assertIsNone(self.emit(parser, {"event": "SECRET"}))
        self.assertIsNone(self.emit(parser, []))
        for _ in range(3):
            self.emit(parser, {"event": "onNetworkRequest"}, tid=8)
        self.assertEqual(parser.records, 2)
        self.assertGreater(parser.dropped, 0)

    def test_invalid_fields_do_not_leak(self):
        result = self.emit(TraceParser(), {"timestamp": "SECRET", "event": "onNetworkRequest",
            "components": [None, 123], "params": {"firstline": {"uri": "https://[broken", "verb": "SECRET"}}})
        self.assertEqual(result, {"event": "onNetworkRequest"})

    def test_block_limit_counts_utf8_bytes(self):
        parser = TraceParser(max_block=10)
        parser.feed(1, "GMA Debug BEGIN")
        parser.feed(1, "GMA Debug CONTENT " + "\u4e2d" * 4)
        self.assertEqual(parser.buffers, {})
        self.assertEqual(parser.dropped, 1)

    def test_collector_scopes_uid_and_private_output(self):
        with tempfile.TemporaryDirectory() as directory:
            adb = Path(directory) / "fake-adb"
            output = Path(directory) / "trace.json"
            adb.write_text(
                "#!" + sys.executable + "\n"
                "import sys\n"
                "assert '--uid=11077' in sys.argv\n"
                "for text in ['GMA Debug BEGIN', "
                "'GMA Debug CONTENT {\"event\":\"onNetworkRequest\",\"params\":{\"body\":\"SECRET\"}}', "
                "'GMA Debug FINISH']:\n"
                " print('11-13 15:50:00.123 1234 5678 I Ads : ' + text)\n"
            )
            adb.chmod(0o700)
            result = subprocess.run([
                sys.executable, "scripts/qa_ad_network_trace.py", "--adb", str(adb),
                "--serial", "synthetic", "--uid", "11077", "--seconds", "1",
                "--output", str(output),
            ], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(report["records"], [{"event": "onNetworkRequest"}])
            self.assertNotIn("SECRET", output.read_text())
            self.assertEqual(os.stat(output).st_mode & 0o777, 0o600)

    def test_deadline_terminates_own_collector(self):
        with tempfile.TemporaryDirectory() as directory:
            adb = Path(directory) / "fake-adb"
            output = Path(directory) / "trace.json"
            adb.write_text("#!" + sys.executable + "\nimport time\ntime.sleep(30)\n")
            adb.chmod(0o700)
            start = time.monotonic()
            result = subprocess.run([
                sys.executable, "scripts/qa_ad_network_trace.py", "--adb", str(adb),
                "--serial", "synthetic", "--uid", "11077", "--seconds", "1",
                "--output", str(output),
            ], capture_output=True, text=True, timeout=6)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertLess(time.monotonic() - start, 5)
            self.assertEqual(json.loads(output.read_text())["logcat_exit"], -15)

    def test_pid_mode_verifies_identity_and_rejects_foreign_fragments(self):
        with tempfile.TemporaryDirectory() as directory:
            adb = Path(directory) / "fake-adb"
            output = Path(directory) / "trace.json"
            adb.write_text("#!" + sys.executable + "\n"
                "import sys\n"
                "if 'shell' in sys.argv:\n"
                " print('UID PID\\n11077 1234')\n"
                "else:\n"
                " assert '--pid=1234' in sys.argv and '--uid=11077' not in sys.argv\n"
                " assert 'threadtime,uid' in sys.argv\n"
                " for uid,pid,text in [\n"
                "  (11077,1234,'GMA Debug BEGIN'),\n"
                "  (11078,1234,'GMA Debug CONTENT {\"event\":\"onNetworkResponse\"}'),\n"
                "  (11077,1234,'GMA Debug FINISH'),\n"
                "  (11077,5678,'GMA Debug BEGIN'),\n"
                "  (11077,1234,'GMA Debug BEGIN'),\n"
                "  (11077,1234,'GMA Debug CONTENT {\"event\":\"onNetworkRequest\",\"params\":{\"body\":\"SECRET\"}}'),\n"
                "  (11077,1234,'GMA Debug FINISH')]:\n"
                "  print(f'11-13 18:40:00.123 {uid} {pid} 5678 I Ads : {text}')\n")
            adb.chmod(0o700)
            result = subprocess.run([sys.executable, "scripts/qa_ad_network_trace.py",
                "--adb", str(adb), "--serial", "synthetic", "--uid", "11077", "--pid", "1234",
                "--seconds", "1", "--output", str(output)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(report["records"], [{"event": "onNetworkRequest"}])
            self.assertEqual(report["drop_reasons"], {"scope_mismatch": 2})
            self.assertEqual(report["collection_mode"], "verified_pid")
            self.assertNotIn("SECRET", output.read_text())

    def test_pid_mode_rejects_wrong_or_unavailable_identity_before_collecting(self):
        for identity in ("11078 1234", "11077 5678", "", "u0_a1077 1234"):
            with self.subTest(identity=identity), tempfile.TemporaryDirectory() as directory:
                adb = Path(directory) / "fake-adb"
                output = Path(directory) / "trace.json"
                adb.write_text("#!" + sys.executable + "\nimport sys\n"
                    "assert 'shell' in sys.argv\nprint(" + repr("UID PID\n" + identity) + ")\n")
                adb.chmod(0o700)
                result = subprocess.run([sys.executable, "scripts/qa_ad_network_trace.py",
                    "--adb", str(adb), "--serial", "synthetic", "--uid", "11077", "--pid", "1234",
                    "--seconds", "1", "--output", str(output)], capture_output=True, text=True, timeout=5)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("PID identity", result.stderr)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()

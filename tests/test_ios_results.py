import gzip
import json
import tempfile
import unittest
from pathlib import Path

from mitmproxy import connection, http

from capture_console.ios_projects import IOSProjects, domain_matches, normalize_domains
from capture_console.ios_results import IOSCaptureArchive


def make_flow(url="https://api.example.test/items?query=one"):
    flow = http.HTTPFlow(connection.Client(peername=("192.168.1.11", 1234), sockname=("192.168.1.10", 9180)),
                         connection.Server(address=("api.example.test", 443)))
    flow.request = http.Request.make("POST", url, b'{"request":1}', {"content-type": "application/json"})
    flow.response = http.Response.make(200, b'{"response":true}', {"content-type": "application/json"})
    return flow


class IOSProjectTests(unittest.TestCase):
    def test_domain_normalization_and_explicit_subdomain_boundary(self):
        self.assertEqual(normalize_domains([" API.Example.COM ", "*.Example.com", "API.Example.COM"]),
                         ["api.example.com", "*.example.com"])
        self.assertTrue(domain_matches("a.example.com", ["*.example.com"]))
        self.assertFalse(domain_matches("example.com", ["*.example.com"]))
        self.assertFalse(domain_matches("badexample.com", ["*.example.com"]))
        self.assertFalse(domain_matches("a.example.com.evil.test", ["*.example.com"]))
        for values in [[], ["*"], ["https://example.com/path"], ["user@example.com"],
                       ["example.com:443"], ["bad\nhost"], ["capture-check.invalid"]]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                normalize_domains(values)

    def test_projects_persist_and_return_independent_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "projects.json"
            projects = IOSProjects(path)
            self.assertEqual(projects.list()[0]["name"], "PokeHub")
            saved = projects.save(name="Example", domains=["api.example.com"])
            saved["domains"].append("evil.test")
            restored = IOSProjects(path).get(saved["id"])
            self.assertEqual(restored["domains"], ["api.example.com"])
            updated = projects.save(project_id=saved["id"], name="Renamed", domains=["new.example.com"])
            self.assertEqual(IOSProjects(path).get(saved["id"]), updated)

    def test_project_storage_limit_preserves_last_readable_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'projects.json'
            projects = IOSProjects(path)
            domains = [('a' * 60 + '.') * 3 + 'example' + str(i) + '.test' for i in range(64)]
            for i in range(100):
                before = projects.list()
                try:
                    projects.save(name=str(i), domains=domains)
                except ValueError:
                    self.assertEqual(projects.list(), before)
                    break
            self.assertLessEqual(path.stat().st_size, 512 * 1024)


class IOSArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_summary_types_update_with_headers_and_remain_readable_in_old_archives(self):
        archive = IOSCaptureArchive(self.root)
        flow = make_flow()
        flow.request.headers['Content-Type'] = ' Application/JSON; charset=utf-8 '
        archive.begin(flow)
        first = archive.page()
        self.assertEqual((first['flows'][0].get('request_content_type'),
                          first['flows'][0].get('response_content_type')), ('application/json', ''))
        flow.response.headers['Content-Type'] = ' IMAGE/PNG; charset=binary '
        archive.headers(flow)
        changed = archive.page(cursor=first['cursor'])
        self.assertEqual(changed['flows'][0]['response_content_type'], 'image/png')
        flow.response.headers['Content-Type'] = 'x' * 10000
        archive.finish(flow)
        self.assertEqual(archive.page()['flows'][0]['response_content_type'], 'x' * 256)
        with archive.connect() as conn:
            old = {k: v for k, v in first['flows'][0].items() if not k.endswith('_content_type')}
            conn.execute('UPDATE flows SET summary=?', (json.dumps(old),))
        archive.close()
        self.assertEqual(IOSCaptureArchive(self.root, read_only=True).page()['flows'], [old])

    def test_request_then_response_updates_same_record_and_preserves_full_url(self):
        archive = IOSCaptureArchive(self.root)
        flow = make_flow()
        self.assertTrue(archive.begin(flow))
        first = archive.page()
        self.assertEqual(first["flows"][0]["status"], "NO_RESPONSE")
        archive.append_body(flow.id, "request", flow.request.raw_content)
        archive.request_complete(flow)
        archive.append_body(flow.id, "response", flow.response.raw_content)
        archive.finish(flow)
        changed = archive.page(cursor=first["cursor"])
        self.assertEqual(len(changed["flows"]), 1)
        self.assertEqual(changed["total"], 1)
        self.assertEqual(changed["flows"][0]["status"], "200")
        self.assertEqual(changed["flows"][0]["url"], flow.request.url)
        detail = archive.detail(flow.id)
        self.assertEqual(detail["request_text"], '{"request":1}')
        self.assertEqual(detail["response_text"], '{"response":true}')
        self.assertIn("query=one", archive.curl(flow.id))

    def test_pagination_never_returns_an_unbounded_list(self):
        archive = IOSCaptureArchive(self.root)
        for _ in range(205):
            archive.begin(make_flow())
        first = archive.page()
        self.assertEqual(len(first["flows"]), 200)
        self.assertIsNotNone(first["next_cursor"])
        second = archive.page(cursor=first["next_cursor"])
        self.assertEqual(len(second["flows"]), 5)
        self.assertIsNone(second["next_cursor"])

    def test_stop_rejects_old_callbacks_and_keeps_saved_results(self):
        archive = IOSCaptureArchive(self.root)
        flow = make_flow()
        archive.begin(flow)
        archive.close()
        before = archive.page()
        archive.append_body(flow.id, "response", b"late response")
        archive.finish(flow)
        self.assertFalse(archive.begin(make_flow()))
        self.assertEqual(archive.page(), before)
        self.assertEqual(IOSCaptureArchive(self.root, read_only=True).page(), before)

    def test_body_limit_is_explicit_and_curl_cannot_fake_complete_request(self):
        archive = IOSCaptureArchive(self.root, body_limit=8)
        flow = make_flow()
        archive.begin(flow)
        archive.append_body(flow.id, "request", b"a" * 20)
        archive.finish(flow)
        body = archive.detail(flow.id)["request_body"]
        self.assertEqual(Path(body["path"]).stat().st_size, 8)
        self.assertTrue(body["truncated"])
        with self.assertRaises(ValueError):
            archive.curl(flow.id)

    def test_incomplete_request_cannot_be_replayed_and_binary_is_not_displayed_as_text(self):
        archive = IOSCaptureArchive(self.root)
        flow = make_flow()
        archive.begin(flow)
        archive.append_body(flow.id, "request", b"partial")
        with self.assertRaises(ValueError):
            archive.curl(flow.id)
        self.assertTrue(archive.detail(flow.id)['request_body']['truncated'])
        archive.request_complete(flow)
        flow.response.headers['content-type'] = 'image/png'
        archive.append_body(flow.id, 'response', b'\x89PNG\x00\x01\x02')
        archive.finish(flow)
        detail = archive.detail(flow.id)
        self.assertEqual((detail['response_body_kind'], detail['response_text']), ('binary', ''))

    def test_large_urls_have_byte_bounded_pages_and_oversized_metadata_stops_safely(self):
        archive = IOSCaptureArchive(self.root)
        for _ in range(100):
            archive.begin(make_flow('https://example.test/' + 'a' * 16000))
        page = archive.page()
        self.assertLess(len(json.dumps(page).encode()), 1024 * 1024 + 4096)
        self.assertIsNotNone(page['next_cursor'])
        huge = make_flow()
        huge.request.headers['x-huge'] = 'x' * 200000
        self.assertFalse(archive.begin(huge))
        self.assertEqual(archive.limit_reason, 'metadata_limit')

    def test_capture_count_and_storage_limits_stop_recording_without_deleting_results(self):
        archive = IOSCaptureArchive(self.root, record_limit=1)
        archive.begin(make_flow())
        self.assertFalse(archive.begin(make_flow()))
        self.assertEqual(archive.limit_reason, "record_limit")
        self.assertEqual(archive.page()["total"], 1)
        another = IOSCaptureArchive(self.root / "storage", storage_limit=65536)
        flow = make_flow()
        another.begin(flow)
        another.append_body(flow.id, "request", b"x" * 100000)
        self.assertEqual(another.limit_reason, "storage_limit")
        self.assertLessEqual(another.stored_bytes, 65536)

    def test_large_gzip_response_has_bounded_decoded_preview_and_large_curl_uses_file(self):
        archive = IOSCaptureArchive(self.root)
        flow = make_flow()
        flow.response.headers["content-encoding"] = "gzip"
        archive.begin(flow)
        archive.append_body(flow.id, "request", b"r" * 300000)
        archive.request_complete(flow)
        archive.append_body(flow.id, "response", gzip.compress(b"a" * 2000000))
        archive.finish(flow)
        detail = archive.detail(flow.id)
        self.assertLessEqual(len(detail["response_text"].encode()), 256 * 1024)
        self.assertTrue(detail["response_body"]["truncated"])
        curl = archive.curl(flow.id)
        self.assertLess(len(curl), 4096)
        self.assertIn("--data-binary", curl)
        self.assertIn("@", curl)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from mitmproxy.test import tflow


class ArchiveTests(unittest.TestCase):
    def test_header_only_edit_preserves_original_and_effective_curl(self):
        from capture_console.breakpoints.archive import BreakpointArchive
        with tempfile.TemporaryDirectory() as temp:
            archive = BreakpointArchive(Path(temp))
            flow = tflow.tflow(resp=True)
            flow.request.url = 'https://example.test/old'
            flow.request.content = b''
            archive.begin(flow)
            original = archive.snapshot(flow, 'request')
            flow.request.path = '/new'
            archive.record_decision(flow, 'request', original, 'apply', 'user')
            archive.request_complete(flow)
            archive.finish(flow)
            detail = archive.detail(flow.id)
            self.assertEqual(detail['breakpoints']['request']['original']['url'], 'https://example.test/old')
            self.assertEqual(detail['url'], 'https://example.test/new')
            self.assertIn('/new', archive.curl(flow.id))
            self.assertEqual(archive.page()['total'], 1)

    def test_original_versions_share_body_and_count_towards_quota(self):
        from capture_console.breakpoints.archive import BreakpointArchive
        with tempfile.TemporaryDirectory() as temp:
            archive = BreakpointArchive(Path(temp), storage_limit=128*1024)
            flow = tflow.tflow()
            flow.request.content = b'a' * 4096
            archive.begin(flow)
            original = archive.snapshot(flow, 'request')
            self.assertTrue(archive.record_decision(flow, 'request', original, 'original', 'user'))
            versions = archive.detail(flow.id)['breakpoints']['request']
            self.assertEqual(versions['original']['body_file'], versions['effective']['body_file'])
            self.assertEqual(archive.body_bytes, 4096)
            flow.request.content = b'b' * (128*1024)
            self.assertFalse(archive.record_decision(flow, 'request', original, 'apply', 'user'))
            self.assertEqual(archive.limit_reason, 'storage_limit')
            self.assertLess(archive.stored_bytes, archive.storage_limit)

    def test_android_reader_uses_committed_archive_and_effective_curl(self):
        from capture_console.breakpoints.archive import BreakpointArchive
        from capture_console.breakpoints.runtime import private_json
        from capture_console.results import scan_capture, get_flow_detail, build_curl
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = BreakpointArchive(root)
            private_json(root/'breakpoint-archive.json', {'version': 1})
            flow = tflow.tflow(resp=True)
            flow.request.content = b'new'
            archive.begin(flow)
            archive.append_body(flow.id, 'request', flow.request.raw_content)
            archive.request_complete(flow)
            archive.finish(flow)
            self.assertEqual([f['flow_id'] for f in scan_capture(root)], [flow.id])
            detail = get_flow_detail(root, flow.id)
            self.assertEqual(detail['request_text'], 'new')
            self.assertEqual(build_curl(detail), archive.curl(flow.id))

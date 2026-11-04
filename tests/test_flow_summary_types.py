import json
import tempfile
import unittest
from pathlib import Path

from capture_console.results import scan_capture


class FlowSummaryTypesTests(unittest.TestCase):
    def test_android_summary_exposes_bounded_mime_without_reading_bodies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'candidates.tsv').write_text(
                'url\tmeta\nhttps://example.test/resource\tflow.meta.json\n', encoding='utf-8')
            meta = root / 'flow.meta.json'
            for request_type, response_type, expected in [
                (' Application/JSON; charset=utf-8 ', ' IMAGE/PNG ', ('application/json', 'image/png')),
                (None, None, ('', '')),
                ('x' * 10000, 'y' * 10000, ('x' * 256, 'y' * 256)),
            ]:
                with self.subTest(expected=expected):
                    meta.write_text(json.dumps({'summary': {
                        'request_content_type': request_type, 'response_content_type': response_type,
                        'request_headers': [['authorization', 'not-for-list']],
                    }}), encoding='utf-8')
                    flow = scan_capture(root)[0]
                    self.assertEqual((flow.get('request_content_type'), flow.get('response_content_type')), expected)
                    self.assertNotIn('not-for-list', json.dumps(flow))

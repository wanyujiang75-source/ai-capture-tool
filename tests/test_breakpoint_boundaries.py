import ast
import asyncio
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from mitmproxy import http
from mitmproxy.test import tflow

from capture_console.breakpoints.archive import BreakpointArchive
from capture_console.breakpoints.models import RuleInput
from capture_console.breakpoints.runtime import RecordingRuntime
from capture_console.results import build_curl, get_flow_detail, scan_capture


class BoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = RecordingRuntime(None, self.root, '1', 'device-1')
        await self.runtime.start()
        self.addAsyncCleanup(self.runtime.close)

    def flow(self):
        flow = tflow.tflow()
        flow.request.url = 'https://example.test/api'
        flow.request.method = 'POST'
        flow.request.headers['content-type'] = 'application/json'
        flow.request.content = b'{"old":1}'
        return flow

    def enable(self):
        engine = self.runtime.addon.engine
        engine.put_rule('r', 0, RuleInput(scheme='https', host='example.test',
                        path='/api', method='POST', once=False))
        engine.enable()
        return engine

    async def test_close_waits_for_transport_after_decision_ack(self):
        self.enable()
        flow = self.flow()
        flow.live = True
        self.runtime.requestheaders(flow)
        request = asyncio.create_task(self.runtime.request(flow))
        await asyncio.sleep(0)
        closing = asyncio.create_task(self.runtime.close())
        await asyncio.sleep(.12)
        self.assertFalse(closing.done(), 'decision ACK is not HTTP completion')
        self.assertIsNone(flow.response)
        flow.live = False
        await closing
        await request

    async def test_concurrent_close_waits_for_same_cleanup(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def blocked_close():
            entered.set()
            await release.wait()
        with patch.object(self.runtime.addon, 'close', blocked_close):
            first = asyncio.create_task(self.runtime.close())
            await entered.wait()
            second = asyncio.create_task(self.runtime.close())
            await asyncio.sleep(.02)
            try:
                self.assertFalse(second.done())
            finally:
                release.set()
                await asyncio.gather(first, second)
        self.assertFalse(self.runtime.descriptor.exists())

    async def test_late_trailers_bypass_editing(self):
        engine = self.enable()
        flow = self.flow()
        self.runtime.requestheaders(flow)
        flow.request.trailers = http.Headers(digest='old-checksum')
        task = asyncio.create_task(self.runtime.request(flow))
        await asyncio.sleep(.02)
        try:
            self.assertTrue(task.done())
            self.assertEqual(engine.reserved_bytes, 0)
            self.assertEqual(flow.request.trailers['digest'], 'old-checksum')
        finally:
            engine.stop()
            await task

    async def test_archive_quota_stops_other_pending_items(self):
        engine = self.enable()
        flows = [self.flow(), self.flow()]
        for flow in flows:
            self.runtime.requestheaders(flow)
        tasks = [asyncio.create_task(self.runtime.request(flow)) for flow in flows]
        await asyncio.sleep(0)
        item = engine.pending()['data'][0]
        def quota(*args):
            self.runtime.archive._limit('storage_limit')
            return False
        try:
            with patch.object(self.runtime.archive, 'record_decision', quota):
                engine.resolve(item['id'], item['id']+'.a', 1, 'original')
                await asyncio.sleep(.05)
                self.assertFalse(engine.enabled)
                self.assertTrue(all(task.done() for task in tasks))
        finally:
            engine.stop()
            await asyncio.gather(*tasks)

    def test_short_write_does_not_publish_corrupt_version(self):
        archive = self.runtime.archive
        flow = self.flow()
        archive.begin(flow)
        original = archive.snapshot(flow, 'request')
        path = self.root / (hashlib.sha256(original['body']).hexdigest()+'.bp.bin')
        real_open = Path.open
        class BrokenFile:
            def __init__(self, file):
                self.file = file
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.file.close()
            def write(self, data):
                self.file.write(data[:3])
                raise OSError('disk full')
        def faulty_open(target, mode='r', *args, **kwargs):
            file = real_open(target, mode, *args, **kwargs)
            return BrokenFile(file) if mode == 'xb' else file
        with patch.object(Path, 'open', faulty_open), self.assertRaises(OSError):
            archive.record_decision(flow, 'request', original, 'original', 'user')
        self.assertFalse(path.exists())

    def test_corrupt_existing_version_is_not_reused(self):
        archive = self.runtime.archive
        flow = self.flow()
        archive.begin(flow)
        original = archive.snapshot(flow, 'request')
        path = self.root / (hashlib.sha256(original['body']).hexdigest()+'.bp.bin')
        path.write_bytes(b'bad')
        with self.assertRaises(OSError):
            archive.record_decision(flow, 'request', original, 'original', 'user')

    def test_android_scan_does_not_duplicate_updated_rows(self):
        archive = self.runtime.archive
        flow = self.flow()
        archive.begin(flow)
        summary = archive.page()['flows'][0]
        pages = [{'flows': [summary], 'next_cursor': 1}, {'flows': [summary], 'next_cursor': None}]
        with patch('capture_console.ios_results.IOSCaptureArchive.page', side_effect=pages):
            result = scan_capture(self.root)
        self.assertEqual(len(result), 1)

    def test_incomplete_android_curl_is_409(self):
        flow = self.flow()
        self.runtime.archive.begin(flow)
        source = Path('capture_console/app.py').read_text()
        function = next(n for n in ast.parse(source).body
                        if isinstance(n, ast.FunctionDef) and n.name == 'api_get_flow_curl')
        function.decorator_list = []
        scope = dict(Path=Path, HTTPException=HTTPException, build_curl=build_curl,
                     get_flow_detail=get_flow_detail,
                     session_or_404=lambda _: {'mode': 'system', 'outdir': str(self.root)})
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<curl-route>', 'exec'), scope)
        with self.assertRaises(HTTPException) as error:
            scope['api_get_flow_curl'](1, flow.id)
        self.assertEqual(error.exception.status_code, 409)

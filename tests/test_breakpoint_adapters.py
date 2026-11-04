import asyncio
import gzip
import tempfile
import unittest
from pathlib import Path

from mitmproxy.test import tflow

from capture_console.breakpoints.models import Patch, RuleInput


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from capture_console.breakpoints.addon import BreakpointAddon
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addon = BreakpointAddon('test', 'device-1', Path(self.tmp.name))
        self.flow = tflow.tflow(resp=True)
        self.flow.request.url = 'https://example.test/api'
        self.flow.request.method = 'POST'
        self.flow.request.headers['content-type'] = 'application/json'
        self.flow.request.content = b'{"old":1}'

    def enable(self, stage='request'):
        self.addon.engine.put_rule('r', 0, RuleInput(scheme='https', host='example.test',
            path='/api', method='POST', stage=stage))
        self.addon.engine.enable()

    async def test_disabled_does_not_admit_or_change(self):
        self.addon.requestheaders(self.flow)
        await self.addon.request(self.flow)
        self.assertEqual(self.flow.request.content, b'{"old":1}')
        self.assertEqual(self.addon.engine.status()['in_flight'], 0)

    async def test_request_modification_and_budget_released(self):
        self.enable()
        self.addon.requestheaders(self.flow)
        task = asyncio.create_task(self.addon.request(self.flow))
        await asyncio.sleep(0)
        item = self.addon.engine.pending()['data'][0]
        self.assertFalse(task.done())
        self.addon.engine.resolve(item['id'], item['id']+'.a', 1, 'apply',
                                  Patch(body_text='{"new":2}', url='https://example.test/changed'))
        await task
        self.assertEqual(self.flow.request.content, b'{"new":2}')
        self.assertEqual(self.flow.request.path, '/changed')
        self.assertEqual(self.addon.engine.reserved_bytes, 0)

    async def test_abort_does_not_make_success_response(self):
        self.enable()
        self.flow.response = None
        self.addon.requestheaders(self.flow)
        task = asyncio.create_task(self.addon.request(self.flow))
        await asyncio.sleep(0)
        item = self.addon.engine.pending()['data'][0]
        self.addon.engine.resolve(item['id'], item['id']+'.a', 1, 'abort')
        await task
        self.assertIsNone(self.flow.response)
        self.assertIsNotNone(self.flow.error)
        self.assertEqual(self.addon.engine.reserved_bytes, 0)

    async def test_empty_204_edit_does_not_send_compressed_empty_body(self):
        self.enable('response')
        self.flow.response.headers['content-type'] = 'application/json'
        self.flow.response.headers['content-encoding'] = 'gzip'
        self.flow.response.raw_content = gzip.compress(b'{"reply":1}')
        self.flow.response.headers['content-length'] = str(len(self.flow.response.raw_content))
        self.addon.requestheaders(self.flow)
        self.addon.responseheaders(self.flow)
        task = asyncio.create_task(self.addon.response(self.flow))
        await asyncio.sleep(0)
        item = self.addon.engine.pending()['data'][0]
        self.addon.engine.resolve(item['id'], item['id']+'.empty', 1, 'apply', Patch(status=204, body_text=''))
        await task
        self.assertEqual(self.flow.response.raw_content, b'')
        self.assertNotIn('transfer-encoding', self.flow.response.headers)
        self.assertNotIn('content-length', self.flow.response.headers)

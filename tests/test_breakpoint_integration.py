"""Real isolated clients -> product hooks/UDS -> TLS origin and archive."""

import asyncio
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import socket
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.request import build_opener, ProxyHandler, Request

from fastapi import FastAPI
import uvicorn
import zlib

from capture_console.breakpoints.supervisor import client_for
from capture_console.ios_results import IOSCaptureArchive
from tests.fixtures.breakpoints.wire import Origin, certificates, client


@unittest.skipUnless(os.environ.get('CAPTURE_TEST_BREAKPOINT_TRANSPORT') == '1', 'isolated transport opt-in')
class ProductionTests(unittest.IsolatedAsyncioTestCase):
    mode = 'regular'

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bp2-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.origin = Origin()
        self.clients = []
        _, tls = await asyncio.to_thread(certificates, self.root)
        self.origin_tls = tls
        await self.origin.start(tls)
        self.log = (self.root/'worker.log').open('wb')
        self.process = await asyncio.create_subprocess_exec(sys.executable, '-m',
            'tests.fixtures.breakpoints.production', str(self.root), self.mode,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=self.log)
        self.addAsyncCleanup(self.cleanup)
        self.port = (await self.event('ready'))['port']
        self.control = client_for(self.root/'archive')
        self.archive = IOSCaptureArchive(self.root/'archive', read_only=True)

    async def event(self, kind):
        line = await asyncio.wait_for(self.process.stdout.readline(), 10)
        self.assertTrue(line, (self.root/'worker.log').read_text()[-2500:])
        value = json.loads(line)
        self.assertEqual(value['kind'], kind, value)
        return value

    async def command(self, action):
        self.process.stdin.write(json.dumps({'action': action}).encode()+b'\n')
        await self.process.stdin.drain()

    async def cleanup(self):
        for exchange in self.clients:
            await exchange.close()
        await self.origin.close()
        if self.process.returncode is None:
            await self.command('shutdown')
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except TimeoutError:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), 3)
                self.fail('worker did not stop')
        self.log.close()
        tail = await self.process.stdout.read()
        self.assertNotIn(b'addon_error', tail, tail.decode())
        self.assertEqual(self.process.returncode, 0, (self.root/'worker.log').read_text()[-2500:])
        self.assertFalse((self.root/'archive'/'breakpoint-worker.json').exists())

    async def enable(self, stage='both'):
        await self.control.call('rule', {'id': 'r', 'expected_revision': 0, 'rule': {
            'scheme': 'https', 'host': '127.0.0.1', 'port': self.origin.port,
            'path': '/hit', 'path_match': 'prefix', 'method': 'POST', 'stage': stage, 'once': False}})
        await self.control.call('enable')

    async def begin(self, body=b'{"original":1}', protocol='http/1.1', *, headers=(), finish=True, unknown=False):
        exchange = await client(self.port, self.origin.port, self.root/'ca'/'mitmproxy-ca-cert.pem', protocol,
            mode=self.mode, auth=base64.b64encode(b'fixture:fixture').decode() if self.mode == 'ios' else '')
        self.clients.append(exchange)
        fields = [(':method', 'POST'), (':scheme', 'https'), (':authority', f'127.0.0.1:{self.origin.port}'),
                  (':path', '/hit'), ('content-type', 'application/json'), *headers]
        if not unknown:
            fields.append(('content-length', str(len(body) if finish else 100)))
        elif protocol == 'http/1.1':
            fields.append(('transfer-encoding', 'chunked'))
        await exchange.wire.headers(fields)
        if body:
            await exchange.wire.data(body)
        if finish:
            await exchange.wire.end()
        return exchange

    async def pending(self, stage):
        for _ in range(150):
            page = await self.control.call('pending')
            rows = [v for v in page['data'] if v['stage'] == stage and v['state'] == 'paused']
            if rows:
                return rows[0]
            await asyncio.sleep(.02)
        self.fail('no paused '+stage+' '+str(await self.control.call('status')))

    async def resolve(self, item, action='original', patch=None):
        value = dict(id=item['id'], operation_id=item['id']+'.a', expected_revision=item['revision'], action=action)
        if patch is not None:
            value['patch'] = patch
        await self.control.call('resolve', value)

    async def test_edit_wire_and_archive(self):
        self.origin.responses['/hit'] = {'body': b'{"reply":1}'}
        await self.enable()
        for protocol in ('http/1.1', 'h2'):
            exchange = await self.begin(protocol=protocol)
            request = await self.pending('request')
            count = len(self.origin.records)
            await asyncio.sleep(.05)
            self.assertEqual(len(self.origin.records), count)
            await self.resolve(request, 'apply', {'url': f'https://127.0.0.1:{self.origin.port}/hit?changed=1', 'body_text': '{"changed":2}'})
            response = await self.pending('response')
            self.assertEqual(bytes(self.origin.records[-1]['preview']), b'{"changed":2}')
            self.assertFalse(exchange.headers_seen.is_set())
            await self.resolve(response, 'apply', {'body_text': '{"reply":3}', 'status': 201})
            self.assertEqual(await asyncio.wait_for(exchange.task, 5), 'end')
            self.assertEqual((dict(exchange.headers)[':status'], bytes(exchange.preview)), ('201', b'{"reply":3}'))
            detail = self.archive.detail(request['flow_id'])
            self.assertEqual((detail['request_text'], detail['response_text']), ('{"changed":2}', '{"reply":3}'))
            self.assertEqual(detail['breakpoints']['request']['original']['url'], f'https://127.0.0.1:{self.origin.port}/hit')
            self.assertIn('changed=1', self.archive.curl(request['flow_id']))
        self.assertEqual(self.archive.page()['total'], 2)

    async def test_mounted_backend_controls_real_capture(self):
        from capture_console.breakpoints.supervisor import mount_control
        app = FastAPI()
        store = SimpleNamespace(get_session=lambda _: dict(status='running', outdir=str(self.root/'archive')))
        with patch.dict(os.environ, {'CAPTURE_BREAKPOINTS': '1'}):
            mount_control(app, store, self.root/'backend')
        token = json.loads((self.root/'backend'/'breakpoint-desktop.json').read_text())['token']
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False))
        task = asyncio.create_task(server.serve(sockets=[listener]))
        async def api(method, suffix, value=None):
            def call():
                request = Request(f'http://127.0.0.1:{port}/api/captures/1/breakpoints{suffix}',
                    data=json.dumps(value or {}).encode() if method != 'GET' else None, method=method,
                    headers={'Authorization': 'Bearer '+token, 'X-Device-ID': self.control.device_id,
                             'X-Breakpoint-Epoch': self.control.epoch, 'Content-Type': 'application/json'})
                with build_opener(ProxyHandler({})).open(request, timeout=4) as reply:
                    return json.load(reply)
            return await asyncio.to_thread(call)
        try:
            async with asyncio.timeout(3):
                while not server.started:
                    await asyncio.sleep(.01)
            await api('PUT', '/rules/r', {'expected_revision': 0, 'rule': {
                'scheme': 'https', 'host': '127.0.0.1', 'port': self.origin.port,
                'path': '/hit', 'method': 'POST', 'stage': 'request'}})
            await api('POST', '/enable')
            exchange = await self.begin()
            item = await self.pending('request')
            self.assertEqual((await api('GET', '/pending'))['data'][0]['id'], item['id'])
            await api('POST', f'/pending/{item["id"]}/resolve', {
                'operation_id': item['id']+'.http', 'expected_revision': item['revision'],
                'action': 'apply', 'patch': {'body_text': '{"http_control":true}'}})
            self.assertEqual(await asyncio.wait_for(exchange.task, 5), 'end')
            self.assertEqual(bytes(self.origin.records[-1]['preview']), b'{"http_control":true}')
            self.assertEqual(self.archive.detail(item['flow_id'])['request_text'], '{"http_control":true}')
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, 3)
            listener.close()

    async def test_default_off_and_large_passthrough(self):
        exchange = await self.begin()
        self.assertEqual(await asyncio.wait_for(exchange.task, 5), 'end')
        self.assertEqual((await self.control.call('status'))['in_flight'], 0)
        await self.enable()
        large = b'x' * (512*1024)
        exchange = await self.begin(large, unknown=True)
        self.assertEqual(await asyncio.wait_for(exchange.task, 5), 'end')
        self.assertEqual(self.origin.records[-1]['digest'].hexdigest(), hashlib.sha256(large).hexdigest())
        self.assertEqual((await self.control.call('status'))['reserved_bytes'], 0)

    async def test_stop_resumes_wait_and_removes_control(self):
        self.origin.responses['/hit'] = {'headers_gate': asyncio.Event()}
        await self.enable('request')
        exchange = await self.begin()
        await self.pending('request')
        await self.command('stop')
        await asyncio.sleep(.2)
        self.assertTrue(self.control.path.exists(), 'must wait for actual HTTP completion')
        self.origin.responses['/hit']['headers_gate'].set()
        await self.event('stopped')
        self.assertEqual(await asyncio.wait_for(exchange.task, 5), 'end')
        self.assertFalse(self.control.path.exists())

    async def test_h2_stream_reset_settles_pending_on_live_connection(self):
        await self.enable('request')
        exchange = await self.begin(protocol='h2')
        request = await self.pending('request')
        await exchange.wire.reset(1)
        await asyncio.sleep(.15)
        status = await self.control.call('status')
        self.assertEqual((status['in_flight'], status['reserved_bytes']), (0, 0))
        self.assertFalse(exchange.wire.eof)
        from capture_console.breakpoints.models import Issue
        with self.assertRaises(Issue):
            await self.resolve(request)

    async def test_stop_drains_h2_send_queue_after_flow_done(self):
        self.origin.responses['/hit'] = {'size': 128*1024}
        await self.enable('response')
        exchange = await self.begin(protocol='h2')
        exchange.consume_gate = asyncio.Event()
        item = await self.pending('response')
        await self.resolve(item)
        await asyncio.sleep(.15)
        await self.command('stop')
        await asyncio.sleep(.15)
        self.assertTrue(self.control.path.exists(), 'H2 buffered DATA/END_STREAM must drain')
        exchange.consume_gate.set()
        self.assertEqual(await asyncio.wait_for(exchange.task, 2), 'end')
        await self.event('stopped')
        self.assertEqual(exchange.size, 128*1024)

    async def test_slow_body_cancel(self):
        await self.enable('request')
        exchange = await self.begin(b'x', protocol='h2', finish=False)
        outcome = await asyncio.wait_for(exchange.task, 5)
        self.assertEqual(outcome, 'closed')
        self.assertEqual(len(self.origin.records), 0)
        self.assertEqual((await self.control.call('status'))['reserved_bytes'], 0)

    async def test_compressed_edits_preserve_wire_and_archive(self):
        await self.enable()
        for encoding, encode, decode in [('gzip', gzip.compress, gzip.decompress),
                                         ('deflate', zlib.compress, zlib.decompress)]:
            original = encode(b'{"original":1}')
            self.origin.responses['/hit'] = {'body': original, 'headers': [('content-encoding', encoding)]}
            exchange = await self.begin(original, headers=[('content-encoding', encoding)])
            request = await self.pending('request')
            await self.resolve(request, 'apply', {'body_text': '{"modified":2}'})
            response = await self.pending('response')
            self.assertEqual(decode(bytes(self.origin.records[-1]['preview'])), b'{"modified":2}')
            await self.resolve(response, 'apply', {'body_text': '{"modified":3}'})
            self.assertEqual(await asyncio.wait_for(exchange.task, 5), 'end')
            self.assertEqual(decode(bytes(exchange.preview)), b'{"modified":3}')
            detail = self.archive.detail(request['flow_id'])
            self.assertEqual((detail['request_text'], detail['response_text']), ('{"modified":2}', '{"modified":3}'))
            original_path = self.root/'archive'/detail['breakpoints']['request']['original']['body_file']
            self.assertEqual(original_path.read_bytes(), original)

    async def test_compressed_response_edited_to_204_has_no_wire_body(self):
        self.origin.responses['/hit'] = {'body': gzip.compress(b'{"reply":1}'),
                                       'headers': [('content-encoding', 'gzip')]}
        await self.enable('response')
        exchange = await self.begin()
        item = await self.pending('response')
        await self.resolve(item, 'apply', {'status': 204, 'body_text': ''})
        self.assertEqual(await asyncio.wait_for(exchange.task, 3), 'end')
        self.assertEqual((dict(exchange.headers)[':status'], exchange.size), ('204', 0))
        self.assertEqual(self.archive.detail(item['flow_id'])['response_text'], '')

    async def test_h2_client_to_h1_origin_edit(self):
        self.origin_tls.set_alpn_protocols(['http/1.1'])
        await self.enable()
        exchange = await self.begin(protocol='h2')
        item = await self.pending('request')
        await self.resolve(item, 'apply', {'body_text': '{"mixed":1}'})
        response = await self.pending('response')
        await self.resolve(response, 'apply', {'body_text': '{"mixed":2}'})
        self.assertEqual(await asyncio.wait_for(exchange.task, 3), 'end')
        self.assertEqual(bytes(exchange.preview), b'{"mixed":2}')
        self.assertEqual(bytes(self.origin.records[-1]['preview']), b'{"mixed":1}')

    async def test_request_abort_is_not_forwarded(self):
        await self.enable('request')
        exchange = await self.begin(protocol='h2')
        request = await self.pending('request')
        await self.resolve(request, 'abort')
        self.assertEqual(await asyncio.wait_for(exchange.task, 5), 'closed')
        self.assertEqual(len(self.origin.records), 0)
        self.assertEqual(self.archive.detail(request['flow_id'])['status'], 'ABORTED')
        with self.assertRaises(ValueError):
            self.archive.curl(request['flow_id'])

    async def test_disconnect_releases_pending(self):
        await self.enable('request')
        exchange = await self.begin()
        await self.pending('request')
        await exchange.close()
        for _ in range(100):
            if not (await self.control.call('status'))['in_flight']:
                break
            await asyncio.sleep(.02)
        self.assertEqual((await self.control.call('status'))['in_flight'], 0)

    async def test_stop_while_collecting_closes_stream(self):
        await self.enable('request')
        exchange = await self.begin(b'x', protocol='h2', finish=False)
        await asyncio.sleep(.1)
        await self.command('stop')
        await self.event('stopped')
        self.assertEqual(await asyncio.wait_for(exchange.task, 1), 'closed')

    async def test_brotli_and_expansion_bypass_without_changes(self):
        import brotli
        await self.enable()
        for encoding, original in [('br', brotli.compress(b'{"safe":1}')),
                                   ('gzip', gzip.compress(b'x'*(2*1024*1024)))]:
            self.origin.responses['/hit'] = {'body': original, 'headers': [('content-encoding', encoding)]}
            exchange = await self.begin(original, headers=[('content-encoding', encoding)])
            self.assertEqual(await asyncio.wait_for(exchange.task, 5), 'end')
            self.assertEqual(bytes(exchange.preview), original)
            self.assertEqual(bytes(self.origin.records[-1]['preview']), original)
            self.assertEqual((await self.control.call('status'))['in_flight'], 0)

    async def test_100mib_response_is_bounded_and_archived_as_truncated(self):
        size = 100*1024*1024
        self.origin.responses['/hit'] = {'size': size, 'unknown': True}
        await self.enable('response')
        await self.command('stats')
        before = (await self.event('stats'))['maxrss_bytes']
        expected = hashlib.sha256()
        for _ in range(size//65536):
            expected.update(b'x'*65536)
        for protocol in ('http/1.1', 'h2'):
            self.origin.responses['/hit']['headers'] = [('transfer-encoding', 'chunked')] if protocol == 'http/1.1' else []
            exchange = await self.begin(protocol=protocol)
            self.assertEqual(await asyncio.wait_for(exchange.task, 30), 'end')
            self.assertEqual((exchange.size, exchange.digest.hexdigest()), (size, expected.hexdigest()))
        await self.command('stats')
        after = await self.event('stats')
        self.assertLess(after['maxrss_bytes'] - before, 64*1024*1024, after)
        self.assertEqual(after['reserved_bytes'], 0)
        for summary in self.archive.page()['flows']:
            detail = self.archive.detail(summary['flow_id'])
            self.assertTrue(detail['meta_json']['summary']['response_truncated'])
        print(f'BP2 {self.mode} 100MiB H1/H2 RSS delta={after["maxrss_bytes"] - before}', flush=True)


class SocksTests(ProductionTests):
    mode = 'socks'


class IOSAdapterTests(ProductionTests):
    mode = 'ios'

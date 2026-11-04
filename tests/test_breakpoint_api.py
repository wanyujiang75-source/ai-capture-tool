import asyncio
import json
from pathlib import Path
import socket
import tempfile
import unittest

import uvicorn

from capture_console.breakpoints.api import create_control_app
from capture_console.breakpoints.engine import BreakpointEngine
from capture_console.breakpoints.ipc import WorkerClient, WorkerServer
from capture_console.breakpoints.models import RuleInput
from tests.test_breakpoint_engine import request


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bp1-api-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.engine = BreakpointEngine('c', 'd')
        self.worker = WorkerServer(Path(self.tmp.name) / 'w', self.engine)
        await self.worker.start()
        self.addAsyncCleanup(self.worker.close)
        self.client = WorkerClient(self.worker.path, self.worker.token, 'c', 'd', self.engine.epoch)
        self.token = 'a' * 40
        self.app = create_control_app({'c': self.client}, self.token)
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.port = self.listener.getsockname()[1]
        self.http = uvicorn.Server(uvicorn.Config(self.app, host='127.0.0.1', log_level='error', access_log=False))
        self.task = asyncio.create_task(self.http.serve(sockets=[self.listener]))
        async def cleanup():
            self.http.should_exit = True
            await asyncio.wait_for(self.task, 3)
            self.listener.close()
        self.addAsyncCleanup(cleanup)
        async with asyncio.timeout(3):
            while not self.http.started:
                await asyncio.sleep(0.01)

    async def call(self, method='GET', path='', body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else b''
        fields = {'Host': f'127.0.0.1:{self.port}', 'Authorization': f'Bearer {self.token}',
                  'X-Device-ID': 'd', 'X-Breakpoint-Epoch': self.engine.epoch,
                  'Content-Type': 'application/json', 'Connection': 'close'}
        fields.update(headers or {})
        reader, writer = await asyncio.open_connection('127.0.0.1', self.port)
        try:
            wire = f'{method} /api/captures/c/breakpoints{path} HTTP/1.1\r\n'
            wire += ''.join(f'{key}: {value}\r\n' for key, value in fields.items())
            writer.write((wire + f'Content-Length: {len(data)}\r\n\r\n').encode()
                         + (data if len(data) <= 1024 * 1024 else b''))
            await writer.drain()
            head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 4)
            length = next(int(line.split(b':', 1)[1]) for line in head.split(b'\r\n')
                          if line.lower().startswith(b'content-length:'))
            content = await asyncio.wait_for(reader.readexactly(length), 4)
            return int(head.split()[1]), json.loads(content)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    async def test_full_api_to_worker_decision_and_idempotency(self):
        rule = dict(scheme='https', host='example.test', path='/hit', method='POST')
        self.assertEqual((await self.call('PUT', '/rules/r', {'expected_revision': 0, 'rule': rule}))[0], 200)
        self.assertEqual((await self.call('POST', '/enable'))[0], 200)
        message = request(body=b'')
        pending = self.engine.admit('f', message).pending_id
        self.engine.pause('f', message)
        listing = (await self.call(path='/pending'))[1]
        self.assertEqual(listing['data'][0]['id'], pending)
        self.assertNotIn('secret=hidden', json.dumps(listing))
        self.assertEqual((await self.call(path=f'/pending/{pending}'))[1]['original']['url'], message.url)
        payload = {'operation_id': f'{pending}.op', 'expected_revision': 1, 'action': 'apply',
                   'patch': {'url': 'https://example.test/hit?edited=1'}}
        first = await self.call('POST', f'/pending/{pending}/resolve', payload)
        self.assertEqual(first[0], 200)
        self.assertEqual(await self.call('POST', f'/pending/{pending}/resolve', payload), first)
        self.assertEqual((await self.engine.wait(pending)).effective.url, 'https://example.test/hit?edited=1')
        self.engine.ack(pending)
        self.assertEqual((await self.call())[1]['in_flight'], 0)

    async def test_desktop_context_is_authenticated_and_never_contains_worker_secret(self):
        code, context = await self.call(path='/context', headers={'X-Device-ID': '', 'X-Breakpoint-Epoch': ''})
        self.assertEqual(code, 200)
        self.assertEqual(context, {'capture_id': 'c', 'device_id': 'd', 'epoch': self.engine.epoch})
        self.assertNotIn(self.worker.token, json.dumps(context))
        for headers, expected in [({'Authorization': ''}, 401), ({'Origin': 'https://evil.test'}, 403),
                                  ({'Host': 'evil.test'}, 403)]:
            self.assertEqual((await self.call(path='/context', headers=headers))[0], expected)

    async def test_chunked_input_limit_cannot_be_bypassed_without_content_length(self):
        reader, writer = await asyncio.open_connection('127.0.0.1', self.port)
        try:
            writer.write((f'POST /api/captures/c/breakpoints/enable HTTP/1.1\r\nHost: localhost\r\n'
                          f'Authorization: Bearer {self.token}\r\nX-Device-ID: d\r\n'
                          f'X-Breakpoint-Epoch: {self.engine.epoch}\r\n'
                          'Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n').encode())
            for _ in range(65):
                writer.write(b'4000\r\n' + b'x' * 16384 + b'\r\n')
                await writer.drain()
            head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 4)
            self.assertEqual(int(head.split()[1]), 413)
            self.assertFalse(self.engine.enabled)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    async def test_slow_http_body_capacity_and_timeout_release(self):
        connections = []
        try:
            for _ in range(8):
                reader, writer = await asyncio.open_connection('127.0.0.1', self.port)
                connections.append((reader, writer))
                writer.write((f'POST /api/captures/c/breakpoints/enable HTTP/1.1\r\nHost: localhost\r\n'
                              f'Authorization: Bearer {self.token}\r\nX-Device-ID: d\r\n'
                              f'X-Breakpoint-Epoch: {self.engine.epoch}\r\n'
                              'Content-Length: 10\r\nConnection: close\r\n\r\n{').encode())
                await writer.drain()
            await asyncio.sleep(0.05)
            self.assertEqual((await self.call())[0], 429)
            for reader, _ in connections:
                head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 3.5)
                self.assertEqual(int(head.split()[1]), 503)
            self.assertEqual((await self.call())[0], 200)
            self.assertFalse(self.engine.enabled)
        finally:
            for _, writer in connections:
                writer.close()
                await writer.wait_closed()

    async def test_non_loopback_and_duplicate_auth_are_rejected(self):
        headers = [('Authorization', f'Bearer {self.token}'), ('X-Device-ID', 'd'),
                   ('X-Breakpoint-Epoch', self.engine.epoch)]
        for peer, extra, expected in [('192.0.2.10', [], 403),
                                      ('127.0.0.1', [('Authorization', f'Bearer {self.token}')], 401)]:
            responses = []
            async def receive():
                return {'type': 'http.request', 'body': b''}
            async def send(event):
                responses.append(event)
            scope = dict(type='http', asgi={'version': '3.0'}, http_version='1.1', method='GET',
                         scheme='http', path='/api/captures/c/breakpoints', query_string=b'',
                         client=(peer, 32123), server=('127.0.0.1', self.port),
                         headers=[(key.lower().encode(), value.encode())
                                  for key, value in headers + extra + [('host', 'localhost')]])
            await self.app(scope, receive, send)
            self.assertEqual(responses[0]['status'], expected)

    async def test_all_routes_require_auth_origin_and_target(self):
        for change, status in [({'Authorization': ''}, 401), ({'Origin': 'https://evil.test'}, 403),
                               ({'Host': 'evil.test'}, 403), ({'X-Device-ID': 'wrong'}, 409),
                               ({'X-Breakpoint-Epoch': 'old'}, 409)]:
            for method, path in [('GET', ''), ('GET', '/pending'), ('GET', '/pending/id'),
                                 ('POST', '/enable'), ('POST', '/disable'), ('POST', '/heartbeat'),
                                 ('POST', '/release-all'), ('POST', '/pending/id/resolve'), ('PUT', '/rules/r')]:
                with self.subTest(change=change, path=path):
                    response = await self.call(method, path, headers=change)
                    self.assertEqual(response[0], status)
        self.assertFalse(self.engine.enabled)

    async def test_invalid_payload_limit_and_worker_unavailable(self):
        for body in [{'operation_id': 'op', 'action': 'apply', 'expected_revision': True},
                     {'secret': 'credential-value'}, {'junk': 'x' * (1024 * 1024)}]:
            status, error = await self.call('POST', '/pending/id/resolve', body)
            self.assertIn(status, {413, 422})
            self.assertNotIn('credential-value', json.dumps(error))
        await self.worker.close()
        self.assertEqual((await self.call())[0], 503)

    async def test_page_and_patch_errors_do_not_release_pending(self):
        self.engine.put_rule('r', 0, RuleInput(scheme='https', host='example.test', path='/hit', method='POST'))
        self.engine.enable()
        pending = self.engine.admit('f', request(body=b'')).pending_id
        self.engine.pause('f', request(body=b''))
        self.assertEqual((await self.call(path='/pending?limit=51'))[0], 422)
        status, _ = await self.call('POST', f'/pending/{pending}/resolve',
                                    {'operation_id': f'{pending}.op', 'expected_revision': 1, 'action': 'apply',
                                     'patch': {'url': 'https://other.test/'}})
        self.assertEqual(status, 422)
        self.assertEqual(self.engine.detail(pending)['state'], 'paused')
        await self.call('POST', '/disable')
        self.assertEqual((await self.engine.wait(pending)).action, 'original')
        self.engine.ack(pending)

    async def test_form_validation_is_atomic_and_keeps_duplicate_fields(self):
        self.engine.put_rule('r', 0, RuleInput(scheme='https', host='example.test', path='/hit', method='POST'))
        self.engine.enable()
        message = request(body=b'', headers=(('content-type', 'application/x-www-form-urlencoded'),))
        pending = self.engine.admit('f', message).pending_id
        self.engine.pause('f', message)
        before = (self.engine.reserved_bytes, self.engine.detail(pending))
        for body in ('x=%FF', 'x=%ZZ', 'x=%', 'x=%0'):
            result = await self.call('POST', f'/pending/{pending}/resolve',
                                     {'operation_id': f'{pending}.form', 'expected_revision': 1, 'action': 'apply',
                                      'patch': {'body_text': body}})
            self.assertEqual(result[0], 422)
            self.assertEqual((self.engine.reserved_bytes, self.engine.detail(pending)), before)
        body = 'x=%E4%B8%AD&x=two+words&empty='
        self.assertEqual((await self.call('POST', f'/pending/{pending}/resolve',
                                          {'operation_id': f'{pending}.form', 'expected_revision': 1, 'action': 'apply',
                                           'patch': {'body_text': body}}))[0], 200)
        self.assertEqual((await self.engine.wait(pending)).effective.body, body.encode())
        self.engine.ack(pending)

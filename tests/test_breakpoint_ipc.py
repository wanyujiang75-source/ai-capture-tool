import asyncio
import json
from pathlib import Path
import tempfile
import socket
import sys
import unittest
from unittest.mock import patch, Mock

from capture_console.breakpoints.engine import BreakpointEngine
from capture_console.breakpoints.ipc import WorkerServer, WorkerClient, read_frame, write_frame
from capture_console.breakpoints.models import Issue, FRAME_LIMIT, RuleInput
from tests.test_breakpoint_engine import request


class IpcTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_cleanup_is_scheduled_even_when_reply_fails(self):
        callback = self.server.on_stop = Mock()
        async def broken_reply(writer, payload):
            if 'data' in payload:
                raise ConnectionResetError()
            await write_frame(writer, payload)
        with patch('capture_console.breakpoints.ipc.write_frame', side_effect=broken_reply):
            with self.assertRaises(Issue):
                await self.client.call('stop')
            await asyncio.sleep(.02)
        self.assertTrue(self.engine.stopped)
        callback.assert_called_once_with()

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bp1-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.engine = BreakpointEngine('c', 'd')
        self.server = WorkerServer(Path(self.tmp.name) / 'w', self.engine)
        await self.server.start()
        self.addAsyncCleanup(self.server.close)
        self.client = WorkerClient(self.server.path, self.server.token, 'c', 'd', self.engine.epoch)

    async def raw(self, envelope):
        reader, writer = await asyncio.open_unix_connection(self.server.path)
        try:
            await write_frame(writer, envelope)
            return await read_frame(reader)
        finally:
            writer.close()
            await writer.wait_closed()

    def envelope(self, **changes):
        body = dict(version=1, token=self.server.token, epoch=self.engine.epoch,
                    capture_id='c', device_id='d', command='status', payload={})
        body.update(changes)
        return body

    async def test_roundtrip_permissions_and_owned_cleanup(self):
        self.assertEqual(self.server.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.server.path.parent.stat().st_mode & 0o777, 0o700)
        self.assertFalse((await self.client.call('status'))['enabled'])
        self.assertTrue((await self.client.call('enable'))['enabled'])
        await self.server.close()
        self.assertFalse(self.server.path.exists())
        with self.assertRaises(Issue):
            await self.client.call('status')

    async def test_rejects_auth_target_epoch_version_and_arbitrary_command(self):
        for change, code in [({'token': 'wrong'}, 'unauthorized'), ({'epoch': 'old'}, 'target_conflict'),
                             ({'device_id': 'other'}, 'target_conflict'), ({'capture_id': 'other'}, 'target_conflict'),
                             ({'version': 2}, 'invalid_command'), ({'command': '__dict__'}, 'invalid_command'),
                             ({'payload': {'file': '/etc/passwd'}}, 'invalid_command')]:
            with self.subTest(change=change):
                result = await self.raw(self.envelope(**change))
                self.assertEqual(result['error']['code'], code)
                self.assertNotIn(self.server.token, json.dumps(result))
        self.assertFalse(self.engine.enabled)

    async def test_oversize_and_partial_frames_are_bounded(self):
        reader, writer = await asyncio.open_unix_connection(self.server.path)
        writer.write((FRAME_LIMIT + 1).to_bytes(4, 'big'))
        await writer.drain()
        result = await read_frame(reader)
        self.assertEqual(result['error']['code'], 'frame_too_large')
        writer.close()
        await writer.wait_closed()
        self.assertFalse((await self.client.call('status'))['enabled'])

    async def test_lease_expires_without_api_polling(self):
        await self.client.call('enable')
        self.engine.lease = self.engine.clock() + 0.08
        await asyncio.sleep(0.2)
        self.assertFalse(self.engine.enabled)

    async def test_existing_directory_is_never_reused_or_removed(self):
        other = WorkerServer(self.server.path.parent, BreakpointEngine('x', 'y'))
        with self.assertRaises(Issue):
            await other.start()
        self.assertTrue(self.server.path.exists())

    async def test_rule_validation_is_sanitized(self):
        secret = 'private-secret-not-an-int'
        result = await self.raw(self.envelope(command='rule', payload={'id': 'r', 'expected_revision': secret, 'rule': {}}))
        self.assertEqual(result['error']['code'], 'invalid_command')
        self.assertNotIn(secret, json.dumps(result))

    async def test_slow_clients_are_capped_and_expire(self):
        connections = []
        try:
            for _ in range(8):
                reader, writer = await asyncio.open_unix_connection(self.server.path)
                connections.append((reader, writer))
                writer.write(b'\x00')
                await writer.drain()
            await asyncio.sleep(0.05)
            self.assertEqual(len(self.server.tasks), 8)
            reader, writer = await asyncio.open_unix_connection(self.server.path)
            connections.append((reader, writer))
            self.assertEqual(await asyncio.wait_for(reader.read(), 1), b'')
            self.assertEqual(await asyncio.wait_for(connections[0][0].read(), 3.5), b'')
            await asyncio.sleep(0.05)
            self.assertFalse((await self.client.call('status'))['enabled'])
        finally:
            for _, writer in connections:
                writer.close()
                await writer.wait_closed()

    async def test_restart_rejects_old_identity_and_does_not_restore_rules(self):
        await self.client.call('enable')
        old = self.envelope()
        await self.server.close()
        fresh = WorkerServer(self.server.root, BreakpointEngine('c', 'd'))
        self.addAsyncCleanup(fresh.close)
        await fresh.start()
        self.assertNotEqual(fresh.engine.epoch, self.engine.epoch)
        self.assertEqual((await self.raw(old))['error']['code'], 'unauthorized')
        old['token'] = fresh.token
        self.assertEqual((await self.raw(old))['error']['code'], 'target_conflict')
        self.assertFalse(fresh.engine.enabled)

    async def test_start_failure_removes_only_newly_owned_directory(self):
        worker = WorkerServer(Path(self.tmp.name) / 'failed', BreakpointEngine('c', 'd'))
        with patch('capture_console.breakpoints.ipc.asyncio.start_unix_server', side_effect=OSError('fixture')):
            with self.assertRaises(OSError):
                await worker.start()
        self.assertFalse(worker.root.exists())

    async def test_replaced_socket_is_never_unlinked_on_close(self):
        self.server.path.rename(self.server.path.with_suffix('.saved'))
        self.server.path.touch()
        await self.server.close()
        self.assertTrue(self.server.path.is_file())

    async def test_nonreading_detail_client_cannot_block_shutdown(self):
        self.engine.put_rule('r', 0, RuleInput(scheme='https', host='example.test', path='/hit', method='POST'))
        self.engine.enable()
        message = request(body=b'x' * 262144)
        pending = self.engine.admit('f', request(body=b'')).pending_id
        self.engine.reserve('f', len(message.body), len(message.body))
        self.engine.pause('f', message)
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        client.setblocking(False)
        try:
            loop = asyncio.get_running_loop()
            await loop.sock_connect(client, str(self.server.path))
            data = json.dumps(self.envelope(command='detail', payload={'id': pending})).encode()
            await loop.sock_sendall(client, len(data).to_bytes(4, 'big') + data)
            await asyncio.sleep(0.1)
            await asyncio.wait_for(self.server.close(), 5)
            self.assertEqual((len(self.engine.flows), self.engine.reserved_bytes, len(self.server.tasks)), (0, 0, 0))
            self.assertFalse(self.server.path.exists())
        finally:
            client.close()

    async def test_real_worker_process_and_owned_exit(self):
        root = Path(self.tmp.name) / 'process'
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'tests.fixtures.breakpoints.control', str(root),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            metadata = json.loads(await asyncio.wait_for(process.stdout.readline(), 3))
            client = WorkerClient(Path(metadata['path']), metadata['token'], 'fixture', 'fixture-device', metadata['epoch'])
            self.assertFalse((await client.call('status'))['enabled'])
            self.assertTrue((await client.call('enable'))['enabled'])
            self.assertFalse((await self.client.call('status'))['enabled'])
            await client.call('stop')
            await asyncio.wait_for(process.wait(), 4)
            self.assertEqual(process.returncode, 0)
            self.assertEqual(await process.stderr.read(), b'')
            self.assertFalse(root.exists())
        finally:
            if process.returncode is None:
                process.terminate()
                await asyncio.wait_for(process.wait(), 3)

    async def test_large_rule_set_remains_readable_through_frame_limit(self):
        rejected = False
        for i in range(100):
            try:
                await self.client.call('rule', {'id': f'r{i}', 'expected_revision': 0,
                                               'rule': {'scheme': 'https', 'host': 'example.test',
                                                        'path': '/' + '"' * 8000}})
            except Issue as issue:
                self.assertEqual(issue.code, 'rule_budget_exceeded')
                rejected = True
                break
        self.assertGreater(len((await self.client.call('status'))['rules']), 0)
        self.assertTrue(rejected)

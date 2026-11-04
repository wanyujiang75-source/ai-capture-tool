"""Strict safety acceptance for the opt-in, version-bound BP-0 adapter."""

import asyncio
import hashlib
import time
import unittest
from types import SimpleNamespace

import h2.config
import h2.connection
import h2.events
from mitmproxy import connection, http, options
from mitmproxy.proxy import commands, events
from mitmproxy.proxy.context import Context
from mitmproxy.proxy.layers.http import HTTPMode, HttpStream

from tests import test_breakpoint_transport as transport
from tests.fixtures.breakpoints.wire import Exchange, Wire
from tests.fixtures.breakpoints.guard import check_version, GuardLayer, WindowedH2


class WireContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_coalesced_data_goaway_preserves_terminal_evidence(self):
        reader = asyncio.StreamReader()
        writer = SimpleNamespace(write=lambda data: None, drain=lambda: asyncio.sleep(0),
                                 get_extra_info=lambda key: SimpleNamespace(selected_alpn_protocol=lambda: 'h2'))
        wire = Wire(reader, writer, client=False)
        sender = h2.connection.H2Connection()
        sender.initiate_connection()
        sender.send_headers(1, [(':method', 'POST'), (':scheme', 'https'),
                                (':authority', 'localhost'), (':path', '/')])
        sender.send_data(1, b'partial')
        sender.close_connection()
        reader.feed_data(sender.data_to_send())
        reader.feed_eof()
        await asyncio.wait_for(wire.task, 1)
        self.assertEqual((wire.goaway, wire.eof, wire.failure), (True, True, None))


class GuardContractTests(unittest.TestCase):
    def test_collection_tick_waits_for_queued_response_headers(self):
        for admitted in [False, True]:
            with self.subTest(admitted=admitted):
                context = Context(connection.Client(peername=('127.0.0.1', 1),
                                                    sockname=('127.0.0.1', 2)), options.Options())
                flow = http.HTTPFlow(context.client, context.server)
                flow.request = http.Request.make('POST', 'https://127.0.0.1/hit')
                probe = SimpleNamespace(active={flow.id: {'collect_timeout': 10}} if admitted else {},
                                        matched=lambda flow: True)
                guard = GuardLayer(context, HTTPMode.regular, probe, lambda *args, **kwargs: None)
                stream = HttpStream(context.fork(), 1)
                stream.flow = flow
                guard.streams[1] = stream
                now = time.monotonic()
                guard.collecting[1] = ['response', now, now]
                guard.tick = commands.RequestWakeup(0.05)
                emitted = list(guard._handle_event(events.Wakeup(guard.tick)))
                self.assertEqual(emitted, [guard.tick])
                self.assertIsNone(flow.response)
                self.assertIn(1, guard.collecting)
                flow.response = http.Response.make(200)
                flow.response.stream = True
                self.assertEqual(list(guard._handle_event(events.Wakeup(guard.tick))), [])
                self.assertEqual(guard.collecting, {})

    def test_fragmented_send_buffer_preserves_bytes_and_end(self):
        sender = WindowedH2(h2.config.H2Configuration(client_side=True), lambda stream_id: False)
        receiver = h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=False))
        receiver.local_settings.initial_window_size = 0
        receiver.local_settings.acknowledge()
        receiver.initiate_connection()
        sender.initiate_connection()
        sender.receive_data(receiver.data_to_send())
        receiver.receive_data(sender.data_to_send())
        sender.send_headers(1, [(':method', 'POST'), (':scheme', 'https'),
                                (':authority', 'localhost'), (':path', '/')])
        receiver.receive_data(sender.data_to_send())
        for _ in range(2000):
            sender.send_data(1, b'')
            sender.send_data(1, b'x')
        sender.end_stream(1)
        self.assertLessEqual(len(sender.stream_buffers[1]), 2)
        receiver.increment_flow_control_window(2000, 1)
        sender.receive_data(receiver.data_to_send())
        received = receiver.receive_data(sender.data_to_send())
        self.assertEqual(b''.join(event.data for event in received if isinstance(event, h2.events.DataReceived)),
                         b'x' * 2000)
        self.assertTrue(any(isinstance(event, h2.events.StreamEnded) for event in received))

    def test_coalesced_data_goaway_does_not_ack_closed_connection(self):
        receiver = WindowedH2(h2.config.H2Configuration(client_side=False), lambda stream_id: True)
        sender = h2.connection.H2Connection()
        sender.initiate_connection()
        receiver.initiate_connection()
        receiver.receive_data(sender.data_to_send())
        sender.receive_data(receiver.data_to_send())
        sender.send_headers(1, [(':method', 'POST'), (':scheme', 'https'),
                                (':authority', 'localhost'), (':path', '/')])
        sender.send_data(1, b'partial')
        sender.close_connection()
        received = receiver.receive_data(sender.data_to_send())
        self.assertTrue(any(isinstance(event, h2.events.ConnectionTerminated) for event in received))
        for event in received:
            if isinstance(event, h2.events.DataReceived):
                receiver.acknowledge_received_data(event.flow_controlled_length, event.stream_id)
        self.assertEqual(dict(receiver.credits), {})

    def test_remote_reset_reclaims_deferred_credits(self):
        receiver = WindowedH2(h2.config.H2Configuration(client_side=False), lambda stream_id: True)
        sender = h2.connection.H2Connection()
        sender.initiate_connection()
        receiver.initiate_connection()
        receiver.receive_data(sender.data_to_send())
        sender.receive_data(receiver.data_to_send())
        for stream_id in range(1, 202, 2):
            sender.send_headers(stream_id, [(':method', 'POST'), (':scheme', 'https'),
                                            (':authority', 'localhost'), (':path', '/')])
            sender.send_data(stream_id, b'partial')
            coalesced = stream_id % 4 == 3
            if coalesced:
                sender.reset_stream(stream_id)
            for event in receiver.receive_data(sender.data_to_send()):
                if isinstance(event, h2.events.DataReceived):
                    receiver.acknowledge_received_data(event.flow_controlled_length, event.stream_id)
            self.assertEqual(dict(receiver.credits), {} if coalesced else {stream_id: 7})
            if stream_id != 201:
                if not coalesced:
                    receiver.stream_trailers[stream_id] = []
                    sender.reset_stream(stream_id)
                    receiver.receive_data(sender.data_to_send())
                self.assertEqual((dict(receiver.credits), receiver.stream_trailers), ({}, {}))
            sender.receive_data(receiver.data_to_send())
        receiver.stream_trailers[201] = []
        sender.close_connection()
        receiver.receive_data(sender.data_to_send())
        self.assertEqual((dict(receiver.credits), receiver.stream_trailers), ({}, {}))


class GuardTransportTests(transport.BreakpointTransportTests):
    guarded = True

    async def h1_waiting_for_upstream_tls(self, *, shutdown=False, disconnect=False):
        await self.configure(enabled=False, transport_wait_timeout=1 if disconnect else 10)
        release = asyncio.Event()
        peers = []
        target_port = self.origin.port
        async def relay(reader, writer):
            while data := await reader.read(65536):
                writer.write(data)
                await writer.drain()
        async def delayed(reader, writer):
            await release.wait()
            remote_reader, remote_writer = await asyncio.open_connection('127.0.0.1', target_port)
            peers.append(remote_writer)
            await asyncio.gather(relay(reader, remote_writer), relay(remote_reader, writer))
        def accept(reader, writer):
            peers.append(writer)
            self.background.append(asyncio.create_task(delayed(reader, writer)))
        server = await asyncio.start_server(accept, '127.0.0.1', 0)
        async def cleanup():
            server.close()
            for writer in peers:
                writer.close()
            await asyncio.wait_for(server.wait_closed(), 2)
        self.addAsyncCleanup(cleanup)
        self.origin.port = server.sockets[0].getsockname()[1]
        baseline = (await self.stats())['maxrss_bytes']
        size = 100 * 1024 * 1024
        exchange = await self.begin('/unmatched', finish=False, declared_length=size)
        async def upload():
            for _ in range(size // 16384):
                await exchange.wire.data(b'x' * 16384)
            await exchange.wire.end()
        sending = asyncio.create_task(upload())
        self.background.append(sending)
        await asyncio.sleep(0.5)
        stats = await self.stats()
        self.assertLess(stats['queued_events'], 128, 'H1 queued the upload while upstream TLS was stalled')
        self.assertFalse(sending.done(), 'H1 producer must be backpressured before sending the entire upload')
        if disconnect:
            exchange.wire.writer.transport.abort()
            await self.event('transport_wait_expired', timeout=3)
            async with asyncio.timeout(2):
                while (await self.stats())['connections']:
                    await asyncio.sleep(0.05)
            self.assertIsNone(self.process.returncode)
            self.assertFalse(release.is_set(), 'TLS must remain stalled throughout cancellation')
            return
        if shutdown:
            await self.command(action='shutdown')
            await asyncio.wait_for(self.process.wait(), 3)
            self.assertEqual(self.process.returncode, 0)
            return
        release.set()
        await self.done(exchange)
        await sending
        expected = hashlib.sha256()
        for _ in range(size // 16384):
            expected.update(b'x' * 16384)
        self.assertEqual((self.origin.records[-1]['size'], self.origin.records[-1]['digest'].hexdigest()),
                         (size, expected.hexdigest()))
        delta = (await self.stats())['maxrss_bytes'] - baseline
        self.assertLess(delta, 64 * 1024 * 1024)
        self.evidence(stalled_tls=True, extra_peak_rss_bytes=delta, streamed_bytes=size)

    async def test_h1_upload_waiting_for_upstream_tls_is_bounded(self):
        await self.h1_waiting_for_upstream_tls()

    async def test_shutdown_reclaims_h1_reader_waiting_for_upstream_tls(self):
        await self.h1_waiting_for_upstream_tls(shutdown=True)

    async def test_disconnected_h1_reader_has_bounded_wait_for_upstream_tls(self):
        await self.h1_waiting_for_upstream_tls(disconnect=True)

    async def test_empty_and_fragmented_data_do_not_grow_paused_queue(self):
        await self.configure(mode='headers', stage='request')
        exchange = await self.begin(protocol='h2', declared_length=2000, finish=False)
        paused = await self.event('paused', stage='request')
        for _ in range(2000):
            exchange.wire.codec.send_data(1, b'')
            exchange.wire.codec.send_data(1, b'x')
        exchange.wire.codec.end_stream(1)
        exchange.wire.writer.write(exchange.wire.codec.data_to_send())
        await exchange.wire.writer.drain()
        await asyncio.sleep(0.2)
        self.assertLessEqual((await self.stats())['queued_events'], 3)
        await self.resolve(paused)
        await self.done(exchange)
        self.assertEqual(bytes(self.origin.records[-1]['preview']), b'x' * 2000)

    async def slow_collection(self, protocol, *, response=False, trickle=False):
        await self.configure(stage='response' if response else 'request',
                             collect_timeout=0.4, collect_idle=0.2)
        if response:
            self.origin.responses['/hit'] = {'body': b'x', 'unknown': True, 'hang': True}
        started = time.monotonic()
        exchange = await self.begin(protocol=protocol, body=b'' if response else b'x',
                                    unknown=not trickle, declared_length=4096 if trickle else None,
                                    finish=response)
        if trickle:
            async def send():
                while not exchange.ended.is_set():
                    await asyncio.sleep(0.05)
                    try:
                        await exchange.wire.data(b'x')
                    except (ConnectionError, RuntimeError):
                        return
            self.background.append(asyncio.create_task(send()))
        self.assertEqual(await asyncio.wait_for(exchange.task, 2), 'closed')
        self.assertLess(time.monotonic() - started, 1.5)
        event = await self.event('collection_expired')
        self.assertEqual(event['reason'], 'total' if trickle else 'idle')
        self.assertEqual((await self.stats())['active'], 0)
        self.assertFalse(exchange.headers_seen.is_set())
        if not response:
            self.assertFalse(self.origin.records)
        self.evidence(protocol=protocol, cancelled=True, reason=event['reason'])

    async def test_slow_collection_kill_does_not_close_transport_negative_control(self):
        for protocol in ['http/1.1', 'h2']:
            await self.slow_collection(protocol)

    async def test_declared_length_trickle_does_not_enforce_collection_deadline(self):
        for protocol in ['http/1.1', 'h2']:
            await self.slow_collection(protocol, trickle=True)

    async def test_slow_response_collection_has_same_timeout_limitation(self):
        for protocol in ['http/1.1', 'h2']:
            await self.slow_collection(protocol, response=True)

    async def header_memory(self, protocol, stage):
        size = 100 * 1024 * 1024
        await self.configure(mode='headers', stage=stage)
        baseline = (await self.stats())['maxrss_bytes']
        if stage == 'request':
            exchange = await self.begin(protocol=protocol, finish=False, declared_length=size)
            async def upload():
                for _ in range(size // 16384):
                    await exchange.wire.data(b'x' * 16384)
                await exchange.wire.end()
            self.background.append(asyncio.create_task(upload()))
        else:
            self.origin.responses['/hit'] = {'size': size}
            exchange = await self.begin(protocol=protocol)
        await self.event('header_bypass', stage=stage)
        await self.done(exchange)
        expected = hashlib.sha256(b'x' * 16384)
        for _ in range(size // 16384 - 1):
            expected.update(b'x' * 16384)
        actual = self.origin.records[-1] if stage == 'request' else exchange
        count = actual['size'] if stage == 'request' else actual.size
        digest = actual['digest'] if stage == 'request' else actual.digest
        self.assertEqual((count, digest.hexdigest()), (size, expected.hexdigest()))
        stats = await self.stats()
        delta = stats['maxrss_bytes'] - baseline
        self.evidence(protocol=protocol, stage=stage, extra_peak_rss_bytes=delta,
                      streamed_bytes=size, auto_bypass=True)
        self.assertEqual((stats['active'], stats['pending']), (0, 0))
        self.assertLess(delta, 64 * 1024 * 1024)

    async def test_unknown_length_header_mode_bypasses_without_pause(self):
        for protocol in ['http/1.1', 'h2']:
            await self.configure(mode='headers', stage='both')
            self.origin.responses['/hit'] = {'body': b'unknown-response', 'unknown': True}
            exchange = await self.begin(body=b'unknown-request', unknown=True, protocol=protocol)
            for stage in ['request', 'response']:
                self.assertEqual((await self.event('header_bypass', stage=stage))['reason'],
                                 'large_or_unknown_body')
            await self.done(exchange)
            self.assertEqual(bytes(exchange.preview), b'unknown-response')
            self.assertEqual(bytes(self.origin.records[-1]['preview']), b'unknown-request')
            self.assertEqual((await self.stats())['pending'], 0)
            self.assertFalse(any(item['kind'] == 'paused' for item in self.backlog))

    async def streamed_memory(self, protocol, *, enabled):
        # Existing test retains the wire hash and strict RSS assertion.
        await super().streamed_memory(protocol, enabled=enabled)

    def safety_gate(self, passed, reason):
        self.assertTrue(passed, reason)

    async def test_wrong_dependency_version_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'requires verified'):
            check_version('12.3.0')

    async def test_small_header_pause_edits_and_forwards_original_body(self):
        await self.configure(mode='headers', stage='both')
        for protocol in ['http/1.1', 'h2']:
            count = len(self.origin.records)
            exchange = await self.begin(body=b'original', protocol=protocol)
            request = await self.event('paused', stage='request')
            self.assertEqual(len(self.origin.records), count)
            await self.resolve(request, path='/hit?modified=1', headers=[['x-added', 'yes']])
            response = await self.event('paused', stage='response')
            self.assertFalse(exchange.headers_seen.is_set())
            await self.resolve(response, status=201)
            await self.done(exchange)
            record = self.origin.records[-1]
            self.assertEqual(bytes(record['preview']), b'original')
            self.assertEqual(dict(record['headers'])['x-added'], 'yes')
            self.assertEqual(dict(record['headers'])[':path'], '/hit?modified=1')
            self.assertEqual(dict(exchange.headers)[':status'], '201')

    async def test_parallel_h2_slow_consumers_remain_bounded(self):
        await self.configure(enabled=False)
        size = 8 * 1024 * 1024
        self.origin.responses['/unmatched'] = {'size': size, 'unknown': True}
        baseline = (await self.stats())['maxrss_bytes']
        held = []
        for _ in range(20):
            exchange = await self.begin('/unmatched', protocol='h2')
            exchange.consume_gate = asyncio.Event()
            held.append(exchange)
        await asyncio.sleep(0.2)
        self.assertTrue(all(not item.ended.is_set() for item in held))
        for item in held:
            item.consume_gate.set()
        await asyncio.gather(*(self.done(item) for item in held))
        expected = hashlib.sha256()
        for _ in range(size // 16384):
            expected.update(b'x' * 16384)
        self.assertEqual([(item.size, item.digest.hexdigest()) for item in held],
                         [(size, expected.hexdigest())] * 20)
        delta = (await self.stats())['maxrss_bytes'] - baseline
        self.evidence(concurrent=20, extra_peak_rss_bytes=delta, total_streamed_bytes=size * 20)
        self.assertLess(delta, 64 * 1024 * 1024)

    async def test_h2_timeout_preserves_sibling_stream_on_same_connection(self):
        await self.configure(stage='request', collect_timeout=0.4, collect_idle=0.2)
        stuck = await self.begin(protocol='h2', body=b'x', unknown=True, finish=False)
        sibling = Exchange(stuck.wire, stream_id=3)
        self.clients.append(sibling)
        size = 512 * 1024
        self.origin.responses['/unmatched'] = {'size': size, 'delay': 0.02}
        await stuck.wire.headers([(':method', 'GET'), (':scheme', 'https'),
                                  (':authority', f'127.0.0.1:{self.origin.port}'),
                                  (':path', '/unmatched')], stream_id=3)
        await stuck.wire.end(stream_id=3)
        self.assertEqual(await asyncio.wait_for(stuck.task, 2), 'closed')
        self.assertFalse(sibling.ended.is_set(), 'sibling must remain active across target cancellation')
        await self.done(sibling)
        self.assertEqual((sibling.size, sibling.digest.hexdigest()),
                         (size, hashlib.sha256(b'x' * size).hexdigest()))
        self.assertEqual(stuck.wire.resets, {1})
        self.assertEqual((stuck.wire.goaway, stuck.wire.eof, stuck.wire.failure), (False, False, None))
        self.assertEqual(len(self.origin.records), 1)
        self.assertEqual((await self.stats())['active'], 0)

    async def test_h2_slow_consumer_does_not_block_bulk_sibling(self):
        await self.configure(enabled=False)
        self.origin.responses['/slow'] = {'size': 8 * 1024 * 1024, 'unknown': True}
        self.origin.responses['/healthy'] = {'size': 1024 * 1024, 'unknown': True}
        slow = await self.begin('/slow', protocol='h2')
        slow.consume_gate = asyncio.Event()
        await asyncio.sleep(0.3)
        healthy = Exchange(slow.wire, stream_id=3)
        self.clients.append(healthy)
        await slow.wire.headers([(':method', 'GET'), (':scheme', 'https'),
                                 (':authority', f'127.0.0.1:{self.origin.port}'),
                                 (':path', '/healthy')], stream_id=3)
        await slow.wire.end(stream_id=3)
        completed, _ = await asyncio.wait([healthy.task], timeout=3)
        self.assertTrue(completed, 'healthy sibling stalled behind another stream')
        await self.done(healthy)
        self.assertEqual((healthy.size, healthy.digest.hexdigest()),
                         (1024 * 1024, hashlib.sha256(b'x' * 1024 * 1024).hexdigest()))
        self.assertFalse(slow.ended.is_set())
        self.assertEqual((slow.wire.goaway, slow.wire.eof, slow.wire.failure), (False, False, None))
        slow.consume_gate.set()
        await self.done(slow)

    async def test_h2_upstream_admission_queue_is_bounded_and_cancelled(self):
        await self.configure(enabled=False)
        self.origin.max_streams = 1
        release = asyncio.Event()
        self.origin.responses['/occupied'] = {'size': 512 * 1024, 'gate': release}
        first = await self.begin('/occupied', protocol='h2')
        await asyncio.wait_for(first.headers_seen.wait(), 3)
        await first.wire.headers([(':method', 'POST'), (':scheme', 'https'),
                                  (':authority', f'127.0.0.1:{self.origin.port}'),
                                  (':path', '/queued'), ('content-length', str(100 * 1024 * 1024))],
                                 stream_id=3)
        sent = 0
        async def upload():
            nonlocal sent
            for _ in range(100 * 64):
                await first.wire.data(b'x' * 16384, stream_id=3)
                sent += 16384
            await first.wire.end(stream_id=3)
        sending = asyncio.create_task(upload())
        self.background.append(sending)
        baseline = (await self.stats())['maxrss_bytes']
        await asyncio.sleep(0.5)
        self.assertLess(sent, 1024 * 1024, 'unadmitted upstream DATA must be backpressured')
        sending.cancel()
        await asyncio.gather(sending, return_exceptions=True)
        await first.wire.reset(3)
        release.set()
        await self.done(first)
        healthy = Exchange(first.wire, stream_id=5)
        self.clients.append(healthy)
        await first.wire.headers([(':method', 'GET'), (':scheme', 'https'),
                                  (':authority', f'127.0.0.1:{self.origin.port}'),
                                  (':path', '/after-cancel')], stream_id=5)
        await first.wire.end(stream_id=5)
        await self.done(healthy)
        self.assertEqual([dict(item['headers'])[':path'] for item in self.origin.records],
                         ['/occupied', '/after-cancel'])
        delta = (await self.stats())['maxrss_bytes'] - baseline
        self.assertLess(delta, 64 * 1024 * 1024)
        self.evidence(queued_upload_bytes=sent, extra_peak_rss_bytes=delta, cancelled_before_origin=True)

    async def test_h2_upstream_close_reclaims_unadmitted_streams(self):
        await self.configure(enabled=False)
        self.origin.max_streams = 1
        self.origin.responses['/occupied'] = {'size': 512 * 1024, 'unknown': True, 'hang': True}
        for goaway in [True, False]:
            first = await self.begin('/occupied', protocol='h2')
            await asyncio.wait_for(first.headers_seen.wait(), 3)
            queued = Exchange(first.wire, stream_id=3)
            self.clients.append(queued)
            await first.wire.headers([(':method', 'GET'), (':scheme', 'https'),
                                      (':authority', f'127.0.0.1:{self.origin.port}'),
                                      (':path', '/queued-close')], stream_id=3)
            await first.wire.end(stream_id=3)
            await asyncio.sleep(0.1)
            upstream = self.origin.peers[-1]
            if goaway:
                upstream.codec.send_data(1, b'z')
                upstream.codec.close_connection()
                upstream.writer.write(upstream.codec.data_to_send())
                await upstream.writer.drain()
            else:
                await upstream.close()
            completed, _ = await asyncio.wait([first.task, queued.task], timeout=3)
            self.assertEqual((await self.stats())['active'], 0)
            self.assertEqual(len(completed), 2, 'upstream close left queued requests hanging: ' +
                             (self.root / 'worker.log').read_text()[-6000:])
        self.assertNotIn('/queued-close', [dict(item['headers'])[':path'] for item in self.origin.records])

    async def test_h2_slow_consumer_memory_and_resume(self):
        await self.configure(enabled=False)
        size = 100 * 1024 * 1024
        self.origin.responses['/unmatched'] = {'size': size, 'unknown': True}
        baseline = (await self.stats())['maxrss_bytes']
        exchange = await self.begin('/unmatched', protocol='h2')
        exchange.consume_gate = asyncio.Event()
        await asyncio.sleep(0.5)
        self.assertTrue(self.origin.records)
        produced = self.origin.records[0]['wire'].sent_bytes
        self.assertLess(produced, size, 'slow consumer must prevent the full upload from being accepted')
        exchange.consume_gate.set()
        await self.done(exchange)
        expected = hashlib.sha256()
        for _ in range(size // 16384):
            expected.update(b'x' * 16384)
        self.assertEqual((exchange.size, exchange.digest.hexdigest()), (size, expected.hexdigest()))
        delta = (await self.stats())['maxrss_bytes'] - baseline
        self.evidence(slow_consumer=True, produced_before_resume=produced, extra_peak_rss_bytes=delta)
        self.assertLess(delta, 64 * 1024 * 1024)

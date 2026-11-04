"""Opt-in BP-0 transport experiments; never load the desktop runtime or phone settings."""

import asyncio
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import zlib

import brotli

from tests.fixtures.breakpoints.wire import Origin, certificates, client


@unittest.skipUnless(os.environ.get('CAPTURE_TEST_BREAKPOINT_TRANSPORT') == '1', 'opt-in BP-0 loopback test')
class BreakpointTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='capture-bp0-')
        self.root = Path(self.tmp.name)
        self.origin = Origin()
        self.clients = []
        self.background = []
        self.backlog = []
        self.err = None
        self.process = None
        self.addAsyncCleanup(self.cleanup)
        _, tls = await asyncio.to_thread(certificates, self.root)
        await self.origin.start(tls)
        self.err = (self.root / 'worker.log').open('wb')
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'tests.fixtures.breakpoints.probe', str(self.root), str(self.origin.port),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=self.err,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        self.port = (await self.event('ready'))['port']
        self.ca = self.root / 'ca' / 'mitmproxy-ca-cert.pem'

    async def cleanup(self):
        for task in self.background:
            task.cancel()
        await asyncio.gather(*self.background, return_exceptions=True)
        for exchange in self.clients:
            await exchange.close()
        await self.origin.close()
        if self.process and self.process.returncode is None:
            try:
                await self.command(action='shutdown')
                await asyncio.wait_for(self.process.wait(), 3)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                if self.process.returncode is None:
                    self.process.terminate()
                await asyncio.wait_for(self.process.wait(), 3)
        if self.err:
            self.err.close()
        if self.process:
            self.assertIsNotNone(self.process.returncode)
            tail = await self.process.stdout.read()
            for line in tail.splitlines():
                self.assertNotEqual(json.loads(line)['kind'], 'addon_error', line.decode())
        if hasattr(self, 'port'):
            with self.assertRaises(OSError):
                await asyncio.open_connection('127.0.0.1', self.port)
        self.tmp.cleanup()

    async def event(self, kind, *, stage=None, timeout=8):
        async def read():
            while True:
                for index, item in enumerate(self.backlog):
                    if item['kind'] == kind and (stage is None or item.get('stage') == stage):
                        return self.backlog.pop(index)
                line = await self.process.stdout.readline()
                if not line:
                    self.fail('worker exited: ' + (self.root / 'worker.log').read_text()[-3000:])
                item = json.loads(line)
                self.assertNotEqual(item['kind'], 'addon_error', item.get('message'))
                if item['kind'] == kind and (stage is None or item.get('stage') == stage):
                    return item
                self.backlog.append(item)
                self.assertLess(len(self.backlog), 300, 'fixture event backlog must stay bounded')
        return await asyncio.wait_for(read(), timeout)

    async def command(self, **fields):
        self.process.stdin.write(json.dumps(fields).encode() + b'\n')
        await self.process.stdin.drain()

    async def configure(self, **fields):
        await self.command(action='config', values=fields)
        await self.event('configured')

    async def stats(self):
        await self.command(action='stats')
        return await self.event('stats')

    async def begin(self, path='/hit', body=b'', *, protocol='http/1.1', unknown=False, finish=True,
                    headers=(), declared_length=None):
        exchange = await client(self.port, self.origin.port, self.ca, protocol)
        self.clients.append(exchange)
        fields = [(':method', 'POST'), (':scheme', 'https'),
                  (':authority', f'127.0.0.1:{self.origin.port}'), (':path', path), *headers]
        if not unknown:
            fields.append(('content-length', str(len(body) if declared_length is None else declared_length)))
        elif protocol == 'http/1.1':
            fields.append(('transfer-encoding', 'chunked'))
        await exchange.wire.headers(fields)
        if body:
            await exchange.wire.data(body)
        if finish:
            await exchange.wire.end()
        return exchange

    async def resolve(self, event, **patch):
        if isinstance(patch.get('body'), bytes):
            patch['body'] = base64.b64encode(patch['body']).decode()
        await self.command(action='resolve', id=event['id'], stage=event['stage'], **patch)
        await self.event('resolved')

    async def done(self, exchange):
        self.assertEqual(await asyncio.wait_for(exchange.task, 15), 'end')

    def evidence(self, **fields):
        print('BP0 ' + json.dumps({'test': self._testMethodName, **fields}, sort_keys=True), flush=True)

    def safety_gate(self, passed, reason):
        if os.environ.get('CAPTURE_REQUIRE_BP0_SAFE') == '1':
            self.assertTrue(passed, reason)

    async def test_request_and_response_pause_before_forward_and_edit(self):
        for protocol in ['http/1.1', 'h2']:
            count = len(self.origin.records)
            exchange = await self.begin(body=b'{"old":true}', protocol=protocol)
            request = await self.event('paused', stage='request')
            await asyncio.sleep(0.1)
            self.assertEqual(len(self.origin.records), count, 'even HTTP request headers must not reach origin')
            self.assertFalse(exchange.headers_seen.is_set())
            await self.resolve(request, body=b'{"new":true}', path='/hit?value=edited', headers=[['x-test', 'yes']])
            response = await self.event('paused', stage='response')
            self.assertEqual(len(self.origin.records), count + 1)
            record = self.origin.records[-1]
            self.assertEqual(bytes(record['preview']), b'{"new":true}')
            self.assertEqual(dict(record['headers'])[':path'], '/hit?value=edited')
            self.assertEqual(dict(record['headers'])['x-test'], 'yes')
            self.assertEqual(record['protocol'], protocol)
            self.assertFalse(exchange.headers_seen.is_set(), 'final response headers must not reach client')
            await self.resolve(response, body=b'{"edited":true}', status=201)
            await self.done(exchange)
            self.assertEqual((dict(exchange.headers)[':status'], bytes(exchange.preview)),
                             ('201', b'{"edited":true}'))
            self.evidence(protocol=protocol, request_before_origin=True, response_before_client=True)

    async def test_original_bytes_and_compressed_edits_on_both_protocols(self):
        await self.configure(stage='both')
        raw = '{"text":"中文🙂","n":1}'.encode()
        codecs = [('gzip', gzip.compress, gzip.decompress), ('deflate', zlib.compress, zlib.decompress),
                  ('br', brotli.compress, brotli.decompress)]
        for protocol in ['http/1.1', 'h2']:
            for encoding, encode, decode in codecs:
                encoded = encode(raw)
                self.origin.responses['/hit'] = {'body': encoded, 'headers': [('content-encoding', encoding)]}
                exchange = await self.begin('/hit?a=1&a=2', encoded, protocol=protocol,
                                            headers=[('content-encoding', encoding), ('x-repeat', 'a'), ('x-repeat', 'b')])
                await self.resolve(await self.event('paused', stage='request'))
                response = await self.event('paused', stage='response')
                self.assertEqual(bytes(self.origin.records[-1]['preview']), encoded)
                self.assertEqual([v for k, v in self.origin.records[-1]['headers'] if k == 'x-repeat'], ['a', 'b'])
                await self.resolve(response)
                await self.done(exchange)
                self.assertEqual(bytes(exchange.preview), encoded)
                exchange = await self.begin(body=encoded, protocol=protocol, headers=[('content-encoding', encoding)])
                edited = b'{"changed":2}'
                await self.resolve(await self.event('paused', stage='request'), body=edited)
                response = await self.event('paused', stage='response')
                self.assertEqual(decode(bytes(self.origin.records[-1]['preview'])), edited)
                await self.resolve(response, body=edited)
                await self.done(exchange)
                self.assertEqual(decode(bytes(exchange.preview)), edited)
                self.assertEqual(int(dict(exchange.headers)['content-length']), exchange.size)
                self.evidence(protocol=protocol, encoding=encoding, unchanged_bytes=True, edited_roundtrip=True)

    async def test_unknown_length_small_pauses_and_large_streams_without_loss(self):
        for protocol in ['http/1.1', 'h2']:
            self.origin.responses['/hit'] = {'body': b'unknown-response', 'unknown': True}
            exchange = await self.begin(body=b'unknown-request', unknown=True, protocol=protocol)
            await self.resolve(await self.event('paused', stage='request'))
            await self.resolve(await self.event('paused', stage='response'))
            await self.done(exchange)
            self.assertEqual(bytes(exchange.preview), b'unknown-response')
            size = 2 * 1024 * 1024
            self.origin.responses['/hit'] = {'size': size, 'unknown': True}
            exchange = await self.begin(unknown=True, finish=False, protocol=protocol)
            for _ in range(size // 16384):
                await exchange.wire.data(b'x' * 16384)
            await exchange.wire.end()
            await self.done(exchange)
            self.assertEqual(self.origin.records[-1]['size'], size)
            self.assertEqual(exchange.size, size)
            self.assertEqual(exchange.digest.hexdigest(), self.origin.records[-1]['digest'].hexdigest())
            self.assertEqual((await self.stats())['pending'], 0)
            self.evidence(protocol=protocol, unknown_small=True, streamed_bytes=size, hashes_equal=True)

    async def test_compressed_expansion_and_malformed_bodies_bypass_unchanged(self):
        payload = b'x' * (4 * 1024 * 1024)
        cases = [('gzip', gzip.compress(payload)), ('deflate', zlib.compress(payload)),
                 ('br', brotli.compress(payload)), ('gzip', b'invalid-compressed-data')]
        baseline = (await self.stats())['maxrss_bytes']
        for protocol in ['http/1.1', 'h2']:
            for encoding, encoded in cases:
                self.origin.responses['/hit'] = {'body': encoded, 'headers': [('content-encoding', encoding)]}
                exchange = await self.begin(body=encoded, protocol=protocol,
                                            headers=[('content-encoding', encoding)])
                await self.done(exchange)
                self.assertEqual(bytes(self.origin.records[-1]['preview']), encoded)
                self.assertEqual(bytes(exchange.preview), encoded)
                for stage in ['request', 'response']:
                    self.assertEqual((await self.event('bypass', stage=stage))['reason'], 'body_not_editable')
                stats = await self.stats()
                self.assertEqual((stats['pending'], stats['active']), (0, 0))
        delta = (await self.stats())['maxrss_bytes'] - baseline
        self.assertLess(delta, 64 * 1024 * 1024)
        self.evidence(decoded_source_bytes=len(payload), extra_peak_rss_bytes=delta, invalid_bypassed=True)

    async def test_abort_and_pause_timeout_preserve_stage_semantics(self):
        for protocol in ['http/1.1', 'h2']:
            await self.configure(stage='request', pause_timeout=15)
            before = len(self.origin.records)
            exchange = await self.begin(protocol=protocol)
            await self.resolve(await self.event('paused', stage='request'), abort=True)
            self.assertEqual(await asyncio.wait_for(exchange.task, 3), 'closed')
            self.assertEqual(len(self.origin.records), before)
            await self.configure(stage='response')
            exchange = await self.begin(protocol=protocol)
            await self.resolve(await self.event('paused', stage='response'), abort=True)
            self.assertEqual(await asyncio.wait_for(exchange.task, 3), 'closed')
            self.assertEqual(len(self.origin.records), before + 1)
            await self.configure(stage='request', pause_timeout=0.25)
            exchange = await self.begin(body=b'unchanged', protocol=protocol)
            await self.event('paused', stage='request')
            await self.event('timeout')
            await self.done(exchange)
            self.assertEqual(bytes(self.origin.records[-1]['preview']), b'unchanged')
            self.evidence(protocol=protocol, request_abort_not_sent=True, response_abort_already_sent=True,
                          paused_timeout_resumes=True)

    async def test_twenty_collecting_and_paused_slots_do_not_block_unmatched(self):
        await self.configure(stage='request')
        held = []
        for index in range(20):
            exchange = await self.begin(f'/hit?i={index}', b'x', declared_length=2 if index < 10 else 1,
                                        finish=index >= 10)
            held.append(exchange)
            await self.event('collecting')
            if index >= 10:
                await self.event('paused', stage='request')
        stats = await self.stats()
        self.assertEqual((stats['active'], stats['pending']), (20, 10))
        extra = await self.begin('/hit?capacity=full')
        self.assertEqual((await self.event('bypass'))['reason'], 'capacity')
        await self.done(extra)
        free = await self.begin('/unmatched')
        await self.done(free)
        for exchange in held[:10]:
            await exchange.close()
        for _ in range(10):
            await self.event('flow_error')
        self.assertEqual((await self.stats())['active'], 10)
        await self.command(action='release')
        await self.event('released')
        for exchange in held[10:]:
            await self.done(exchange)
        self.assertEqual((await self.stats())['active'], 0)
        self.evidence(collecting=10, paused=10, overflow_bypassed=True, disconnect_reclaims=True)

    async def test_origin_matching_does_not_intercept_other_scheme_or_port(self):
        for fields in [{'scheme': 'http'}, {'scheme': 'https', 'port': self.origin.port + 1}]:
            await self.configure(**fields)
            exchange = await self.begin('/hit')
            await self.done(exchange)
            self.assertEqual((await self.stats())['peak_active'], 0)
        self.evidence(wrong_scheme_bypassed=True, wrong_port_bypassed=True)

    async def test_slow_collection_kill_does_not_close_transport_negative_control(self):
        # Pin the observed limitation, not a production guarantee of successful timeout cleanup.
        for protocol in ['http/1.1', 'h2']:
            await self.configure(stage='request', collect_timeout=0.25)
            exchange = await self.begin(body=b'x', protocol=protocol, unknown=True, finish=False)
            await self.event('kill_called')
            await asyncio.sleep(0.5)
            self.assertFalse(exchange.ended.is_set(), 'revisit capability decision if upstream fixes in-transit kill')
            self.assertEqual((await self.stats())['active'], 1)
            self.assertFalse(self.origin.records)
            await exchange.close()
            await self.event('flow_error')
            self.assertEqual((await self.stats())['active'], 0)
            self.evidence(protocol=protocol, candidate='collecting-flow.kill', supported=False,
                          still_open_after_deadline=True)
            self.safety_gate(False, 'NO-GO: flow.kill does not end incomplete request transport')

    async def test_declared_length_trickle_does_not_enforce_collection_deadline(self):
        for protocol in ['http/1.1', 'h2']:
            await self.configure(stage='request', collect_timeout=0.25)
            exchange = await self.begin(body=b'x', protocol=protocol, declared_length=4096, finish=False)
            for _ in range(12):
                await asyncio.sleep(0.05)
                await exchange.wire.data(b'x')
            await self.event('kill_called')
            self.assertFalse(exchange.ended.is_set())
            self.assertEqual((await self.stats())['active'], 1)
            await exchange.close()
            await self.event('flow_error')
            self.assertEqual((await self.stats())['active'], 0)
            self.evidence(protocol=protocol, known_length_trickle=True, collection_deadline_enforced=False)
            self.safety_gate(False, 'NO-GO: Content-Length does not make slow collection cancellable')

    async def test_slow_response_collection_has_same_timeout_limitation(self):
        await self.configure(stage='response', collect_timeout=0.25)
        self.origin.responses['/hit'] = {'body': b'x', 'unknown': True, 'hang': True}
        for protocol in ['http/1.1', 'h2']:
            exchange = await self.begin(protocol=protocol)
            await self.event('kill_called')
            await asyncio.sleep(0.5)
            self.assertFalse(exchange.headers_seen.is_set())
            self.assertFalse(exchange.ended.is_set())
            self.assertEqual((await self.stats())['active'], 1)
            await exchange.close()
            await self.event('flow_error')
            self.evidence(protocol=protocol, candidate='response-collecting-flow.kill', supported=False)
            self.safety_gate(False, 'NO-GO: flow.kill does not end incomplete response transport')

    async def test_unmatched_latency_baseline(self):
        results = {}
        for enabled in [False, True]:
            await self.configure(enabled=enabled)
            durations = []
            for _ in range(20):
                started = time.monotonic()
                exchange = await self.begin('/unmatched')
                await self.done(exchange)
                durations.append((time.monotonic() - started) * 1000)
                await exchange.close()
            results[enabled] = sorted(durations)[18]
        self.evidence(disabled_p95_ms=round(results[False], 2), enabled_p95_ms=round(results[True], 2),
                      delta_ms=round(results[True] - results[False], 2))
        self.assertLess(results[True] - results[False], 10)

    async def streamed_memory(self, protocol, *, enabled):
        size = 100 * 1024 * 1024
        expected = hashlib.sha256()
        for _ in range(size // 16384):
            expected.update(b'x' * 16384)
        await self.configure(stage='response', enabled=enabled)
        baseline = (await self.stats())['maxrss_bytes']
        self.origin.responses['/hit'] = {'size': size, 'unknown': True}
        exchange = await self.begin(protocol=protocol)
        await self.done(exchange)
        self.assertEqual((exchange.size, exchange.digest.hexdigest()), (size, expected.hexdigest()))
        stats = await self.stats()
        delta = stats['maxrss_bytes'] - baseline
        self.evidence(protocol=protocol, streamed_bytes=size, extra_peak_rss_bytes=delta,
                      breakpoints_enabled=enabled, memory_gate_pass=delta < 64 * 1024 * 1024)
        self.safety_gate(delta < 64 * 1024 * 1024, 'NO-GO: streaming memory exceeds 64 MiB headroom')
        if protocol == 'http/1.1':
            self.assertLess(delta, 64 * 1024 * 1024)

    async def test_h1_stream_memory(self):
        await self.streamed_memory('http/1.1', enabled=True)

    async def test_h2_stream_memory_baseline(self):
        await self.streamed_memory('h2', enabled=False)

    async def test_h2_stream_memory_candidate(self):
        await self.streamed_memory('h2', enabled=True)

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
            task = asyncio.create_task(upload())
            self.background.append(task)
        else:
            self.origin.responses['/hit'] = {'size': size}
            exchange = await self.begin(protocol=protocol)
        pause = await self.event('paused', stage=stage)
        await asyncio.sleep(1.5)
        stats = await self.stats()
        delta = stats['maxrss_bytes'] - baseline
        sender = exchange.wire if stage == 'request' else self.origin.records[-1]['wire']
        load_complete = sender.sent_bytes == size
        gate = False if delta >= 64 * 1024 * 1024 else (True if load_complete else None)
        # Observation, not a green production memory acceptance: report the gate separately.
        self.evidence(protocol=protocol, candidate=f'{stage}-header-pause',
                      extra_peak_rss_bytes=delta, memory_gate_pass=gate,
                      sender_bytes_while_paused=sender.sent_bytes, intended_load_bytes=size,
                      load_complete=load_complete, load_incomplete=not load_complete)
        if stage == 'request':
            self.assertFalse(self.origin.records)
        self.assertFalse(exchange.headers_seen.is_set())
        await self.resolve(pause)
        if stage == 'request':
            await asyncio.wait_for(task, 15)
        await self.done(exchange)
        if stage == 'request':
            self.assertEqual(self.origin.records[-1]['size'], size)
        else:
            self.assertEqual(exchange.size, size)
        expected = hashlib.sha256()
        for _ in range(size // 16384):
            expected.update(b'x' * 16384)
        actual = self.origin.records[-1]['digest'] if stage == 'request' else exchange.digest
        self.assertEqual(actual.hexdigest(), expected.hexdigest())
        self.safety_gate(gate is True, 'NO-GO: header pause memory exceeds budget or load evidence is incomplete')

    async def test_h1_request_header_memory(self):
        await self.header_memory('http/1.1', 'request')

    async def test_h2_request_header_memory(self):
        await self.header_memory('h2', 'request')

    async def test_h1_response_header_memory(self):
        await self.header_memory('http/1.1', 'response')

    async def test_h2_response_header_memory(self):
        await self.header_memory('h2', 'response')


if __name__ == '__main__':
    unittest.main()

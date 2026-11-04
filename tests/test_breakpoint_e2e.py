"""Opt-in acceptance executed with a relocated bundle's Python/backend.

Test fixtures remain external to the distributable. Actual product imports and
the subprocess proxy must resolve inside the bundle, not the source checkout.
"""

import asyncio
import importlib
import importlib.metadata
import math
import os
from pathlib import Path
import time
import unittest

from tests import test_breakpoint_integration as production


@unittest.skipUnless(os.environ.get('CAPTURE_TEST_BP4_APP'), 'requires relocated bundle runtime')
class PackagedBreakpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_product_modules_are_from_relocated_bundle(self):
        backend = Path(os.environ['CAPTURE_TEST_BP4_APP']).resolve() / 'Contents/Resources/backend'
        for name in ('capture_console.breakpoints.runtime', 'capture_console.breakpoints.guard',
                     'capture_console.breakpoints.api', 'capture_console.breakpoints.android',
                     'capture_console.breakpoints.ios', 'capture_console.breakpoint_preview'):
            self.assertTrue(Path(importlib.import_module(name).__file__).resolve().is_relative_to(backend), name)
        self.assertTrue((backend / 'scripts/breakpoint_addon.py').is_file())
        self.assertEqual(importlib.metadata.version('mitmproxy'), '12.2.3')
        for mode in ('regular', 'socks', 'ios'):
            with self.subTest(mode=mode):
                fixture = production.ProductionTests()
                fixture.mode = mode
                await fixture.asyncSetUp()
                try:
                    await fixture.command('provenance')
                    child = await fixture.event('provenance')
                    self.assertTrue(Path(child['executable']).resolve().is_relative_to(backend.parent / 'runtime'))
                    required = {'capture_console.breakpoints.runtime', 'capture_console.breakpoints.guard',
                                'capture_console.breakpoints.android', 'capture_console.ios_pairing_proxy'}
                    self.assertTrue(required.issubset(child['modules']), child['modules'].keys())
                    for name, path in child['modules'].items():
                        self.assertTrue(Path(path).is_relative_to(backend), name)
                finally:
                    await fixture.cleanup()
                    fixture.tmp.cleanup()

    async def test_unmatched_latency_and_rss_for_each_product_transport(self):
        for mode in ('regular', 'socks', 'ios'):
            with self.subTest(mode=mode):
                fixture = production.ProductionTests()
                fixture.mode = mode
                await fixture.asyncSetUp()
                try:
                    await fixture.control.call('rule', {'id': 'unmatched', 'expected_revision': 0, 'rule': {
                        'scheme': 'https', 'host': '127.0.0.1', 'port': fixture.origin.port,
                        'path': '/not-hit', 'method': 'POST', 'stage': 'both', 'once': False}})
                    samples = {False: [], True: []}
                    rss = {}
                    for enabled in (False, True, False, True):
                        await fixture.control.call('enable' if enabled else 'disable')
                        for number in range(20):
                            start = time.perf_counter()
                            exchange = await fixture.begin()
                            self.assertEqual(await asyncio.wait_for(exchange.task, 5), 'end')
                            elapsed = (time.perf_counter() - start) * 1000
                            if number >= 5:
                                samples[enabled].append(elapsed)
                            await exchange.close()
                            fixture.clients.remove(exchange)
                            if enabled:
                                await fixture.control.call('heartbeat')
                        state = await fixture.control.call('status')
                        self.assertEqual((state['enabled'], state['in_flight'], state['reserved_bytes']),
                                         (enabled, 0, 0))
                        await fixture.command('stats')
                        peak = (await fixture.event('stats'))['maxrss_bytes']
                        # A process high-water mark cannot reset on the second disabled round.
                        if enabled:
                            rss[True] = max(rss.get(True, 0), peak)
                        else:
                            rss.setdefault(False, peak)
                    p95 = {key: sorted(values)[math.ceil(len(values) * .95) - 1] for key, values in samples.items()}
                    extra_rss = max(0, rss[True] - rss[False])
                    print(f'BP4_PERFORMANCE mode={mode} off_p95_ms={p95[False]:.3f} '
                          f'on_p95_ms={p95[True]:.3f} extra_rss_bytes={extra_rss}', flush=True)
                    self.assertLessEqual(p95[True] - p95[False], 10)
                    self.assertLess(extra_rss, 64 * 1024 * 1024)
                    self.assertEqual((await fixture.control.call('pending'))['data'], [])
                finally:
                    await fixture.cleanup()
                    fixture.tmp.cleanup()

    async def test_packaged_request_response_reach_wire(self):
        for mode in ('regular', 'socks', 'ios'):
            with self.subTest(mode=mode):
                fixture = production.ProductionTests()
                fixture.mode = mode
                await fixture.asyncSetUp()
                try:
                    await fixture.test_edit_wire_and_archive()
                    await fixture.control.call('disable')
                    state = await fixture.control.call('status')
                    self.assertEqual(state['in_flight'], 0)
                finally:
                    await fixture.cleanup()
                    fixture.tmp.cleanup()

    async def test_packaged_request_abort_never_reaches_origin(self):
        for mode in ('regular', 'socks', 'ios'):
            with self.subTest(mode=mode):
                fixture = production.ProductionTests()
                fixture.mode = mode
                await fixture.asyncSetUp()
                try:
                    await fixture.test_request_abort_is_not_forwarded()
                finally:
                    await fixture.cleanup()
                    fixture.tmp.cleanup()

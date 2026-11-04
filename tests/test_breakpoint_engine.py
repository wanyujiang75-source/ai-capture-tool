import asyncio
import unittest
from dataclasses import replace

from capture_console.breakpoints.engine import BreakpointEngine
from capture_console.breakpoints.models import Message, RuleInput, Patch, Issue


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def request(**changes):
    return replace(Message(url='https://example.test/hit?secret=hidden', method='POST',
                           headers=(('content-type', 'application/json'),), body=b'{}'), **changes)


class EngineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = Clock()
        self.engine = BreakpointEngine('capture', 'device', clock=self.clock)

    def rule(self, rule_id='r', **changes):
        values = dict(scheme='https', host='example.test', path='/hit', method='POST',
                      stage='both', once=True)
        values.update(changes)
        return self.engine.put_rule(rule_id, 0, RuleInput(**values))

    def paused(self, flow='f', message=None):
        message = message or request()
        admission = self.engine.admit(flow, replace(message, body=b''))
        self.assertIsNotNone(admission)
        self.assertTrue(self.engine.reserve(flow, len(message.body), len(message.body)))
        self.engine.pause(flow, message)
        return admission.pending_id

    def resolve(self, pending, action='original', patch=None, op='op'):
        return self.engine.resolve(pending, f'{pending}.{op}', 1, action, patch)

    def test_default_off_origin_and_internal_exclusions(self):
        self.rule()
        self.assertIsNone(self.engine.admit('off', request()))
        self.engine.enable()
        for index, url in enumerate(['http://example.test/hit', 'https://example.test:444/hit',
                                     'https://other.test/hit', 'https://example.test/miss']):
            self.assertIsNone(self.engine.admit(str(index), request(url=url)))
        self.assertIsNone(self.engine.admit('system', request(), internal=True))
        self.assertIsNone(self.engine.admit('not-recording', request(), recording=False))
        self.assertIsNone(self.engine.admit('h3', request(protocol='h3')))
        self.assertIsNotNone(self.engine.admit('ok', request(url='https://EXAMPLE.test:443/hit?q=2')))

    async def test_both_stages_snapshot_original_immutable_and_ack(self):
        self.rule()
        self.engine.enable()
        pending = self.paused()
        waiter = asyncio.create_task(self.engine.wait(pending))
        result = self.resolve(pending, 'apply', Patch(url='https://example.test/changed?a=1&a=2', body_text='{"v":2}'))
        self.assertEqual(result['state'], 'applying')
        decision = await waiter
        self.assertEqual(decision.original.body, b'{}')
        self.assertEqual(decision.effective.body, b'{"v":2}')
        self.assertEqual(self.engine.status()['in_flight'], 1)
        self.engine.put_rule('r', 1, RuleInput(scheme='https', host='other.test', path='/', method='GET'))
        self.engine.ack(pending)
        response = request(url=decision.effective.url, status=200, body=b'{"ok":true}')
        response_id = self.engine.response('f', replace(response, body=b''))
        self.engine.reserve('f', len(response.body), len(response.body))
        self.engine.pause('f', response)
        self.resolve(response_id, op='response')
        self.assertEqual((await self.engine.wait(response_id)).effective, response)
        self.engine.ack(response_id)
        self.assertEqual((self.engine.status()['in_flight'], self.engine.status()['reserved_bytes']), (0, 0))

    def test_once_reservation_returns_before_pause_but_consumed_after(self):
        self.rule()
        self.engine.enable()
        self.engine.admit('collecting', request(body=b''))
        self.assertIsNone(self.engine.admit('blocked', request()))
        self.engine.disconnect('collecting')
        self.paused('next')
        self.engine.disconnect('next')
        self.assertIsNone(self.engine.admit('consumed', request()))

    def test_order_first_rule_per_stage_and_limits(self):
        self.rule('first', stage='request', once=False)
        self.rule('second', stage='both', once=False)
        self.engine.enable()
        pending = self.paused()
        self.assertEqual(self.engine.detail(pending)['matched_rule'], 'first')
        for index in range(19):
            self.engine.admit(f'f{index}', request(body=b''))
        self.assertIsNone(self.engine.admit('overflow', request()))
        self.assertEqual(self.engine.status()['in_flight'], 20)
        with self.assertRaises(Issue):
            self.engine.put_rule('first', 0, RuleInput(scheme='https', host='example.test', path='/'))

    async def test_deadline_trickle_empty_and_lease_are_independent(self):
        self.rule(once=False)
        self.engine.enable()
        admission = self.engine.admit('slow', request(body=b''))
        self.clock.now += 2
        self.engine.reserve('slow', 0, 0)
        self.engine.heartbeat()
        self.clock.now += 1.1
        self.engine.tick()
        self.assertEqual((await self.engine.wait(admission.pending_id)).reason, 'collection_idle')
        self.engine.ack(admission.pending_id)
        pending = self.paused('lease')
        self.clock.now += 5.1
        self.engine.tick()
        self.assertFalse(self.engine.status()['enabled'])
        self.assertEqual((await self.engine.wait(pending)).reason, 'lease_expired')
        self.engine.heartbeat()
        self.assertFalse(self.engine.status()['enabled'])

    async def test_total_deadline_cannot_be_renewed_by_data(self):
        self.rule()
        self.engine.enable()
        admission = self.engine.admit('slow', request(body=b''))
        for count in range(1, 12):
            self.clock.now += 1
            self.engine.heartbeat()
            if count <= 10:
                self.engine.reserve('slow', count, count)
            self.engine.tick()
        self.assertEqual((await self.engine.wait(admission.pending_id)).reason, 'collection_total')

    async def test_timeout_invalid_patch_and_duplicate_decisions(self):
        self.rule(timeout_seconds=15)
        self.engine.enable()
        pending = self.paused()
        before = self.engine.detail(pending)
        with self.assertRaises(Issue):
            self.resolve(pending, 'apply', Patch(url='https://evil.test/'))
        self.assertEqual(self.engine.detail(pending), before)
        first = self.resolve(pending, 'apply', Patch(body_text='{"a":1}'))
        self.assertEqual(self.resolve(pending, 'apply', Patch(body_text='{"a":1}')), first)
        with self.assertRaises(Issue):
            self.resolve(pending, 'abort')
        self.clock.now += 2
        self.engine.tick()
        self.assertEqual((await self.engine.wait(pending)).action, 'apply')

    async def test_timeout_wins_against_late_resolution(self):
        self.rule(timeout_seconds=15)
        self.engine.enable()
        pending = self.paused()
        for _ in range(4):
            self.clock.now += 4
            self.engine.heartbeat()
        with self.assertRaises(Issue):
            self.resolve(pending)
        self.assertEqual((await self.engine.wait(pending)).reason, 'pause_timeout')

    async def test_stop_drains_and_reclaims_without_claiming_delivery(self):
        self.rule(once=False)
        self.engine.enable()
        pending = self.paused('ready')
        collecting = self.engine.admit('slow', request(body=b''))
        self.engine.stop()
        self.assertEqual((await self.engine.wait(pending)).action, 'original')
        self.clock.now += 3.1
        self.engine.tick()
        self.assertEqual(self.engine.status()['in_flight'], 0)
        self.assertEqual((await self.engine.wait(collecting.pending_id)).action, 'abort')
        with self.assertRaises(Issue):
            self.engine.enable()

    async def test_unacknowledged_decisions_have_bounded_lifetime(self):
        self.rule(once=False)
        self.engine.enable()
        pending = self.paused()
        self.resolve(pending, 'apply', Patch(body_text='{"a":1}'))
        self.clock.now += 3.1
        self.engine.tick()
        self.assertEqual((len(self.engine.flows), self.engine.reserved_bytes), (0, 0))
        with self.assertRaises(Issue):
            await self.engine.wait(pending)
        with self.assertRaises(Issue):
            self.engine.ack(pending)

    async def test_disconnected_waiter_never_receives_stale_edit(self):
        self.rule()
        self.engine.enable()
        pending = self.paused()
        waiter = asyncio.create_task(self.engine.wait(pending))
        await asyncio.sleep(0)
        self.resolve(pending, 'apply', Patch(body_text='{"a":1}'))
        self.engine.disconnect('f')
        with self.assertRaises(Issue):
            await waiter
        self.assertEqual(self.engine.reserved_bytes, 0)

    async def test_failed_ack_records_disconnect_not_delivery(self):
        self.rule()
        self.engine.enable()
        pending = self.paused()
        self.resolve(pending, 'apply', Patch(body_text='{"a":1}'))
        await self.engine.wait(pending)
        self.engine.ack(pending, connected=False)
        self.assertEqual(self.engine.completed[pending][2], 'disconnected')
        self.assertEqual(self.engine.reserved_bytes, 0)

    async def test_pagination_does_not_skip_when_previous_page_completes(self):
        self.rule(once=False, stage='request')
        self.engine.enable()
        ids = [self.paused(f'f{i}') for i in range(3)]
        first = self.engine.pending(limit=1)
        self.resolve(ids[0])
        await self.engine.wait(ids[0])
        self.engine.ack(ids[0])
        second = self.engine.pending(cursor=first['next_cursor'], limit=1)
        self.assertEqual([p['id'] for p in second['data']], [ids[1]])

    def test_small_budget_rejects_edit_without_changing_pending(self):
        self.engine = BreakpointEngine('capture', 'device', clock=self.clock, budget=150)
        self.rule()
        self.engine.enable()
        pending = self.paused()
        before = (self.engine.reserved_bytes, self.engine.detail(pending))
        with self.assertRaisesRegex(Issue, 'budget_exceeded'):
            self.resolve(pending, 'apply', Patch(body_text='"' + 'x' * 100 + '"'))
        self.assertEqual((self.engine.reserved_bytes, self.engine.detail(pending)), before)
        self.engine.disconnect('f')
        self.assertEqual(self.engine.reserved_bytes, 0)

    def test_invalid_zero_port_cannot_match_or_edit(self):
        self.rule(once=False)
        self.engine.enable()
        self.assertIsNone(self.engine.admit('bad', request(url='https://example.test:0/hit')))
        pending = self.paused()
        with self.assertRaises(Issue):
            self.resolve(pending, 'apply', Patch(url='https://example.test:0/hit'))

    def test_body_budget_and_unreserved_bytes_never_enter_editor(self):
        self.rule(once=False)
        self.engine.enable()
        self.engine.admit('large', request(body=b''))
        self.assertFalse(self.engine.reserve('large', 262145, 262145))
        self.assertEqual(self.engine.status()['reserved_bytes'], 0)
        self.engine.admit('unreserved', request(body=b''))
        with self.assertRaises(Issue):
            self.engine.pause('unreserved', request())
        self.assertEqual(self.engine.pending()['data'], [])

    def test_patch_headers_duplicates_json_and_body_semantics(self):
        self.rule(once=False)
        self.engine.enable()
        message = request(headers=(('content-type', 'application/json'), ('x-a', '1'), ('x-a', '2')))
        pending = self.paused(message=message)
        for patch in [Patch(headers=[('x-a', 'bad\r\nX: 1')]), Patch(headers=[('Host', 'other.test')]),
                      Patch(body_text='{bad'), Patch(method='HEAD'), Patch(body_text='界' * 100000)]:
            with self.assertRaises(Issue):
                self.resolve(pending, 'apply', patch)
        self.resolve(pending, 'apply', Patch(headers=[('content-type', 'application/json'), ('x-a', '3'), ('x-a', '4')]))
        self.assertEqual(self.engine.detail(pending)['original']['headers'], [list(h) for h in message.headers])

    def test_summaries_do_not_leak_query_headers_or_body(self):
        self.rule()
        self.engine.enable()
        self.paused(message=request(headers=(('authorization', 'secret-token'),)))
        summary = str(self.engine.pending()) + str(self.engine.status())
        for secret in ['secret-token', 'secret=hidden', "b'{}'"]:
            self.assertNotIn(secret, summary)
        with self.assertRaises(Issue):
            self.engine.pending(limit=51)

    async def test_simultaneous_commands_choose_one_and_cancelled_waiter_is_safe(self):
        self.rule()
        self.engine.enable()
        pending = self.paused()
        waiter = asyncio.create_task(self.engine.wait(pending))
        await asyncio.sleep(0)
        waiter.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await waiter
        async def decide(op):
            try:
                return self.resolve(pending, op=op)
            except Issue:
                return None
        results = await asyncio.gather(*(decide(str(i)) for i in range(20)))
        self.assertEqual(sum(item is not None for item in results), 1)
        self.assertEqual((await self.engine.wait(pending)).action, 'original')

    async def test_disable_while_collecting_continues_after_completion_and_skips_response(self):
        self.rule()
        self.engine.enable()
        pending = self.engine.admit('f', request(body=b'')).pending_id
        self.engine.release_all()
        self.assertTrue(self.engine.reserve('f', 2, 2))
        self.engine.pause('f', request())
        self.assertEqual((await self.engine.wait(pending)).reason, 'disabled')
        self.engine.ack(pending)
        self.assertIsNone(self.engine.response('f', request(status=200)))
        self.assertFalse(self.engine.rules['r'].consumed)
        self.assertEqual((len(self.engine.flows), self.engine.reserved_bytes), (0, 0))

    async def test_stop_and_resolve_order_has_no_second_decision(self):
        for stop_first in (False, True):
            self.setUp()
            self.rule()
            self.engine.enable()
            pending = self.paused()
            if stop_first:
                self.engine.stop()
                with self.assertRaises(Issue):
                    self.resolve(pending, 'apply', Patch(body_text='{"v":1}'))
                expected = 'original'
            else:
                self.resolve(pending, 'apply', Patch(body_text='{"v":1}'))
                self.engine.stop()
                expected = 'apply'
            self.assertEqual((await self.engine.wait(pending)).action, expected)
            self.engine.ack(pending)
            self.assertEqual((len(self.engine.flows), self.engine.reserved_bytes), (0, 0))

    def test_response_only_timeout_returns_unconsumed_once_rule(self):
        self.rule(stage='response')
        self.engine.enable()
        self.assertIsNone(self.engine.admit('waiting', request()).pending_id)
        for _ in range(15):
            self.clock.now += 4
            self.engine.heartbeat()
        self.assertEqual((len(self.engine.flows), self.engine.reserved_bytes), (0, 0))
        self.assertIsNotNone(self.engine.admit('next', request()))

    async def test_response_semantics_and_integrity_fields(self):
        self.rule(stage='response', once=False)
        self.engine.enable()
        self.engine.admit('f', request())
        original = request(status=200, headers=(('content-type', 'application/json'), ('content-length', '2'),
                                                ('content-encoding', 'gzip'), ('etag', 'old'), ('digest', 'old')))
        pending = self.engine.response('f', replace(original, body=b''))
        self.engine.reserve('f', 22, 2)
        self.engine.pause('f', original)
        for patch in (Patch(status=204), Patch(status=304), Patch(url=original.url), Patch(body_text='NaN')):
            with self.assertRaises(Issue):
                self.resolve(pending, 'apply', patch)
        self.resolve(pending, 'apply', Patch(body_text='{"v":1}'))
        decision = await self.engine.wait(pending)
        self.assertEqual(decision.effective.headers, (('content-type', 'application/json'), ('content-encoding', 'gzip')))
        self.assertEqual(decision.original, original)

    def test_full_body_and_draft_capacity_reclaims_all_bytes(self):
        self.rule(once=False, stage='request')
        self.engine.enable()
        body = b'x' * (256 * 1024)
        for i in range(20):
            pending = self.paused(f'f{i}', request(headers=(('content-type', 'text/plain'),), body=body))
            self.resolve(pending, 'apply', Patch(body_text='y' * len(body)), op=f'op{i}')
            self.assertLessEqual(self.engine.reserved_bytes, 16 * 1024 * 1024)
        self.assertGreater(self.engine.reserved_bytes, 15 * 1024 * 1024)
        self.clock.now += 3.1
        self.engine.tick()
        self.assertEqual((len(self.engine.flows), self.engine.reserved_bytes), (0, 0))
        self.assertTrue(all(item[1].original is None and item[1].effective is None
                            for item in self.engine.completed.values()))

    async def test_rule_limit_and_terminal_operation_cache_are_bounded(self):
        self.rule(once=False, stage='request')
        for i in range(99):
            self.rule(f'r{i}', path=f'/{i}')
        with self.assertRaisesRegex(Issue, 'rule_limit'):
            self.rule('excess')
        self.engine.enable()
        for i in range(260):
            pending = self.paused(f'f{i}')
            self.resolve(pending, op=f'op{i}')
            await self.engine.wait(pending)
            self.engine.ack(pending)
        self.assertEqual((len(self.engine.operations), len(self.engine.completed)), (256, 256))
        self.clock.now += 301
        self.engine.tick()
        self.assertEqual((len(self.engine.operations), len(self.engine.completed)), (0, 0))

    async def test_identical_body_patch_reuses_original_storage(self):
        self.rule()
        self.engine.enable()
        message = request(headers=(('content-type', 'text/plain'),), body=b'x' * 4096)
        pending = self.paused(message=message)
        self.resolve(pending, 'apply', Patch(body_text=message.body.decode()))
        decision = await self.engine.wait(pending)
        self.assertIs(decision.original.body, decision.effective.body)

    def test_binary_message_bypasses_without_consuming_once(self):
        self.rule()
        self.engine.enable()
        self.assertIsNone(self.engine.admit('binary', request(editable_body=False, body=b'',
                                                             headers=(('content-type', 'application/octet-stream'),))))
        self.assertFalse(self.engine.rules['r'].consumed)
        self.assertIsNotNone(self.engine.admit('text', request()))

    def test_binary_response_returns_unconsumed_reservation(self):
        self.rule(stage='response')
        self.engine.enable()
        self.engine.admit('f', request())
        self.assertIsNone(self.engine.response('f', request(status=200, editable_body=False)))
        self.assertFalse(self.engine.rules['r'].consumed)
        self.assertEqual(self.engine.reserved_bytes, 0)
        self.assertIsNotNone(self.engine.admit('next', request()))

    async def test_ack_requires_transport_to_claim_decision_first(self):
        self.rule(stage='request')
        self.engine.enable()
        pending = self.paused()
        self.resolve(pending)
        with self.assertRaisesRegex(Issue, 'decision_not_claimed'):
            self.engine.ack(pending)
        await self.engine.wait(pending)
        self.engine.ack(pending)
        self.assertEqual(self.engine.reserved_bytes, 0)

    async def test_evicted_operation_id_cannot_be_rebound_to_another_stage(self):
        self.rule(stage='request', once=False)
        self.engine.enable()
        for i in range(257):
            pending = self.paused(f'f{i}')
            operation = f'{pending}.op'
            if i == 0:
                old_operation = operation
            self.engine.resolve(pending, operation, 1, 'original')
            await self.engine.wait(pending)
            self.engine.ack(pending)
        new_pending = self.paused('new')
        with self.assertRaisesRegex(Issue, 'operation_target_conflict'):
            self.engine.resolve(new_pending, old_operation, 1, 'original')
        self.assertEqual(self.engine.detail(new_pending)['state'], 'paused')

    def test_release_all_reports_collecting_paused_and_waiting(self):
        self.rule('req', path='/hit', stage='request', once=False)
        self.rule('resp', path='/other', stage='response', once=False)
        self.engine.enable()
        self.paused('paused')
        self.engine.admit('collecting', request(body=b''))
        self.engine.admit('waiting', request(url='https://example.test/other'))
        data = self.engine.release_all()['data']
        self.assertEqual({row['flow_id']: row['state'] for row in data},
                         {'paused': 'applying', 'collecting': 'collecting', 'waiting': 'ended'})

    async def test_clearing_body_allows_bodyless_response_status(self):
        self.rule(stage='response')
        self.engine.enable()
        self.engine.admit('f', request())
        message = request(status=200, headers=(('content-type', 'application/json'), ('content-length', '2')))
        pending = self.engine.response('f', replace(message, body=b''))
        self.engine.reserve('f', 2, 2)
        self.engine.pause('f', message)
        self.resolve(pending, 'apply', Patch(status=204, body_text=''))
        effective = (await self.engine.wait(pending)).effective
        self.assertEqual((effective.status, effective.body, effective.headers),
                         (204, b'', (('content-type', 'application/json'),)))

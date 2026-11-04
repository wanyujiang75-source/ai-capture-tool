"""Event-loop-owned state machine. Decisions are not proof of network delivery."""

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field, replace
import hashlib
import json
import secrets
import time

from .models import Admission, BODY_LIMIT, FRAME_LIMIT, Decision, Issue, Message, RuleInput
from .validation import edited, identifier, message_json, metadata_size, rule_key, url


@dataclass
class Rule:
    id: str
    revision: int
    spec: RuleInput
    origin: tuple
    wire_size: int
    reserved: str | None = None
    consumed: bool = False


@dataclass
class Pending:
    id: str
    flow_id: str
    stage: str
    rule: Rule
    original: Message | None
    started: float
    updated: float
    state: str = 'collecting'
    revision: int = 1
    deadline: float = 0
    encoded: int = 0
    decoded: int = 0
    decision: Decision | None = None
    claimed: bool = False
    closed: bool = False
    sequence: int = 0
    event: asyncio.Event = field(default_factory=asyncio.Event)


@dataclass
class Flow:
    id: str
    request: Message
    rules: dict
    reserved: int
    created: float
    current: Pending | None = None
    skip_future: bool = False


class BreakpointEngine:
    def __init__(self, capture_id, device_id, *, clock=time.monotonic, budget=16 * 1024 * 1024):
        self.capture_id, self.device_id = identifier(capture_id), identifier(device_id)
        self.epoch = secrets.token_hex(16)
        if type(budget) is not int or not 1 <= budget <= 16 * 1024 * 1024:
            raise ValueError('invalid budget')
        self.clock, self.budget = clock, budget
        self.rules, self.flows = OrderedDict(), {}
        self.items, self.completed, self.operations = {}, OrderedDict(), OrderedDict()
        self.reserved_bytes = 0
        self.enabled = False
        self.stopped = False
        self.lease = 0
        self.drain_deadline = None
        self.owner_loop = None
        self.sequence = 0

    def put_rule(self, rule_id, expected_revision, spec):
        self.tick()
        identifier(rule_id)
        origin = rule_key(spec)
        old = self.rules.get(rule_id)
        if type(expected_revision) is not int or expected_revision != (old.revision if old else 0):
            raise Issue('revision_conflict')
        if not old and len(self.rules) >= 100:
            raise Issue('rule_limit')
        size = len(json.dumps(dict(id=rule_id, revision=expected_revision + 1, consumed=False,
                                   **spec.model_dump()), ensure_ascii=False).encode('utf-8'))
        if sum(r.wire_size for r in self.rules.values()) - (old.wire_size if old else 0) + size > FRAME_LIMIT // 2:
            raise Issue('rule_budget_exceeded')
        self.rules[rule_id] = Rule(rule_id, expected_revision + 1, spec, origin, size)
        return {'id': rule_id, 'revision': expected_revision + 1}

    def enable(self):
        self.tick()
        if self.stopped:
            raise Issue('capture_ended', 410)
        self.enabled = True
        self.lease = self.clock() + 5
        return self.status()

    def heartbeat(self):
        self.tick()
        if self.stopped:
            raise Issue('capture_ended', 410)
        self.lease = self.clock() + 5
        return {'enabled': self.enabled}

    def _charge(self, flow, size):
        if self.reserved_bytes + size > self.budget:
            return False
        self.reserved_bytes += size
        flow.reserved += size
        return True

    def _new_stage(self, flow, stage, message):
        now = self.clock()
        pending = Pending(secrets.token_hex(16), flow.id, stage, flow.rules[stage], message, now, now)
        flow.current = pending
        self.items[pending.id] = pending
        return pending.id

    def admit(self, flow_id, request, *, recording=True, internal=False):
        self.tick()
        identifier(flow_id)
        if flow_id in self.flows:
            raise Issue('flow_exists')
        if not self.enabled or not recording or internal or len(self.flows) >= 20:
            return None
        if request.protocol not in {'http/1.1', 'h2'} or request.streaming or not request.editable_body:
            return None
        try:
            size = metadata_size(request)
            origin, path = url(request.url)
        except Issue:
            return None
        matched = {}
        for rule in self.rules.values():
            spec = rule.spec
            if (not spec.enabled or spec.method != request.method or rule.origin != origin
                    or spec.once and (rule.consumed or rule.reserved)):
                continue
            if not (path == spec.path if spec.path_match == 'exact' else path.startswith(spec.path)):
                continue
            for stage in ('request', 'response'):
                if stage not in matched and spec.stage in {stage, 'both'}:
                    matched[stage] = rule
        if not matched:
            return None
        flow = Flow(flow_id, replace(request, body=b''), matched, 0, self.clock())
        if not self._charge(flow, size):
            return None
        self.flows[flow_id] = flow
        for rule in matched.values():
            if rule.spec.once:
                rule.reserved = flow_id
        pending_id = self._new_stage(flow, 'request', flow.request) if 'request' in matched else None
        return Admission(flow_id, pending_id)

    def response(self, flow_id, response):
        self.tick()
        flow = self.flows.get(flow_id)
        if not flow:
            return None
        if flow.current is not None:
            raise Issue('stage_conflict')
        if flow.skip_future or 'response' not in flow.rules or response.streaming or not response.editable_body:
            self._finish(flow)
            return None
        try:
            size = metadata_size(response)
        except Issue:
            self._finish(flow)
            return None
        if response.protocol not in {'http/1.1', 'h2'} or not self._charge(flow, size):
            self._finish(flow)
            return None
        return self._new_stage(flow, 'response', replace(response, body=b''))

    def reserve(self, flow_id, encoded, decoded):
        self.tick()
        flow = self.flows.get(flow_id)
        pending = flow.current if flow else None
        if not pending or pending.state != 'collecting':
            return False
        if any(type(n) is not int or n < 0 for n in (encoded, decoded)) or encoded < pending.encoded or decoded < pending.decoded:
            raise Issue('invalid_reservation', 422)
        if max(encoded, decoded) > BODY_LIMIT or not self._charge(flow, encoded + decoded - pending.encoded - pending.decoded):
            self._choose(pending, 'original', 'budget_bypass')
            self._finish(flow)
            return False
        if encoded > pending.encoded or decoded > pending.decoded:
            pending.updated = self.clock()
        pending.encoded, pending.decoded = encoded, decoded
        return True

    def pause(self, flow_id, message):
        self.tick()
        flow = self.flows.get(flow_id)
        pending = flow.current if flow else None
        if not pending or pending.state != 'collecting':
            raise Issue('stage_ended', 410)
        if (message.body and len(message.body) > pending.decoded or
                replace(message, body=b'') != pending.original):
            raise Issue('unreserved_message', 422)
        pending.original = message
        if flow.skip_future:
            self._choose(pending, 'original', 'disabled')
            return
        pending.state = 'paused'
        self._visible(pending)
        pending.deadline = self.clock() + pending.rule.spec.timeout_seconds
        if pending.rule.spec.once:
            pending.rule.consumed = True

    def _visible(self, pending):
        if pending.sequence == 0:
            self.sequence += 1
            pending.sequence = self.sequence

    def _choose(self, pending, action, reason, effective=None):
        if pending.decision is not None:
            return
        pending.decision = Decision(action, reason, pending.original,
                                    effective if effective is not None else pending.original)
        pending.state = 'applying'
        pending.deadline = self.clock() + 3
        self._visible(pending)
        pending.revision += 1
        pending.event.set()

    async def wait(self, pending_id):
        self.tick()
        pending = self.items.get(pending_id)
        if not pending:
            terminal = self.completed.get(pending_id)
            if terminal and terminal[1].action == 'abort':
                return terminal[1]
            raise Issue('stage_ended', 410)
        await pending.event.wait()
        self.tick()
        if pending.closed and pending.decision.action != 'abort':
            raise Issue('stage_ended', 410)
        if pending.claimed:
            raise Issue('decision_claimed')
        pending.claimed = True
        return pending.decision

    def resolve(self, pending_id, operation_id, expected_revision, action, patch=None):
        self.tick()
        identifier(operation_id)
        if not operation_id.startswith(pending_id + '.') or operation_id == pending_id + '.':
            raise Issue('operation_target_conflict')
        fingerprint = hashlib.sha256(json.dumps([pending_id, expected_revision, action,
                                                 patch.model_dump(mode='json') if patch else None],
                                                sort_keys=True).encode()).hexdigest()
        previous = self.operations.get(operation_id)
        if previous:
            if fingerprint != previous[1]:
                raise Issue('operation_conflict')
            return dict(previous[2])
        pending = self.items.get(pending_id)
        if not pending or pending.state != 'paused':
            raise Issue('stage_ended', 410)
        if type(expected_revision) is not int or expected_revision != pending.revision:
            raise Issue('revision_conflict')
        if action not in {'apply', 'original', 'abort'} or action != 'apply' and patch is not None:
            raise Issue('invalid_decision', 422)
        effective = pending.original
        if action == 'apply':
            if patch is None:
                raise Issue('missing_patch', 422)
            flow = self.flows[pending.flow_id]
            effective = edited(pending.original, patch, pending.stage, flow.request.method)
            size = metadata_size(effective) + (len(effective.body) if effective.body != pending.original.body else 0)
            if not self._charge(flow, size):
                raise Issue('budget_exceeded')
        self._choose(pending, action, 'user', effective)
        result = {'id': pending_id, 'state': 'applying', 'revision': pending.revision,
                  'action': action, 'decision_recorded': True}
        self.operations[operation_id] = (self.clock(), fingerprint, dict(result))
        while len(self.operations) > 256:
            self.operations.popitem(last=False)
        return result

    def _archive(self, pending, state):
        decision = pending.decision or Decision('abort', state, None, None)
        pending.closed = True
        pending.original = None
        pending.decision = replace(decision, original=None, effective=None)
        pending.event.set()
        self.completed[pending.id] = (self.clock(), pending.decision, state)
        self.items.pop(pending.id, None)
        while len(self.completed) > 256:
            self.completed.popitem(last=False)

    def _finish(self, flow):
        for rule in flow.rules.values():
            if rule.reserved == flow.id:
                rule.reserved = None
        if flow.current:
            self._archive(flow.current, 'disconnected')
        self.reserved_bytes -= flow.reserved
        self.flows.pop(flow.id, None)

    def ack(self, pending_id, *, connected=True):
        self.tick()
        pending = self.items.get(pending_id)
        if not pending or pending.decision is None:
            raise Issue('stage_ended', 410)
        if not pending.claimed:
            raise Issue('decision_not_claimed')
        flow = self.flows[pending.flow_id]
        decision = pending.decision
        self._archive(pending, 'disconnected' if not connected else
                      'continued_modified' if decision.action == 'apply' else 'continued_original'
                      if decision.action == 'original' else 'aborted')
        flow.current = None
        if pending.stage == 'request' and decision.action != 'abort' and connected and not flow.skip_future and 'response' in flow.rules:
            flow.request = replace(decision.effective, body=b'')
            keep = metadata_size(flow.request)
            self.reserved_bytes -= flow.reserved - keep
            flow.reserved = keep
            flow.created = self.clock()
        else:
            self._finish(flow)

    def disconnect(self, flow_id):
        self.tick()
        flow = self.flows.get(flow_id)
        if flow:
            if flow.current:
                self._choose(flow.current, 'abort', 'client_disconnected')
            self._finish(flow)

    def release_all(self, reason='disabled'):
        self.enabled = False
        results = []
        for flow in list(self.flows.values()):
            flow.skip_future = True
            if flow.current is None:
                self._finish(flow)
                results.append({'flow_id': flow.id, 'id': None, 'state': 'ended'})
            else:
                if flow.current.state == 'paused':
                    self._choose(flow.current, 'original', reason)
                results.append({'flow_id': flow.id, 'id': flow.current.id, 'state': flow.current.state})
        return {'data': results}

    def stop(self):
        result = self.release_all('stopped')
        self.stopped = True
        if self.drain_deadline is None:
            self.drain_deadline = self.clock() + 3
        return result

    def tick(self):
        if self.owner_loop is not None and asyncio.get_running_loop() is not self.owner_loop:
            raise Issue('wrong_worker_loop')
        now = self.clock()
        for cache in (self.operations, self.completed):
            while cache and next(iter(cache.values()))[0] + 300 <= now:
                cache.popitem(last=False)
        if self.enabled and self.lease <= now:
            self.release_all('lease_expired')
        for flow in list(self.flows.values()):
            pending = flow.current
            if self.drain_deadline is not None and now >= self.drain_deadline:
                if pending:
                    self._choose(pending, 'abort', 'stop_deadline')
                self._finish(flow)
            elif pending is None:
                if now - flow.created >= 60:
                    self._finish(flow)
            elif pending.state == 'collecting':
                reason = 'collection_total' if now - pending.started >= 10 else 'collection_idle' if now - pending.updated >= 3 else None
                if reason:
                    self._choose(pending, 'abort', reason)
            elif pending.state == 'paused' and now >= pending.deadline:
                self._choose(pending, 'original', 'pause_timeout')
            elif pending.state == 'applying' and now >= pending.deadline:
                self._finish(flow)

    async def run_clock(self):
        self.owner_loop = asyncio.get_running_loop()
        while True:
            self.tick()
            await asyncio.sleep(0.05)

    def status(self):
        self.tick()
        return {'version': 1, 'epoch': self.epoch, 'capture_id': self.capture_id, 'device_id': self.device_id,
                'enabled': self.enabled, 'stopped': self.stopped, 'in_flight': len(self.flows),
                'reserved_bytes': self.reserved_bytes, 'pending_count': sum(p.state == 'paused' for p in self.items.values()),
                'rules': [dict(id=r.id, revision=r.revision, consumed=r.consumed, **r.spec.model_dump()) for r in self.rules.values()],
                'transport_attached': False}

    def pending(self, cursor=0, limit=50):
        self.tick()
        if type(cursor) is not int or cursor < 0 or type(limit) is not int or not 1 <= limit <= 50:
            raise Issue('invalid_page', 422)
        items = sorted((p for p in self.items.values() if p.sequence > cursor), key=lambda p: p.sequence)
        page = items[:limit]
        return {'data': [{'id': p.id, 'flow_id': p.flow_id, 'stage': p.stage, 'state': p.state,
                          'revision': p.revision, 'matched_rule': p.rule.id,
                          'remaining_seconds': max(0, p.deadline - self.clock())} for p in page],
                'next_cursor': page[-1].sequence if len(items) > limit else None}

    def detail(self, pending_id):
        self.tick()
        pending = self.items.get(pending_id)
        if not pending or pending.state not in {'paused', 'applying'}:
            raise Issue('stage_ended', 410)
        return {'id': pending.id, 'stage': pending.stage, 'revision': pending.revision,
                'state': pending.state, 'matched_rule': pending.rule.id, 'deadline': pending.deadline,
                'original': message_json(pending.original)}

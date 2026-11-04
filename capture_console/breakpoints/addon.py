"""Per-capture transport adapter. No rules or interception are enabled on creation."""

import asyncio
from dataclasses import replace
import time
import weakref
import zlib
import sqlite3

from mitmproxy import http

from .engine import BreakpointEngine
from .models import BODY_LIMIT, Issue, Message


def message_of(flow, stage, body=b''):
    message = getattr(flow, stage)
    content_type = message.headers.get('content-type', '').split(';')[0].lower()
    editable = (not body and not content_type or content_type.startswith('text/')
                or content_type in {'application/json', 'application/x-www-form-urlencoded'}
                or content_type.endswith('+json'))
    editable &= content_type != 'text/event-stream'
    return Message(url=flow.request.url, method=flow.request.method,
                   headers=tuple(message.headers.items(multi=True)), body=body,
                   status=message.status_code if stage == 'response' else None,
                   protocol='h2' if message.is_http2 else message.http_version.lower(),
                   streaming=bool(message.stream), editable_body=bool(editable))


def decode(message):
    raw = message.raw_content or b''
    if len(raw) > BODY_LIMIT:
        return None
    encoding = message.headers.get('content-encoding', 'identity').lower()
    try:
        if encoding in {'gzip', 'deflate'}:
            decoder = zlib.decompressobj(31 if encoding == 'gzip' else 15)
            data = decoder.decompress(raw, BODY_LIMIT + 1)
            if not decoder.eof or decoder.unused_data:
                return None
        elif encoding in {'identity', ''}:
            data = raw
        else:
            # Brotli's output limit is not a hard allocation bound. Passthrough
            # until a bounded decoder is available; never call Message.content.
            return None
        if len(data) > BODY_LIMIT:
            return None
        data.decode('utf-8')
        return data
    except (UnicodeError, zlib.error):
        return None


class BreakpointAddon:
    def __init__(self, capture_id, device_id, root, *, archive=None, master=None):
        self.engine = BreakpointEngine(capture_id, device_id)
        self.engine.transport_attached = True
        self.root, self.archive, self.master = root, archive, master
        self.active = {}
        self.guards = weakref.WeakSet()
        self.config = {}
        self.flows = weakref.WeakValueDictionary()
        self.tasks = set()
        self.stream_callback = None

    def matched(self, flow):
        return flow.id in self.active

    def next_layer(self, nextlayer):
        from .guard import GuardLayer, install
        install(nextlayer, self, self.emit)
        if isinstance(nextlayer.layer, GuardLayer):
            self.guards.add(nextlayer.layer)

    def emit(self, kind, **fields):
        if kind == 'collection_expired':
            self.engine.disconnect(fields['id'])

    def candidate(self, flow, stage):
        message = getattr(flow, stage)
        try:
            size = int(message.headers.get('content-length', '0'))
            return (not message.stream and 0 <= size <= BODY_LIMIT
                    and not flow.request.headers.get('upgrade') and not message.trailers
                    and message.headers.get('content-encoding', 'identity').lower() in {'', 'identity', 'gzip', 'deflate'}
                    and message_of(flow, stage).editable_body)
        except (ValueError, UnicodeError):
            return False

    def requestheaders(self, flow):
        if not self.candidate(flow, 'request'):
            return
        try:
            admitted = self.engine.admit(flow.id, message_of(flow, 'request'),
                                        internal=flow.request.host == 'capture-check.invalid')
        except (Issue, UnicodeError):
            return
        if admitted:
            self.flows[flow.id] = flow
            if admitted.pending_id and not self.engine.reserve(flow.id, BODY_LIMIT, BODY_LIMIT):
                return
            self.active[flow.id] = {'mode': 'body'}

    def responseheaders(self, flow):
        if flow.id not in self.engine.flows:
            return
        if not self.candidate(flow, 'response'):
            self.bypass(flow)
            return
        pending = self.engine.response(flow.id, message_of(flow, 'response'))
        if pending and not self.engine.reserve(flow.id, BODY_LIMIT, BODY_LIMIT):
            self.bypass(flow)

    def collecting(self, flow, stage):
        entry = self.engine.flows.get(flow.id)
        return bool(entry and entry.current and entry.current.stage == stage
                    and entry.current.state == 'collecting')

    def progress(self, flow):
        entry = self.engine.flows.get(flow.id)
        if entry and entry.current and entry.current.state == 'collecting':
            entry.current.updated = self.engine.clock()

    def must_cancel(self, flow):
        entry = self.engine.flows.get(flow.id)
        return bool(entry and entry.current and entry.current.decision
                    and entry.current.decision.action == 'abort' or
                    flow.id in self.active and self.engine.drain_deadline is not None
                    and time.monotonic() >= self.engine.drain_deadline)

    def bypass(self, flow):
        self.engine.disconnect(flow.id)
        self.active.pop(flow.id, None)

    async def intercept(self, flow, stage):
        if not self.collecting(flow, stage):
            return
        message = getattr(flow, stage)
        decoded = None if message.stream or message.trailers else decode(message)
        if decoded is None:
            self.bypass(flow)
            return
        entry = self.engine.flows[flow.id]
        pending_id = entry.current.id
        original = self.archive.snapshot(flow, stage) if self.archive else None
        task = asyncio.current_task()
        self.tasks.add(task)
        flow.intercept()
        try:
            self.engine.pause(flow.id, replace(entry.current.original, body=decoded))
            decision = await self.engine.wait(pending_id)
            if decision.action == 'abort' or decision.effective is None:
                if flow.killable:
                    flow.kill()
            elif decision.action == 'apply':
                effective = decision.effective
                message.headers = http.Headers([(k.encode('utf-8'), v.encode('utf-8')) for k, v in effective.headers])
                if stage == 'request':
                    message.url, message.method = effective.url, effective.method
                else:
                    message.status_code = effective.status
                if effective.body != decision.original.body:
                    no_body = (flow.request.method == 'HEAD'
                               or stage == 'response' and effective.status in {204, 304})
                    if no_body:
                        message.raw_content = b''
                        for header in ('content-length', 'transfer-encoding', 'content-encoding'):
                            message.headers.pop(header, None)
                    else:
                        message.content = effective.body
            if self.archive and not self.archive.record_decision(flow, stage, original, decision.action, decision.reason):
                self.engine.stop()
                raise Issue('archive_unavailable', 503)
            self.engine.ack(pending_id, connected=not bool(flow.error))
        except (Issue, asyncio.CancelledError, OSError, sqlite3.Error):
            if self.archive and self.archive.closed:
                self.engine.stop()
            if flow.killable:
                flow.kill()
            self.engine.disconnect(flow.id)
        finally:
            flow.resume()
            self.tasks.discard(task)
            if flow.id not in self.engine.flows:
                self.active.pop(flow.id, None)

    async def request(self, flow):
        await self.intercept(flow, 'request')

    async def response(self, flow):
        await self.intercept(flow, 'response')
        self.bypass(flow)

    def error(self, flow):
        self.bypass(flow)

    def transport_error(self, flow):
        self.bypass(flow)
        if flow.killable:
            flow.kill()
        flow.resume()

    def client_disconnected(self, client):
        for flow in list(self.flows.values()):
            if flow.client_conn is client:
                self.engine.disconnect(flow.id)
                flow.resume()
                self.active.pop(flow.id, None)

    async def close(self):
        self.engine.stop()
        deadline = time.monotonic() + 3.1
        # ACK only releases the editor budget. HTTP can still be awaiting its
        # origin or draining its response after the engine entry has gone away.
        while (self.engine.flows or any(flow.live for flow in self.flows.values())
               or any(guard.transport_pending() for guard in self.guards)) and time.monotonic() < deadline:
            self.engine.tick()
            await asyncio.sleep(0.05)
        for flow in list(self.flows.values()):
            if flow.live and flow.killable:
                flow.kill()
                flow.resume()
            self.engine.disconnect(flow.id)
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        for guard in self.guards:
            guard.close_pending_transport()
        self.active.clear()

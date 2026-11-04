"""BP-0-only adapter for mitmproxy 12.2.3; no installed/global classes are patched.

The public next_layer hook selects this layer, but its HTTP internals are version
specific. Never load this experiment in the desktop runtime without BP-2 review.
"""

from collections import defaultdict
from importlib.metadata import version
import time

import h2.connection
import h2.events
import h2.exceptions
from mitmproxy.proxy import commands, events
from mitmproxy.proxy.layers.http import HttpLayer, HttpStream, HttpClient, RegisterHttpConnection, ReceiveHttp
from mitmproxy.proxy.layers.http._events import (
    ErrorCode, RequestData, RequestEndOfMessage, RequestHeaders, RequestProtocolError,
    ResponseData, ResponseEndOfMessage, ResponseHeaders, ResponseProtocolError,
)
from mitmproxy.proxy.layers.http._http1 import Http1Client
from mitmproxy.proxy.layers.http._http2 import Http2Connection, Http2Client
from mitmproxy.proxy.layers.http._http_h2 import BufferedH2Connection, SendH2Data


WINDOW = 65535
QUEUE_LIMIT = 256 * 1024
HEADER_LIMIT = 128 * 1024
CHUNK_LIMIT = 16 * 1024


def coalesce(queue, event):
    if (queue and type(queue[-1]) is type(event) and queue[-1].stream_id == event.stream_id
            and len(queue[-1].data) + len(event.data) <= CHUNK_LIMIT):
        queue[-1].data += event.data
        return True
    return False


def check_version(installed=None):
    if (installed or version('mitmproxy')) != '12.2.3':
        raise RuntimeError('BP0 transport adapter requires verified mitmproxy 12.2.3')


class WindowedH2(BufferedH2Connection):
    def __init__(self, config, blocked):
        super().__init__(config)
        self.local_settings.initial_window_size = WINDOW
        self.local_settings.max_concurrent_streams = 32
        if config.client_side:
            self.local_settings.enable_push = 0
        self.local_settings.acknowledge()
        self.credits = defaultdict(int)
        self.blocked = blocked

    def initiate_connection(self):
        # The base wrapper advertises a 2 GiB window; retain hyper-h2's default.
        h2.connection.H2Connection.initiate_connection(self)

    def acknowledge_received_data(self, acknowledged_size, stream_id):
        if not acknowledged_size or self.state_machine.state is h2.connection.ConnectionState.CLOSED:
            return
        # Replenish connection credit so a paused stream cannot stall siblings.
        self.increment_flow_control_window(acknowledged_size)
        if self.streams[stream_id].closed:
            self.credits.pop(stream_id, None)
            return
        self.credits[stream_id] += acknowledged_size
        self.release_credits()

    def release_credits(self):
        if self.state_machine.state is h2.connection.ConnectionState.CLOSED:
            self.credits.clear()
            return
        for stream_id, amount in list(self.credits.items()):
            if not self.streams[stream_id].closed and self.blocked(stream_id):
                continue
            try:
                self.increment_flow_control_window(amount, stream_id)
            except h2.exceptions.StreamClosedError:
                pass
            self.credits.pop(stream_id, None)

    def reset_stream(self, stream_id, error_code=0):
        self.credits.pop(stream_id, None)
        self.stream_trailers.pop(stream_id, None)
        super().reset_stream(stream_id, error_code)

    def send_data(self, stream_id, data, end_stream=False, pad_length=None):
        assert pad_length is None
        if not data and not end_stream:
            return
        queue = self.stream_buffers.get(stream_id)
        if (queue and not queue[-1].end_stream and len(queue[-1].data) + len(data) <= CHUNK_LIMIT):
            queue[-1] = SendH2Data(queue[-1].data + data, end_stream)
        else:
            super().send_data(stream_id, data, end_stream)

    def receive_data(self, data):
        received = super().receive_data(data)
        for event in received:
            if isinstance(event, h2.events.StreamReset):
                self.credits.pop(event.stream_id, None)
                self.stream_trailers.pop(event.stream_id, None)
            elif isinstance(event, h2.events.ConnectionTerminated):
                self.credits.clear()
                self.stream_trailers.clear()
        return received


class GuardH2Client(Http2Client):
    def __init__(self, context):
        super().__init__(context)
        self.closed_queue = []

    def _handle_event(self, event):
        if isinstance(event, RequestProtocolError) and event.stream_id not in self.our_stream_id:
            # A queued request has no upstream stream to reset. Never forward it later.
            self.stream_queue.pop(event.stream_id, None)
            return
        if isinstance(event, RequestData):
            if not event.data or coalesce(self.stream_queue.get(event.stream_id), event):
                return
        yield from super()._handle_event(event)
        # These ids are external flow ids and must not pass through the parent's
        # upstream-wire-id remapping, because they were never admitted upstream.
        queued, self.closed_queue = self.closed_queue, []
        for stream_id, message in queued:
            yield ReceiveHttp(ResponseProtocolError(stream_id, message, ErrorCode.GENERIC_SERVER_ERROR))

    def close_connection(self, msg):
        queued, self.stream_queue = self.stream_queue, defaultdict(list)
        self.closed_queue.extend((stream_id, msg) for stream_id in queued)
        yield from super().close_connection(msg)


class GuardClient(HttpClient):
    def __init__(self, context, owner):
        super().__init__(context)
        self.owner = owner

    def _handle_event(self, event):
        err = None if self.context.server.connected else (yield commands.OpenConnection(self.context.server))
        if not err:
            if self.context.server.alpn == b'h2':
                self.child_layer = GuardH2Client(self.context)
                self.owner.window(self.child_layer)
            else:
                self.child_layer = Http1Client(self.context)
            self._handle_event = self.child_layer.handle_event
            yield from self._handle_event(event)
        yield RegisterHttpConnection(self.context.server, err)


class GuardLayer(HttpLayer):
    def __init__(self, context, mode, probe, emit):
        super().__init__(context, mode)
        self.probe, self.emit = probe, emit
        self.collecting = {}
        self.h2_layers = set()
        self.tick = None
        self.read_gate = None

    def window(self, child):
        def blocked(wire_id):
            flow_id = child.their_stream_id.get(wire_id) if isinstance(child, Http2Client) else wire_id
            return self.buffered(flow_id) >= QUEUE_LIMIT
        child.h2_conn = WindowedH2(child.h2_conf, blocked)
        self.h2_layers.add(child)

    def upstream_client(self, child):
        parent = child
        while hasattr(parent, 'child_layer'):
            nested = parent.child_layer
            if type(nested) is HttpClient:
                nested.context.layers.remove(nested)
                parent.child_layer = GuardClient(nested.context, self)
                return
            parent = nested

    def buffered(self, flow_id):
        stream = self.streams.get(flow_id)
        queued = sum(len(event.data) for event in (stream._paused_event_queue if stream else ())
                     if isinstance(event, (RequestData, ResponseData)))
        for conn in self.h2_layers:
            wire_id = flow_id
            if isinstance(conn, Http2Client):
                wire_id = conn.our_stream_id.get(flow_id)
                queued += sum(len(event.data) for event in conn.stream_queue.get(flow_id, ())
                              if isinstance(event, RequestData))
            queued += sum(len(chunk.data) for chunk in conn.h2_conn.stream_buffers.get(wire_id, ()))
        return queued

    def event_to_child(self, child, event):
        # END_STREAM arrives separately as EndOfMessage; empty DATA has no body
        # semantics and must not extend deadlines or allocate paused queue entries.
        if isinstance(event, (RequestData, ResponseData)) and not event.data:
            return
        self.upstream_client(child)
        if isinstance(child, Http2Connection) and not isinstance(child.h2_conn, WindowedH2):
            self.window(child)
        if isinstance(child, HttpStream):
            now = time.monotonic()
            if isinstance(event, (RequestHeaders, ResponseHeaders)):
                stage = 'request' if isinstance(event, RequestHeaders) else 'response'
                self.collecting[child.stream_id] = [stage, now, now]
            elif isinstance(event, (RequestData, ResponseData)):
                collection = self.collecting.get(child.stream_id)
                if collection:
                    collection[2] = now
                if getattr(child, 'flow', None) and child.flow.intercepted:
                    size = len(event.data) + sum(len(item.data) for item in child._paused_event_queue
                                                if isinstance(item, (RequestData, ResponseData)))
                    config = self.probe.active.get(child.flow.id, {})
                    if size >= HEADER_LIMIT and config.get('mode') == 'headers':
                        stage = 'request' if isinstance(event, RequestData) else 'response'
                        getattr(child.flow, stage).stream = True
                        child.flow.resume()
                        self.emit('header_bypass', id=child.flow.id, stage=stage, buffered_bytes=size)
                if child._paused and coalesce(child._paused_event_queue, event):
                    return
            elif isinstance(event, (RequestEndOfMessage, ResponseEndOfMessage,
                                    RequestProtocolError, ResponseProtocolError)):
                self.collecting.pop(child.stream_id, None)
        yield from super().event_to_child(child, event)
        if isinstance(child, HttpStream) and isinstance(event, (RequestHeaders, ResponseHeaders)):
            stage = 'request' if isinstance(event, RequestHeaders) else 'response'
            child.flow.metadata[f'bp0_end_{stage}'] = event.end_stream

    def _handle_event(self, event):
        if isinstance(event, events.Wakeup) and event.command is self.tick:
            self.tick = None
            yield from self.expire_collections()
        else:
            yield from super()._handle_event(event)
        for conn in list(self.h2_layers):
            if not conn.conn.connected:
                self.h2_layers.discard(conn)
                continue
            # Feed credit frames through the owning TLS stack, not directly to its socket.
            if conn.h2_conn.credits:
                conn.h2_conn.release_credits()
                data = conn.h2_conn.data_to_send()
                if data:
                    root = self.connections[conn.conn]
                    if root is conn:
                        yield commands.SendData(conn.conn, data)
                    else:
                        # TunnelLayer routes child commands through TLS encryption.
                        yield from root._handle_command(commands.SendData(conn.conn, data))
        for stream_id in set(self.collecting) - self.streams.keys():
            self.collecting.pop(stream_id, None)
        for stream_id, (stage, _, _) in list(self.collecting.items()):
            flow = getattr(self.streams[stream_id], 'flow', None)
            message = getattr(flow, stage, None)
            if message and (message.stream or
                            flow.id not in self.probe.active and not self.probe.matched(flow)):
                self.collecting.pop(stream_id, None)
        if self.collecting and self.tick is None:
            self.tick = commands.RequestWakeup(0.05)
            yield self.tick
        if self.read_gate:
            self.read_gate.changed.set()

    def expire_collections(self):
        now = time.monotonic()
        for stream_id, (stage, started, updated) in list(self.collecting.items()):
            stream = self.streams.get(stream_id)
            flow = getattr(stream, 'flow', None)
            if not flow or flow.intercepted:
                continue
            config = self.probe.active.get(flow.id)
            message = getattr(flow, stage, None)
            if not config or message is None or message.stream:
                continue
            total = config.get('collect_timeout', 10)
            idle = config.get('collect_idle', 3)
            reason = 'total' if now - started >= total else 'idle' if now - updated >= idle else None
            if reason:
                self.collecting.pop(stream_id, None)
                self.emit('collection_expired', id=flow.id, stage=stage, reason=reason)
                if stage == 'response' and flow.server_conn in self.connections:
                    yield from super().event_to_child(self.connections[flow.server_conn],
                        RequestProtocolError(stream_id, 'BP0 collection expired', ErrorCode.CANCEL))
                # Drive the HTTP state machine, rather than only setting Flow.error.
                yield from super().event_to_child(stream,
                    ResponseProtocolError(stream_id, 'BP0 collection expired', ErrorCode.CANCEL))
                stream.request_body_buf.clear()
                stream.response_body_buf.clear()


def install(nextlayer, probe, emit):
    check_version()
    original = nextlayer.layer
    if type(original) is HttpLayer:
        original.context.layers.remove(original)
        nextlayer.layer = GuardLayer(original.context, original.mode, probe, emit)
        from tests.fixtures.breakpoints.read_gate import attach
        handler = probe.master.addons.get('proxyserver').connections[original.context.client.id]
        attach(handler, nextlayer.layer)

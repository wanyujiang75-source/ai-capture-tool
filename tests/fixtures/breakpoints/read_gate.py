"""Instance-scoped BP-0 H1 ingress gate for the verified mitmproxy runtime only."""

import asyncio
import weakref

from mitmproxy.proxy.layers.http._events import RequestData, ResponseData


class ReadGate:
    def __init__(self, handler):
        self.handler = handler
        self.original_drain = handler.drain_writers
        self.layers = weakref.WeakSet()
        self.changed = asyncio.Event()

    def buffered(self, connection):
        size = 0
        for layer in self.layers:
            for stream in layer.streams.values():
                flow = getattr(stream, 'flow', None)
                for event in stream._paused_event_queue:
                    if (isinstance(event, RequestData) and connection is layer.context.client
                            or isinstance(event, ResponseData) and flow and connection is flow.server_conn):
                        size += len(event.data)
        return size

    async def drain(self):
        await self.original_drain()
        task = asyncio.current_task()
        source = next((conn for conn, io in self.handler.transports.items() if io.handler is task), None)
        if source is None or source.alpn == b'h2':
            return
        # Gate the specific reader task, not the connection-wide event dispatcher.
        # Upstream TLS, timers, hooks and cancellation must remain runnable.
        layer = next(iter(self.layers), None)
        if layer is None:
            return
        try:
            # A blocked reader cannot observe EOF. Wakeups must not renew its lease.
            async with asyncio.timeout(layer.probe.config.get('transport_wait_timeout', 10)):
                while True:
                    self.changed.clear()
                    if self.buffered(source) < 256 * 1024:
                        return
                    await self.changed.wait()
        except TimeoutError:
            layer.emit('transport_wait_expired')
            if source is self.handler.client:
                # H1 has no concurrent sibling streams. Reclaim its owned upstream
                # handshakes too; closing only ingress leaves GetConnection waiting.
                for connection in list(self.handler.transports):
                    if connection is not source:
                        self.handler.close_connection(connection, False)
            self.handler.close_connection(source, False)


def attach(handler, layer):
    gate = getattr(handler, '_bp0_read_gate', None)
    if gate is None:
        gate = handler._bp0_read_gate = ReadGate(handler)
        handler.drain_writers = gate.drain
    gate.layers.add(layer)
    layer.read_gate = gate

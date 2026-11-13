"""Payload-free byte/closure counters on the existing opaque TCP relay."""

from mitmproxy.proxy import events
from mitmproxy.proxy.layers import tcp


class ObservedOpaqueTCP(tcp.TCPLayer):
    def __init__(self, context, diagnostics, host, role):
        super().__init__(context, ignore=True)
        self.diagnostics, self.host, self.role = diagnostics, host, role
        self.server_seen = False
        self.closed_seen = False

    def relay_messages(self, event):
        entry = self.diagnostics.entries.get((self.host, self.role, 'opaque'))
        if entry is not None:
            side = 'client' if event.connection == self.context.client else 'server'
            if isinstance(event, events.DataReceived):
                key = side + '_bytes'
                entry[key] = min(2**63 - 1, entry[key] + len(event.data))
                if side == 'server' and event.data and not self.server_seen:
                    entry['server_replied'] += 1
                    self.server_seen = True
            elif isinstance(event, events.ConnectionClosed) and not self.closed_seen:
                entry[side + '_closed_first'] += 1
                self.closed_seen = True
        yield from super().relay_messages(event)

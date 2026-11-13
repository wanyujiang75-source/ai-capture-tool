import unittest

from mitmproxy import connection, options
from mitmproxy.proxy import context, events, commands
from capture_console.android_physical_ad_routing import RoutingDiagnostics
from capture_console.android_physical_opaque_probe import ObservedOpaqueTCP


class OpaqueProbeTests(unittest.TestCase):
    def test_counts_without_retaining_or_modifying_bytes(self):
        client = connection.Client(peername=('127.0.0.1', 32100), sockname=('127.0.0.1', 443))
        ctx = context.Context(client, options.Options())
        ctx.server.timestamp_start = 1
        diagnostics = RoutingDiagnostics()
        diagnostics.record('ad.example', 'target', 'opaque')
        probe = ObservedOpaqueTCP(ctx, diagnostics, 'ad.example', 'target')
        list(probe.handle_event(events.Start()))
        payload = b'not-stored-client-secret'
        server_payload = b'not-stored-server-secret'
        for source, target, data in [(client, ctx.server, payload), (ctx.server, client, server_payload)]:
            emitted = list(probe.handle_event(events.DataReceived(source, data)))
            self.assertEqual(len(emitted), 1)
            self.assertIsInstance(emitted[0], commands.SendData)
            self.assertEqual((emitted[0].connection, emitted[0].data), (target, data))
        list(probe.handle_event(events.ConnectionClosed(client)))
        entry = diagnostics.summary()['entries'][0]
        self.assertEqual({key: entry[key] for key in ('client_bytes', 'server_bytes', 'server_replied',
                         'client_closed_first', 'server_closed_first')}, {
            'client_bytes': len(payload), 'server_bytes': len(server_payload), 'server_replied': 1,
            'client_closed_first': 1, 'server_closed_first': 0})
        self.assertIsNone(probe.flow)
        self.assertNotIn('not-stored', repr(vars(probe)) + repr(diagnostics.summary()))

    def test_server_closure_is_recorded_only_once_without_new_entry(self):
        client = connection.Client(peername=('127.0.0.1', 32100), sockname=('127.0.0.1', 443))
        ctx = context.Context(client, options.Options())
        ctx.server.timestamp_start = 1
        diagnostics = RoutingDiagnostics()
        probe = ObservedOpaqueTCP(ctx, diagnostics, 'missing.example', 'login')
        list(probe.handle_event(events.Start()))
        list(probe.handle_event(events.DataReceived(ctx.server, b'x')))
        self.assertEqual(diagnostics.summary()['entries'], [])
        diagnostics.record('missing.example', 'login', 'opaque')
        for _ in range(2):
            list(probe.relay_messages(events.ConnectionClosed(ctx.server)))
        entry = diagnostics.summary()['entries'][0]
        self.assertEqual(entry['server_closed_first'], 1)

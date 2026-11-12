import asyncio
import hashlib
import hmac
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from mitmproxy import connection, options
from mitmproxy.proxy import commands, context, events, layer
from mitmproxy.proxy.layers import tcp
from mitmproxy.proxy import mode_specs
from capture_console.android_physical_routing import ConnectionRouting, OwnerClient, RejectLayer


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    def request(self, transport='tcp', port=443):
        client = connection.Client(peername=('10.0.0.2', 45678), sockname=('1.2.3.4', port),
                                   transport_protocol=transport)
        ctx = context.Context(client, options.Options())
        ctx.server.address = ('1.2.3.4', port)
        ctx.server.transport_protocol = transport
        return SimpleNamespace(context=ctx, layer=object(), data_client=lambda: b'opaque')

    async def test_only_target_retains_capture_layer(self):
        route = ConnectionRouting(OwnerClient(1, 'secret'), ['127.0.0.1', 7897])
        route.owner.role = AsyncMock(return_value='target')
        item = self.request()
        original = item.layer
        await route.next_layer(item)
        self.assertIs(item.layer, original)
        route.owner.role.assert_awaited_once_with(item.context)

    async def test_unknown_rejected_not_decrypted_or_direct(self):
        for role in ('unknown', '', 'login-other'):
            route = ConnectionRouting(OwnerClient(1, 'secret'), ['127.0.0.1', 7897])
            route.owner.role = AsyncMock(return_value=role)
            item = self.request()
            await route.next_layer(item)
            self.assertIsInstance(item.layer, RejectLayer)
            result = list(item.layer.handle_event(events.Start()))
            self.assertTrue(all(isinstance(x, commands.CloseConnection) for x in result))

    async def test_login_has_connect_tunnel_and_no_flow(self):
        route = ConnectionRouting(OwnerClient(1, 'secret'), ['127.0.0.1', 7897])
        route.owner.role = AsyncMock(return_value='login')
        item = self.request()
        await route.next_layer(item)
        self.assertEqual(item.context.server.via, ('http', ('127.0.0.1', 7897)))
        self.assertTrue(item.layer.send_connect)
        self.assertIsInstance(item.layer.child_layer, tcp.TCPLayer)
        self.assertIsNone(item.layer.child_layer.flow)
        route.client_disconnected(item.context.client)
        self.assertFalse(route.roles)

    async def test_login_without_upstream_and_quic_fail_closed(self):
        route = ConnectionRouting(OwnerClient(1, 'secret'), None)
        route.owner.role = AsyncMock(return_value='login')
        for item in (self.request(), self.request('udp')):
            await route.next_layer(item)
            self.assertIsInstance(item.layer, RejectLayer)

    async def test_dns_keeps_existing_resolver_without_owner_lookup(self):
        route = ConnectionRouting(OwnerClient(1, 'secret'), None)
        route.owner.role = AsyncMock()
        item = self.request('udp', 53)
        item.context.server.address = ('10.0.0.53', 53)
        item.context.client.proxy_mode = mode_specs.ProxyMode.parse('wireguard')
        original = item.layer
        await route.next_layer(item)
        self.assertIs(item.layer, original)
        route.owner.role.assert_not_called()

    async def test_arbitrary_udp_dns_destination_is_not_forwarded(self):
        route = ConnectionRouting(OwnerClient(1, 'secret'), None)
        route.owner.role = AsyncMock()
        item = self.request('udp', 53)
        await route.next_layer(item)
        self.assertIsInstance(item.layer, RejectLayer)

    async def test_role_capacity_is_bounded_and_unexpected_error_cannot_leave_interceptor(self):
        route = ConnectionRouting(OwnerClient(1, 'secret'), ['127.0.0.1', 7897])
        route.roles = {str(index): 'target' for index in range(1024)}
        route.owner.role = AsyncMock()
        item = self.request()
        await route.next_layer(item)
        self.assertIsInstance(item.layer, RejectLayer)
        self.assertEqual(len(route.roles), 1024)
        route.owner.role.assert_not_called()
        route.roles.clear()
        route.owner.role.side_effect = RuntimeError('unexpected')
        item = self.request()
        with self.assertRaises(RuntimeError):
            await route.next_layer(item)
        self.assertIsNone(item.layer)

    async def test_concurrent_owner_queries_cannot_exceed_role_capacity(self):
        gate = asyncio.Event()
        async def role(ctx):
            await gate.wait()
            return 'target'
        route = ConnectionRouting(SimpleNamespace(role=role), ['127.0.0.1', 7897])
        route.roles = {str(index): 'target' for index in range(1023)}
        items = [self.request() for _ in range(8)]
        tasks = [asyncio.create_task(route.next_layer(item)) for item in items]
        await asyncio.sleep(0)
        gate.set()
        await asyncio.gather(*tasks)
        self.assertEqual(len(route.roles), 1024)
        self.assertEqual(sum(isinstance(item.layer, RejectLayer) for item in items), 7)

    async def test_malformed_and_oversized_owner_replies_fail_closed(self):
        for response in (b'not-json\n', b'{"role":"admin"}\n', b'{"role":"target"}\n', b'x' * 1024 + b'\n'):
            async def handle(reader, writer):
                await reader.readline()
                writer.write(response)
                await writer.drain()
                writer.close()
            server = await asyncio.start_server(handle, '127.0.0.1', 0)
            async with server:
                client = OwnerClient(server.sockets[0].getsockname()[1], 'secret')
                self.assertEqual(await client.role(self.request().context), 'unknown')

    async def test_replayed_signed_reply_is_bound_to_query_nonce(self):
        responses, queries = [], []
        async def handle(reader, writer):
            query = json.loads(await reader.readline())
            queries.append(query)
            if not responses:
                message = '\n'.join(map(str, [query['nonce'], *query['local'], *query['remote']]))
                proof = hmac.new(b'secret', ('reply\n' + message + '\nlogin').encode(), hashlib.sha256).hexdigest()
                responses.append(json.dumps({'role': 'login', 'proof': proof}).encode() + b'\n')
            writer.write(responses[0])
            await writer.drain()
            writer.close()
        server = await asyncio.start_server(handle, '127.0.0.1', 0)
        async with server:
            client = OwnerClient(server.sockets[0].getsockname()[1], 'secret')
            self.assertEqual(await client.role(self.request().context), 'login')
            self.assertEqual(await client.role(self.request().context), 'unknown')
        self.assertNotEqual(queries[0]['nonce'], queries[1]['nonce'])

    async def test_owner_query_validates_bounded_reply_and_disconnect(self):
        received = []
        async def handle(reader, writer):
            query = json.loads(await reader.readline())
            received.append(query)
            message = '\n'.join(map(str, [query['nonce'], *query['local'], *query['remote']]))
            self.assertEqual(query['proof'], hmac.new(b'secret', ('query\n' + message).encode(), hashlib.sha256).hexdigest())
            proof = hmac.new(b'secret', ('reply\n' + message + '\nlogin').encode(), hashlib.sha256).hexdigest()
            writer.write(json.dumps({'role': 'login', 'proof': proof}).encode() + b'\n')
            await writer.drain()
            writer.close()
        server = await asyncio.start_server(handle, '127.0.0.1', 0)
        port = server.sockets[0].getsockname()[1]
        client = OwnerClient(port, 'secret')
        async with server:
            self.assertEqual(await client.role(self.request().context), 'login')
        self.assertEqual(received[0]['local'], ['10.0.0.2', 45678])
        self.assertEqual(received[0]['remote'], ['1.2.3.4', 443])
        self.assertNotIn('secret', json.dumps(received))
        self.assertNotIn('token', received[0])
        self.assertEqual(await client.role(self.request().context), 'unknown')

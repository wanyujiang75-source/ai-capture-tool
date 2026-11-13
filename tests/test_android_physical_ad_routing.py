import unittest
import ssl
from types import SimpleNamespace
from unittest.mock import AsyncMock

from capture_console.android_physical_routing import ConnectionRouting, RejectLayer
from mitmproxy import connection, options
from mitmproxy.proxy import context
from mitmproxy.proxy.layers import tcp


def client_hello(host):
    incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
    client = ssl.create_default_context().wrap_bio(incoming, outgoing, server_hostname=host)
    try:
        client.do_handshake()
    except ssl.SSLWantReadError:
        return outgoing.read()


class AdRoutingTests(unittest.IsolatedAsyncioTestCase):
    def item(self, payload):
        client = connection.Client(peername=('10.0.0.2', 45000), sockname=('1.2.3.4', 443))
        ctx = context.Context(client, options.Options())
        ctx.server.address = ('1.2.3.4', 443)
        return SimpleNamespace(context=ctx, layer=object(), data_client=lambda: payload)

    def route(self, role='target', package='com.meta.inno.sticker', upstream=('127.0.0.1', 7897)):
        return ConnectionRouting(SimpleNamespace(role=AsyncMock(return_value=role)), upstream,
                                 package=package, ad_compatibility_probe=True)

    async def test_exact_ad_host_uses_original_tls_without_http_flow(self):
        route = self.route()
        item = self.item(client_hello('googleads.g.doubleclick.net'))
        await route.next_layer(item)
        self.assertEqual(item.context.server.address, ('googleads.g.doubleclick.net', 443))
        self.assertTrue(item.layer.send_connect)
        self.assertIsInstance(item.layer.child_layer, tcp.TCPLayer)
        self.assertIsNone(item.layer.child_layer.flow)
        self.assertEqual(route.diagnostics.summary()['entries'][0]['route'], 'opaque')

    async def test_unaccepted_policy_is_disabled_by_default(self):
        route = ConnectionRouting(SimpleNamespace(role=AsyncMock(return_value='target')),
                                  ('127.0.0.1', 7897), package='com.meta.inno.sticker')
        item = self.item(client_hello('googleads.g.doubleclick.net'))
        original = item.layer
        await route.next_layer(item)
        self.assertIs(item.layer, original)

    async def test_observed_sdk_dependency_is_exact_not_a_cdn_wildcard(self):
        for host in ('static.googleadsserving.cn', 'lh3.googleadsserving.cn', 'rr1---sn-i3belnls.gvt1.com',
                     'pagead2.googleadservices.com', 'fundingchoicesmessages.google.com'):
            item = self.item(client_hello(host))
            await self.route().next_layer(item)
            self.assertTrue(hasattr(item.layer, 'send_connect'))
            self.assertTrue(item.layer.send_connect)
        for host in ('other.gvt1.com', 'rr1---sn-i3belnls.gvt1.com.evil.example'):
            item = self.item(client_hello(host))
            original = item.layer
            await self.route().next_layer(item)
            self.assertIs(item.layer, original)

    async def test_business_mixed_unknown_hosts_and_other_packages_still_capture(self):
        for host, package in [('pbzhiqxtoqqgizddjblb.supabase.co', 'com.meta.inno.sticker'),
                              ('graph.facebook.com', 'com.meta.inno.sticker'),
                              ('googleads.g.doubleclick.net.evil.example', 'com.meta.inno.sticker'),
                              ('unknown.example', 'com.meta.inno.sticker'),
                              ('googleads.g.doubleclick.net', 'another.package'),
                              (None, 'com.meta.inno.sticker')]:
            with self.subTest(host=host, package=package):
                item = self.item(client_hello(host))
                original = item.layer
                await self.route(package=package).next_layer(item)
                self.assertIs(item.layer, original)

    async def test_render_dependencies_do_not_expand_shared_font_namespaces(self):
        hosts = ('www.gstatic.com', 'www.googletagservices.com', 'tpc.googlesyndication.com',
                 'fonts.googleapis.com', 'fonts.gstatic.com')
        for host in hosts:
            with self.subTest(host=host):
                item = self.item(client_hello(host))
                await self.route().next_layer(item)
                self.assertTrue(hasattr(item.layer, 'child_layer'), 'render dependency was intercepted')
                self.assertIsInstance(item.layer.child_layer, tcp.TCPLayer)
                self.assertIsNone(item.layer.child_layer.flow)
                non_matches = [host + '.evil.example']
                if host != 'tpc.googlesyndication.com':
                    non_matches.append('sub.' + host)
                for other in non_matches:
                    item = self.item(client_hello(other))
                    original = item.layer
                    await self.route().next_layer(item)
                    self.assertIs(item.layer, original)
                item = self.item(client_hello(host))
                original = item.layer
                await self.route(package='other.package').next_layer(item)
                self.assertIs(item.layer, original)

    async def test_fragmented_hello_waits_then_routes_without_repeat_owner_query(self):
        payload = client_hello('pagead2.googlesyndication.com')
        route = self.route()
        item = self.item(b'')
        await route.next_layer(item)
        self.assertIsNone(item.layer)
        item.data_client = lambda: payload[:5]
        await route.next_layer(item)
        self.assertIsNone(item.layer)
        self.assertEqual(route.diagnostics.summary()['entries'], [])
        item.data_client = lambda: payload
        await route.next_layer(item)
        self.assertTrue(item.layer.send_connect)
        route.owner.role.assert_awaited_once()

    async def test_ad_service_rotation_is_bounded_by_domain_and_package(self):
        for host in ('googleads4.g.doubleclick.net', 'www.googleadservices.com',
                     's0.2mdn.net', 's1.2mdn.net', 'new.googlesyndication.com'):
            with self.subTest(host=host):
                item = self.item(client_hello(host))
                await self.route().next_layer(item)
                self.assertTrue(hasattr(item.layer, 'send_connect'))
                self.assertIsNone(item.layer.child_layer.flow)
                item = self.item(client_hello(host))
                original = item.layer
                await self.route(package='other.package').next_layer(item)
                self.assertIs(item.layer, original)
        for host in ('evildoubleclick.net', 'doubleclick.net.evil.example',
                     '2mdn.net.evil.example', 'other.gstatic.com', 'other.googleapis.com',
                     'new.gvt1.com', 'pbzhiqxtoqqgizddjblb.supabase.co'):
            item = self.item(client_hello(host))
            original = item.layer
            await self.route().next_layer(item)
            self.assertIs(item.layer, original)

    async def test_malformed_oversized_and_unknown_owner_fail_closed(self):
        for payload, role in [(b'\x16' + b'X' * 65536, 'target'),
                              (b'\x16\x03\x03\x00\x05\x00\x00\x00\x01\xff', 'target'),
                              (client_hello('googleads.g.doubleclick.net'), 'unknown')]:
            item = self.item(payload)
            await self.route(role=role).next_layer(item)
            self.assertIsInstance(item.layer, RejectLayer)

    async def test_ad_without_upstream_rejects_and_plain_or_decrypted_target_is_unchanged(self):
        item = self.item(client_hello('googleads.g.doubleclick.net'))
        await self.route(upstream=None).next_layer(item)
        self.assertIsInstance(item.layer, RejectLayer)
        for payload in (b'GET / HTTP/1.1\r\n\r\n', client_hello('googleads.g.doubleclick.net')):
            item = self.item(payload)
            item.context.client.tls = True
            item.context.client.timestamp_tls_setup = 1
            original = item.layer
            await self.route().next_layer(item)
            self.assertIs(item.layer, original)


class AdDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_target_tls_failure_is_attributed_without_payload(self):
        route = ConnectionRouting(SimpleNamespace(role=AsyncMock()), ['127.0.0.1', 7897])
        client = SimpleNamespace(id='a', sni='googleads.g.doubleclick.net')
        route.roles['a'] = 'target'
        data = SimpleNamespace(context=SimpleNamespace(client=client),
                               client_hello=SimpleNamespace(sni=client.sni))
        self.assertTrue(hasattr(route, 'diagnostics'))
        route.tls_clienthello(data)
        route.tls_failed_client(data)
        self.assertEqual(route.diagnostics.summary(), {
            'entries': [{'host': client.sni, 'role': 'target', 'route': 'capture',
                         'connections': 1, 'tls_failures': 1}], 'overflow': 0})

    async def test_diagnostics_are_bounded_and_reject_non_host_content(self):
        route = ConnectionRouting(None, None)
        self.assertTrue(hasattr(route, 'diagnostics'))
        for index in range(100):
            route.diagnostics.record(f'host{index}.example', 'target', 'capture')
        summary = route.diagnostics.summary()
        self.assertEqual(len(summary['entries']), 64)
        self.assertEqual(summary['overflow'], 36)
        route.diagnostics.record('host.example/path?token=secret', 'target', 'capture')
        self.assertNotIn('secret', str(route.diagnostics.summary()))


if __name__ == '__main__':
    unittest.main()

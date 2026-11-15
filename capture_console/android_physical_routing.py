"""Separate app capture from opaque login-service forwarding before TLS starts."""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import secrets

from mitmproxy.proxy import commands, events, layer, mode_specs
from mitmproxy.proxy.layers import tcp
from mitmproxy.proxy.layers.http._upstream_proxy import HttpUpstreamProxy
from mitmproxy.proxy.layers.tls import parse_client_hello
from .android_physical_ad_routing import (
    POKE_VIDEO_HOSTS, RoutingDiagnostics, STICKER_AD_DOMAINS, STICKER_AD_HOSTS,
)
from .android_physical_opaque_probe import ObservedOpaqueTCP


class OwnerClient:
    def __init__(self, port, token):
        self.port, self.token = port, token
        self.slots = asyncio.Semaphore(32)

    async def role(self, ctx):
        writer = None
        try:
            async with asyncio.timeout(2), self.slots:
                local, remote = ctx.client.peername, ctx.server.address
                for address in (local, remote):
                    ipaddress.ip_address(address[0])
                    if not 0 < address[1] < 65536:
                        return 'unknown'
                reader, writer = await asyncio.open_connection('127.0.0.1', self.port, limit=512)
                nonce = secrets.token_hex(16)
                message = '\n'.join(map(str, [nonce, *local[:2], *remote[:2]]))
                key = self.token.encode()
                query = {'nonce': nonce, 'local': list(local[:2]), 'remote': list(remote[:2]),
                         'proof': hmac.new(key, ('query\n' + message).encode(), hashlib.sha256).hexdigest()}
                writer.write(json.dumps(query).encode() + b'\n')
                await writer.drain()
                reply = json.loads(await reader.readline())
                role = reply.get('role')
                if role not in ('target', 'login', 'unknown'):
                    return 'unknown'
                expected = hmac.new(key, ('reply\n' + message + '\n' + role).encode(), hashlib.sha256).hexdigest()
                if not hmac.compare_digest(expected, reply.get('proof', '')):
                    return 'unknown'
                return role if role in ('target', 'login') else 'unknown'
        except (OSError, TimeoutError, ValueError, TypeError, AttributeError, IndexError):
            return 'unknown'
        finally:
            if writer:
                writer.close()


class RejectLayer(layer.Layer):
    def _handle_event(self, event):
        if isinstance(event, events.Start):
            yield commands.CloseConnection(self.context.client)


class ObservedUpstreamProxy(HttpUpstreamProxy):
    observer = None

    def receive_handshake_data(self, data):
        done, error = yield from super().receive_handshake_data(data)
        if self.observer is not None and (done or error):
            diagnostics, host, role = self.observer
            diagnostics.record_connect(host, role, done and not error)
            self.observer = None
        return done, error


class ConnectionRouting:
    def __init__(self, owner, upstream, *, package='', ad_compatibility_probe=False):
        self.owner, self.upstream = owner, upstream
        # StickerHub Banner is accepted; PokeHub video remains an opt-in probe.
        # Never inherit another app's hosts or learn bypasses from TLS failures.
        probing_ads = package == 'com.meta.inno.sticker' or (
            ad_compatibility_probe is True and package == 'com.mi.poketrade'
        )
        self.ad_hosts = frozenset()
        if probing_ads:
            self.ad_hosts = STICKER_AD_HOSTS if package == 'com.meta.inno.sticker' else POKE_VIDEO_HOSTS
        self.ad_domains = STICKER_AD_DOMAINS if probing_ads and package == 'com.meta.inno.sticker' else ()
        self.probing_ads = probing_ads
        self.roles = {}
        self.diagnostics = RoutingDiagnostics()

    async def next_layer(self, data):
        ctx = data.context
        if ctx.server.transport_protocol == 'udp':
            # Only the tunnel's virtual resolver is exempt from app-UID lookup:
            # Android's DNS service may own these sockets. Arbitrary UDP is not.
            if (ctx.server.address == ('10.0.0.53', 53)
                    and isinstance(ctx.client.proxy_mode, mode_specs.WireGuardMode)):
                return
            data.layer = RejectLayer(ctx)
            return
        original_layer = data.layer
        # Any unexpected hook failure must not leave the default TLS interceptor enabled.
        data.layer = None
        key = ctx.client.id
        if key not in self.roles:
            if len(self.roles) >= 1024:
                data.layer = RejectLayer(ctx)
                return
            role = await self.owner.role(ctx)
            # Other connections may fill the cache while this query is suspended.
            if key not in self.roles and len(self.roles) >= 1024:
                data.layer = RejectLayer(ctx)
                return
            self.roles[key] = role
            if self.probing_ads:
                self.diagnostics.owner_roles[role if role in ('target', 'login') else 'unknown'] += 1
        role = self.roles[key]
        # Constructing the default TLS layer sets client.tls before this hook.
        # Only a completed handshake means these are already decrypted bytes.
        if role == 'target' and (not self.ad_hosts or ctx.client.timestamp_tls_setup is not None):
            data.layer = original_layer
            return
        if role not in ('target', 'login'):
            data.layer = RejectLayer(ctx)
            return
        # A TLS ClientHello provides the destination for VPN fake-IP cache entries.
        # Never terminate TLS: the original bytes go through CONNECT unchanged.
        payload = data.data_client()
        # Wait for client bytes before choosing an IP or SNI CONNECT destination.
        if not payload:
            self.diagnostics.empty_client_waits[role] += 1
            return
        host = None
        if payload[:1] == b'\x16':
            if len(payload) > 65536:
                data.layer = RejectLayer(ctx)
                return
            try:
                hello = parse_client_hello(payload)
            except ValueError:
                data.layer = RejectLayer(ctx)
                return
            if hello is None:
                data.layer = None
                return
            if hello.sni:
                host = hello.sni.lower().rstrip('.')
        is_ad_dependency = host in self.ad_hosts or bool(host and any(
            host == domain or host.endswith('.' + domain) for domain in self.ad_domains))
        if role == 'target' and not is_ad_dependency:
            data.layer = original_layer
            return
        if not self.upstream:
            data.layer = RejectLayer(ctx)
            return
        if host:
            ctx.server.address = (host, ctx.server.address[1])
            self.diagnostics.record(host, role, 'opaque')
        ctx.server.via = ('http', tuple(self.upstream))
        stack = ObservedUpstreamProxy.make(ctx, True)
        stack[-1].observer = (self.diagnostics, host, role)
        stack /= (ObservedOpaqueTCP(ctx, self.diagnostics, host, role) if self.probing_ads
                  else tcp.TCPLayer(ctx, ignore=True))
        data.layer = stack[0]

    def client_disconnected(self, client):
        self.roles.pop(client.id, None)

    def tls_clienthello(self, data):
        self.diagnostics.record(data.client_hello.sni, self.roles.get(data.context.client.id, 'unknown'), 'capture')

    def tls_failed_client(self, data):
        self.diagnostics.record(data.context.client.sni, self.roles.get(data.context.client.id, 'unknown'),
                                'capture', failure=True)

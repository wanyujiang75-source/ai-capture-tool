"""Loopback TLS/CONNECT acceptance: no phone, VPN, credentials or external network."""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import AsyncMock

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from mitmproxy import options
from mitmproxy.tools.dump import DumpMaster
from capture_console.android_physical_routing import ConnectionRouting


class OpaqueWireTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_tls_preserves_origin_certificate_and_skips_http_hooks(self):
        await self.exercise('login', True)

    async def test_upstream_refusal_never_falls_back_to_direct_origin(self):
        await self.exercise('login', False)

    async def test_unknown_owner_never_contacts_upstream_or_origin(self):
        await self.exercise('unknown', True)

    async def test_target_ad_preserves_original_certificate_and_skips_http(self):
        await self.exercise('target', True, host='googleads.g.doubleclick.net')

    async def test_target_ad_upstream_refusal_has_no_direct_fallback(self):
        await self.exercise('target', False, host='pagead2.googlesyndication.com')

    async def exercise(self, role, upstream_accepts, host='localhost'):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
            cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                    .serial_number(x509.random_serial_number())
                    .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
                    .not_valid_after(datetime.now(timezone.utc) + timedelta(hours=1))
                    .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), False)
                    .sign(key, hashes.SHA256()))
            (root / 'cert').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            (root / 'key').write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                      serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(root / 'cert', root / 'key')
            received, connects, http_flows = [], [], []

            async def origin(reader, writer):
                received.append(await reader.readuntil(b'\r\n\r\n'))
                writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK')
                await writer.drain()
                writer.close()

            async def pipe(reader, writer):
                try:
                    while block := await reader.read(16384):
                        writer.write(block)
                        await writer.drain()
                finally:
                    writer.close()

            upstream_origin = await asyncio.start_server(origin, '127.0.0.1', 0, ssl=tls)
            origin_port = upstream_origin.sockets[0].getsockname()[1]

            async def upstream(reader, writer):
                connects.append(await reader.readuntil(b'\r\n\r\n'))
                if not upstream_accepts:
                    writer.write(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n')
                    await writer.drain()
                    writer.close()
                    return
                other_reader, other_writer = await asyncio.open_connection('127.0.0.1', origin_port)
                writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                await writer.drain()
                await asyncio.gather(pipe(reader, other_writer), pipe(other_reader, writer), return_exceptions=True)

            proxy = await asyncio.start_server(upstream, '127.0.0.1', 0)
            proxy_port = proxy.sockets[0].getsockname()[1]
            master = DumpMaster(options.Options(confdir=str(root / 'ca'), listen_host='127.0.0.1', listen_port=0,
                               mode=[f'reverse:tcp://127.0.0.1:{origin_port}']), with_termlog=False, with_dumper=False)
            master.options.update(connection_strategy='lazy')
            owner = type('Owner', (), {'role': AsyncMock(return_value=role)})()
            routing = ConnectionRouting(owner, ['127.0.0.1', proxy_port],
                                        package='com.meta.inno.sticker', ad_compatibility_probe=True)
            master.addons.add(routing)
            class Spy:
                def request(self, flow): http_flows.append(flow)
                def response(self, flow): http_flows.append(flow)
            master.addons.add(Spy())
            task = asyncio.create_task(master.run())
            try:
                for _ in range(100):
                    servers = list(master.addons.get('proxyserver').servers)
                    if servers and servers[0].listen_addrs: break
                    await asyncio.sleep(.02)
                listen_port = servers[0].listen_addrs[0][1]
                trust = ssl.create_default_context(cafile=str(root / 'cert'))
                if role == 'unknown' or not upstream_accepts:
                    async with asyncio.timeout(5):
                        with self.assertRaises((OSError, ConnectionError)):
                            await asyncio.open_connection('127.0.0.1', listen_port, ssl=trust, server_hostname=host)
                    self.assertEqual(received, [])
                    self.assertEqual(http_flows, [])
                    self.assertEqual(len(connects), 0 if role == 'unknown' else 1)
                    entries = routing.diagnostics.summary()['entries']
                    if role != 'unknown':
                        self.assertEqual(entries[0]['connect_rejected'], 1)
                        self.assertEqual(entries[0]['connect_accepted'], 0)
                    return
                async with asyncio.timeout(5):
                    reader, writer = await asyncio.open_connection('127.0.0.1', listen_port, ssl=trust, server_hostname=host)
                    self.assertEqual(writer.get_extra_info('ssl_object').getpeercert(binary_form=True),
                                     cert.public_bytes(serialization.Encoding.DER))
                    writer.write(f'GET /synthetic HTTP/1.1\r\nHost: {host}\r\n\r\n'.encode())
                    await writer.drain()
                    self.assertTrue((await reader.read()).endswith(b'OK'))
                    writer.close()
                    await writer.wait_closed()
                self.assertEqual(len(received), 1)
                self.assertIn(f'CONNECT {host}:{origin_port} HTTP/1.1'.encode(), connects[0])
                self.assertEqual(http_flows, [])
                entry = routing.diagnostics.summary()['entries'][0]
                self.assertEqual((entry['connect_accepted'], entry['connect_rejected']), (1, 0))
            finally:
                await master.addons.get('proxyserver').servers.update([])
                master.shutdown()
                await task
                proxy.close()
                upstream_origin.close()
                await proxy.wait_closed()
                await upstream_origin.wait_closed()

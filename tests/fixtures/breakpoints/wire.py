"""Loopback-only HTTP/1.1 and HTTP/2 wire peers; no system trust or proxy changes."""

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import ssl

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import h11
import h2.config
import h2.connection
import h2.events


def certificates(root):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'BP0 Loopback Only')])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), False)
            .sign(key, hashes.SHA256()))
    pem, private = root / 'origin.pem', root / 'origin.key'
    pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption()))
    private.chmod(0o600)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(pem, private)
    context.set_alpn_protocols(['h2', 'http/1.1'])
    return pem, context


class Wire:
    def __init__(self, reader, writer, *, client):
        self.reader, self.writer, self.client = reader, writer, client
        tls = writer.get_extra_info('ssl_object')
        self.protocol = tls.selected_alpn_protocol() if tls else 'http/1.1'
        self.events = asyncio.Queue(maxsize=8)
        self.window = asyncio.Event()
        self.sent_bytes = 0
        if self.protocol == 'h2':
            self.codec = h2.connection.H2Connection(config=h2.config.H2Configuration(
                client_side=client, header_encoding='utf-8'))
            self.codec.initiate_connection()
            writer.write(self.codec.data_to_send())
        else:
            self.codec = h11.Connection(h11.CLIENT if client else h11.SERVER)
        self.task = asyncio.create_task(self._receive())

    async def _receive(self):
        try:
            while data := await self.reader.read(65536):
                if self.protocol == 'h2':
                    for event in self.codec.receive_data(data):
                        if isinstance(event, (h2.events.RequestReceived, h2.events.ResponseReceived)):
                            await self.events.put(('headers', event.headers))
                        elif isinstance(event, h2.events.DataReceived):
                            await self.events.put(('data', event.data))
                            self.codec.acknowledge_received_data(event.flow_controlled_length, event.stream_id)
                        elif isinstance(event, h2.events.StreamEnded):
                            await self.events.put(('end', None))
                        elif isinstance(event, (h2.events.StreamReset, h2.events.ConnectionTerminated)):
                            await self.events.put(('closed', str(event)))
                        elif isinstance(event, (h2.events.WindowUpdated, h2.events.RemoteSettingsChanged)):
                            self.window.set()
                    self.writer.write(self.codec.data_to_send())
                    await self.writer.drain()
                else:
                    self.codec.receive_data(data)
                    while True:
                        event = self.codec.next_event()
                        if event in (h11.NEED_DATA, h11.PAUSED):
                            break
                        if isinstance(event, (h11.Request, h11.Response)):
                            headers = [(k.decode(), v.decode()) for k, v in event.headers]
                            if isinstance(event, h11.Request):
                                headers += [(':path', event.target.decode()), (':method', event.method.decode())]
                            else:
                                headers += [(':status', str(event.status_code))]
                            await self.events.put(('headers', headers))
                        elif isinstance(event, h11.Data):
                            await self.events.put(('data', bytes(event.data)))
                        elif isinstance(event, h11.EndOfMessage):
                            await self.events.put(('end', None))
        except (OSError, h11.RemoteProtocolError, h2.exceptions.ProtocolError) as error:
            await self.events.put(('closed', type(error).__name__))
        finally:
            self.window.set()
            if not asyncio.current_task().cancelling():
                await self.events.put(('closed', 'eof'))

    async def headers(self, fields):
        fields = [(k.lower(), str(v)) for k, v in fields]
        if self.protocol == 'h2':
            self.codec.send_headers(1, fields)
            self.writer.write(self.codec.data_to_send())
        else:
            info = dict(fields)
            headers = [(k, v) for k, v in fields if not k.startswith(':')]
            if self.client:
                headers.append(('host', info[':authority']))
                event = h11.Request(method=info[':method'], target=info[':path'], headers=headers)
            else:
                event = h11.Response(status_code=int(info[':status']), headers=headers)
            self.writer.write(self.codec.send(event))
        await self.writer.drain()

    async def data(self, data):
        if self.protocol != 'h2':
            self.writer.write(self.codec.send(h11.Data(data=data)))
            await self.writer.drain()
            self.sent_bytes += len(data)
            return
        offset = 0
        while offset < len(data):
            count = min(self.codec.local_flow_control_window(1), self.codec.max_outbound_frame_size,
                        len(data) - offset)
            if count <= 0:
                if self.task.done():
                    raise ConnectionError('closed while waiting for window')
                self.window.clear()
                await asyncio.wait_for(self.window.wait(), 8)
                continue
            self.codec.send_data(1, data[offset:offset + count])
            self.writer.write(self.codec.data_to_send())
            await self.writer.drain()
            offset += count
            self.sent_bytes += count

    async def end(self):
        if self.protocol == 'h2':
            self.codec.end_stream(1)
            self.writer.write(self.codec.data_to_send())
        else:
            self.writer.write(self.codec.send(h11.EndOfMessage()))
        await self.writer.drain()

    async def close(self):
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
        self.writer.close()
        try:
            await asyncio.wait_for(self.writer.wait_closed(), 1)
        except (OSError, TimeoutError):
            pass


class Exchange:
    def __init__(self, wire):
        self.wire = wire
        self.headers_seen = asyncio.Event()
        self.ended = asyncio.Event()
        self.headers = []
        self.size = 0
        self.digest = hashlib.sha256()
        self.preview = bytearray()
        self.task = asyncio.create_task(self.read())

    async def read(self):
        while True:
            kind, value = await self.wire.events.get()
            if kind == 'headers':
                self.headers = value
                self.headers_seen.set()
            elif kind == 'data':
                self.size += len(value)
                self.digest.update(value)
                self.preview.extend(value[:max(0, 262144 - len(self.preview))])
            elif kind in {'end', 'closed'}:
                self.ended.set()
                return kind

    async def close(self):
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
        await self.wire.close()


class Origin:
    def __init__(self):
        self.records = []
        self.responses = {}
        self.peers = []
        self.tasks = set()
        self.server = None

    async def start(self, context):
        self.server = await asyncio.start_server(self.accept, '127.0.0.1', 0, ssl=context)
        self.port = self.server.sockets[0].getsockname()[1]

    async def accept(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        wire = Wire(reader, writer, client=False)
        self.peers.append(wire)
        record = None
        try:
            while True:
                kind, value = await wire.events.get()
                if kind == 'headers':
                    record = {'headers': value, 'size': 0, 'digest': hashlib.sha256(),
                              'preview': bytearray(), 'protocol': wire.protocol, 'ended': False, 'wire': wire}
                    self.records.append(record)
                elif kind == 'data':
                    record['size'] += len(value)
                    record['digest'].update(value)
                    record['preview'].extend(value[:max(0, 262144 - len(record['preview']))])
                elif kind == 'end':
                    record['ended'] = True
                    path = dict(record['headers'])[':path'].split('?')[0]
                    config = self.responses.get(path, {})
                    body = config.get('body', b'{"origin":true}')
                    size = config.get('size', len(body))
                    headers = [(':status', '200'), ('content-type', 'application/json')]
                    headers += config.get('headers', [])
                    if not config.get('unknown'):
                        headers.append(('content-length', str(size)))
                    await wire.headers(headers)
                    sent = 0
                    while sent < size:
                        chunk = (b'x' * min(16384, size - sent) if 'size' in config
                                 else body[sent:sent + 16384])
                        await wire.data(chunk)
                        sent += len(chunk)
                        if config.get('delay'):
                            await asyncio.sleep(config['delay'])
                    if config.get('hang'):
                        await asyncio.Event().wait()
                    await wire.end()
                    return
                elif kind == 'closed':
                    return
        except (ConnectionError, TimeoutError, h2.exceptions.ProtocolError, h11.LocalProtocolError):
            pass
        finally:
            self.tasks.discard(task)

    async def close(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for peer in self.peers:
            await peer.close()


async def client(proxy_port, origin_port, ca, protocol='http/1.1'):
    reader, writer = await asyncio.open_connection('127.0.0.1', proxy_port)
    wire = None
    try:
        writer.write(f'CONNECT 127.0.0.1:{origin_port} HTTP/1.1\r\nHost: 127.0.0.1:{origin_port}\r\n\r\n'.encode())
        await writer.drain()
        reply = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 5)
        if not reply.startswith(b'HTTP/1.1 200'):
            raise AssertionError(reply)
        trust = ssl.create_default_context(cafile=ca)
        trust.set_alpn_protocols([protocol])
        await asyncio.wait_for(writer.start_tls(trust, server_hostname='127.0.0.1'), 5)
        wire = Wire(reader, writer, client=True)
        if wire.protocol != protocol:
            raise AssertionError(f'ALPN {wire.protocol} != {protocol}')
        return Exchange(wire)
    except BaseException:
        if wire:
            await wire.close()
        else:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), 1)
            except (OSError, TimeoutError):
                pass
        raise

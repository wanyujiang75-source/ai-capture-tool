"""Bounded, authenticated per-worker Unix socket. No ambient runtime paths."""

import asyncio
from dataclasses import dataclass
import hmac
import json
import os
from pathlib import Path
import secrets

from pydantic import ValidationError

from .control import Empty, dispatch, error_json
from .models import FRAME_LIMIT, Issue


class Envelope(Empty):
    version: int
    token: str
    epoch: str
    capture_id: str
    device_id: str
    command: str
    payload: dict


async def read_frame(reader):
    size = int.from_bytes(await reader.readexactly(4), 'big')
    if not 0 < size <= FRAME_LIMIT:
        raise Issue('frame_too_large', 413)
    try:
        return json.loads(await reader.readexactly(size))
    except (ValueError, UnicodeError, RecursionError):
        raise Issue('invalid_command', 422) from None


async def write_frame(writer, payload):
    try:
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    except (ValueError, UnicodeError, RecursionError):
        raise Issue('invalid_command', 422) from None
    if len(raw) > FRAME_LIMIT:
        raise Issue('frame_too_large', 413)
    writer.write(len(raw).to_bytes(4, 'big') + raw)
    await writer.drain()


async def close_writer(writer):
    writer.close()
    try:
        await asyncio.wait_for(writer.wait_closed(), 1)
    except (OSError, TimeoutError):
        writer.transport.abort()
    except asyncio.CancelledError:
        writer.transport.abort()
        raise


class WorkerServer:
    def __init__(self, root, engine):
        self.root = Path(root)
        self.path = self.root / 'control.sock'
        self.engine = engine
        self.token = secrets.token_urlsafe(32)
        self.server = None
        self.timer = None
        self.tasks = set()
        self.inode = None
        self.root_inode = None

    async def start(self):
        if os.name == 'nt' or len(os.fsencode(self.path)) > 100:
            raise Issue('unsupported_socket_path', 422)
        try:
            self.root.mkdir(mode=0o700)
        except OSError:
            raise Issue('socket_directory_unavailable', 503) from None
        try:
            info = self.root.lstat()
            self.root_inode = (info.st_dev, info.st_ino)
            os.chmod(self.root, 0o700)
            self.server = await asyncio.start_unix_server(self.accept, path=self.path, limit=FRAME_LIMIT + 4)
            info = self.path.lstat()
            self.inode = (info.st_dev, info.st_ino)
            os.chmod(self.path, 0o600)
            self.engine.owner_loop = asyncio.get_running_loop()
            self.timer = asyncio.create_task(self.engine.run_clock())
        except BaseException:
            await self.close()
            raise

    def accept(self, reader, writer):
        if len(self.tasks) >= 8:
            writer.transport.abort()
            return
        task = asyncio.create_task(self.serve(reader, writer))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def serve(self, reader, writer):
        try:
            try:
                async with asyncio.timeout(3):
                    raw = await read_frame(reader)
                    try:
                        envelope = Envelope.model_validate(raw)
                    except ValidationError:
                        raise Issue('invalid_command', 422) from None
                    if not hmac.compare_digest(envelope.token.encode(), self.token.encode()):
                        raise Issue('unauthorized', 401)
                    if envelope.version != 1:
                        raise Issue('invalid_command', 422)
                    if (envelope.epoch, envelope.capture_id, envelope.device_id) != (
                            self.engine.epoch, self.engine.capture_id, self.engine.device_id):
                        raise Issue('target_conflict')
                    result = dispatch(self.engine, envelope.command, envelope.payload)
                    await write_frame(writer, {'version': 1, 'data': result})
            except Issue as issue:
                async with asyncio.timeout(1):
                    await write_frame(writer, {'version': 1, 'error': error_json(issue)})
            except (ValueError, TypeError, UnicodeError, RecursionError):
                async with asyncio.timeout(1):
                    await write_frame(writer, {'version': 1, 'error': error_json(Issue('invalid_command', 422))})
        except (OSError, TimeoutError, asyncio.IncompleteReadError):
            pass
        finally:
            await close_writer(writer)

    async def close(self):
        closing = self.server
        if self.server:
            self.server.close()
            self.server = None
        self.engine.stop()
        deadline = asyncio.get_running_loop().time() + 3.1
        while self.engine.flows and asyncio.get_running_loop().time() < deadline:
            self.engine.tick()
            await asyncio.sleep(0.05)
        if self.timer:
            self.timer.cancel()
            await asyncio.gather(self.timer, return_exceptions=True)
            self.timer = None
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        if closing:
            await asyncio.wait_for(closing.wait_closed(), 1)
        if self.inode:
            try:
                info = self.path.lstat()
                if (info.st_dev, info.st_ino) == self.inode:
                    self.path.unlink()
            except OSError:
                pass
            self.inode = None
        if self.root_inode:
            try:
                info = self.root.lstat()
                if (info.st_dev, info.st_ino) == self.root_inode:
                    self.root.rmdir()
            except OSError:
                pass
            self.root_inode = None


@dataclass(frozen=True)
class WorkerClient:
    path: Path
    token: str
    capture_id: str
    device_id: str
    epoch: str

    async def call(self, command, payload=None):
        writer = None
        try:
            async with asyncio.timeout(3):
                reader, writer = await asyncio.open_unix_connection(self.path, limit=FRAME_LIMIT + 4)
                await write_frame(writer, dict(version=1, token=self.token, capture_id=self.capture_id,
                                               device_id=self.device_id, epoch=self.epoch,
                                               command=command, payload=payload or {}))
                reply = await read_frame(reader)
                if reply.get('version') != 1:
                    raise Issue('worker_protocol', 503)
                if 'error' in reply:
                    error = reply['error']
                    raise Issue(error['code'], error['status'])
                return reply['data']
        except (OSError, TimeoutError, asyncio.IncompleteReadError, KeyError, TypeError, AttributeError):
            raise Issue('worker_unavailable', 503) from None
        finally:
            if writer:
                await close_writer(writer)

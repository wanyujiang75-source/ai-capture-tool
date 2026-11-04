"""Owned per-recording lifecycle and opt-in recorder, shared by both proxy modes."""

import asyncio
import json
import os
from pathlib import Path
import tempfile
import secrets

from .addon import BreakpointAddon
from .archive import BreakpointArchive
from .guard import check_version
from .ipc import WorkerServer


def private_json(path, value):
    data = json.dumps(value).encode()
    temporary = path.with_name(path.name + '.' + secrets.token_hex(8) + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as file:
            file.write(data)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class RecordingRuntime:
    def __init__(self, master, root, capture_id, device_id):
        check_version()
        self.root = Path(root)
        self.archive = BreakpointArchive(root)
        self.addon = BreakpointAddon(str(capture_id), device_id, root, archive=self.archive, master=master)
        self.addon.stream_callback = self.stream
        self.temp = Path(tempfile.mkdtemp(prefix='bp-'))
        self.server = WorkerServer(self.temp / 's', self.addon.engine)
        self.descriptor = self.root / 'breakpoint-worker.json'
        self.closing = False
        self.close_task = None
        self.server.on_stop = self.begin_close

    async def start(self):
        try:
            await self.server.start()
            engine = self.addon.engine
            private_json(self.descriptor, dict(path=str(self.server.path), token=self.server.token,
                         capture_id=engine.capture_id, device_id=engine.device_id, epoch=engine.epoch))
            private_json(self.root / 'breakpoint-archive.json', {'version': 1})
        except BaseException:
            await self.close()
            raise

    def stream(self, flow, stage):
        def append(chunk):
            self.save(self.archive.append_body, flow.id, stage, chunk)
            return chunk
        return append

    def save(self, operation, *args):
        import sqlite3
        if self.archive.closed:
            self.addon.engine.stop()
            return
        try:
            return operation(*args)
        except (OSError, sqlite3.Error):
            self.archive._limit('storage_error')
        finally:
            if self.archive.closed:
                self.addon.engine.stop()

    def requestheaders(self, flow):
        if self.closing or not self.save(self.archive.begin, flow):
            flow.request.stream = True
            return
        flow.metadata['breakpoint_recording'] = self.addon.engine.epoch
        self.addon.flows[flow.id] = flow
        self.addon.requestheaders(flow)
        if not self.addon.collecting(flow, 'request'):
            flow.request.stream = self.stream(flow, 'request')

    def owns(self, flow):
        return flow.metadata.get('breakpoint_recording') == self.addon.engine.epoch

    async def request(self, flow):
        if not self.owns(flow):
            return
        await self.addon.request(flow)
        if not flow.request.stream:
            self.save(self.archive.append_body, flow.id, 'request', flow.request.raw_content or b'')
        if not flow.error:
            self.save(self.archive.request_complete, flow)

    def responseheaders(self, flow):
        if not self.owns(flow):
            return
        self.addon.responseheaders(flow)
        self.save(self.archive.headers, flow)
        if not self.addon.collecting(flow, 'response'):
            flow.response.stream = self.stream(flow, 'response')

    async def response(self, flow):
        if not self.owns(flow):
            return
        await self.addon.response(flow)
        if not flow.response.stream:
            self.save(self.archive.append_body, flow.id, 'response', flow.response.raw_content or b'')
        self.save(self.archive.finish, flow)

    def error(self, flow):
        if self.owns(flow):
            self.addon.error(flow)
            self.save(self.archive.finish, flow)

    def begin_close(self):
        if self.close_task is None:
            self.closing = True
            self.close_task = asyncio.create_task(self._close())
        return self.close_task

    async def close(self):
        await asyncio.shield(self.begin_close())

    async def _close(self):
        await self.addon.close()
        await self.server.close()
        self.archive.close()
        self.descriptor.unlink(missing_ok=True)
        self.temp.rmdir()

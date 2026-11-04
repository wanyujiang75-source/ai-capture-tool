"""Trusted backend composition; descriptors are never accepted from API payloads."""

import asyncio
import json
import os
from pathlib import Path
import secrets
import stat
import sys

from .api import create_control_app
from .ipc import WorkerClient
from .models import Issue
from .runtime import private_json


def client_for(root):
    path = Path(root) / 'breakpoint-worker.json'
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_size > 4096):
            raise ValueError('unsafe descriptor')
        data = json.loads(path.read_bytes())
        socket = Path(data['path'])
        info = socket.lstat()
        parent = socket.parent.lstat()
        if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or parent.st_uid != os.getuid()
                or parent.st_mode & 0o077 or not stat.S_ISDIR(parent.st_mode)):
            raise ValueError('unsafe socket')
        return WorkerClient(socket, data['token'], data['capture_id'], data['device_id'], data['epoch'])
    except (OSError, ValueError, KeyError, TypeError):
        raise Issue('worker_unavailable', 503) from None


def mount_control(app, store, runtime_dir):
    if os.environ.get('CAPTURE_BREAKPOINTS') != '1':
        return
    token = secrets.token_urlsafe(32)
    root = Path(runtime_dir)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    private_json(root / 'breakpoint-desktop.json', {'token': token})

    def target(capture_id):
        if not capture_id.isdecimal():
            return None
        session = store.get_session(int(capture_id))
        if not session or session['status'] != 'running':
            return None
        worker = client_for(session['outdir'])
        if worker.capture_id != capture_id:
            raise Issue('target_conflict')
        return worker

    app.include_router(create_control_app(target, token).router)


async def drain(root):
    try:
        async with asyncio.timeout(4.2):
            client = client_for(root)
            await client.call('stop')
            # Disappearance follows transport drain, IPC and archive cleanup;
            # engine.in_flight alone only measures pending editor decisions.
            while (Path(root) / 'breakpoint-worker.json').exists():
                await asyncio.sleep(0.05)
    except (Issue, TimeoutError):
        pass  # The existing owned-process stop remains the final fallback.


if __name__ == '__main__':
    asyncio.run(drain(sys.argv[1]))

"""Explicit iPhone acceptance with read-only reuse of this tool's own identity.

Run with the extracted bundle's Python and its backend first in PYTHONPATH.
No VPN, routing, trust, original metadata or Keychain writes are permitted.
The existing proxy endpoint must be free and on the same LAN address.
"""

import argparse
import asyncio
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import socket
import signal

import uvicorn


class AcceptanceServer(uvicorn.Server):
    @contextmanager
    def capture_signals(self):
        # The CLI harness owns proxy cleanup; do not re-raise before its finally.
        previous = {sig: signal.signal(sig, self.handle_exit) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            yield
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


class ReadOnlyKeychain:
    def __init__(self, source):
        self.source = source

    def read(self):
        return self.source.read()

    def create(self, data):
        raise RuntimeError('Acceptance must not create or rotate the existing identity')

    def delete(self):
        raise RuntimeError('Acceptance must not delete the existing identity')


async def run(args):
    from capture_console.ios_pairing_identity import IOSPairingIdentity
    from capture_console.ios_setup import local_wifi_address
    from capture_console.breakpoints.runtime import private_json

    os.umask(0o077)
    source = IOSPairingIdentity(Path(args.identity_root).resolve())
    metadata = source.path.read_bytes()
    saved = json.loads(metadata)
    identity = source.load()
    if not identity or saved['host'] != local_wifi_address():
        raise RuntimeError('Existing identity or network cannot be reused without configuration changes')
    root = Path(args.runtime_dir).resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.environ.update(CAPTURE_RUNTIME_DIR=str(root), CAPTURE_BREAKPOINTS='1',
                      TRACEDECK_DESKTOP='1', TRACEDECK_DESKTOP_BUILD_ID=args.build_id,
                      PYTHONDONTWRITEBYTECODE='1')
    os.environ.pop('CAPTURE_DEVICES_CONFIG', None)
    os.environ.pop('TRACEDECK_CONFIG', None)
    from capture_console import app as backend
    service = backend.ios_setup_service
    service.identity.keychain = ReadOnlyKeychain(source.keychain)
    service.root.mkdir(mode=0o700, parents=True, exist_ok=True)
    private_json(service.identity.path, saved)
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    server = AcceptanceServer(uvicorn.Config(backend.app, log_level='error', access_log=False, lifespan='off'))
    with server.capture_signals():
        try:
            state = await asyncio.to_thread(service.prepare, saved['ssid'])
            private_json(root / 'acceptance-info.json', dict(port=port, pid=os.getpid(),
                         check_url=state['check_url'], source_metadata_sha256=hashlib.sha256(metadata).hexdigest()))
            print(json.dumps(dict(port=port, runtime=str(root), connection_state=state['connection_state'],
                                  identity_reused=state['identity_reused'])), flush=True)
            await server.serve(sockets=[listener])
        finally:
            await asyncio.to_thread(service.shutdown)
            listener.close()
            if source.path.read_bytes() != metadata or source.load() != identity:
                raise RuntimeError('Original identity changed during acceptance; investigate without overwriting it')
            print('original_identity_unchanged=true; owned_proxy_stopped=true', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity-root', required=True)
    parser.add_argument('--runtime-dir', required=True)
    parser.add_argument('--build-id', required=True)
    asyncio.run(run(parser.parse_args()))

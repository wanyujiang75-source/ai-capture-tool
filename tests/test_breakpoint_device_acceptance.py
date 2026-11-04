"""The phone harness must clean up even when uvicorn receives OS signals."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


class DeviceAcceptanceCleanupTests(unittest.TestCase):
    def test_preparation_signal_cleans_materials_without_reading_real_identity(self):
        script = '''
import asyncio, json, os, signal, tempfile, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import capture_console
from tests import breakpoint_device_acceptance as harness
class Identity:
    def __init__(self, root):
        self.path = root / 'identity.json'
        self.keychain = SimpleNamespace(read=lambda: b'fake')
    def load(self):
        return {'fake': 'identity'}
async def app(scope, receive, send):
    pass
with tempfile.TemporaryDirectory() as directory:
    base = Path(directory)
    (base / 'identity.json').write_text(json.dumps({'host':'127.0.0.1', 'ssid':'synthetic'}))
    root = base / 'runtime'
    service = SimpleNamespace(root=root/'ios-setup', identity=Identity(root/'ios-setup'))
    marker = service.root / 'private-material'
    def prepare(ssid):
        marker.write_text('synthetic only')
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(.05)
        return {'check_url':'https://example.invalid', 'connection_state':'synthetic', 'identity_reused':True}
    def shutdown():
        marker.unlink()
    service.prepare, service.shutdown = prepare, shutdown
    backend = SimpleNamespace(app=app, ios_setup_service=service)
    args = SimpleNamespace(identity_root=str(base), runtime_dir=str(root), build_id='test')
    with patch('capture_console.ios_pairing_identity.IOSPairingIdentity', Identity), \\
         patch('capture_console.ios_setup.local_wifi_address', return_value='127.0.0.1'), \\
         patch.object(capture_console, 'app', backend, create=True):
        asyncio.run(harness.run(args))
    assert not marker.exists()
    print('prepare-cleaned', flush=True)
'''
        result = subprocess.run(
            [sys.executable, '-c', script], cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('prepare-cleaned', result.stdout)

    def test_signals_return_to_cleanup_instead_of_terminating_the_process(self):
        script = '''
import asyncio, os, signal, socket, sys
import uvicorn
from tests import breakpoint_device_acceptance as harness
async def app(scope, receive, send):
    pass
async def run():
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    server = harness.AcceptanceServer(uvicorn.Config(app, lifespan='off', log_level='error'))
    async def stop():
        while not server.started:
            await asyncio.sleep(.01)
        os.kill(os.getpid(), getattr(signal, sys.argv[1]))
    task = asyncio.create_task(stop())
    try:
        await server.serve(sockets=[listener])
    finally:
        listener.close()
        await task
        print('cleanup-returned', flush=True)
asyncio.run(run())
'''
        for name in ('SIGTERM', 'SIGINT'):
            with self.subTest(signal=name):
                result = subprocess.run(
                    [sys.executable, '-c', script, name],
                    cwd=Path(__file__).resolve().parents[1],
                    env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual((result.returncode, result.stdout.strip()),
                                 (0, 'cleanup-returned'), result.stderr)

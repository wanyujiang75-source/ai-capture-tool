"""Opt-in isolated worker lifecycle; no device or VPN changes."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest

from capture_console.ios_setup import process_identity
from capture_console.ios_results import IOSCaptureArchive


@unittest.skipUnless(os.environ.get('CAPTURE_TEST_PHYSICAL_WORKER') == '1', 'opt-in isolated WireGuard listener')
class PhysicalWorkerTests(unittest.TestCase):
    def test_real_worker_exports_private_single_app_config_and_expires(self):
        root = Path(__file__).resolve().parents[1]
        python = root / 'macos-native/build/physical-runtime/bin/python3'
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.bind(('127.0.0.1', 0))
                port = probe.getsockname()[1]
            config = {'directory': directory, 'outdir': str(work / 'captures/test'), 'host': '127.0.0.1',
                      'port': port, 'upstream': None, 'owner_pid': os.getpid(),
                      'owner_identity': process_identity(os.getpid()), 'parent_pid': os.getpid(),
                      'package': 'com.example.test', 'session_id': 1}
            path = work / 'config.json'
            path.write_text(json.dumps(config))
            path.chmod(0o600)
            lease = work / 'lease'
            lease.touch(mode=0o600)
            with (work / 'worker.log').open('wb') as log:
                process = subprocess.Popen([str(python), '-m', 'capture_console.android_physical_worker', str(path)],
                                           cwd=root, stdout=log, stderr=log, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            try:
                deadline = time.monotonic() + 15
                while not (work / 'tunnel.conf').exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(.1)
                self.assertIsNone(process.poll(), (work / 'worker.log').read_text()[-2000:])
                tunnel = work / 'tunnel.conf'
                self.assertIn('IncludedApplications = com.example.test', tunnel.read_text())
                self.assertEqual(tunnel.stat().st_mode & 0o777, 0o600)
                page = IOSCaptureArchive(config['outdir'], read_only=True).page()
                self.assertEqual(page['total'], 0)
                os.utime(lease, (time.time() - 30, time.time() - 30))
                self.assertEqual(process.wait(timeout=6), 0)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)

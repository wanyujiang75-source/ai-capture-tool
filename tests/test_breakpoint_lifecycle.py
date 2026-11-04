import json
import asyncio
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

from fastapi import FastAPI

from capture_console.breakpoints.runtime import RecordingRuntime
from capture_console.breakpoints.supervisor import client_for, mount_control
from capture_console.breakpoints.models import Issue
from capture_console.runner import ConsoleRunner, CommandResult


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_script_load_and_owner_exit_cleanup(self):
        from capture_console.breakpoints.runtime import private_json
        with tempfile.TemporaryDirectory(prefix='bp2-script-') as tmp:
            root = Path(tmp)
            config = root/'launch.json'
            private_json(config, dict(outdir=str(root/'archive'), capture_id='1', device_id='device-1',
                                     owner_pid=os.getpid(), owner_identity='deliberately-not-this-process'))
            env = dict(os.environ, CAPTURE_BP_CONFIG=str(config), PYTHONDONTWRITEBYTECODE='1')
            process = await asyncio.create_subprocess_exec(sys.executable, '-c',
                'from mitmproxy.tools.main import mitmdump; mitmdump()', '-q',
                '--listen-host', '127.0.0.1', '--listen-port', '0', '--set', f'confdir={root}/ca',
                '-s', str(Path('scripts/breakpoint_addon.py').resolve()), env=env,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            try:
                async with asyncio.timeout(6):
                    while not (root/'archive'/'breakpoint-worker.json').exists() and process.returncode is None:
                        await asyncio.sleep(.01)
                worker = client_for(root/'archive')
                self.assertTrue((await worker.call('status'))['transport_attached'])
                out, error = await asyncio.wait_for(process.communicate(), 6)
                self.assertEqual(process.returncode, 0, (out+error).decode())
                self.assertNotIn(b'error', error.lower())
                self.assertFalse(worker.path.exists())
                self.assertFalse((root/'archive'/'breakpoint-worker.json').exists())
            finally:
                if process.returncode is None:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), 3)

    async def test_descriptor_permissions_rejects_stale_target_and_cleans_owned_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = RecordingRuntime(None, root, '1', 'device-1')
            await runtime.start()
            client = client_for(root)
            self.assertTrue((await client.call('status'))['transport_attached'])
            self.assertEqual(runtime.descriptor.stat().st_mode & 0o777, 0o600)
            runtime.descriptor.chmod(0o644)
            with self.assertRaises(Issue):
                client_for(root)
            runtime.descriptor.chmod(0o600)
            socket_path = client.path
            await runtime.close()
            with self.assertRaises(Issue):
                await client.call('enable')
            self.assertFalse(socket_path.exists())
            self.assertTrue((root/'ios-flows.sqlite').exists())

    def test_backend_routes_are_absent_by_default(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'CAPTURE_BREAKPOINTS': '0'}):
            app = FastAPI()
            mount_control(app, None, tmp)
            self.assertFalse(any('breakpoints' in route.path for route in app.routes))
            self.assertFalse(list(Path(tmp).iterdir()))
            with patch.dict(os.environ, {'CAPTURE_BREAKPOINTS': '1'}):
                mount_control(app, None, tmp)
            self.assertTrue(any('breakpoints' in route.path for route in app.routes))
            self.assertEqual((Path(tmp)/'breakpoint-desktop.json').stat().st_mode & 0o777, 0o600)

    def test_runner_sets_launch_only_when_explicitly_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = ConsoleRunner(tmp, runtime_dir=tmp)
            with patch.object(runner, 'run', return_value=CommandResult(0, '', '')) as run:
                with patch.dict(os.environ, {'CAPTURE_BREAKPOINTS': '0'}):
                    runner.start_capture(package_name='test', activity='', mode='flutter-socks', outdir=tmp)
                self.assertEqual(run.call_args.kwargs['env'], {'OUTDIR': tmp})
                with patch.dict(os.environ, {'CAPTURE_BREAKPOINTS': '1'}):
                    runner.start_capture(package_name='test', activity='', mode='flutter-socks', outdir=tmp, capture_id='17')
                config = json.loads(Path(run.call_args.kwargs['env']['CAPTURE_BP_CONFIG']).read_text())
                self.assertEqual((config['capture_id'], config['device_id'], config['owner_pid']),
                                 ('17', 'device-1', os.getpid()))
                self.assertIn('--restart-mitm', run.call_args.args[0])

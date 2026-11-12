import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from capture_console.android_physical_service import PhysicalCaptureService
from capture_console.store import CaptureStore
from capture_console.ios_results import IOSCaptureArchive


class PhysicalServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = CaptureStore(self.root / 'console.db')
        self.service = PhysicalCaptureService(self.root / 'android-physical', self.store, 'adb')

    def test_requires_explicit_experimental_consent(self):
        with self.assertRaises(ValueError): self.service.start('serial', 42, False)
        self.assertEqual(self.service.status()['phase'], 'idle')

    def test_restart_does_not_silently_resume_or_discard_recovery(self):
        self.service.journal({'serial': 'phone', 'original_vpn': 'com.example.vpn'})
        restarted = PhysicalCaptureService(self.service.root, self.store, 'adb')
        self.assertEqual(restarted.status()['phase'], 'recovery_required')
        with self.assertRaises(ValueError): restarted.start('newphone', 42, True)

    def test_recovery_needs_actual_vpn_confirmation(self):
        device = Mock()
        device.vpn.return_value = 'com.local.capture.bridge'
        device.restore.return_value = False
        self.service.device = device
        self.service.info = {'serial': 'phone', 'original_vpn': 'com.example.vpn'}
        self.service.journal(self.service.info)
        self.service._finish_recovery(wait_seconds=0)
        self.assertEqual(self.service.status()['phase'], 'recovery_required')
        self.assertTrue(self.service.marker.exists())
        device.vpn.return_value = 'com.example.vpn'
        device.restore.return_value = True
        self.service._finish_recovery(wait_seconds=0)
        self.assertEqual(self.service.status()['phase'], 'stopped')
        self.assertFalse(self.service.marker.exists())

    def test_stopping_idle_is_idempotent(self):
        self.assertEqual(self.service.stop()['phase'], 'idle')
        self.assertEqual(self.service.stop()['phase'], 'idle')

    def test_failed_cancellation_ack_keeps_recovery_marker(self):
        device = Mock()
        device.stop.side_effect = ValueError('pending consent has not closed')
        self.service.device = device
        self.service.info = {'serial': 'phone', 'original_vpn': 'com.example.vpn'}
        self.service.journal(self.service.info)
        self.service._finish_recovery(wait_seconds=0)
        self.assertEqual(self.service.status()['phase'], 'recovery_required')
        self.assertTrue(self.service.marker.exists())
        device.restore.assert_not_called()
        device.cleanup.assert_not_called()

    def test_helper_cancelled_is_terminal_before_another_lease_renewal(self):
        runtime = self.root / 'physical-runtime/bin/python3'
        runtime.parent.mkdir(parents=True)
        runtime.touch()
        (self.root / 'android-bridge.apk').touch()
        device = Mock()
        device.inspect.return_value = {'serial': 'phone', 'package': 'com.app.test', 'original_vpn': None}
        device.state.side_effect = ['cancelled', 'denied']
        device.vpn.return_value = None
        device.restore.return_value = True
        self.service.device = device
        def spawn(command, **kwargs):
            config = json.loads(Path(command[-1]).read_text())
            (Path(config['directory']) / 'tunnel.conf').write_text('test config')
            return Mock(poll=Mock(return_value=None))
        with patch('capture_console.android_physical_service.ROOT', self.root / 'backend'), \
             patch('capture_console.android_physical_service.existing_upstream', return_value=None), \
             patch('capture_console.android_physical_service.local_wifi_address', return_value='192.168.1.2'), \
             patch('capture_console.android_physical_service.process_identity', return_value='test-owner'), \
             patch('capture_console.android_physical_service.subprocess.Popen', side_effect=spawn), \
             patch('capture_console.android_physical_service.socket.socket') as socket_mock, \
             patch.object(self.service.cancel, 'wait', return_value=False):
            socket_mock.return_value.__enter__.return_value.getsockname.return_value = ('192.168.1.2', 12345)
            self.service._run(42, 'test-owner')
        self.assertEqual(device.state.call_count, 1)
        device.renew.assert_called_once()
        self.assertEqual(self.service.status()['phase'], 'failed')
        self.assertFalse(self.service.marker.exists())

    def test_physical_session_is_separate_from_emulator(self):
        session = self.store.create_physical_session(serial='phone', package='com.app.test', outdir=str(self.root / 'captures/web-physical-one'))
        self.assertEqual((session['platform'], session['mode'], session['device_id']), ('android', 'android-physical-wireguard', 'physical-phone'))
        self.assertIsNone(self.store.active_session(device_id='device-1'))

    def test_worker_start_failure_keeps_empty_history_readable(self):
        runtime = self.root / 'physical-runtime/bin/python3'
        runtime.parent.mkdir(parents=True)
        runtime.touch()
        (self.root / 'android-bridge.apk').touch()
        device = Mock()
        device.inspect.return_value = {'serial': 'phone', 'package': 'com.app.test', 'original_vpn': None}
        device.vpn.return_value = None
        device.restore.return_value = True
        self.service.device = device
        with patch('capture_console.android_physical_service.ROOT', self.root / 'backend'), \
             patch('capture_console.android_physical_service.existing_upstream', return_value=None), \
             patch('capture_console.android_physical_service.local_wifi_address', return_value='127.0.0.2'), \
             patch('capture_console.android_physical_service.ipaddress.ip_address') as address, \
             patch('capture_console.android_physical_service.subprocess.Popen', side_effect=OSError('test failure')):
            address.return_value.is_private = True
            address.return_value.is_loopback = False
            self.service._run(42, 'test-owner')
        session = self.store.get_session(self.service.status()['session_id'])
        self.assertEqual(session['status'], 'stopped')
        self.assertEqual(IOSCaptureArchive(session['outdir'], read_only=True).page()['total'], 0)
        self.assertFalse(self.service.marker.exists())

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from capture_console.android_physical_service import PhysicalCaptureService
from capture_console.store import CaptureStore


class PhysicalConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.service = PhysicalCaptureService(root / 'physical', CaptureStore(root / 'db.sqlite'), 'adb')
        self.info = {'serial': 'phone', 'name': 'Phone', 'original_vpn': None}
        self.service.info = self.info.copy()
        self.service.journal(self.info)
        self.service.update(phase='recovery_required', serial='phone')
        self.online = patch('capture_console.android_physical_service.devices',
                            return_value=[{'serial': 'phone', 'status': 'device'}])
        self.device = patch('capture_console.android_physical_service.PhysicalDevice')
        self.worker = patch('capture_console.android_physical_service.owned_worker_active', return_value=False)
        self.online.start()
        self.phone = self.device.start().return_value
        self.worker.start()
        self.addCleanup(self.online.stop)
        self.addCleanup(self.device.stop)
        self.addCleanup(self.worker.stop)
        self.phone.vpn.return_value = 'com.example.vpn'
        self.phone.shell.return_value = ''

    def test_explicit_confirmation_keeps_user_vpn_and_other_records(self):
        other = {'serial': 'other', 'name': 'Other', 'original_vpn': 'original.vpn'}
        path = self.service.pending.path('other')
        path.write_text(json.dumps(other))
        result = self.service.confirm_network('phone', confirmed=True)
        self.assertEqual(result['phase'], 'stopped')
        self.assertIn('用户确认', result['message'])
        self.assertFalse(self.service.marker.exists())
        self.assertEqual(json.loads(path.read_text()), other)
        self.phone.restore.assert_not_called()
        self.phone.stop.assert_not_called()
        self.phone.cleanup.assert_not_called()

    def test_wrong_phone_unconfirmed_or_disconnected_preserves_marker(self):
        for serial, confirmed in [('phone', False), ('other', True)]:
            with self.subTest(serial=serial, confirmed=confirmed), self.assertRaises(ValueError):
                self.service.confirm_network(serial, confirmed=confirmed)
        with patch('capture_console.android_physical_service.devices', return_value=[]):
            with self.assertRaises(ValueError): self.service.confirm_network('phone', confirmed=True)
        self.assertTrue(self.service.marker.exists())

    def test_running_helper_vpn_worker_or_service_thread_rejected(self):
        for vpn, pid, worker in [('com.local.capture.bridge', '', False),
                                 ('com.example.vpn', '123', False),
                                 ('com.example.vpn', '', True)]:
            with self.subTest(vpn=vpn, pid=pid, worker=worker):
                self.phone.vpn.return_value = vpn
                self.phone.shell.return_value = pid
                with patch('capture_console.android_physical_service.owned_worker_active', return_value=worker):
                    with self.assertRaises(ValueError): self.service.confirm_network('phone', confirmed=True)
                self.assertTrue(self.service.marker.exists())
        self.service.thread = Mock()
        self.service.thread.is_alive.return_value = True
        with self.assertRaises(ValueError): self.service.confirm_network('phone', confirmed=True)
        self.assertTrue(self.service.marker.exists())

    def test_confirm_pending_phone_leaves_other_pending_records(self):
        self.service.marker.replace(self.service.pending.path('phone'))
        other = {'serial': 'other', 'name': 'Other'}
        path = self.service.pending.path('other')
        path.write_text(json.dumps(other))
        self.service.last = {'phase': 'idle'}
        result = self.service.confirm_network('phone', confirmed=True)
        self.assertEqual(result['phase'], 'idle')
        self.assertFalse(self.service.pending.path('phone').exists())
        self.assertEqual(json.loads(path.read_text()), other)

    def test_device_check_or_local_cleanup_failure_preserves_marker(self):
        self.phone.vpn.side_effect = RuntimeError('disconnected')
        with self.assertRaises(RuntimeError): self.service.confirm_network('phone', confirmed=True)
        self.assertTrue(self.service.marker.exists())
        self.phone.vpn.side_effect = None
        with patch.object(self.service, '_close_local_capture', side_effect=OSError('cannot stop')):
            with self.assertRaises(OSError): self.service.confirm_network('phone', confirmed=True)
        self.assertTrue(self.service.marker.exists())

    def test_other_active_recovery_cannot_be_discarded(self):
        path = self.service.pending.path('other')
        path.write_text(json.dumps({'serial': 'other'}))
        with self.assertRaises(ValueError): self.service.confirm_network('other', confirmed=True)
        self.assertTrue(path.exists())
        self.assertTrue(self.service.marker.exists())

    def test_helper_starting_during_cleanup_preserves_marker(self):
        self.phone.shell.side_effect = ['', '123']
        with self.assertRaises(ValueError):
            self.service.confirm_network('phone', confirmed=True)
        self.assertTrue(self.service.marker.exists())

    def test_invalid_serial_does_not_inspect_device(self):
        with self.assertRaises(ValueError): self.service.confirm_network('emulator-5554', confirmed=True)
        self.assertTrue(self.service.marker.exists())

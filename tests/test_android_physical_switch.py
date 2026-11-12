import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from capture_console.android_physical_service import PhysicalCaptureService
from capture_console.store import CaptureStore


class PhysicalSwitchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = CaptureStore(self.root / 'console.db')
        self.service = PhysicalCaptureService(self.root / 'android-physical', self.store, 'adb')
        session = self.store.create_physical_session(serial='old-phone', package='com.example.app',
                                                     outdir=str(self.root / 'captures/web-physical-test'))
        self.session_id = session['id']
        self.service.info = {'serial': 'old-phone', 'name': 'Old phone', 'original_vpn': 'com.example.vpn',
                             'session_id': self.session_id}
        self.service.journal(self.service.info)
        self.service.update(phase='recovery_required', serial='old-phone')

    def terminate(self):
        self.service.terminate()
        self.service.thread.join(timeout=3)
        self.assertFalse(self.service.thread.is_alive())

    def test_terminate_retains_recovery_and_history_without_touching_any_phone(self):
        with patch('capture_console.android_physical_service.PhysicalDevice') as device:
            self.terminate()
            device.assert_not_called()
        self.assertEqual(self.service.status()['phase'], 'idle')
        self.assertEqual(self.service.status()['pending_recoveries'], [{'serial': 'old-phone', 'name': 'Old phone'}])
        self.assertEqual(self.store.get_session(self.session_id)['status'], 'stopped')
        self.assertFalse(self.service.marker.exists())
        restarted = PhysicalCaptureService(self.service.root, self.store, 'adb')
        self.assertEqual(restarted.status()['pending_recoveries'], self.service.status()['pending_recoveries'])
        self.assertEqual(restarted.status()['phase'], 'idle')

    def test_different_phone_can_start_but_original_must_recover_first(self):
        self.terminate()
        with patch('capture_console.android_physical_service.process_identity', return_value='owner'), \
             patch.object(self.service, '_run') as run:
            with self.assertRaises(ValueError):
                self.service.start('old-phone', 42, True)
            self.service.start('new-phone', 42, True)
            self.service.thread.join(timeout=3)
        self.assertEqual(self.service.status()['serial'], 'new-phone')
        self.assertEqual(self.service.info, {})
        run.assert_called_once()

    def test_terminate_waits_for_old_thread_before_releasing_task(self):
        entered, release = threading.Event(), threading.Event()
        def old_work():
            entered.set()
            release.wait(timeout=3)
            self.service.update(phase='recovery_required')
        self.service.thread = threading.Thread(target=old_work)
        self.service.thread.start()
        entered.wait(timeout=1)
        try:
            self.service.terminate()
            coordinator = self.service.thread
            self.service.terminate()
            self.assertIs(self.service.thread, coordinator)
            self.assertEqual(self.service.status()['phase'], 'terminating')
            with self.assertRaises(ValueError):
                self.service.start('new-phone', 42, True)
        finally:
            release.set()
            self.service.thread.join(timeout=3)
        self.assertEqual(self.service.status()['phase'], 'idle')
        self.assertEqual(len(self.service.status()['pending_recoveries']), 1)

    def test_failed_local_shutdown_does_not_release_or_discard_recovery(self):
        process = Mock()
        process.poll.return_value = None
        process.terminate.side_effect = OSError('cannot stop')
        self.service.process = process
        self.terminate()
        self.assertEqual(self.service.status()['phase'], 'recovery_required')
        self.assertTrue(self.service.marker.exists())
        self.assertEqual(self.service.status()['pending_recoveries'], [])

    def test_stop_does_not_cancel_during_an_exclusive_task_transition(self):
        entered = threading.Event()
        def stop():
            entered.set()
            self.service.stop()
        with self.service.lock:
            stopper = threading.Thread(target=stop)
            stopper.start()
            entered.wait(timeout=1)
            cancelled_while_locked = self.service.cancel.wait(timeout=0.1)
        stopper.join(timeout=1)
        self.assertFalse(cancelled_while_locked)
        self.assertTrue(self.service.cancel.is_set())

    def test_only_explicit_connected_original_phone_is_recovered(self):
        self.terminate()
        with patch('capture_console.android_physical_service.devices', return_value=[{'serial': 'new-phone', 'status': 'device'}]), \
             patch('capture_console.android_physical_service.PhysicalDevice') as device:
            with self.assertRaises(ValueError): self.service.recover('old-phone')
            with self.assertRaises(ValueError): self.service.recover('new-phone')
            device.assert_not_called()
        with patch('capture_console.android_physical_service.devices', return_value=[{'serial': 'old-phone', 'status': 'device'}]), \
             patch('capture_console.android_physical_service.PhysicalDevice') as device:
            device.return_value.vpn.return_value = 'com.example.vpn'
            device.return_value.restore.return_value = True
            self.service.recover('old-phone')
            self.service.thread.join(timeout=3)
            device.assert_called_once_with('adb', 'old-phone')
        self.assertEqual(self.service.status()['pending_recoveries'], [])
        self.assertEqual(self.service.status()['phase'], 'stopped')

    def test_failed_recovery_can_be_deferred_again_without_losing_other_phone(self):
        self.terminate()
        self.service.info = {'serial': 'second-phone', 'name': 'Second phone', 'original_vpn': None}
        self.service.journal(self.service.info)
        self.terminate()
        self.assertEqual(len(self.service.status()['pending_recoveries']), 2)
        with patch('capture_console.android_physical_service.devices', return_value=[{'serial': 'old-phone', 'status': 'device'}]), \
             patch('capture_console.android_physical_service.PhysicalDevice') as device:
            device.return_value.stop.side_effect = RuntimeError('USB disconnected')
            self.service.recover('old-phone')
            self.service.thread.join(timeout=3)
        self.terminate()
        self.assertEqual({item['serial'] for item in self.service.status()['pending_recoveries']}, {'old-phone', 'second-phone'})
        self.assertNotIn('original_vpn', json.dumps(self.service.status()['pending_recoveries']))

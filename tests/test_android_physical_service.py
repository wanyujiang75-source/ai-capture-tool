import json
from contextlib import ExitStack, contextmanager
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from capture_console.android_physical_service import PhysicalCaptureService
from capture_console.store import CaptureStore
from capture_console.ios_results import IOSCaptureArchive
from capture_console.android_physical_network import NetworkIssue


class PhysicalServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = CaptureStore(self.root / 'console.db')
        self.service = PhysicalCaptureService(self.root / 'android-physical', self.store, 'adb')
        self.network_patch = patch('capture_console.android_physical_service.NetworkReadiness')
        self.network = self.network_patch.start().return_value
        self.network.summary.return_value = {'phone_network': 'ready', 'upstream_network': 'ready'}
        self.addCleanup(self.network_patch.stop)

    def test_requires_explicit_experimental_consent(self):
        with self.assertRaises(ValueError): self.service.start('serial', 42, False)
        self.assertEqual(self.service.status()['phase'], 'idle')

    def test_stale_or_stopped_app_evidence_never_claims_current_success(self):
        evidence = {'state': 'responded', 'observed_at': 100.0,
                    'https_response_count': 1, 'last_status_code': 200, 'response_age_seconds': 0}
        self.service.update(phase='capturing', application_network=evidence)
        with patch('capture_console.android_physical_service.time.monotonic', return_value=110):
            self.assertEqual(self.service.status()['application_network']['state'], 'responded')
        with patch('capture_console.android_physical_service.time.monotonic', return_value=116):
            self.assertEqual(self.service.status()['application_network'], {'state': 'unverified'})
        self.service.update(phase='stopped')
        self.assertIsNone(self.service.status()['application_network'])

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

    def test_restarted_service_cleans_persisted_owner_channel_without_losing_recovery(self):
        channel = {'port': 12345, 'remote': 'localabstract:capture-owner-' + 'a' * 64}
        self.service.journal({'serial': 'phone', 'original_vpn': None, 'owner_channel': channel})
        restarted = PhysicalCaptureService(self.service.root, self.store, 'adb')
        restarted.device = Mock()
        restarted.device.close_owner_channel.side_effect = OSError('ADB temporarily unavailable')
        with self.assertRaises(OSError): restarted._close_local_capture()
        self.assertEqual(json.loads(restarted.marker.read_text())['owner_channel'], channel)
        restarted.device.close_owner_channel.side_effect = None
        restarted._close_local_capture()
        restarted.device.close_owner_channel.assert_called_with(channel)
        self.assertNotIn('owner_channel', json.loads(restarted.marker.read_text()))
        self.assertTrue(restarted.marker.exists())

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
        device.state.side_effect = [{'phase': 'cancelled'}, {'phase': 'denied'}]
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

    def test_failed_network_admission_does_not_touch_phone_or_create_recovery(self):
        runtime = self.root / 'physical-runtime/bin/python3'
        runtime.parent.mkdir(parents=True)
        runtime.touch()
        (self.root / 'android-bridge.apk').touch()
        device = Mock()
        device.inspect.return_value = {'serial': 'phone', 'package': 'com.app.test', 'original_vpn': 'original.vpn'}
        self.service.device = device
        self.network.check.side_effect = NetworkIssue('phone_wifi_unavailable', '请连接 Wi-Fi')
        with patch('capture_console.android_physical_service.ROOT', self.root / 'backend'), \
             patch('capture_console.android_physical_service.existing_upstream', return_value=['127.0.0.1', 7897]), \
             patch('capture_console.android_physical_service.local_wifi_address', return_value='192.168.1.2'):
            self.service._run(42, 'owner')
        device.install.assert_not_called()
        device.stop.assert_not_called()
        device.restore.assert_not_called()
        self.assertFalse(self.service.marker.exists())
        self.assertEqual(self.service.status()['code'], 'phone_wifi_unavailable')
        self.assertEqual(self.service.status()['phase'], 'failed')

    def test_local_forwarding_stops_before_phone_restore(self):
        calls = Mock()
        self.service.device = calls.device
        self.service.device.vpn.return_value = None
        self.service.device.restore.return_value = True
        self.service.info = {'serial': 'phone', 'original_vpn': 'original.vpn'}
        self.service.journal(self.service.info)
        with patch.object(self.service, '_close_local_capture', calls.close):
            self.service._finish_recovery()
        self.assertEqual(calls.mock_calls[0], unittest.mock.call.close())

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

    @contextmanager
    def running_fixture(self, snapshots):
        runtime = self.root / 'physical-runtime/bin/python3'
        runtime.parent.mkdir(parents=True)
        runtime.touch()
        (self.root / 'android-bridge.apk').touch()
        device = Mock()
        device.inspect.return_value = {'serial': 'phone', 'package': 'com.app.test', 'original_vpn': 'original.vpn'}
        device.vpn.return_value = 'com.local.capture.bridge'
        device.stop.side_effect = lambda: setattr(device.vpn, 'return_value', 'original.vpn')
        device.restore.return_value = True
        self.service.device = device
        states = iter(snapshots)
        observed = []
        def state():
            observed.append(self.service.status()['phase'])
            return next(states, {'phase': 'cancelled'})
        device.state.side_effect = state
        def spawn(command, **kwargs):
            config = json.loads(Path(command[-1]).read_text())
            directory = Path(config['directory'])
            (directory / 'tunnel.conf').write_text('test config')
            (directory / 'state.json').write_text(json.dumps({'flow_count': 2, 'response_count': 1, 'tls_failures': 0}))
            return Mock(poll=Mock(return_value=None))
        with ExitStack() as stack:
            for name, value in [('ROOT', self.root / 'backend'), ('existing_upstream', Mock(return_value=['127.0.0.1', 7897])),
                                ('local_wifi_address', Mock(return_value='192.168.1.2')), ('process_identity', Mock(return_value='owner'))]:
                stack.enter_context(patch('capture_console.android_physical_service.' + name, value))
            stack.enter_context(patch('capture_console.android_physical_service.subprocess.Popen', side_effect=spawn))
            sock = stack.enter_context(patch('capture_console.android_physical_service.socket.socket'))
            sock.return_value.__enter__.return_value.getsockname.return_value = ('192.168.1.2', 12345)
            stack.enter_context(patch.object(self.service.cancel, 'wait', return_value=False))
            yield observed, device

    def test_service_waits_for_real_handshake_before_running(self):
        with self.running_fixture([{'phase': 'connecting', 'sequence': 1}, {'phase': 'connecting', 'sequence': 2},
                                   {'phase': 'connected', 'sequence': 3}]) as (phases, device):
            self.service._run(42, 'owner')
        self.assertEqual(phases, ['waiting_vpn', 'waiting_tunnel', 'waiting_tunnel', 'capturing'])
        self.assertEqual([call.args[0] for call in device.launch.call_args_list], ['com.local.capture.bridge', 'com.app.test'])
        self.assertEqual(self.service.status()['response_count'], 1)

    def test_network_failure_after_authorization_never_claims_capture(self):
        self.network.check.side_effect = [None, None, NetworkIssue('upstream_changed', '电脑代理发生变化')]
        with self.running_fixture([{'phase': 'connected', 'sequence': 1}]) as (phases, device):
            self.service._run(42, 'owner')
        self.assertEqual(phases, ['waiting_vpn'])
        self.assertEqual(self.service.status()['code'], 'upstream_changed')
        self.assertEqual(self.service.status()['phase'], 'failed')
        device.restore.assert_called_once_with('original.vpn')

    def test_running_network_failure_preserves_results_and_pending_recovery(self):
        self.network.check.side_effect = [None, None, None, NetworkIssue('upstream_unreachable', '电脑代理连接中断')]
        with self.running_fixture([{'phase': 'connected', 'sequence': n} for n in range(1, 5)]) as (phases, device), \
             patch('capture_console.android_physical_service.time.monotonic', side_effect=range(0, 1000, 11)):
            device.restore.return_value = False
            self.service._run(42, 'owner')
        self.assertEqual(phases, ['waiting_vpn', 'waiting_tunnel', 'waiting_tunnel', 'capturing'])
        status = self.service.status()
        self.assertEqual((status['phase'], status['code'], status['response_count']), ('recovery_required', 'upstream_unreachable', 1))
        self.assertTrue(self.service.marker.exists())
        self.assertEqual(self.store.get_session(status['session_id'])['status'], 'stopped')

    def test_proxy_change_during_install_blocks_before_helper_launch(self):
        self.network.check.side_effect = [None, NetworkIssue('upstream_changed', '电脑代理发生变化')]
        with self.running_fixture([]) as (phases, device):
            self.service._run(42, 'owner')
        device.launch.assert_not_called()
        self.assertEqual(phases, [])
        self.assertEqual(self.service.status()['code'], 'upstream_changed')

    def test_cancel_during_vpn_inspection_never_launches_target(self):
        with self.running_fixture([{'phase': 'connected', 'sequence': 1}]) as (phases, device):
            def vpn():
                self.service.cancel.set()
                return 'original.vpn' if device.stop.called else 'com.local.capture.bridge'
            device.vpn.side_effect = vpn
            self.service._run(42, 'owner')
        self.assertEqual([call.args[0] for call in device.launch.call_args_list], ['com.local.capture.bridge'])
        self.assertNotIn('capturing', phases)
        self.assertEqual(self.service.status()['phase'], 'stopped')

    def test_stop_during_probe_does_not_promote_stale_connected_snapshot(self):
        with self.running_fixture([{'phase': 'connected', 'sequence': 1}, {'phase': 'stopped'}]) as (phases, device):
            self.service._run(42, 'owner')
        self.assertEqual([call.args[0] for call in device.launch.call_args_list], ['com.local.capture.bridge'])
        self.assertNotIn('capturing', phases)
        self.assertEqual(self.service.status()['code'], 'tunnel_lost')

    def test_local_close_failure_still_stops_phone_and_keeps_marker(self):
        self.service.device = Mock()
        self.service.device.vpn.return_value = None
        self.service.device.restore.return_value = True
        self.service.info = {'serial': 'phone', 'original_vpn': 'original.vpn'}
        self.service.journal(self.service.info)
        with patch.object(self.service, '_close_local_capture', side_effect=OSError('child cleanup failed')):
            self.service._finish_recovery()
        self.service.device.stop.assert_called_once()
        self.service.device.restore.assert_called_once_with('original.vpn')
        self.assertTrue(self.service.marker.exists())
        self.assertEqual(self.service.status()['phase'], 'recovery_required')

    def test_helper_stopping_during_target_launch_never_promotes_session(self):
        with self.running_fixture([{'phase': 'connected', 'sequence': 1}, {'phase': 'connected', 'sequence': 2},
                                   {'phase': 'stopped'}]) as (phases, device):
            self.service._run(42, 'owner')
        self.assertNotIn('capturing', phases)
        self.assertEqual(self.service.status()['code'], 'tunnel_lost')

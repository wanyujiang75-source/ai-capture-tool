import os
import socket
import subprocess
import time
import unittest
from unittest.mock import Mock, patch

from capture_console.android_physical_network import NetworkIssue, NetworkReadiness, PreparationCancelled, TunnelReadiness, check_https, check_phone


class NetworkReadinessTests(unittest.TestCase):
    def test_no_upstream_never_falls_back_to_direct(self):
        with self.assertRaisesRegex(NetworkIssue, '电脑.*代理'):
            NetworkReadiness(Mock(), '192.168.1.2', None, lambda: None)

    def test_proxy_connect_is_not_external_https_success(self):
        for code, stdout in ((0, '200 502'), (0, '407 000'), (60, '200 000'), (0, '200 302')):
            with self.subTest(code=code, stdout=stdout), patch(
                    'capture_console.android_physical_network.subprocess.run',
                    return_value=subprocess.CompletedProcess([], code, stdout, 'private diagnostics')):
                with self.assertRaises(NetworkIssue) as caught:
                    check_https(['127.0.0.1', 7897])
                self.assertEqual(caught.exception.code, 'upstream_unreachable')
                self.assertNotIn('private diagnostics', str(caught.exception))

    def test_https_probe_forces_the_selected_proxy_and_keeps_tls_verification(self):
        with patch.dict(os.environ, {'NO_PROXY': '*', 'HTTPS_PROXY': 'http://wrong:9'}), patch(
                'capture_console.android_physical_network.subprocess.run',
                return_value=subprocess.CompletedProcess([], 0, '200 204', '')) as run:
            check_https(['127.0.0.1', 7897])
        command = run.call_args.args[0]
        self.assertEqual(command[:2], ['/usr/bin/curl', '-q'])
        self.assertEqual(command[command.index('--proxy') + 1], 'http://127.0.0.1:7897')
        self.assertEqual(command[command.index('--noproxy') + 1], '')
        self.assertFalse(any(value in command for value in ('-k', '--insecure', '-L')))
        self.assertFalse(any(key.lower().endswith('_proxy') for key in run.call_args.kwargs['env']))
        self.assertLessEqual(run.call_args.kwargs['timeout'], 6)

    def test_proxy_change_blocks_before_any_probe(self):
        device = Mock()
        guard = NetworkReadiness(device, '192.168.1.2', ['127.0.0.1', 7897], lambda: None)
        with self.assertRaises(NetworkIssue) as caught:
            guard.check()
        self.assertEqual(caught.exception.code, 'upstream_changed')
        device.shell.assert_not_called()

    def test_wifi_disabled_does_not_open_listener(self):
        device = Mock()
        device.shell.return_value = 'Wifi is disabled\nWifi scanning is always available'
        with patch('capture_console.android_physical_network.socket.socket') as listener:
            with self.assertRaises(NetworkIssue) as caught:
                check_phone(device, '192.168.1.2')
        self.assertEqual(caught.exception.code, 'phone_wifi_unavailable')
        listener.assert_not_called()

    def test_real_local_roundtrip_has_bounded_echo_and_listener_closes(self):
        device = Mock()
        address = []
        def shell(*args, **kwargs):
            if args == ('cmd', 'wifi', 'status'):
                return 'Wifi is enabled\nWifi is connected to "Test"'
            parts = args[-1].split()
            host, port = parts[-2], int(parts[-1])
            nonce = parts[2]
            address.append((host, port))
            with socket.create_connection((host, port), timeout=2) as client:
                client.sendall((nonce + '\n').encode())
                return client.recv(128).decode()
        device.shell.side_effect = shell
        check_phone(device, '127.0.0.1')
        with self.assertRaises(OSError):
            socket.create_connection(address[0], timeout=.1)

    def test_wrong_roundtrip_is_not_connected(self):
        device = Mock()
        device.shell.side_effect = ['Wifi is enabled\nWifi is connected to "Test"', 'wrong']
        with self.assertRaises(NetworkIssue) as caught:
            check_phone(device, '127.0.0.1')
        self.assertEqual(caught.exception.code, 'phone_lan_unreachable')

    def test_health_is_not_fresh_after_network_failure(self):
        guard = NetworkReadiness(Mock(), '192.168.1.2', ['127.0.0.1', 7897], lambda: ['127.0.0.1', 7897])
        with patch('capture_console.android_physical_network.check_phone'), patch(
                'capture_console.android_physical_network.check_https') as https:
            guard.check()
            self.assertEqual(guard.summary(), {'phone_network': 'ready', 'upstream_network': 'ready'})
            https.side_effect = NetworkIssue('upstream_unreachable', '代理断开')
            with self.assertRaises(NetworkIssue): guard.check()
        self.assertEqual(guard.summary(), {'phone_network': 'ready', 'upstream_network': 'failed'})

    def test_renewal_checkpoints_separate_bounded_network_stages(self):
        events = []
        def upstream():
            events.append('proxy')
            return ['127.0.0.1', 7897]
        guard = NetworkReadiness(Mock(), '192.168.1.2', ['127.0.0.1', 7897], upstream)
        with patch('capture_console.android_physical_network.check_phone', side_effect=lambda *a: events.append('phone')), \
             patch('capture_console.android_physical_network.check_https', side_effect=lambda *a: events.append('https')):
            guard.check(lambda: events.append('renew'))
        self.assertEqual(events, ['renew', 'proxy', 'renew', 'phone', 'renew', 'https', 'renew'])

    def test_cancellation_between_stages_prevents_external_probe(self):
        guard = NetworkReadiness(Mock(), '192.168.1.2', ['127.0.0.1', 7897], lambda: ['127.0.0.1', 7897])
        heartbeat = Mock(side_effect=[None, None, PreparationCancelled()])
        with patch('capture_console.android_physical_network.check_phone'), \
             patch('capture_console.android_physical_network.check_https') as https:
            with self.assertRaises(PreparationCancelled):
                guard.check(heartbeat)
        https.assert_not_called()

    def test_probe_closes_accepted_socket_on_early_failure(self):
        clients = []
        def shell(*args, **kwargs):
            if args == ('cmd', 'wifi', 'status'):
                return 'Wifi is enabled\nWifi is connected to Test'
            parts = args[-1].split()
            client = socket.create_connection((parts[-2], int(parts[-1])), timeout=2)
            clients.append(client)
            client.sendall(b'a')
            time.sleep(.05)
            return 'wrong'
        try:
            with self.assertRaises(NetworkIssue):
                check_phone(Mock(shell=Mock(side_effect=shell)), '127.0.0.1')
            clients[0].settimeout(.5)
            try:
                self.assertEqual(clients[0].recv(128), b'')
            except ConnectionResetError:
                pass
        finally:
            for client in clients:
                client.close()


class TunnelReadinessTests(unittest.TestCase):
    def test_up_without_handshake_waits_then_times_out(self):
        guard = TunnelReadiness()
        self.assertFalse(guard.observe({'phase': 'connecting', 'sequence': 1}, 0))
        for now in range(2, 30, 2):
            self.assertFalse(guard.observe({'phase': 'connecting', 'sequence': now}, now))
        with self.assertRaises(NetworkIssue) as caught:
            guard.observe({'phase': 'connecting', 'sequence': 30}, 30)
        self.assertEqual(caught.exception.code, 'tunnel_timeout')

    def test_handshake_with_fresh_samples_and_stale_or_expired_connection(self):
        for stale in ({'phase': 'connected', 'sequence': 2}, {'phase': 'disconnected', 'sequence': 3}):
            guard = TunnelReadiness()
            self.assertFalse(guard.observe({'phase': 'connecting'}, 0))
            self.assertTrue(guard.observe({'phase': 'connected', 'sequence': 1}, 2))
            self.assertTrue(guard.observe({'phase': 'connected', 'sequence': 2}, 10))
            with self.assertRaises(NetworkIssue) as caught:
                guard.observe(stale, 23)
            self.assertEqual(caught.exception.code, 'tunnel_lost')

    def test_old_helper_without_sequence_cannot_claim_connection(self):
        guard = TunnelReadiness()
        self.assertFalse(guard.observe({'phase': 'connected'}, 0))
        with self.assertRaises(NetworkIssue):
            guard.observe({'phase': 'connected'}, 13)

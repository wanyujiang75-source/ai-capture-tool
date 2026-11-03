import json
import os
import plistlib
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes

from capture_console.ios_pairing_identity import IOSPairingIdentity
from capture_console.ios_keychain import IOSPairingError
from capture_console.ios_setup import IOSSetupService, make_profile
from capture_console.ios_setup_api import ios_operation
from fastapi import HTTPException


class MemoryKeychain:
    def __init__(self):
        self.data = None

    def read(self):
        return self.data

    def create(self, data):
        if self.data is not None:
            raise RuntimeError('duplicate identity')
        self.data = data

    def delete(self):
        self.data = None


class IOSIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.keychain = MemoryKeychain()
        self.now = int(time.time())
        self.identity = IOSPairingIdentity(self.root, keychain=self.keychain, clock=lambda: self.now)

    def test_one_year_ca_and_endpoint_survive_reload_without_plaintext_persistence(self):
        first = self.identity.create(9190)
        self.identity.remember(first, 'Office', '192.168.1.10')
        loaded = IOSPairingIdentity(self.root, keychain=self.keychain).load()
        self.assertEqual(loaded, first)
        cert = x509.load_pem_x509_certificate(first['pem'].encode())
        self.assertEqual(int(cert.not_valid_after_utc.timestamp()), self.now + 365 * 86400)
        self.assertEqual(first['expires_at'], int(cert.not_valid_after_utc.timestamp()))
        metadata = (self.root / 'identity.json').read_text()
        self.assertNotIn(first['password'], metadata)
        self.assertNotIn('PRIVATE KEY', metadata)
        self.assertEqual((self.root / 'identity.json').stat().st_mode & 0o777, 0o600)
        self.assertTrue(self.identity.resume_state()['can_resume'])

    def test_profile_uses_absolute_certificate_expiry_and_stable_payload_ids(self):
        identity = self.identity.create(9190)
        cfg = {**identity, 'ssid': 'Office', 'host': '192.168.1.10'}
        cert = x509.load_pem_x509_certificate(identity['pem'].encode())
        from cryptography.hazmat.primitives.serialization import Encoding
        first = make_profile(cfg, cert.public_bytes(Encoding.DER))
        second = make_profile(cfg, cert.public_bytes(Encoding.DER))
        self.assertEqual(first, second)
        profile = plistlib.loads(first)
        self.assertNotIn('DurationUntilRemoval', profile)
        self.assertEqual(profile['RemovalDate'].isoformat(), cert.not_valid_after_utc.replace(tzinfo=None).isoformat())
        self.assertNotIn(b'PRIVATE KEY', first)

    def test_interrupted_metadata_write_does_not_block_reconnect(self):
        identity = self.identity.create(9190)
        (self.root / 'identity.tmp').write_text('interrupted metadata only')
        self.identity.remember(identity, 'New Wi-Fi', '192.168.1.20')
        self.assertEqual(self.identity.resume_state()['ssid'], 'New Wi-Fi')
        self.assertEqual(self.identity.load(), identity)

    def test_after_two_days_same_identity_but_expiry_does_not_silently_rotate(self):
        first = self.identity.create(9190)
        self.identity.remember(first, 'Office', '192.168.1.10')
        later = IOSPairingIdentity(self.root, keychain=self.keychain, clock=lambda: self.now + 2 * 86400)
        self.assertEqual(later.load(), first)
        expired = IOSPairingIdentity(self.root, keychain=self.keychain, clock=lambda: first['expires_at'] + 1)
        with self.assertRaisesRegex(ValueError, '到期'):
            expired.load()
        self.assertFalse(expired.resume_state()['can_resume'])
        self.assertEqual(self.keychain.data, json.dumps(first).encode())

    def test_missing_corrupt_or_locked_keychain_fails_without_replacement(self):
        first = self.identity.create(9190)
        self.identity.remember(first, 'Office', '192.168.1.10')
        for broken in (None, b'not-json', b'{}'):
            with self.subTest(broken=broken):
                self.keychain.data = broken
                with self.assertRaises(ValueError):
                    self.identity.load()
                self.assertEqual(self.keychain.data, broken)
        self.keychain.read = Mock(side_effect=RuntimeError('locked'))
        with self.assertRaises(RuntimeError):
            self.identity.load()

    def test_explicit_removal_revokes_identity_and_next_certificate_is_different(self):
        first = self.identity.create(9190)
        self.identity.remember(first, 'Office', '192.168.1.10')
        self.identity.clear()
        self.assertIsNone(self.keychain.data)
        self.assertFalse((self.root / 'identity.json').exists())
        second = self.identity.create(9190)
        self.assertNotEqual(x509.load_pem_x509_certificate(first['pem'].encode()).fingerprint(hashes.SHA256()),
                            x509.load_pem_x509_certificate(second['pem'].encode()).fingerprint(hashes.SHA256()))

    def test_pairing_failure_preserves_actionable_code_without_secrets(self):
        operation = Mock(side_effect=IOSPairingError('ios_pairing_storage', '请解锁Mac后重试。'))
        with self.assertRaises(HTTPException) as caught:
            ios_operation(operation)
        self.assertEqual(caught.exception.detail, {'code': 'ios_pairing_storage',
                         'user_message': '请解锁Mac后重试。', 'recovery_action': '检查连接后重试'})


class IOSReuseServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.keychain = MemoryKeychain()
        identity = patch('capture_console.ios_setup.process_identity', return_value='owned test process')
        identity.start()
        self.addCleanup(identity.stop)

    def service(self, host='192.168.1.10'):
        return IOSSetupService(self.root, host_provider=lambda: host, keychain=self.keychain)

    def spawn(self, args, **kwargs):
        cfg = json.loads(Path(args[-1]).read_text())
        Path(cfg['state_path']).write_text(json.dumps({'phase': 'waiting_phone', 'connection_state': 'waiting_phone',
                                                       'recording_state': 'idle', 'flow_count': 0, 'flows': []}))
        process = Mock()
        process.poll.return_value = None
        return process

    def test_shutdown_and_three_restarts_reuse_identity_but_never_restore_ready(self):
        with patch('capture_console.ios_setup.subprocess.Popen', side_effect=self.spawn), \
                patch('capture_console.ios_setup.socket.socket') as sock:
            sock.return_value.__enter__.return_value.getsockname.return_value = ('192.168.1.10', 9190)
            first = None
            for _ in range(3):
                service = self.service()
                state = service.prepare('Office')
                actual = {k: service.config[k] for k in ('port', 'username', 'password', 'check_token', 'expires_at')}
                first = first or actual
                self.assertEqual(actual, first)
                self.assertEqual(state['phase'], 'waiting_phone')
                self.assertGreater(service.config['expires_at'], time.time() + 300 * 86400)
                service.shutdown()
                self.assertFalse(service.directory.exists())
                self.assertIsNotNone(self.keychain.data)
                reopened = self.service().status()
                self.assertTrue(reopened['can_resume'])
                self.assertNotEqual(reopened.get('connection_state'), 'ready')
                self.assertNotEqual(reopened.get('recording_state'), 'recording')
            service.stop()
            self.assertIsNone(self.keychain.data)

    def test_occupied_saved_port_does_not_rotate_or_spawn(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            identity = IOSPairingIdentity(self.root, keychain=self.keychain)
            saved = identity.create(listener.getsockname()[1])
            identity.remember(saved, 'Office', '192.168.1.10')
            service = self.service()
            with patch('capture_console.ios_setup.socket.socket') as sock, \
                    patch('capture_console.ios_setup.subprocess.Popen') as popen:
                sock.return_value.__enter__.return_value.bind.side_effect = OSError('occupied')
                with self.assertRaisesRegex(ValueError, '占用'):
                    service.prepare('Office')
                popen.assert_not_called()
                self.assertEqual(identity.load(), saved)
            self.assertEqual(listener.getsockname()[1], saved['port'])

    def test_old_connection_marker_still_requires_manual_cleanup(self):
        (self.root / 'cleanup-required').write_text('session-legacy')
        service = self.service()
        self.assertFalse(service.status().get('can_resume', False))
        with self.assertRaisesRegex(ValueError, '删除'):
            service.prepare('Office')
        self.assertIsNone(self.keychain.data)

    def test_failed_materialization_removes_temporary_secrets_but_keeps_identity(self):
        service = self.service()
        write_text = Path.write_text

        def fail_config(path, *args, **kwargs):
            if path.name == 'config.json':
                raise OSError('disk full')
            return write_text(path, *args, **kwargs)

        with patch('capture_console.ios_setup.socket.socket') as sock, \
                patch.object(Path, 'write_text', fail_config), \
                patch('capture_console.ios_setup.subprocess.Popen') as popen:
            sock.return_value.__enter__.return_value.getsockname.return_value = ('192.168.1.10', 9190)
            with self.assertRaisesRegex(OSError, 'disk full'):
                service.prepare('Office')
            popen.assert_not_called()
        self.assertFalse(service.directory.exists())
        self.assertIsNotNone(self.keychain.data)
        self.assertTrue(self.service().status()['can_resume'])

    def test_early_phone_validation_does_not_abort_healthy_startup(self):
        for phase in ('waiting_trust', 'ready'):
            with self.subTest(phase=phase):
                service = self.service()

                def spawn(args, **kwargs):
                    process = self.spawn(args, **kwargs)
                    cfg = json.loads(Path(args[-1]).read_text())
                    Path(cfg['state_path']).write_text(json.dumps({'phase': phase, 'connection_state': phase,
                                                                  'recording_state': 'idle', 'flow_count': 0, 'flows': []}))
                    return process

                with patch('capture_console.ios_setup.socket.socket') as sock, \
                        patch('capture_console.ios_setup.subprocess.Popen', side_effect=spawn), \
                        patch('capture_console.ios_setup.time.monotonic', side_effect=[0, 0, 0, 20]):
                    sock.return_value.__enter__.return_value.getsockname.return_value = ('192.168.1.10', 9190)
                    try:
                        self.assertEqual(service.prepare('Office')['phase'], phase)
                        self.assertIsNone(service.process.poll())
                    finally:
                        service.shutdown()

    def test_revoke_does_not_depend_on_metadata_surviving(self):
        service = self.service()
        service.identity.create(9190)
        self.assertFalse(service.identity.path.exists())
        service.stop()
        self.assertTrue(self.keychain.data is None, 'scoped identity was not revoked')

    def test_restart_reuses_time_wait_port_but_not_an_active_listener(self):
        listener = socket.socket()
        self.addCleanup(listener.close)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        listener.listen()
        with socket.create_connection(('127.0.0.1', port), timeout=2) as client:
            accepted, _ = listener.accept()
            with accepted:
                accepted.settimeout(2)
                accepted.shutdown(socket.SHUT_WR)
                self.assertEqual(client.recv(1), b'')
                client.shutdown(socket.SHUT_WR)
                self.assertEqual(accepted.recv(1), b'')
        listener.close()
        service = self.service(host='127.0.0.1')
        identity = service.identity.create(port)
        service.identity.remember(identity, 'Office', '127.0.0.1')
        # Only the test address validator is overridden; real kernel bind semantics remain in use.
        with patch('capture_console.ios_setup.ipaddress.ip_address') as address, \
                patch('capture_console.ios_setup.subprocess.Popen', side_effect=self.spawn) as worker:
            address.return_value.is_private = True
            address.return_value.is_loopback = address.return_value.is_link_local = False
            address.return_value.version = 4
            try:
                self.assertEqual(service.prepare('Office')['phase'], 'waiting_phone')
            finally:
                service.shutdown()
            with socket.socket() as occupied:
                occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                occupied.bind(('127.0.0.1', port))
                occupied.listen()
                with self.assertRaisesRegex(ValueError, '占用'):
                    service.prepare('Office')
                self.assertEqual(worker.call_count, 1)

    def test_address_change_survives_failed_start_until_phone_revalidates(self):
        service = self.service(host='192.168.1.20')
        identity = service.identity.create(9190)
        service.identity.remember(identity, 'Office', '192.168.1.10')
        with patch('capture_console.ios_setup.socket.socket') as sock:
            sock.return_value.__enter__.return_value.getsockname.return_value = ('192.168.1.20', 9190)
            with patch('capture_console.ios_setup.subprocess.Popen', side_effect=OSError('start failed')):
                with self.assertRaises(OSError):
                    service.prepare('Office')
            with patch('capture_console.ios_setup.subprocess.Popen', side_effect=self.spawn):
                try:
                    service.prepare('Office')
                    self.assertTrue(service.config['route_changed'])
                    state = {'phase': 'ready', 'connection_state': 'ready', 'recording_state': 'idle'}
                    Path(service.config['state_path']).write_text(json.dumps(state))
                    service.status()
                    service.shutdown()
                    service.prepare('Office')
                    self.assertFalse(service.config['route_changed'])
                    self.assertEqual(service.identity.load(), identity)
                finally:
                    service.shutdown()


if __name__ == '__main__':
    unittest.main()

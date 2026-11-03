"""Opt-in wire/lifetime checks: isolated local proxy, no phone/device changes."""

import base64
from datetime import datetime, timedelta, timezone
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import os
import plistlib
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from capture_console.ios_setup import IOSSetupService
from capture_console.ios_results import IOSCaptureArchive
from capture_console.ios_pairing_identity import IOSPairingIdentity
from capture_console.ios_setup import local_wifi_address
import socket
from tests.test_ios_identity import MemoryKeychain


@unittest.skipUnless(os.environ.get("CAPTURE_TEST_IOS_PROXY") == "1", "opt-in LAN proxy test")
class IOSSetupIntegrationTests(unittest.TestCase):
    def test_same_trust_and_credentials_survive_three_proxy_restarts_after_two_days(self):
        with tempfile.TemporaryDirectory(prefix='ios-reuse-wire-') as tmp:
            root = Path(tmp) / 'ios-setup'
            keychain = MemoryKeychain()
            host = local_wifi_address()
            with socket.socket() as available:
                available.bind((host, 0))
                port = available.getsockname()[1]
            identity = IOSPairingIdentity(root, keychain=keychain, clock=lambda: time.time() - 2 * 86400)
            saved = identity.create(port)
            identity.remember(saved, 'Synthetic Reuse Only', host)
            cert = x509.load_pem_x509_certificate(saved['pem'].encode())
            trust = ssl.create_default_context(cadata=cert.public_bytes(serialization.Encoding.PEM).decode())
            auth = 'Basic ' + base64.b64encode(f"{saved['username']}:{saved['password']}".encode()).decode()
            service = None
            try:
                for _ in range(3):
                    service = IOSSetupService(root, keychain=keychain)
                    self.assertTrue(service.status()['can_resume'])
                    state = service.prepare('Synthetic Reuse Only')
                    self.assertEqual(state['phase'], 'waiting_phone')
                    self.assertTrue(state['identity_reused'])
                    self.assertEqual(service.config['port'], port)
                    with self.assertRaises(ValueError):
                        service.start_recording('pokehub')
                    profile = plistlib.loads(Path(state['profile_path']).read_bytes())
                    self.assertEqual(profile['PayloadContent'][1]['PayloadContent'],
                                     cert.public_bytes(serialization.Encoding.DER))
                    conn = http.client.HTTPSConnection(host, port, context=trust, timeout=5)
                    conn.set_tunnel('capture-check.invalid', 443, headers={'Proxy-Authorization': auth})
                    try:
                        conn.request('GET', '/' + saved['check_token'])
                        response = conn.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertIn(b'HTTPS', response.read())
                    finally:
                        conn.close()
                    self.assertEqual(service.status()['phase'], 'waiting_phone')
                    worker = service.process
                    directory = service.directory
                    service.shutdown()
                    self.assertIsNotNone(worker.poll())
                    self.assertFalse(directory.exists())
                    self.assertEqual(identity.load(), saved)
                service.stop()
                self.assertIsNone(keychain.data)
                self.assertFalse((root / 'identity.json').exists())
            finally:
                if service:
                    service.stop()

    def test_real_http_tls_stop_passthrough_restart_and_scope(self):
        class Origin(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        with tempfile.TemporaryDirectory(prefix='ios-wire-') as tmp:
            root = Path(tmp)
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Local Test Only')])
            cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                    .serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
                    .not_valid_after(datetime.now(timezone.utc) + timedelta(hours=1))
                    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                    .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1')),
                                                               x509.DNSName('localhost')]), critical=False)
                    .sign(key, hashes.SHA256()))
            certificate = root / 'origin.pem'
            certificate.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            private = root / 'origin.key'
            private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                  serialization.NoEncryption()))
            server = ThreadingHTTPServer(('127.0.0.1', 0), Origin)
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(certificate, private)
            server.socket = tls.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            plain = ThreadingHTTPServer(('127.0.0.1', 0), Origin)
            plain_thread = threading.Thread(target=plain.serve_forever, daemon=True)
            plain_thread.start()
            service = IOSSetupService(root / 'setup', keychain=MemoryKeychain())
            original_popen = subprocess.Popen

            def spawn(args, **kwargs):
                if args[1:3] == ['-m', 'capture_console.ios_pairing_proxy']:
                    args = [args[0], '-m', 'tests.ios_proxy_worker_fixture', args[-1], str(certificate)]
                return original_popen(args, **kwargs)

            try:
                with patch('capture_console.ios_setup.subprocess.Popen', side_effect=spawn):
                    state = service.prepare('Wire Acceptance Only')
                cfg = service.config
                profile_before = Path(state['profile_path']).read_bytes()
                ca = plistlib.loads(profile_before)['PayloadContent'][1]['PayloadContent']
                trust = ssl.create_default_context(cadata=ssl.DER_cert_to_PEM_cert(ca))
                trust.load_verify_locations(cafile=certificate)
                auth = 'Basic ' + base64.b64encode(f"{cfg['username']}:{cfg['password']}".encode()).decode()

                unauthorized = http.client.HTTPConnection(cfg['host'], cfg['port'], timeout=5)
                unauthorized.request('POST', f'http://127.0.0.1:{plain.server_port}/unrelated', b'not-recorded')
                self.assertEqual(unauthorized.getresponse().status, 407)
                unauthorized.close()
                unauthorized_tls = http.client.HTTPSConnection(cfg['host'], cfg['port'], context=trust, timeout=5)
                unauthorized_tls.set_tunnel('localhost', server.server_port)
                with self.assertRaisesRegex(OSError, '407'):
                    unauthorized_tls.connect()
                unauthorized_tls.close()

                def request(host='127.0.0.1', secure=True):
                    if secure:
                        conn = http.client.HTTPSConnection(cfg['host'], cfg['port'], context=trust, timeout=5)
                        conn.set_tunnel(host, server.server_port, headers={'Proxy-Authorization': auth})
                        path, headers = '/items?full=query', {'Content-Type': 'application/json'}
                    else:
                        conn = http.client.HTTPConnection(cfg['host'], cfg['port'], timeout=5)
                        path = f'http://{host}:{plain.server_port}/items?full=query'
                        headers = {'Proxy-Authorization': auth, 'Content-Type': 'application/json'}
                    try:
                        conn.request('POST', path, b'{"wire":true}', headers)
                        response = conn.getresponse()
                        self.assertEqual((response.status, response.read()), (200, b'{"wire":true}'))
                    finally:
                        conn.close()

                probe = http.client.HTTPSConnection(cfg['host'], cfg['port'], context=trust, timeout=5)
                probe.set_tunnel('capture-check.invalid', 443, headers={'Proxy-Authorization': auth})
                probe.request('GET', '/' + cfg['check_token'])
                self.assertEqual(probe.getresponse().status, 200)
                probe.close()
                for _ in range(30):
                    if service.status().get('connection_state') == 'ready':
                        break
                    time.sleep(0.1)
                request()
                self.assertEqual(service.status()['flow_count'], 0)
                project = service.projects.save(name='Controlled', domains=['127.0.0.1'])
                first = service.start_recording(project['id'])
                first_archive = IOSCaptureArchive(service.session['outdir'], read_only=True)
                request()
                request(secure=False)
                request(host='localhost')
                stopped = service.stop_recording()
                self.assertEqual(stopped['connection_state'], 'ready')
                first_page = first_archive.page()
                self.assertEqual(first_page['total'], 2)
                for row in first_page['flows']:
                    detail = first_archive.detail(row['id'])
                    self.assertEqual((detail['request_text'], detail['response_text']), ('{"wire":true}', '{"wire":true}'))
                    self.assertNotIn('Proxy-Authorization', first_archive.curl(row['id']))
                request()
                request(secure=False)
                self.assertEqual(first_archive.page(), first_page)
                self.assertIsNone(service.process.poll())
                self.assertEqual(Path(state['profile_path']).read_bytes(), profile_before)
                second = service.start_recording(project['id'])
                self.assertNotEqual(first['session_id'], second['session_id'])
                request()
                service.stop_recording()
                self.assertEqual(IOSCaptureArchive(service.session['outdir'], read_only=True).page()['total'], 1)
                self.assertEqual(first_archive.page(), first_page)
                third = service.start_recording(project['id'])
                request()
                request()
                request()
                for _ in range(30):
                    limited = service.status()
                    if limited['recording_state'] == 'limit_reached':
                        break
                    time.sleep(0.1)
                self.assertEqual(limited['recording_state'], 'limit_reached')
                self.assertEqual(limited['connection_state'], 'ready')
                self.assertEqual(service.store.get_session(third['session_id'])['status'], 'stopped')
                request()
                self.assertEqual(IOSCaptureArchive(service.session['outdir'], read_only=True).page()['total'], 2)
            finally:
                service.stop()
                server.shutdown()
                plain.shutdown()
                server.server_close()
                plain.server_close()
                thread.join(timeout=3)
                plain_thread.join(timeout=3)

    def test_authenticated_tls_and_desktop_exit_cleanup(self):
        with tempfile.TemporaryDirectory(prefix="ios-setup-acceptance-") as tmp:
            # A separately owned inert process stands in for the desktop lifecycle.
            desktop = subprocess.Popen(["/bin/sleep", "60"])
            keychain = MemoryKeychain()
            service = IOSSetupService(Path(tmp) / "ios-setup", keychain=keychain)
            try:
                state = service.prepare("Acceptance Test Only", owner_pid=desktop.pid)
                cfg = service.config
                profile = plistlib.loads(Path(state["profile_path"]).read_bytes())
                wifi, ca, _ = profile["PayloadContent"]
                self.assertEqual((wifi["ProxyServer"], wifi["ProxyServerPort"]), (cfg["host"], cfg["port"]))
                self.assertNotIn("Password", wifi)
                trust = ssl.create_default_context(cadata=ssl.DER_cert_to_PEM_cert(ca["PayloadContent"]))
                unauthenticated = http.client.HTTPSConnection(cfg["host"], cfg["port"], context=trust, timeout=5)
                unauthenticated.set_tunnel("capture-check.invalid", 443)
                try:
                    with self.assertRaisesRegex(OSError, "407"):
                        unauthenticated.connect()
                finally:
                    unauthenticated.close()
                auth = base64.b64encode(f"{cfg['username']}:{cfg['password']}".encode()).decode()
                connection = http.client.HTTPSConnection(cfg["host"], cfg["port"], context=trust, timeout=5)
                connection.set_tunnel("capture-check.invalid", 443, headers={"Proxy-Authorization": "Basic " + auth})
                try:
                    connection.request("GET", "/" + cfg["check_token"])
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertIn("HTTPS", response.read().decode())
                finally:
                    connection.close()
                self.assertEqual(service.status()["phase"], "waiting_phone")
                worker = service.process
                directory = service.directory
                desktop.terminate()
                desktop.wait(timeout=3)
                self.assertEqual(worker.wait(timeout=6), 0)
                self.assertEqual(service.status()["phase"], "failed")
                for name in ["ca", "config.json", "iPhone.mobileconfig"]:
                    self.assertFalse((directory / name).exists(), name)
                self.assertTrue(service.marker.exists())
                restarted = IOSSetupService(service.root, keychain=keychain)
                self.assertEqual(restarted.status()["phase"], "failed")
                self.assertTrue(restarted.status()['can_resume'])
                restarted.stop()
                self.assertFalse(service.marker.exists())
                self.assertFalse(directory.exists())
            finally:
                service.stop()
                if desktop.poll() is None:
                    desktop.terminate()
                    desktop.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()

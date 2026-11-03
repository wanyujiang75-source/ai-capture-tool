"""Persistent one-year iPhone identity; secrets live only in macOS Keychain."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import time

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from .ios_keychain import IOSPairingError, MacOSPairingKeychain


class IOSPairingIdentity:
    def __init__(self, root, *, keychain=None, clock=time.time):
        self.root = Path(root)
        self.path = self.root / 'identity.json'
        account = hashlib.sha256(str(self.root.resolve()).encode()).hexdigest()
        self.keychain = keychain if keychain is not None else MacOSPairingKeychain(account)
        self.clock = clock

    def load(self):
        raw = self.keychain.read()
        if raw is None and not self.path.exists():
            return None
        try:
            if raw is None or len(raw) > 32768:
                raise ValueError('missing identity')
            value = json.loads(raw)
            if (value['version'] != 1 or not 1024 <= value['port'] <= 65535
                    or value['username'] != 'ios' or len(value['password']) < 24
                    or len(value['check_token']) != 32):
                raise ValueError('invalid identity')
            pem = value['pem'].encode()
            certificate = x509.load_pem_x509_certificate(pem)
            private = serialization.load_pem_private_key(pem, password=None)
            if (private.public_key().public_numbers() != certificate.public_key().public_numbers()
                    or not certificate.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
                    or int(certificate.not_valid_after_utc.timestamp()) != value['expires_at']):
                raise ValueError('invalid certificate')
        except (ValueError, KeyError, TypeError, AttributeError, x509.ExtensionNotFound):
            raise IOSPairingError('ios_pairing_invalid', '抓包身份缺失或损坏，请恢复手机网络并结束连接后重新配置。') from None
        now = self.clock()
        if now >= value['expires_at']:
            raise IOSPairingError('ios_pairing_expired', '抓包证书已到期，请恢复手机网络并结束连接后更新证书。')
        if now < certificate.not_valid_before_utc.timestamp():
            raise IOSPairingError('ios_pairing_clock', '本机时间早于证书生效时间，请检查系统时间。')
        return value

    def create(self, port):
        now = datetime.fromtimestamp(int(self.clock()), timezone.utc)
        token = secrets.token_hex(16)
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Capture iPhone Test ' + token[:6])])
        certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                       .public_key(private.public_key()).serial_number(x509.random_serial_number())
                       .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=365))
                       .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                       .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                                   key_encipherment=False, data_encipherment=False,
                                                   key_agreement=False, key_cert_sign=True, crl_sign=True,
                                                   encipher_only=False, decipher_only=False), critical=True)
                       .add_extension(x509.SubjectKeyIdentifier.from_public_key(private.public_key()), critical=False)
                       .sign(private, hashes.SHA256()))
        pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                    serialization.NoEncryption()) + certificate.public_bytes(serialization.Encoding.PEM)
        identity = {'version': 1, 'username': 'ios', 'password': secrets.token_urlsafe(24),
                    'port': port, 'check_token': token, 'pem': pem.decode(),
                    'expires_at': int(certificate.not_valid_after_utc.timestamp())}
        self.keychain.create(json.dumps(identity).encode())
        return identity

    def remember(self, identity, ssid, host, *, route_pending=False):
        certificate = x509.load_pem_x509_certificate(identity['pem'].encode())
        value = {'version': 1, 'ssid': ssid, 'host': host, 'expires_at': identity['expires_at'],
                 'certificate_name': certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value,
                 'certificate_fingerprint': certificate.fingerprint(hashes.SHA256()).hex(),
                 'route_pending': route_pending}
        self._write_metadata(value)

    def confirm_route(self):
        value = json.loads(self.path.read_text())
        value['route_pending'] = False
        self._write_metadata(value)

    def _write_metadata(self, value):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink() or self.path.is_symlink():
            raise ValueError('抓包身份目录异常，未写入配置。')
        self.root.chmod(0o700)
        descriptor, name = tempfile.mkstemp(prefix='identity-', suffix='.tmp', dir=self.root)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(value, stream)
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def resume_state(self):
        try:
            if self.path.is_symlink() or self.path.stat().st_size > 4096:
                return {'can_resume': False}
            value = json.loads(self.path.read_text())
            valid = value['version'] == 1 and self.clock() < value['expires_at']
            return {'can_resume': valid, 'ssid': value['ssid'], 'certificate_name': value['certificate_name'],
                    'certificate_expires_at': value['expires_at'], 'identity_reused': True}
        except (OSError, ValueError, KeyError, TypeError):
            return {'can_resume': False}

    def clear(self):
        self.keychain.delete()
        self.path.unlink(missing_ok=True)

import os
import subprocess
import sys
import unittest
import uuid

from capture_console.ios_keychain import MacOSPairingKeychain


@unittest.skipUnless(sys.platform == 'darwin' and os.environ.get('CAPTURE_TEST_IOS_KEYCHAIN') == '1',
                     'opt-in isolated macOS Keychain check')
class IOSKeychainTests(unittest.TestCase):
    def test_create_read_duplicate_and_delete_only_test_entry(self):
        keychain = MacOSPairingKeychain('acceptance-' + uuid.uuid4().hex,
                                      service='com.local.capture.ios.acceptance')
        self.addCleanup(keychain.delete)
        self.assertIsNone(keychain.read())
        keychain.create(b'isolated test value - not a real credential')
        self.assertEqual(keychain.read(), b'isolated test value - not a real credential')
        child = subprocess.run([sys.executable, '-B', '-c',
                                'from capture_console.ios_keychain import MacOSPairingKeychain; '
                                'import sys; '
                                'value = MacOSPairingKeychain(sys.argv[1], service=sys.argv[2]).read(); '
                                'assert value == b"isolated test value - not a real credential"',
                                keychain.account, keychain.service], capture_output=True, text=True, timeout=10)
        self.assertEqual(child.returncode, 0, child.stderr)
        with self.assertRaises(ValueError):
            keychain.create(b'must not overwrite')
        self.assertEqual(keychain.read(), b'isolated test value - not a real credential')
        keychain.delete()
        self.assertIsNone(keychain.read())


if __name__ == '__main__':
    unittest.main()

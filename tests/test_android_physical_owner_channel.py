import hashlib
import unittest
from unittest.mock import Mock
from capture_console.android_physical_device import PhysicalDevice


class OwnerChannelTests(unittest.TestCase):
    def test_channel_name_does_not_disclose_authentication_token(self):
        device = PhysicalDevice('adb', 'phone')
        device.call = Mock(return_value='12345\n')
        token = 'ab' * 32
        channel = device.open_owner_channel(token)
        self.assertEqual(channel, {'port': 12345, 'remote': 'localabstract:capture-owner-' + hashlib.sha256(token.encode()).hexdigest()})
        self.assertNotIn(token, repr(device.call.call_args))

    def test_cleanup_only_removes_exact_owned_forward(self):
        device = PhysicalDevice('adb', 'phone')
        remote = 'localabstract:capture-owner-' + 'a' * 64
        channel = {'port': 12345, 'remote': remote}
        for mapping, removed in ((f'phone tcp:12345 {remote}', True),
                                 (f'other tcp:12345 {remote}', False),
                                 ('phone tcp:12345 tcp:8080', False), ('', False)):
            device.call = Mock(return_value=mapping)
            device.close_owner_channel(channel)
            self.assertEqual(device.call.call_count, 2 if removed else 1)
            if removed:
                device.call.assert_called_with('forward', '--remove', 'tcp:12345', timeout=3)

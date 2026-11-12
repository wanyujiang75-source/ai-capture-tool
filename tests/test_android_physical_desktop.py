import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import subprocess

from mitmproxy import connection, http
from capture_console.android_physical_worker import PhysicalRecorder, single_app_config
from capture_console.android_physical_device import BRIDGE, PhysicalDevice, parse_vpn, foreground_package


class PhysicalContractTests(unittest.TestCase):
    def test_shared_uid_target_is_rejected_before_takeover(self):
        device = PhysicalDevice('adb', 'phone')
        for packages, allowed in (
            ('package:com.app.target uid:10123\npackage:com.other uid:10124\n', True),
            ('package:com.app.target uid:10123\npackage:com.sibling uid:10123\n', False),
            ('package:com.app.target uid:1000\n', False),
            ('package:com.app.other uid:10123\n', False),
            ('unrecognized output', False),
        ):
            with self.subTest(packages=packages), patch.object(device, 'shell', return_value=packages):
                if allowed:
                    device.require_single_uid('com.app.target')
                else:
                    with self.assertRaises(ValueError): device.require_single_uid('com.app.target')

    def test_pending_consent_must_acknowledge_cancellation(self):
        device = PhysicalDevice('adb', 'phone')
        commands = []
        def shell(*args, **kwargs):
            commands.append(args)
            if args[-1] == 'files/stop_ack':
                return next(acks)
            return ''
        acks = iter(['old-session', 'stop-token'])
        with patch.object(device, 'installed', return_value=True), \
             patch.object(device, 'write') as write, \
             patch.object(device, 'shell', side_effect=shell), \
             patch('capture_console.android_physical_device.uuid.uuid4', return_value=Mock(hex='stop-token')), \
             patch('capture_console.android_physical_device.time.sleep'):
            device.stop()
            write.assert_called_once_with('stop', 'stop-token')
            force_stop = ('am', 'force-stop', '--user', '0', BRIDGE)
            self.assertIn(force_stop, commands)
            self.assertGreater(commands.index(force_stop), 1)

    def test_unacknowledged_consent_does_not_appear_stopped(self):
        device = PhysicalDevice('adb', 'phone')
        with patch.object(device, 'installed', return_value=True), \
             patch.object(device, 'write'), patch.object(device, 'shell', return_value='old-ack'), \
             patch('capture_console.android_physical_device.time.sleep'):
            with self.assertRaises(ValueError): device.stop()

    def test_helper_absence_is_not_reported_as_usb_failure(self):
        device = PhysicalDevice('adb', 'phone')
        def package_manager(command, **kwargs):
            if 'pm path' in command[-1]:
                return subprocess.CompletedProcess(command, 1, b'', b'')
            self.assertEqual(command[-1], f'pm list packages --user 0 {BRIDGE}')
            return subprocess.CompletedProcess(command, 0, b'', b'')
        with patch('capture_console.android_physical_device.subprocess.run', side_effect=package_manager):
            self.assertFalse(device.installed())
            device.stop()
            device.cleanup()

    def test_helper_presence_requires_exact_package_match(self):
        device = PhysicalDevice('adb', 'phone')
        for output, expected in ((f'package:{BRIDGE}.other\n', False),
                                 (f'package:{BRIDGE}\n', True)):
            with self.subTest(output=output), patch.object(device, 'shell', return_value=output):
                self.assertEqual(device.installed(), expected)

    def test_helper_check_propagates_real_usb_failure(self):
        device = PhysicalDevice('adb', 'phone')
        with patch('capture_console.android_physical_device.subprocess.run',
                   return_value=subprocess.CompletedProcess([], 1, b'', b'device offline')):
            with self.assertRaises(RuntimeError):
                device.installed()

    def test_tunnel_excludes_all_other_applications_and_no_ipv6_escape(self):
        config = single_app_config('[Interface]\nPrivateKey = secret\n[Peer]\nAllowedIPs = 0.0.0.0/0\n', 'com.mi.poketrade')
        self.assertIn('IncludedApplications = com.mi.poketrade\n', config)
        self.assertIn('AllowedIPs = 0.0.0.0/0, ::/0', config)
        for package in ('com.app\nExcludedApplications = a', 'android', ''):
            with self.assertRaises(ValueError): single_app_config('', package)

    def test_device_parsing_fails_closed(self):
        self.assertEqual(parse_vpn('mPackage=com.example.vpn\nmNetworkInfo=[type: VPN[], state: CONNECTED/CONNECTED]'), 'com.example.vpn')
        self.assertIsNone(parse_vpn('mPackage=com.example.vpn\nmNetworkInfo=[type: VPN[], state: DISCONNECTED/DISCONNECTED]'))
        self.assertEqual(foreground_package('mResumedActivity: ActivityRecord{a u0 com.mi.poketrade/.MainActivity t9}'), 'com.mi.poketrade')
        with self.assertRaises(ValueError): foreground_package('mResumedActivity: ActivityRecord{a u10 com.mi.poketrade/.MainActivity t9}')

    def test_streamed_archive_preserves_request_and_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {'outdir': tmp, 'session_id': 1, 'upstream': ['127.0.0.1', 7897]}
            recorder = PhysicalRecorder(cfg)
            flow = http.HTTPFlow(connection.Client(peername=('10.0.0.1', 22), sockname=('192.168.1.1', 5)), connection.Server(address=('198.18.0.1', 443)))
            flow.client_conn.sni = 'api.example.com'
            flow.request = http.Request.make('POST', 'https://api.example.com/api', b'{"a":1}', {'content-type': 'application/json'})
            original_headers = flow.request.headers.fields
            recorder.requestheaders(flow)
            flow.request.stream(b'{"a":1}')
            recorder.request(flow)
            flow.response = http.Response.make(200, b'{"ok":true}', {'content-type': 'application/json'})
            recorder.responseheaders(flow)
            flow.response.stream(b'{"ok":true}')
            recorder.response(flow)
            detail = recorder.recording.archive.detail(flow.id)
            self.assertEqual(flow.request.headers.fields, original_headers)
            self.assertEqual(flow.server_conn.address, ('api.example.com', 443))
            self.assertEqual(flow.server_conn.via, ('http', ('127.0.0.1', 7897)))
            self.assertEqual(json.loads(detail['request_text']), {'a': 1})
            self.assertEqual(json.loads(detail['response_text']), {'ok': True})
            self.assertEqual(recorder.state['response_count'], 1)

    def test_host_mismatch_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = PhysicalRecorder({'outdir': tmp, 'session_id': 1, 'upstream': None})
            flow = Mock()
            flow.client_conn.sni = 'one.example'
            flow.request.host = 'two.example'
            flow.request.scheme = 'https'
            flow.request.headers.get.return_value = 'two.example'
            recorder.requestheaders(flow)
            flow.kill.assert_called_once()
            self.assertEqual(recorder.state['flow_count'], 0)

    def test_https_authority_port_must_match_the_actual_destination(self):
        for authority, port, accepted in (('api.example.com:8443', 8443, True),
                                          ('api.example.com:443', 8443, False),
                                          ('api.example.com:invalid', 443, False)):
            with self.subTest(authority=authority), tempfile.TemporaryDirectory() as tmp:
                recorder = PhysicalRecorder({'outdir': tmp, 'session_id': 1, 'upstream': None})
                flow = http.HTTPFlow(connection.Client(peername=('10.0.0.1', 22), sockname=('192.168.1.1', 5)),
                                     connection.Server(address=('198.18.0.1', port)))
                flow.client_conn.sni = 'api.example.com'
                flow.live = True
                flow.request = http.Request.make('GET', f'https://api.example.com:{port}/api')
                flow.request.headers['host'] = authority
                recorder.requestheaders(flow)
                self.assertEqual(flow.error is None, accepted)
                recorder.recording.archive.close()

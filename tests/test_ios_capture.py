import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from mitmproxy import options, tls
from mitmproxy.proxy.context import Context

from capture_console.ios_pairing_proxy import PairingMonitor
from capture_console.ios_results import IOSCaptureArchive
from capture_console.ios_setup import IOSSetupService
from capture_console.store import CaptureStore
from tests.test_ios_setup import config
from tests.test_ios_results import make_flow


class IOSRecordingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = config(self.root)
        self.cfg['capture_root'] = str(self.root / 'captures')
        self.monitor = PairingMonitor(self.cfg)
        self.switch = Mock()

    def flow(self, host='api.example.test'):
        flow = make_flow('https://' + host + '/items?full=query')
        flow.client_conn.tls = True
        flow.metadata['proxyauth'] = (self.cfg['username'], self.cfg['password'])
        return flow

    def ready(self):
        flow = self.flow('capture-check.invalid')
        flow.request.path = '/' + self.cfg['check_token']
        self.monitor.request(flow)
        self.monitor.response(flow)

    def start(self, revision=1, session_id=10, *, device=False):
        command = {'revision': revision, 'action': 'start', 'session_id': session_id,
                   'outdir': str(self.root / 'captures' / str(session_id)),
                   'project': {'id': 'test', 'name': 'Test', 'domains': ['api.example.test']}}
        if device:
            command.update(capture_scope='device', project={'id': 'iphone', 'name': 'iPhone', 'domains': []})
        self.monitor.recording.apply(command, self.switch)

    def test_device_capture_records_unknown_domains_without_a_project(self):
        self.ready()
        self.start(device=True)
        self.assertIsNone(self.switch.call_args.args[0])
        for host in ['music.example.test', 'wish.example.test', 'stickers.example.test']:
            self.send(self.flow(host))
        archive = self.monitor.recording.archive
        page = archive.page()
        self.assertEqual(page['total'], 3)
        for row in page['flows']:
            self.assertEqual(archive.detail(row['id'])['response_text'], '{"response":true}')
        self.monitor.recording.apply({'revision': 2, 'action': 'stop'}, self.switch)
        self.assertEqual(self.switch.call_args.args, ([],))
        self.send(self.flow('later.example.test'))
        self.assertEqual(archive.page(), page)
        self.assertEqual(self.monitor.state['connection_state'], 'ready')

    def test_device_capture_still_excludes_checks_and_unauthenticated_or_local_clients(self):
        self.ready()
        self.start(device=True)
        self.ready()
        self.send(self.flow('capture-check.invalid'))
        unauthenticated = self.flow('another.example.test')
        unauthenticated.metadata.clear()
        self.send(unauthenticated)
        local = self.flow('another.example.test')
        local.client_conn.peername = (self.cfg['host'], 12345)
        self.send(local)
        self.assertEqual(self.monitor.state['flow_count'], 0)
        self.send(self.flow('not-preconfigured.example.test'))
        self.assertEqual(self.monitor.state['flow_count'], 1)

    def test_tls_interception_requires_authenticated_bound_phone_before_handshake(self):
        self.ready()
        self.start(device=True)

        def hello(flow):
            self.monitor.http_connect(flow)
            data = tls.ClientHelloData(Context(flow.client_conn, options.Options()),
                                       Mock(sni=flow.request.host))
            self.monitor.tls_clienthello(data)
            return data.ignore_connection

        self.assertFalse(hello(self.flow('unknown.example.test')))
        local = self.flow('unknown.example.test')
        local.client_conn.peername = (self.cfg['host'], 1234)
        self.assertTrue(hello(local))
        unauthenticated = self.flow('unknown.example.test')
        unauthenticated.metadata.clear()
        self.assertTrue(hello(unauthenticated))
        unknown = tls.ClientHelloData(Context(self.flow().client_conn, options.Options()), Mock())
        self.monitor.tls_clienthello(unknown)
        self.assertTrue(unknown.ignore_connection)
        check = self.flow('capture-check.invalid')
        check.client_conn.peername = (self.cfg['host'], 1234)
        self.assertFalse(hello(check))
        untrusted_check = self.flow('capture-check.invalid')
        untrusted_check.metadata.clear()
        self.assertTrue(hello(untrusted_check))
        changed = self.flow('unknown.example.test')
        changed.client_conn.peername = ('192.168.1.12', 1234)
        self.assertTrue(hello(changed))
        self.assertEqual(self.monitor.state['recording_state'], 'failed')
        self.assertTrue(hello(self.flow()))

    def test_tls_interception_stops_immediately_before_existing_connection_handshake(self):
        self.ready()
        self.start(device=True)
        flow = self.flow()
        self.monitor.http_connect(flow)
        self.monitor.recording.apply({'revision': 2, 'action': 'stop'}, self.switch)
        data = tls.ClientHelloData(Context(flow.client_conn, options.Options()), Mock(sni=flow.request.host))
        self.monitor.tls_clienthello(data)
        self.assertTrue(data.ignore_connection)

    def send(self, flow):
        self.monitor.requestheaders(flow)
        if callable(flow.request.stream):
            flow.request.stream(flow.request.raw_content)
        self.monitor.request(flow)
        self.monitor.responseheaders(flow)
        if callable(flow.response.stream):
            flow.response.stream(flow.response.raw_content)
        self.monitor.response(flow)

    def test_connection_ready_does_not_record_until_user_starts(self):
        self.ready()
        self.send(self.flow())
        self.assertEqual(self.monitor.state['connection_state'], 'ready')
        self.assertEqual(self.monitor.state['recording_state'], 'idle')
        self.assertEqual(self.monitor.state['flow_count'], 0)
        self.start()
        self.send(self.flow())
        self.send(self.flow('unrelated.test'))
        self.assertEqual(self.monitor.state['flow_count'], 1)
        result = self.monitor.recording.archive.page()['flows'][0]
        detail = self.monitor.recording.archive.detail(result['id'])
        self.assertEqual(detail['response_text'], '{"response":true}')

    def test_stop_retains_connection_and_late_callbacks_cannot_enter_new_session(self):
        self.ready()
        self.start()
        old = self.flow()
        self.monitor.requestheaders(old)
        callback = old.request.stream
        archive = self.monitor.recording.archive
        self.monitor.recording.apply({'revision': 2, 'action': 'stop'}, self.switch)
        self.assertEqual(self.monitor.state['connection_state'], 'ready')
        self.assertEqual(self.monitor.state['recording_state'], 'stopped')
        before = archive.page()
        self.start(revision=3, session_id=11)
        self.assertEqual(callback(b'old body'), b'old body')
        self.monitor.response(old)
        self.assertEqual(archive.page(), before)
        self.assertEqual(self.monitor.recording.archive.page()['total'], 0)
        self.send(self.flow())
        self.assertEqual(self.monitor.state['flow_count'], 1)
        self.assertEqual(self.monitor.state['applied_revision'], 3)
        self.assertEqual(self.switch.call_count, 3)

    def test_start_requires_real_phone_https_and_revisions_are_idempotent(self):
        with self.assertRaises(ValueError):
            self.start()
        self.ready()
        self.start()
        first = self.monitor.recording.archive
        self.start()
        self.assertIs(self.monitor.recording.archive, first)
        self.assertEqual(self.switch.call_count, 1)

    def test_quota_stops_writes_and_returns_to_passthrough(self):
        self.ready()
        self.start()
        self.monitor.recording.archive.record_limit = 1
        self.send(self.flow())
        self.send(self.flow())
        self.monitor.recording.check_limit(self.switch)
        self.assertEqual(self.monitor.state['recording_state'], 'limit_reached')
        self.assertEqual(self.monitor.state['connection_state'], 'ready')
        self.assertEqual(self.switch.call_args.args[0], [])

    def test_storage_error_does_not_break_network_stream(self):
        self.ready()
        self.start()
        flow = self.flow()
        self.monitor.requestheaders(flow)
        with patch.object(self.monitor.recording.archive, 'append_body', side_effect=sqlite3.OperationalError('disk full')):
            self.assertEqual(flow.request.stream(b'forward'), b'forward')
        self.monitor.recording.check_limit(self.switch)
        self.assertEqual(self.monitor.state['recording_state'], 'limit_reached')
        self.assertEqual(self.monitor.state['limit_reason'], 'storage_error')

    def test_phone_address_change_requires_new_https_check_and_never_resumes_recording(self):
        self.ready()
        self.start()
        changed = self.flow()
        changed.client_conn.peername = ('192.168.1.12', 5555)
        self.monitor.requestheaders(changed)
        self.assertEqual(self.monitor.state['connection_state'], 'waiting_trust')
        self.assertEqual(self.monitor.state['recording_state'], 'failed')
        self.monitor.recording.check_limit(self.switch)
        self.assertEqual(self.switch.call_args.args[0], [])
        probe = self.flow('capture-check.invalid')
        probe.request.path = '/' + self.cfg['check_token']
        probe.client_conn.peername = ('192.168.1.12', 5556)
        count = self.switch.call_count
        self.monitor.http_connect(probe)
        self.monitor.requestheaders(probe)
        self.monitor.recording.check_limit(self.switch)
        self.assertEqual(self.switch.call_count, count)
        self.monitor.request(probe)
        self.monitor.response(probe)
        self.assertEqual(self.monitor.state['connection_state'], 'ready')
        self.assertEqual(self.monitor.state['client_ip'], '192.168.1.12')
        self.assertEqual(self.monitor.state['recording_state'], 'failed')


class IOSCaptureServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = CaptureStore(self.root / 'console.db')

    def test_ios_session_is_not_an_android_device_and_can_coexist(self):
        self.store.upsert_device(device_id='android-test', name='Android', avd_name='Test_AVD',
                                 adb_serial='emulator-5554', proxy_port=9090, web_port=9091, frida_port=27042)
        android = self.store.create_session(app_id=None, device_id='android-test', mode='flutter-socks',
                                            outdir=str(self.root / 'android'))
        before = self.store.list_devices()
        first = self.store.create_ios_session(connection_id='one', project_name='Project', outdir=str(self.root / 'one'))
        self.assertEqual((first['platform'], first['mode'], first['device_id']), ('ios', 'ios-http-proxy', 'ios-one'))
        self.assertEqual(self.store.list_devices(), before)
        with self.assertRaises(ValueError):
            self.store.create_ios_session(connection_id='one', project_name='Other', outdir=str(self.root / 'two'))
        self.store.update_session_status(first['id'], 'stopped')
        second = self.store.create_ios_session(connection_id='one', project_name='Other', outdir=str(self.root / 'two'))
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(self.store.get_session(android['id']), android)
        self.assertEqual(len(self.store.list_active_sessions()), 2)

    def service(self):
        service = IOSSetupService(self.root / 'setup', store=self.store)
        service.directory = service.root / 'session-test'
        service.directory.mkdir(parents=True)
        service.config = config(service.directory)
        service.config['control_path'] = str(service.directory / 'control.json')
        service.process = Mock()
        service.process.poll.return_value = None
        service.last = {'phase': 'ready', 'connection_state': 'ready', 'recording_state': 'idle',
                        'session_id': None, 'flow_count': 0, 'flows': []}
        Path(service.config['state_path']).write_text(json.dumps(service.last))
        return service

    def test_start_stop_waits_for_ack_and_stop_keeps_worker(self):
        service = self.service()
        worker = service.process
        def ack(command):
            state = {**service.last, 'applied_revision': command['revision'],
                     'recording_state': 'recording' if command['action'] == 'start' else 'stopped',
                     'project': command.get('project', service.last.get('project')),
                     'session_id': command.get('session_id', service.last.get('session_id'))}
            Path(service.config['state_path']).write_text(json.dumps(state))
        with patch.object(service, '_write_control', side_effect=ack):
            first = service.start_recording('pokehub')
            self.assertEqual(service.start_recording('pokehub')['session_id'], first['session_id'])
            stopped = service.stop_recording()
            self.assertEqual(stopped['recording_state'], 'stopped')
            self.assertEqual(self.store.get_session(first['session_id'])['status'], 'stopped')
            self.assertIs(service.process, worker)
            worker.terminate.assert_not_called()
            next_state = service.start_recording('pokehub')
            self.assertNotEqual(next_state['session_id'], first['session_id'])

    def test_device_start_does_not_require_project_configuration(self):
        service = self.service()
        def ack(command):
            state = {**service.last, 'applied_revision': command['revision'],
                     'recording_state': 'recording', 'project': command['project'],
                     'capture_scope': command['capture_scope'], 'session_id': command['session_id']}
            Path(service.config['state_path']).write_text(json.dumps(state))
        with patch.object(service.projects, 'get', side_effect=AssertionError('must not read projects')), \
                patch.object(service, '_write_control', side_effect=ack):
            first = service.start_recording(None)
            self.assertEqual(first['capture_scope'], 'device')
            self.assertEqual(first['project'], {'id': 'iphone', 'name': 'iPhone', 'domains': []})
            self.assertEqual(service.start_recording(None)['session_id'], first['session_id'])
            self.assertEqual(len(self.store.list_sessions()), 1)

    def test_ack_timeout_fails_closed_without_reporting_success(self):
        service = self.service()
        worker = service.process
        with patch.object(service, 'command_timeout', 0.01), self.assertRaises(RuntimeError):
            service.start_recording('pokehub')
        worker.terminate.assert_called_once()
        self.assertEqual(self.store.list_sessions()[0]['status'], 'failed')

    def test_network_change_during_ack_cannot_report_running(self):
        service = self.service()
        def ack(command):
            state = {**service.last, 'applied_revision': command['revision'], 'recording_state': 'recording',
                     'session_id': command['session_id']}
            Path(service.config['state_path']).write_text(json.dumps(state))
            service.config['expires_at'] = time.time() + 100
            service.host_provider = lambda: '192.168.2.99'
        with patch.object(service, '_write_control', side_effect=ack), self.assertRaises(RuntimeError):
            service.start_recording('pokehub')
        self.assertIsNone(service.process)
        self.assertEqual(self.store.list_sessions()[0]['status'], 'failed')

    def test_connection_cleanup_preserves_completed_and_failed_record_outcomes(self):
        for outcome in ['stopped', 'failed']:
            with self.subTest(outcome=outcome):
                service = self.service()
                service.session = self.store.create_ios_session(connection_id=outcome, project_name='Test',
                                                                outdir=str(self.root / outcome))
                service.session = self.store.update_session_status(service.session['id'], outcome)
                saved = service.session
                service.process.poll.return_value = 1
                service.status()
                self.assertEqual(self.store.get_session(saved['id']), saved)
                service.shutdown()
                self.assertEqual(self.store.get_session(saved['id']), saved)

    def test_shared_result_routes_dispatch_ios_without_android_runner(self):
        from capture_console import app as module
        session = self.store.create_ios_session(connection_id='phone', project_name='Example', outdir=str(self.root / 'record'))
        archive = IOSCaptureArchive(session['outdir'])
        flow = make_flow()
        archive.begin(flow)
        archive.append_body(flow.id, 'request', flow.request.raw_content)
        archive.request_complete(flow)
        archive.append_body(flow.id, 'response', flow.response.raw_content)
        archive.finish(flow)
        with patch.object(module, 'store', self.store), patch.object(module, 'runner_for_device_id') as runner, \
                patch.object(module.ios_setup_service, 'stop_recording', return_value={'recording_state': 'stopped'}) as stop:
            self.assertEqual(module.api_get_flows(session['id'], cursor=0, limit=1)['total'], 1)
            self.assertEqual(module.api_get_capture(session['id'])['flow_count'], 1)
            self.assertEqual(module.api_get_flow_detail(session['id'], flow.id)['response_text'], '{"response":true}')
            self.assertIn('query=one', module.api_get_flow_curl(session['id'], flow.id))
            self.assertTrue(module.api_stop_capture_session(session['id'])['ok'])
            stop.assert_called_once_with(session_id=session['id'])
            runner.assert_not_called()

    def test_stop_all_preserves_ios_failure_result_without_using_android_runner(self):
        from capture_console import app as module
        session = self.store.create_ios_session(connection_id='phone', project_name='Example', outdir=str(self.root / 'failed'))
        def disconnected(**kwargs):
            self.store.update_session_status(session['id'], 'failed')
            return {'recording_state': 'failed'}
        with patch.object(module, 'store', self.store), patch.object(module, 'runner_for_device_id') as runner, \
                patch.object(module.ios_setup_service, 'stop_recording', side_effect=disconnected):
            module.stop_all_active_captures()
            self.assertEqual(self.store.get_session(session['id'])['status'], 'failed')
            runner.assert_not_called()


if __name__ == '__main__':
    unittest.main()

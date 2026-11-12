import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from capture_console.android_physical_evidence import ApplicationNetworkEvidence, current_evidence
from capture_console.android_physical_worker import PhysicalRecorder


class ApplicationEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.evidence = ApplicationNetworkEvidence(clock=lambda: self.now)

    def test_no_response_is_not_connectivity_success(self):
        self.assertEqual(self.evidence.summary(), {
            'state': 'waiting', 'https_response_count': 0, 'last_status_code': None,
            'response_age_seconds': None, 'observed_at': 100.0,
        })

    def test_completed_response_expires_without_claiming_outage(self):
        self.evidence.response(204)
        self.assertEqual(self.evidence.summary()['state'], 'responded')
        self.now += 31
        self.assertEqual(self.evidence.summary(), {
            'state': 'quiet', 'https_response_count': 1, 'last_status_code': 204,
            'response_age_seconds': 31, 'observed_at': 131.0,
        })

    def test_error_status_is_not_business_success(self):
        for status in (401, 403, 429, 500, 503):
            self.evidence.response(status)
            self.assertEqual(self.evidence.summary()['state'], 'server_error')
        self.evidence.response(200)
        self.assertEqual(self.evidence.summary()['state'], 'responded')

    def test_handshake_only_does_not_prove_response(self):
        for status in (100, 101, 199, None, True, 600):
            self.evidence.response(status)
        self.assertEqual(self.evidence.summary()['state'], 'waiting')

    def test_partial_failure_is_not_hidden_by_success(self):
        self.evidence.failure()
        self.assertEqual(self.evidence.summary()['state'], 'connection_failed')
        self.evidence.response(200)
        self.assertEqual(self.evidence.summary()['state'], 'partial')
        self.now += 31
        self.assertEqual(self.evidence.summary()['state'], 'quiet')
        self.evidence.response(200)
        self.assertEqual(self.evidence.summary()['state'], 'responded')

    def test_evidence_is_constant_size_and_new_instance_is_empty(self):
        for _ in range(10000):
            self.evidence.response(200)
            self.evidence.failure()
        self.assertEqual(len(self.evidence.summary()), 5)
        self.assertEqual(ApplicationNetworkEvidence().summary()['state'], 'waiting')

    def test_old_missing_or_future_snapshot_is_not_current(self):
        self.evidence.response(200)
        sample = self.evidence.summary()
        self.assertEqual(current_evidence(sample, now=110)['state'], 'responded')
        for now in (116, 90):
            self.assertEqual(current_evidence(sample, now=now), {'state': 'unverified'})
        for sample in (None, {}, {'observed_at': float('nan')}, {'observed_at': '100'}):
            self.assertEqual(current_evidence(sample, now=110), {'state': 'unverified'})

    def test_cached_snapshot_cannot_extend_thirty_second_response_window(self):
        self.evidence.response(200)
        self.now += 29
        sample = self.evidence.summary()
        self.assertEqual(current_evidence(sample, now=131), {'state': 'unverified'})


class WorkerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.recorder = PhysicalRecorder({'outdir': str(Path(self.directory.name) / 'capture'), 'session_id': 1})
        self.addCleanup(self.recorder.recording.archive.close)
        self.recorder.recording = Mock(wraps=self.recorder.recording)
        self.recorder.recording.finish = Mock()

    def flow(self, scheme='https', connected=True, replay=False, error=None):
        return SimpleNamespace(request=SimpleNamespace(scheme=scheme),
                               response=SimpleNamespace(status_code=200),
                               server_conn=SimpleNamespace(timestamp_tcp_setup=1 if connected else None),
                               is_replay=replay, error=error)

    def test_only_completed_upstream_https_counts(self):
        for flow in (self.flow(scheme='http'), self.flow(connected=False),
                     self.flow(replay='response'), self.flow(error='incomplete')):
            self.recorder.response(flow)
        self.assertEqual(self.recorder.application_network.summary()['state'], 'waiting')
        self.recorder.response(self.flow())
        self.assertEqual(self.recorder.application_network.summary()['https_response_count'], 1)
        self.assertEqual(self.recorder.recording.finish.call_count, 5)

    def test_tls_and_transport_errors_update_evidence_without_changing_archive(self):
        self.recorder.tls_failed_client(None)
        self.assertEqual(self.recorder.application_network.summary()['state'], 'connection_failed')
        self.recorder.response(self.flow())
        self.recorder.error(self.flow(error='timeout'))
        self.assertEqual(self.recorder.application_network.summary()['state'], 'partial')
        self.assertEqual(self.recorder.state['tls_failures'], 1)
        self.assertEqual(self.recorder.recording.finish.call_count, 2)

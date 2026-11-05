import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from capture_console.ios_results import IOSCaptureArchive
from capture_console.ios_setup import IOSSetupService
from capture_console.store import CaptureStore
from tests.test_ios_results import make_flow


class IOSLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = CaptureStore(self.root / "console.db")
        self.module = importlib.import_module("capture_console.app")
        self.store.upsert_device(device_id="android-test", name="Android", avd_name="Test_AVD",
                                 adb_serial="emulator-5554", proxy_port=9090, web_port=9091, frida_port=27042)
        self.android = self.store.create_session(app_id=None, device_id="android-test", mode="flutter-socks",
                                                  outdir=str(self.root / "android"))
        self.ios = self.store.create_ios_session(connection_id="test", project_name="Example",
                                                  outdir=str(self.root / "ios"))
        archive = IOSCaptureArchive(self.root / "ios")
        self.flow = make_flow()
        archive.begin(self.flow)
        archive.append_body(self.flow.id, "request", self.flow.request.raw_content)
        archive.request_complete(self.flow)
        archive.append_body(self.flow.id, "response", self.flow.response.raw_content)
        archive.finish(self.flow)
        archive.close()
        for name, value in [("store", self.store), ("CAPTURES_DIR", self.root / "captures"),
                            ("start_logcat_reaper", Mock()), ("stop_logcat_reaper", Mock()),
                            ("logcat_service", Mock()), ("weak_network_service", Mock()),
                            ("stop_all_active_captures", Mock())]:
            patcher = patch.object(self.module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def assert_archive_readable(self):
        session_id = self.ios["id"]
        page = self.module.api_get_flows(session_id)
        self.assertEqual([flow["id"] for flow in page["flows"]], [self.flow.id])
        detail = self.module.api_get_flow_detail(session_id, self.flow.id)
        self.assertEqual(detail["request_text"], '{"request":1}')
        self.assertEqual(detail["response_text"], '{"response":true}')

    def test_startup_keeps_stopped_iphone_record_and_body_without_restoring_android(self):
        saved = self.store.update_session_status(self.ios["id"], "stopped")
        with patch.object(self.module.threading, "Thread"):
            self.module.startup()
        reopened = CaptureStore(self.root / "console.db")
        self.assertEqual(reopened.get_session(self.ios["id"]), saved)
        self.assertEqual(reopened.get_session(self.android["id"])["status"], "failed")
        self.assertEqual(reopened.list_active_sessions(), [])
        self.assert_archive_readable()

    def test_startup_marks_abandoned_iphone_record_failed_once_and_preserves_terminal_error(self):
        failed = self.store.create_ios_session(connection_id="other", project_name="Other",
                                                outdir=str(self.root / "other"))
        failed = self.store.update_session_status(failed["id"], "failed", error="original failure")
        with patch.object(self.module.threading, "Thread"):
            self.module.startup()
            interrupted = self.store.get_session(self.ios["id"])
            self.assertIsNotNone(interrupted)
            self.assertEqual(interrupted["status"], "failed")
            self.assertTrue(interrupted["stopped_at"])
            self.assertTrue(interrupted["error"])
            self.module.startup()
        self.assertEqual(self.store.get_session(self.ios["id"]), interrupted)
        self.assertEqual(self.store.get_session(failed["id"]), failed)
        self.assertEqual(self.store.list_active_sessions(), [])
        self.assert_archive_readable()

    def test_shutdown_preserves_iphone_archive_after_owned_service_stops(self):
        service = IOSSetupService(self.root / "ios-setup", store=self.store)
        service.session = self.ios
        with patch.object(self.module, "ios_setup_service", service):
            self.module.shutdown()
        saved = self.store.get_session(self.ios["id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "stopped")
        self.assertEqual(self.store.list_active_sessions(), [])
        self.assert_archive_readable()

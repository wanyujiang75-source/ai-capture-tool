import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from capture_console.store import CaptureStore


class CaptureRetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.captures = self.root / "captures"
        self.captures.mkdir()
        self.store = CaptureStore(self.root / "console.db")
        self.store.upsert_device(device_id="test", name="Test", avd_name="Test",
                                 adb_serial="test", proxy_port=9090, web_port=9091, frida_port=27042)

    def seed(self, number, *, status="stopped", platform="ios", path=None):
        path = path or self.captures / f"{'ios' if platform == 'ios' else 'web'}-{number}"
        if not path.exists():
            path.mkdir(parents=True)
        if path.is_dir():
            (path / "body.txt").write_text(str(number))
        with self.store.connect() as conn:
            conn.execute("""INSERT INTO capture_sessions
                (id, platform, device_id, mode, outdir, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, '2026-11-05', '2026-11-05')""",
                (number, platform, f"device-{number}", "ios-http-proxy" if platform == "ios" else "system",
                 str(path), status))
        return path

    def ids(self):
        return [row["id"] for row in self.store.list_sessions()]

    def test_terminal_update_deletes_older_records_and_files_across_platforms(self):
        paths = [self.seed(i, status="running" if i == 10 else "stopped",
                           platform="android" if i % 2 else "ios") for i in range(1, 11)]
        self.store.update_session_status(10, "stopped")
        self.assertEqual(self.ids(), [10, 9, 8, 7, 6, 5, 4])
        self.assertEqual([p.exists() for p in paths], [False] * 3 + [True] * 7)

    def test_terminal_android_creation_also_runs_retention(self):
        for i in range(1, 9):
            self.seed(i)
        self.store.create_session(app_id=None, device_id="test", mode="system", status="failed",
                                  outdir=str(self.captures / "web-new"))
        self.assertEqual(self.ids(), [9, 8, 7, 6, 5, 4, 3])
        self.assertFalse((self.captures / "ios-1").exists())

    def test_active_and_unknown_records_never_consume_history_slots_or_get_deleted(self):
        protected = [self.seed(i, status=status) for i, status in
                     enumerate(["starting", "running", "stopping", "unknown"], 1)]
        for i in range(5, 15):
            self.seed(i, status="failed" if i == 5 else "stopped")
        result = self.store.prune_history()
        self.assertEqual(result["deleted"], [7, 6, 5])
        self.assertEqual(self.ids(), [14, 13, 12, 11, 10, 9, 8, 4, 3, 2, 1])
        self.assertTrue(all(p.exists() for p in protected))

    def test_startup_preserves_recent_android_and_ios_with_interrupted_marked_failed(self):
        paths = [self.seed(i, platform="android" if i % 2 else "ios",
                           status="running" if i == 10 else "stopped") for i in range(1, 11)]
        self.store.reset_capture_sessions_for_restart()
        self.assertEqual(self.ids(), [10, 9, 8, 7, 6, 5, 4])
        self.assertEqual(self.store.get_session(10)["status"], "failed")
        self.assertEqual([p.exists() for p in paths], [False] * 3 + [True] * 7)
        self.assertEqual(self.store.list_active_sessions(), [])

    def test_missing_files_are_cleaned_idempotently_and_configuration_is_untouched(self):
        for i in range(1, 10):
            self.seed(i)
        for p in (self.captures / "ios-1").iterdir():
            p.unlink()
        (self.captures / "ios-1").rmdir()
        identity = self.root / "ios-setup" / "identity"
        identity.mkdir(parents=True)
        (identity / "cert.pem").write_text("test certificate")
        orphan = self.captures / "ios-unregistered"
        orphan.mkdir()
        self.store.prune_history()
        self.assertEqual(self.store.prune_history(), {"deleted": [], "errors": []})
        self.assertEqual(self.ids(), [9, 8, 7, 6, 5, 4, 3])
        self.assertEqual((identity / "cert.pem").read_text(), "test certificate")
        self.assertTrue(orphan.is_dir())
        self.assertIsNotNone(self.store.get_device("test"))

    def test_unsafe_roots_external_paths_and_symlinks_are_rejected(self):
        external = self.root / "unrelated"
        external.mkdir()
        (external / "keep").write_text("keep")
        link = self.captures / "ios-link"
        link.symlink_to(external, target_is_directory=True)
        paths = [external, self.captures, link, self.captures / "configuration"]
        for i, path in enumerate(paths, 1):
            self.seed(i, path=path)
        for i in range(5, 12):
            self.seed(i)
        with self.assertLogs("capture_console.capture_retention", level="WARNING"):
            result = self.store.prune_history()
        self.assertEqual(result["deleted"], [])
        self.assertEqual(len(result["errors"]), 4)
        self.assertEqual(len(self.ids()), 11)
        self.assertTrue(link.is_symlink())
        self.assertEqual((external / "keep").read_text(), "keep")

    def test_shared_or_nested_archive_path_is_not_deleted(self):
        path = self.seed(1)
        self.seed(2, status="running", path=path / "nested")
        (self.captures / "ios-alias").mkdir()
        self.seed(3, status="running", path=self.captures / "ios-alias" / ".." / "ios-1")
        for i in range(4, 11):
            self.seed(i)
        with self.assertLogs("capture_console.capture_retention", level="WARNING"):
            result = self.store.prune_history()
        self.assertEqual(result["deleted"], [])
        self.assertTrue(path.is_dir())
        self.assertEqual(len(result["errors"]), 1)

    def test_failed_deletion_keeps_row_and_retries_without_failing_stop(self):
        for i in range(1, 9):
            self.seed(i)
        with patch("capture_console.capture_retention.shutil.rmtree", side_effect=PermissionError("denied")):
            with self.assertLogs("capture_console.capture_retention", level="WARNING"):
                stopped = self.store.update_session_status(8, "stopped")
        self.assertEqual(stopped["status"], "stopped")
        self.assertIsNotNone(self.store.get_session(1))
        self.assertTrue((self.captures / "ios-1").exists())
        self.assertEqual(self.store.prune_history()["deleted"], [1])
        self.assertIsNone(self.store.get_session(1))

    def test_concurrent_cleanup_and_terminal_updates_are_serialized(self):
        for i in range(1, 14):
            self.seed(i, status="running" if i > 10 else "stopped")
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(self.store.update_session_status, i, "stopped") for i in (11, 12, 13)]
            futures.append(pool.submit(self.store.prune_history))
            for future in futures:
                future.result(timeout=10)
        self.assertEqual(self.ids(), [13, 12, 11, 10, 9, 8, 7])
        self.assertEqual(sorted(p.name for p in self.captures.iterdir()),
                         sorted(f"ios-{i}" for i in range(7, 14)))

    def test_symlink_inside_expired_archive_does_not_delete_its_target(self):
        external = self.root / "keep.txt"
        external.write_text("unrelated")
        path = self.seed(1)
        (path / "linked.txt").symlink_to(external)
        for i in range(2, 9):
            self.seed(i)
        self.assertEqual(self.store.prune_history()["deleted"], [1])
        self.assertEqual(external.read_text(), "unrelated")

    def test_symlinked_capture_root_cannot_authorize_deletion(self):
        for i in range(1, 9):
            self.seed(i)
        external = self.root / "outside"
        self.captures.rename(external)
        self.captures.symlink_to(external, target_is_directory=True)
        with self.assertLogs("capture_console.capture_retention", level="WARNING"):
            result = self.store.prune_history()
        self.assertEqual(result["deleted"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertTrue((external / "ios-1" / "body.txt").is_file())


if __name__ == "__main__":
    unittest.main()

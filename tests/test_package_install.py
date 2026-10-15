import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

from capture_console.http_errors import structured_http_error_body
from capture_console.runner import CommandResult, ConsoleRunner


class PackageInstallTests(unittest.TestCase):
    def test_storage_profile_preserves_existing_avd_capacity(self):
        for capacity in ("8G", "32G"):
            with self.subTest(capacity=capacity), tempfile.TemporaryDirectory() as tmp:
                runner = ConsoleRunner(tmp, avd_name="Existing")
                runner.avd_home = Path(tmp)
                avd = runner.avd_home / "Existing.avd"
                avd.mkdir()
                (avd / "config.ini").write_text(f"disk.dataPartition.size={capacity}\n")

                profile = runner.recommended_avd_performance_profile()

                self.assertEqual(profile["data_partition_size"], capacity)

    def test_storage_failure_reclaims_cache_and_retries_single_and_split_install(self):
        for names in (["app.apk"], ["split.apk", "base.apk"]):
            with self.subTest(names=names), tempfile.TemporaryDirectory() as tmp:
                runner = ConsoleRunner(tmp, adb_serial="emulator-5554")
                paths = [Path(tmp) / name for name in names]
                storage_error = CommandResult(1, "", "INSTALL_FAILED_INSUFFICIENT_STORAGE")
                success = CommandResult(0, "Success", "")
                with patch.object(runner, "adb", side_effect=[storage_error, success, success]) as adb:
                    result = runner.install_apks(paths)
                self.assertEqual(result, success)
                self.assertEqual(adb.call_count, 3)
                self.assertEqual(adb.call_args_list[0], adb.call_args_list[2])
                self.assertEqual(
                    adb.call_args_list[1],
                    call(["shell", "pm", "trim-caches", "2G", "internal"], timeout=60),
                )

    def test_cache_reclaim_failure_preserves_install_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = ConsoleRunner(tmp)
            failed = CommandResult(1, "", "INSTALL_FAILED_INSUFFICIENT_STORAGE")
            with patch.object(runner, "adb", side_effect=[failed, CommandResult(1, "", "denied")]) as adb:
                self.assertEqual(runner.install_apks([Path(tmp) / "app.apk"]), failed)
            self.assertEqual(adb.call_count, 2)

    def test_storage_retry_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = ConsoleRunner(tmp)
            failed = CommandResult(1, "", "INSTALL_FAILED_INSUFFICIENT_STORAGE")
            with patch.object(runner, "adb", side_effect=[failed, CommandResult(0, "", ""), failed]) as adb:
                self.assertEqual(runner.install_apks([Path(tmp) / "app.apk"]), failed)
            self.assertEqual(adb.call_count, 3)

    def test_signature_failure_does_not_reclaim_cache_or_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = ConsoleRunner(tmp)
            failed = CommandResult(1, "", "INSTALL_FAILED_UPDATE_INCOMPATIBLE")
            with patch.object(runner, "adb", return_value=failed) as adb:
                self.assertEqual(runner.install_apks([Path(tmp) / "app.apk"]), failed)
            self.assertEqual(adb.call_count, 1)

    def test_jenkins_install_failure_reports_android_cause(self):
        for reason, code in (
            ("INSTALL_FAILED_INSUFFICIENT_STORAGE", "device_storage_full"),
            ("INSTALL_FAILED_UPDATE_INCOMPATIBLE", "signature_conflict"),
            ("INSTALL_FAILED_INVALID_APK", "app_install_failed"),
        ):
            with self.subTest(reason=reason):
                body = structured_http_error_body(
                    path="/api/package-sources/jenkins/install",
                    status_code=400,
                    detail={"message": "adb install failed", "output": reason},
                )
                self.assertEqual(body["code"], code)
                self.assertIn(reason, body["technical_detail"])
                self.assertNotIn("公司网络", body["user_message"])

    def test_jenkins_network_failure_keeps_network_recovery(self):
        body = structured_http_error_body(
            path="/api/package-sources/jenkins/install",
            status_code=502,
            detail={"message": "failed to download Jenkins artifact: timed out"},
        )
        self.assertEqual(body["code"], "jenkins_unavailable")


if __name__ == "__main__":
    unittest.main()

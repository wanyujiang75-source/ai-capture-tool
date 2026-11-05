import unittest
import sys

from capture_console import android_physical_capabilities as cap


class CapabilitiesTests(unittest.TestCase):
    def inspect(self, devices="phone device model:PHK110", overrides=None, serial="phone", package="com.mi.poketrade"):
        replies = {
            "devices": "List of devices attached\n" + devices,
            "model": "PHK110", "android": "16", "sdk": "36", "abi": "arm64-v8a",
            "uid": "2000", "boot": "1", "verified_boot": "green", "boot_locked": "1",
            "user": "0", "package": "versionCode=96 minSdk=24 targetSdk=36\nversionName=2.1.0\nflags=[ HAS_CODE ]\ninstallerPackageName=com.android.vending",
            "paths": "package:/data/app/example/base.apk", "proxy": "null",
            "vpn": "Transports: WIFI|VPN", "policy": "",
        }
        replies.update(overrides or {})
        calls = []

        def execute(key, argv):
            calls.append((key, argv))
            value = replies.get(key, "")
            if isinstance(value, Exception):
                raise value
            return value

        result = cap.inspect_device("adb", serial, package, execute=execute)
        return result, calls

    def test_no_device(self):
        result, calls = self.inspect(devices="")
        self.assertEqual(result["status"], "disconnected")
        self.assertEqual([key for key, _ in calls], ["devices"])

    def test_unauthorized_offline_and_emulator_never_probe(self):
        for devices, serial, expected in [("phone unauthorized", "phone", "unauthorized"), ("phone offline", "phone", "offline"), ("emulator-5554 device", "emulator-5554", "wrong_device_kind")]:
            with self.subTest(expected=expected):
                result, calls = self.inspect(devices=devices, serial=serial)
                self.assertEqual(result["status"], expected)
                self.assertEqual(len(calls), 1)

    def test_exact_device_and_only_read_commands(self):
        result, calls = self.inspect(devices="other device\nphone device")
        self.assertEqual(result["status"], "blocked")
        for key, argv in calls[1:]:
            self.assertEqual(argv[:4], ["adb", "-s", "phone", "shell"])
            self.assertNotRegex(argv[-1], r"\b(su|root|install|uninstall|start|put|delete|forward|reverse)\b")
        self.assertEqual(result["tls_state"], "unknown")
        self.assertEqual(result["root_state"], "not_observed")
        self.assertIsNone(result["recommended_mode"])
        self.assertFalse(result["capture_ready"])

    def test_release_is_not_proven_by_installer_or_flags(self):
        result, _ = self.inspect()
        self.assertFalse(result["package_identity"]["debuggable"])
        self.assertEqual(result["package_identity"]["provenance"], "unverified")
        self.assertEqual(result["package_identity"]["version_name"], "2.1.0")

    def test_root_or_debug_does_not_imply_capture(self):
        for overrides in [{"uid": "0"}, {"package": "flags=[ DEBUGGABLE ]"}]:
            result, _ = self.inspect(overrides=overrides)
            self.assertFalse(result["capture_ready"])
            self.assertEqual(result["app_http_state"], "unknown")
        self.assertEqual(self.inspect(overrides={"uid": "0"})[0]["root_state"], "adb_uid_zero")

    def test_failures_remain_unknown(self):
        result, _ = self.inspect(overrides={"uid": TimeoutError(), "package": RuntimeError("secret"), "vpn": OSError()})
        self.assertEqual(result["root_state"], "unknown")
        self.assertIsNone(result["package_identity"]["debuggable"])
        self.assertEqual(result["vpn_state"], "unknown")
        self.assertNotIn("secret", str(result))

    def test_missing_package(self):
        result, _ = self.inspect(overrides={"paths": ""})
        self.assertIn("package_not_confirmed", result["issues"])

    def test_policy_and_empty_vpn_are_not_passes(self):
        result, _ = self.inspect(overrides={"policy": "no_config_vpn=true", "vpn": ""})
        self.assertIn("device_policy_present", result["issues"])
        self.assertEqual(result["vpn_state"], "unknown")

    def test_unsafe_identifiers_rejected_before_execution(self):
        for serial, package in [("-s", "com.test.app"), ("phone;id", "com.test.app"), ("phone", "com.app;id"), ("", "com.app")]:
            with self.subTest(serial=serial, package=package):
                with self.assertRaises(ValueError):
                    self.inspect(serial=serial, package=package)

    def test_other_android_user_does_not_mix_package_identity(self):
        result, calls = self.inspect(overrides={"user": "10"})
        self.assertNotIn("package", [key for key, _ in calls])
        self.assertIn("unsupported_android_user", result["issues"])

    def test_inventory_failure_stops_all_probes(self):
        result, calls = self.inspect(overrides={"devices": OSError()})
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(len(calls), 1)

    def test_process_output_and_exit_are_bounded(self):
        self.assertEqual(cap.run_readonly("fixture", [sys.executable, "-c", "print('ok')"]), "ok")
        with self.assertRaises(ValueError):
            cap.run_readonly("fixture", [sys.executable, "-c", "print('x' * 100000)"])
        with self.assertRaises(RuntimeError):
            cap.run_readonly("fixture", [sys.executable, "-c", "raise SystemExit(2)"])

    def test_silent_process_times_out(self):
        with self.assertRaises(TimeoutError):
            cap.run_readonly("fixture", [sys.executable, "-c", "import time; time.sleep(60)"])


if __name__ == "__main__":
    unittest.main()

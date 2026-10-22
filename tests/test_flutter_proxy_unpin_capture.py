import importlib.util
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


def load_module():
    sys.modules.setdefault("frida", types.SimpleNamespace())
    path = Path(__file__).resolve().parents[1] / "scripts" / "flutter_proxy_unpin_capture.py"
    spec = importlib.util.spec_from_file_location("flutter_proxy_unpin_capture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FlutterProxyUnpinCaptureTests(unittest.TestCase):
    def test_desktop_capture_writes_only_to_managed_runtime(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            backend = Path(tmp) / "bundle/backend"
            backend.mkdir(parents=True)
            runtime = Path(tmp) / "user-runtime"
            with (
                patch.object(sys, "argv", ["capture", "--no-force-stop", "--duration", "1"]),
                patch.dict(module.os.environ, {"CAPTURE_RUNTIME_DIR": str(runtime)}),
                patch.object(module.os, "getcwd", return_value=str(backend)),
                patch.object(module, "build_combined_script", return_value=""),
                patch.object(module, "adb"),
                patch.object(module, "wait_for_pid", return_value=123),
                patch.object(module.frida, "get_device_manager", create=True),
                patch.object(module, "load_capture_script"),
                patch.object(module.time, "time", side_effect=[0, 100, 102]),
            ):
                module.main()
            self.assertTrue((runtime / "last-flutter-proxy-unpin-dir.txt").is_file())
            self.assertEqual(len(list(runtime.glob("captures/*/frida-unpin.log"))), 1)
            self.assertFalse((backend / "runtime").exists())

    def test_failed_initialization_does_not_keep_capture_process_alive(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "runtime").mkdir()
            device = Mock()
            with (
                patch.object(sys, "argv", ["capture", "--outdir", tmp, "--no-force-stop", "--duration", "1"]),
                patch.object(module.os, "getcwd", return_value=tmp),
                patch.object(module, "build_combined_script", return_value=""),
                patch.object(module, "adb"),
                patch.object(module, "wait_for_pid", return_value=123),
                patch.object(module.frida, "get_device_manager", create=True) as manager,
                patch.object(module, "load_capture_script", side_effect=RuntimeError("certificate hook failed")),
                patch.object(module.time, "time", side_effect=[0, 100, 100, 102]),
            ):
                manager.return_value.add_remote_device.return_value = device
                with self.assertRaisesRegex(RuntimeError, "initial frida attach"):
                    module.main()
            device.attach.return_value.detach.assert_called_once()

    def test_bridge_bootstrap_loads_packaged_resource_and_preserves_existing_java(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp)
            (package / "bridges").mkdir()
            (package / "bridges/java.js").write_text("var bridge = { available: true };", encoding="utf-8")
            with patch.object(module.resources, "files", return_value=package):
                source = module.load_android_java_bridge()
        result = subprocess.run(
            ["node", "-e", source + "\nif (!Java.available) process.exit(1);\n"
             + "globalThis.Java = { existing: true };\n" + source
             + "\nif (!Java.existing) process.exit(2);"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_bridge_reports_actionable_error(self):
        module = load_module()
        with patch.object(module.resources, "files", side_effect=ModuleNotFoundError("frida_tools")):
            with self.assertRaisesRegex(RuntimeError, "frida-tools.*Java bridge"):
                module.load_android_java_bridge()

    def test_script_load_waits_for_android_ca_injection(self):
        module = load_module()
        for message, succeeds in [
            ({"type": "send", "payload": {"type": "android-system-ca-ready"}}, True),
            ({"type": "send", "payload": {"type": "android-system-ca-error", "error": "bad CA"}}, False),
            ({"type": "error", "description": "Java unavailable"}, False),
            (None, False),
        ]:
            with self.subTest(message=message):
                script = Mock()
                script.load.side_effect = lambda: script.on.call_args.args[1](message, None) if message else None
                if succeeds:
                    module.load_capture_script(script, Mock(), require_android_ca=True, timeout=0.01)
                else:
                    with self.assertRaisesRegex(RuntimeError, "Android certificate injection"):
                        module.load_capture_script(script, Mock(), require_android_ca=True, timeout=0.01)
                    script.unload.assert_called_once()

    def test_script_without_android_ca_does_not_wait(self):
        module = load_module()
        script = Mock()
        module.load_capture_script(script, Mock(), require_android_ca=False, timeout=0)
        script.load.assert_called_once()
        script.unload.assert_not_called()

    def test_needs_reattach_when_target_app_pid_changes(self):
        module = load_module()

        self.assertFalse(module.needs_reattach(attached_pid=1234, current_pid=1234, detached=False))
        self.assertTrue(module.needs_reattach(attached_pid=1234, current_pid=5678, detached=False))
        self.assertTrue(module.needs_reattach(attached_pid=1234, current_pid=1234, detached=True))
        self.assertFalse(module.needs_reattach(attached_pid=1234, current_pid=None, detached=False))

    def test_wait_for_pid_allows_slow_login_or_cold_start_flows(self):
        module = load_module()

        default_timeout = module.wait_for_pid.__defaults__[0]

        self.assertGreaterEqual(default_timeout, 60)

    def test_build_script_includes_android_system_ca_hook(self):
        module = load_module()
        project_root = Path(__file__).resolve().parents[1]

        with tempfile.TemporaryDirectory() as tmp:
            certificate = Path(tmp) / "mitmproxy-ca-cert.pem"
            certificate.write_text("TEST CERTIFICATE", encoding="utf-8")
            args = types.SimpleNamespace(
                httptoolkit_dir=str(project_root / "tools" / "httptoolkit-frida"),
                cert=str(certificate),
                proxy_host="10.0.2.2",
                proxy_port=9140,
                debug=False,
                socks5=True,
                no_proxy_env=True,
                native_connect_hook=True,
                native_tls_hook=False,
                android_system_cert_hook=True,
                flutter_verify_success_value=1,
            )

            script = module.build_combined_script(args)

        self.assertIn("== System certificate trust injected ==", script)
        self.assertIn("Java.choose(TrustedCertificateIndexClassname", script)
        self.assertLess(script.index("globalThis.Java = bridge"), script.index("const injectAndroidSystemCertificate"))

        with tempfile.TemporaryDirectory() as tmp:
            certificate = Path(tmp) / "ca.pem"
            certificate.write_text("TEST CERTIFICATE", encoding="utf-8")
            args.cert = str(certificate)
            args.android_system_cert_hook = False
            with patch.object(module, "load_android_java_bridge", side_effect=AssertionError("must not load")):
                script = module.build_combined_script(args)
            self.assertNotIn("const injectAndroidSystemCertificate", script)


if __name__ == "__main__":
    unittest.main()

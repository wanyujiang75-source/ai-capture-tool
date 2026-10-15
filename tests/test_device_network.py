import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

from capture_console.runner import CommandResult, ConsoleRunner


class DeviceNetworkTests(unittest.TestCase):
    def test_capture_launcher_keeps_proxy_reset_visible_to_android_observer(self):
        script = (Path(__file__).resolve().parents[1] / "scripts" / "ai_capture.sh").read_text()
        clear_function = script.split("clear_android_http_proxy() {", 1)[1].split("\n}", 1)[0]
        process = subprocess.run(
            ["bash", "-c", """
adb_cmd() {
  if [[ "$3" == "put" ]]; then
    proxy_value="$6"
  elif [[ "$3" == "delete" ]]; then
    proxy_value="missing"
  fi
}
clear_android_http_proxy() {
""" + clear_function + "\n}\nclear_android_http_proxy\nprintf '%s' \"$proxy_value\"\n"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(process.stdout, ":0")

    def test_clear_proxy_resets_android_cached_and_persisted_proxy(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = ConsoleRunner(tmp)
            settings = {
                "http_proxy": "10.0.2.2:9090",
                "global_http_proxy_host": "10.0.2.2",
                "global_http_proxy_port": "9090",
            }
            effective_proxy = "10.0.2.2:9090"

            def android_settings(args, *, timeout):
                nonlocal effective_proxy
                # Android ignores removal of the legacy key, retaining its cached proxy.
                if args == ["shell", "settings", "delete", "global", "http_proxy"]:
                    settings.pop("http_proxy", None)
                elif args == ["shell", "settings", "put", "global", "http_proxy", ":0"]:
                    settings.update({
                        "http_proxy": ":0",
                        "global_http_proxy_host": "",
                        "global_http_proxy_port": "0",
                    })
                    effective_proxy = ""
                else:
                    self.fail(f"Unexpected network mutation: {args}")
                return CommandResult(0, "", "")

            with patch.object(runner, "adb", side_effect=android_settings):
                self.assertTrue(runner.clear_android_proxy().ok)
                self.assertTrue(runner.clear_android_proxy().ok)

            self.assertEqual(effective_proxy, "")
            self.assertEqual(settings, {
                "http_proxy": ":0",
                "global_http_proxy_host": "",
                "global_http_proxy_port": "0",
            })

    def test_clear_proxy_preserves_adb_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = ConsoleRunner(tmp)
            failed = CommandResult(1, "", "device offline")
            with patch.object(runner, "adb", return_value=failed) as adb:
                self.assertEqual(runner.clear_android_proxy(), failed)
            self.assertEqual(adb.call_args_list, [
                call(["shell", "settings", "put", "global", "http_proxy", ":0"], timeout=20),
            ])

    def test_capture_network_reports_neutral_proxy_as_direct(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = ConsoleRunner(tmp)
            state = {
                "adb_online": True,
                "boot_completed": True,
                "android_proxy": ":0",
            }
            with patch.object(runner, "adb", return_value=CommandResult(0, "", "")), \
                    patch.object(runner, "emulator_status", return_value=state):
                result = runner.enter_capture_network()
            self.assertTrue(result["ok"])
            self.assertEqual(result["network"]["mode"], "direct")


if __name__ == "__main__":
    unittest.main()

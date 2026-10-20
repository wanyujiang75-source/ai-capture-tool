import unittest
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from capture_console.weak_network import NetworkProfile, WeakNetworkService
from capture_console.weak_network_device import EmulatorNetworkDevice


class NetworkDeviceTests(unittest.TestCase):
    def setUp(self):
        self.device = EmulatorNetworkDevice(Mock(adb_serial="emulator-5554", avd_name="Capture"))
        self.saved = {"serial": "emulator-5554", "avd": "Capture", "boot_id": "boot",
                      "token": "aiwn12345678", "interfaces": [
                          {"name": "wlan0", "ifb": "aiwn123456780", "had_clsact": True}]}

    def test_reboot_cleans_journal_without_touching_new_kernel(self):
        with patch.object(self.device, "identity", return_value={**self.saved, "boot_id": "new"}), \
             patch.object(self.device, "root") as root:
            self.device.restore(self.saved)
            root.assert_not_called()

    def test_apply_does_not_replace_a_qdisc_created_after_snapshot(self):
        fixture = '''
tc() {
  case "$*" in
    'qdisc replace dev wlan0 root '*) echo overwritten; return 0;;
    'qdisc add dev wlan0 root '*) return 17;;
    *) return 0;;
  esac
}
ip() { return 0; }
'''
        results = []
        def root(command):
            result = subprocess.run(["sh", "-c", fixture + command], text=True, capture_output=True)
            results.append(result)
            if result.returncode:
                raise RuntimeError("foreign qdisc already exists")
            return result.stdout

        with patch.object(self.device, "identity", return_value=self.saved), \
             patch.object(self.device, "root", side_effect=root):
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                self.device.apply(self.saved, NetworkProfile(512, 1024, 200))
        self.assertNotIn("overwritten", "".join(result.stdout for result in results))

    def test_failed_apply_rollback_never_deletes_foreign_same_handle(self):
        fixture = '''
tc() {
  case "$*" in
    'qdisc add dev wlan0 root '*) return 17;;
    'qdisc show') echo 'qdisc netem 9c01: dev wlan0 root refcnt 2';;
    'qdisc del dev wlan0 root handle 9c01:') echo FOREIGN_ROOT_DELETED;;
    *) return 0;;
  esac
}
ip() { return 0; }
cat() { echo prepared:aiwn12345678; }
'''
        results = []
        def root(command):
            result = subprocess.run(["sh", "-c", fixture + command], text=True, capture_output=True)
            results.append(result)
            if result.returncode:
                raise RuntimeError("rule ownership conflict")
            return result.stdout

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(self.device, "snapshot", return_value=self.saved), \
             patch.object(self.device, "identity", return_value=self.saved), \
             patch.object(self.device, "root", side_effect=root):
            service = WeakNetworkService(Path(tmp), lambda _: self.device, lambda _: self.device)
            state = service.apply("one", NetworkProfile(512, 1024, 200))
        self.assertNotIn("FOREIGN_ROOT_DELETED", "".join(result.stdout for result in results))
        self.assertTrue(state["pending_restore"])

    def test_changed_avd_or_corrupt_record_never_mutates_device(self):
        with patch.object(self.device, "identity", return_value={**self.saved, "avd": "Other"}), \
             patch.object(self.device, "root") as root:
            with self.assertRaises(RuntimeError):
                self.device.restore(self.saved)
            self.saved["interfaces"][0]["name"] = "wlan0; reboot"
            with self.assertRaises(RuntimeError):
                self.device.restore(self.saved)
            root.assert_not_called()

    def test_restore_reads_global_qdiscs_and_preserves_system_clsact(self):
        # Execute the generated cleanup shell against stateful fake kernel tools.
        # `tc qdisc show dev wlan0` omits the dev name, unlike the global command.
        fixture = '''
shaped=yes
cat() { echo root:aiwn12345678; }
tc() {
  case "$*" in
    'filter show dev wlan0 ingress') ;;
    'qdisc show')
      if [ "$shaped" = yes ]; then
        echo 'qdisc netem 9c01: dev wlan0 root refcnt 2'
      fi
      echo 'qdisc clsact ffff: dev wlan0 parent ffff:fff1';;
    'qdisc del dev wlan0 root handle 9c01:') shaped=no;;
    *) echo "unexpected command $*" >&2; return 99;;
  esac
}
'''
        results = []
        def root(command):
            result = subprocess.run(["sh", "-c", fixture + command + '\nprintf "%s" "$shaped"'],
                                    text=True, capture_output=True)
            results.append(result)
            return result.stdout

        with patch.object(self.device, "identity", return_value=self.saved), \
             patch.object(self.device, "root", side_effect=root):
            self.device.restore(self.saved)
        self.assertEqual([(r.returncode, r.stdout, r.stderr) for r in results], [(0, "no", "")])

    def test_restore_failure_is_not_silently_successful(self):
        with patch.object(self.device, "identity", return_value=self.saved), \
             patch.object(self.device, "root", side_effect=RuntimeError("device disconnected")):
            with self.assertRaisesRegex(RuntimeError, "disconnected"):
                self.device.restore(self.saved)

    def test_clsact_cleanup_retry_keeps_ownership_until_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            interface = base / "ifb"
            interface.mkdir()
            (interface / "ifalias").write_text("root-clsact:aiwn12345678")
            (base / "clsact").touch()
            (base / "fail_once").touch()
            self.saved["interfaces"][0]["had_clsact"] = False
            fixture = f'''
tc() {{
  case "$*" in
    'qdisc show')
      if [ -f {base}/clsact ]; then echo 'qdisc clsact ffff: dev wlan0 parent ffff:fff1'; fi;;
    'qdisc del dev wlan0 clsact')
      if [ -f {base}/fail_once ]; then rm {base}/fail_once; return 17; fi
      rm {base}/clsact;;
    *) return 0;;
  esac
}}
ip() {{ rm -r {interface}; }}
'''
            def root(command):
                command = command.replace("/sys/class/net/aiwn123456780", str(interface))
                result = subprocess.run(["sh", "-c", fixture + command], text=True, capture_output=True)
                if result.returncode:
                    raise RuntimeError("clsact cleanup interrupted")
                return result.stdout

            with patch.object(self.device, "identity", return_value=self.saved), \
                 patch.object(self.device, "root", side_effect=root):
                with self.assertRaises(RuntimeError):
                    self.device.restore(self.saved)
                self.assertTrue(interface.exists())
                self.device.restore(self.saved)
            self.assertFalse((base / "clsact").exists())
            self.assertFalse(interface.exists())

    def test_verify_detects_wrong_rate_not_just_existing_handle(self):
        with patch.object(self.device, "identity", return_value=self.saved), \
             patch.object(self.device, "root", return_value="qdisc netem 9c01: dev wlan0 root delay 100ms rate 128Kbit"):
            with self.assertRaisesRegex(RuntimeError, "速率"):
                self.device.verify(self.saved, NetworkProfile(512, 1024, 200))

    def test_verify_accepts_normalized_tc_units(self):
        state = "\n".join([
            "qdisc netem 9c01: dev wlan0 root delay 1.0s rate 1Mbit",
            "qdisc netem 9c11: dev aiwn123456780 root delay 1.0s rate 2Mbit",
            "filter pref 49152 matchall redirect dev aiwn123456780",
        ])
        with patch.object(self.device, "identity", return_value=self.saved), \
             patch.object(self.device, "root", return_value=state):
            self.device.verify(self.saved, NetworkProfile(1000, 2000, 2000))

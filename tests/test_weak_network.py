import tempfile
import unittest
from pathlib import Path

from capture_console.weak_network import WeakNetworkService, NetworkProfile


class FakeDevice:
    def __init__(self, serial="emulator-5554"):
        self.serial = serial
        self.rules = False
        self.online = True
        self.fail_apply = False
        self.foreign = False
        self.boot_id = "boot-1"
        self.restores = 0

    def target(self):
        return {"serial": self.serial, "avd": "Capture"}

    def snapshot(self):
        self.check()
        if self.foreign:
            raise RuntimeError("existing traffic rules")
        return {**self.target(), "boot_id": self.boot_id}

    def check(self):
        if not self.online:
            raise RuntimeError("device offline")

    def apply(self, saved, profile):
        self.check()
        self.rules = True
        if self.fail_apply:
            raise RuntimeError("netem unavailable")

    def verify(self, saved, profile):
        self.check()
        if not self.rules or saved["boot_id"] != self.boot_id:
            raise RuntimeError("rules missing")

    def restore(self, saved):
        self.check()
        if saved["serial"] != self.serial:
            raise RuntimeError("device identity changed")
        self.rules = False
        self.restores += 1


class WeakNetworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.devices = {"one": FakeDevice(), "two": FakeDevice("emulator-5556")}
        self.identities = {device.serial: device for device in self.devices.values()}
        self.service = self.new_service()

    def new_service(self):
        return WeakNetworkService(Path(self.tmp.name), self.devices.__getitem__,
                                  lambda saved: self.identities[saved["serial"]])

    def test_apply_update_restore_isolated_and_persisted(self):
        profile = NetworkProfile(128, 256, 600)
        state = self.service.apply("one", profile)
        self.assertTrue(state["enabled"])
        self.assertEqual(state["profile"], {"upload_kbps": 128, "download_kbps": 256, "latency_ms": 600})
        self.assertFalse(self.devices["two"].rules)
        self.assertTrue(list(Path(self.tmp.name).glob("*.json")))
        self.service.apply("one", NetworkProfile(512, 2048, 150))
        self.assertTrue(self.service.restore("one")["available"])
        self.assertFalse(self.devices["one"].rules)
        self.assertFalse(list(Path(self.tmp.name).glob("*.json")))

    def test_partial_failure_rolls_back(self):
        self.devices["one"].fail_apply = True
        state = self.service.apply("one", NetworkProfile(128, 256, 600))
        self.assertFalse(state["enabled"])
        self.assertFalse(self.devices["one"].rules)
        self.assertIn("netem", state["technical_detail"])

    def test_restart_restores_and_offline_restore_retries(self):
        self.service.apply("one", NetworkProfile(128, 256, 600))
        device = self.devices["one"]
        device.online = False
        restarted = self.new_service()
        restarted.recover()
        self.assertTrue(restarted.status("one")["pending_restore"])
        device.online = True
        restarted.recover()
        self.assertFalse(device.rules)
        self.assertFalse(restarted.status("one")["pending_restore"])

    def test_recovery_does_not_turn_off_current_live_profile(self):
        self.service.apply("one", NetworkProfile(128, 256, 600))
        self.service.recover()
        self.assertTrue(self.devices["one"].rules)

    def test_lost_rules_not_reported_enabled(self):
        self.service.apply("one", NetworkProfile(128, 256, 600))
        self.devices["one"].rules = False
        state = self.service.status("one")
        self.assertFalse(state["enabled"])
        self.assertTrue(state["pending_restore"])

    def test_foreign_rules_are_not_touched(self):
        self.devices["one"].foreign = True
        state = self.service.apply("one", NetworkProfile(128, 256, 600))
        self.assertFalse(state["enabled"])
        self.assertEqual(self.devices["one"].restores, 0)

    def test_profile_validation_before_mutation(self):
        for args in [(0, 256, 600), (128, 100001, 600), (128, 256, -1), (True, 256, 5)]:
            with self.assertRaises(ValueError):
                NetworkProfile(*args)
        self.assertFalse(self.devices["one"].rules)

    def test_shutdown_restores_all_even_if_one_is_offline(self):
        for device in self.devices:
            self.service.apply(device, NetworkProfile(128, 256, 600))
        self.devices["one"].online = False
        self.service.restore_all()
        self.assertTrue(self.service.status("one")["pending_restore"])
        self.assertFalse(self.devices["two"].rules)

    def test_discovery_reordering_preserves_device_status_and_recovery(self):
        original = self.devices["one"]
        self.service.apply("one", NetworkProfile(128, 256, 600))
        self.devices["one"], self.devices["two"] = self.devices["two"], self.devices["one"]
        self.assertTrue(self.service.status("two")["enabled"])
        self.assertFalse(self.service.status("one")["enabled"])
        self.service.apply("one", NetworkProfile(512, 1024, 200))
        self.assertEqual(len(self.service.records), 2)
        self.new_service().recover()
        self.assertFalse(original.rules)
        self.assertFalse(self.devices["one"].rules)

    def test_background_detects_offline_without_status_requests(self):
        self.service.apply("one", NetworkProfile(128, 256, 600))
        self.devices["one"].online = False
        self.service.recover()
        self.devices["one"].online = True
        self.service.recover()
        self.assertFalse(self.devices["one"].rules)
        self.assertFalse(self.service.records)

import importlib.util
import sys
import types
import unittest
from pathlib import Path


def load_module():
    sys.modules.setdefault("frida", types.SimpleNamespace())
    path = Path(__file__).resolve().parents[1] / "scripts" / "flutter_proxy_unpin_capture.py"
    spec = importlib.util.spec_from_file_location("flutter_proxy_unpin_capture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FlutterProxyUnpinCaptureTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

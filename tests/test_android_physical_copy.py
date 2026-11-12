"""Keep physical-device instructions aligned with the native UI contract."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PhysicalCopyTests(unittest.TestCase):
    def test_current_guides_match_entry_and_finish_action(self):
        for relative in ('docs/desktop-user-guide.md', 'release/安装说明.md'):
            with self.subTest(file=relative):
                text = (ROOT / relative).read_text()
                self.assertIn('抓包 → Android → 真机', text)
                self.assertTrue('真机（实验）' not in text, f'{relative}: outdated device entry')
                self.assertIn('结束流程并重新检测', text)
                self.assertIn('停止并恢复网络', text)
                self.assertIn('检查网络恢复', text)

    def test_service_recovery_prompt_names_an_available_action(self):
        import tempfile
        import json
        from unittest.mock import Mock
        from capture_console.android_physical_service import PhysicalCaptureService

        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'recovery.json').write_text(json.dumps({'serial': 'old'}))
            service = PhysicalCaptureService(directory, Mock(), 'unused-adb')
            status = service.status()
            self.assertEqual(status['phase'], 'recovery_required')
            self.assertIn('检查网络恢复', status['message'])
            self.assertIn('原 VPN', status['message'])

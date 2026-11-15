"""Keep physical-device instructions aligned with the native UI contract."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PhysicalCopyTests(unittest.TestCase):
    def test_safety_stays_visible_while_supplemental_guidance_is_folded(self):
        view = (ROOT / 'macos-native/Sources/AICaptureNativeApp/AndroidPhysicalView.swift').read_text()
        folded = view.index('DisclosureGroup(AppCopy.AndroidPhysical.connectionHelp)')
        for field in ('boundary', 'network'):
            self.assertLess(view.index(f'Text(AppCopy.AndroidPhysical.{field})'), folded)
        for field in ('automatic', 'googleLogin', 'bannerHelp', 'recovery'):
            self.assertGreater(view.index(f'Text(AppCopy.AndroidPhysical.{field})'), folded)
        self.assertNotIn('Text(AppCopy.AndroidPhysical.terminateHelp)', view)
        self.assertIn('.help(AppCopy.AndroidPhysical.terminateHelp)', view)

    def test_google_login_guidance_is_visible_and_documents_scope(self):
        source = ROOT / 'macos-native/Sources/AICaptureNativeApp'
        self.assertIn('Text(AppCopy.AndroidPhysical.googleLogin)', (source / 'AndroidPhysicalView.swift').read_text())
        for relative in ('macos-native/Sources/AICaptureNativeApp/AndroidPhysicalCopy.swift', 'docs/desktop-user-guide.md'):
            text = (ROOT / relative).read_text()
            self.assertIn('先通过手机原 VPN 完成 Google 登录', text)
            self.assertIn('Google Play 服务', text)
            self.assertIn('停止并恢复网络', text)

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

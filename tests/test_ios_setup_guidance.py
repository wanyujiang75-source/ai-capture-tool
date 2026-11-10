"""Keep first-time and reused iPhone setup recovery guidance reachable in the UI."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class IOSSetupGuidanceTests(unittest.TestCase):
    def test_airdrop_recovery_is_attached_to_share_section(self):
        view = (ROOT / "macos-native/Sources/AICaptureNativeApp/IOSSetupView.swift").read_text()
        share = view.split("private func shareInstructions", 1)[1].split("private var installationInstructions", 1)[0]
        self.assertIn("DisclosureGroup(AppCopy.IOSSetup.airdropHelpTitle)", share)
        self.assertIn("Text(AppCopy.IOSSetup.airdropHelp)", share)

    def test_vpn_record_and_restore_are_visible_for_reused_connections(self):
        view = (ROOT / "macos-native/Sources/AICaptureNativeApp/IOSSetupView.swift").read_text()
        instructions = view.split("private var instructions", 1)[1].split("private func shareInstructions", 1)[0]
        self.assertIn("Text(AppCopy.IOSSetup.vpnPreparation)", instructions)
        self.assertIn("Text(AppCopy.IOSSetup.vpnSwitch)", instructions)
        self.assertIn("Text(AppCopy.IOSSetup.vpnRestore)", instructions)
        self.assertLess(instructions.index("Text(AppCopy.IOSSetup.vpnPreparation)"), instructions.index("if controller.status.identityReused"))

    def test_help_covers_pairing_code_and_does_not_claim_automatic_restore(self):
        copy = (ROOT / "macos-native/Sources/AICaptureNativeApp/IOSSetupCopy.swift").read_text()
        self.assertIn("所有人（10 分钟）", copy)
        self.assertIn("隔空投送代码", copy)
        self.assertIn("恢复原节点和全局路由模式", copy)
        self.assertIn("不会自动替手机恢复", copy)
        self.assertIn("新 iPhone", copy)


if __name__ == "__main__":
    unittest.main()

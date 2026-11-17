import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
APP_CONTENTS = ROOT / "macos-native/build/抓包工具.app/Contents"


@unittest.skipUnless(sys.platform == "darwin", "macOS App bundle")
class DesktopUpdaterPackagingTests(unittest.TestCase):
    def test_update_ready_bundle_carries_release_versions_and_signing_key(self):
        public_key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        feed = "https://example.com/appcast.xml"
        subprocess.run(
            [str(ROOT / "macos-native/scripts/build-app.sh")],
            cwd=ROOT,
            env={
                **os.environ,
                "EMBED_RUNTIME": "0",
                "AI_CAPTURE_APP_VERSION": "0.2.3",
                "TRACEDECK_BUILD_NUMBER": "42",
                "SPARKLE_FEED_URL": feed,
                "SPARKLE_PUBLIC_ED_KEY": public_key,
            },
            check=True,
        )
        plist = plistlib.loads((APP_CONTENTS / "Info.plist").read_bytes())
        self.assertEqual("0.2.3", plist["CFBundleShortVersionString"])
        self.assertEqual("42", plist["CFBundleVersion"])
        self.assertEqual(feed, plist["SUFeedURL"])
        self.assertEqual(public_key, plist["SUPublicEDKey"])
        self.assertFalse(plist["SUEnableAutomaticChecks"])
        self.assertFalse(plist["SUAllowsAutomaticUpdates"])
        self.assertTrue(plist["SUVerifyUpdateBeforeExtraction"])
        self.assertTrue(plist["SURequireSignedFeed"])
        self.assertTrue((APP_CONTENTS / "Frameworks/Sparkle.framework/Versions/Current/Updater.app").is_dir())
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(APP_CONTENTS.parent)], check=True)

    def test_rejects_partial_or_invalid_configuration(self):
        result = subprocess.run(
            [str(ROOT / "macos-native/scripts/build-app.sh")], cwd=ROOT,
            env={**os.environ, "EMBED_RUNTIME": "0", "SPARKLE_FEED_URL": "http://example.com/appcast.xml",
                 "SPARKLE_PUBLIC_ED_KEY": ""},
            capture_output=True, text=True,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Sparkle requires an HTTPS feed URL and a valid EdDSA public key", result.stderr)


    def test_distribution_rejects_key_files_inside_source_tree(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "macos-native") as directory:
            key = Path(directory) / "test-key"
            key.write_text("fixture")
            result = subprocess.run(
                [str(ROOT / "release/package.sh")], cwd=ROOT,
                env={**os.environ, "TRACEDECK_RELEASE_KIND": "distribution",
                     "SPARKLE_PRIVATE_ED_KEY_FILE": str(key)},
                capture_output=True, text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Sparkle private key file must be outside the source checkout", result.stderr)

    def test_generates_signed_feed_for_each_version_and_rejects_wrong_key(self):
        generator = ROOT / "release/build-appcast.sh"
        self.assertTrue(generator.is_file(), "The release must provide a signed appcast generator")
        key = subprocess.run(
            ["swift", "-e", "import CryptoKit; import Foundation; "
             "let key = Curve25519.Signing.PrivateKey(); "
             "print(key.rawRepresentation.base64EncodedString()); "
             "print(key.publicKey.rawRepresentation.base64EncodedString())"],
            capture_output=True, text=True, check=True,
        )
        private_key, public_key = key.stdout.splitlines()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            key_file = root / "test-key"
            key_file.touch(mode=0o600)
            key_file.write_text(private_key)
            notes = root / "notes.md"
            notes.write_text("试用更新说明")
            for build_number, version in (("42", "0.2.3"), ("43", "0.2.4")):
                prefix = f"https://example.com/releases/v{version}/"
                env = {
                    **os.environ, "EMBED_RUNTIME": "0", "AI_CAPTURE_APP_VERSION": version,
                    "TRACEDECK_BUILD_NUMBER": build_number, "SPARKLE_PUBLIC_ED_KEY": public_key,
                    "SPARKLE_FEED_URL": "https://example.com/appcast.xml",
                    "SPARKLE_PRIVATE_ED_KEY_FILE": str(key_file), "SPARKLE_RELEASE_NOTES": str(notes),
                }
                subprocess.run([str(ROOT / "macos-native/scripts/build-app.sh")], cwd=ROOT, env=env, check=True)
                output = root / f"v{version}"
                subprocess.run([str(generator), str(APP_CONTENTS.parent), str(output), prefix], env=env, check=True)
                sparkle = "{http://www.andymatuschak.org/xml-namespaces/sparkle}"
                item = ElementTree.parse(output / "appcast.xml").find("channel/item")
                self.assertEqual(build_number, item.findtext(f"{sparkle}version"))
                self.assertEqual(version, item.findtext(f"{sparkle}shortVersionString"))
                archive = output / f"AI-Capture-Update-{version}-arm64.zip"
                enclosure = item.find("enclosure")
                self.assertEqual(prefix + archive.name, enclosure.get("url"))
                self.assertEqual(str(archive.stat().st_size), enclosure.get("length"))
                self.assertTrue(enclosure.get(f"{sparkle}edSignature"))
            key_file.write_text("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
            output = root / "wrong-key"
            result = subprocess.run(
                [str(generator), str(APP_CONTENTS.parent), str(output), prefix],
                env=env, capture_output=True, text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertFalse(output.exists())

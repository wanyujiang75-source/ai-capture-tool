import hashlib
import json
import os
import platform
import plistlib
import signal
import socket
import subprocess
import tarfile
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "macos-native" / "scripts" / "build-app.sh"
APP_PATH = ROOT / "macos-native" / "build" / "抓包工具.app"
LEGACY_APP_PATH = ROOT / "macos-native" / "build" / "AI抓包工具.app"
PACKAGE_SCRIPT = ROOT / "release" / "package.sh"
NOTARIZE_SCRIPT = ROOT / "release" / "notarize-app.sh"
RELEASE_DIR = ROOT / "release"
SOURCE_ICON = ROOT / "macos-native" / "Resources" / "AppIcon.png"
EXPECTED_ICONSET_FILES = [
    "icon_16x16.png",
    "icon_16x16@2x.png",
    "icon_32x32.png",
    "icon_32x32@2x.png",
    "icon_128x128.png",
    "icon_128x128@2x.png",
    "icon_256x256.png",
    "icon_256x256@2x.png",
    "icon_512x512.png",
    "icon_512x512@2x.png",
]


@unittest.skipUnless(platform.system() == "Darwin", "native app packaging requires macOS")
class NativeAppPackagingTests(unittest.TestCase):
    def test_source_icon_meets_asset_contract(self) -> None:
        self.assertTrue(SOURCE_ICON.is_file(), SOURCE_ICON)
        result = subprocess.run(
            [
                "sips",
                "-g",
                "pixelWidth",
                "-g",
                "pixelHeight",
                "-g",
                "hasAlpha",
                str(SOURCE_ICON),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        properties = {}
        for line in result.stdout.splitlines()[1:]:
            key, separator, value = line.strip().partition(": ")
            if separator:
                properties[key] = value
        self.assertEqual(
            {"pixelWidth": "1024", "pixelHeight": "1024", "hasAlpha": "yes"},
            properties,
        )

    def test_build_app_embeds_macos_icon(self) -> None:
        environment = {**os.environ, "EMBED_RUNTIME": "0"}
        subprocess.run(
            [str(BUILD_SCRIPT)],
            cwd=BUILD_SCRIPT.parents[1],
            env=environment,
            check=True,
        )
        info_plist = APP_PATH / "Contents" / "Info.plist"
        icon_path = APP_PATH / "Contents" / "Resources" / "AppIcon.icns"

        with info_plist.open("rb") as plist_file:
            bundle_properties = plistlib.load(plist_file)
        self.assertEqual("抓包工具", bundle_properties["CFBundleExecutable"])
        self.assertEqual("抓包工具", bundle_properties["CFBundleName"])
        self.assertEqual("抓包工具", bundle_properties["CFBundleDisplayName"])
        self.assertEqual("AppIcon", bundle_properties["CFBundleIconFile"])
        self.assertTrue(icon_path.is_file(), icon_path)
        self.assertFalse(LEGACY_APP_PATH.exists(), LEGACY_APP_PATH)

        with tempfile.TemporaryDirectory() as temporary_directory:
            iconset_path = Path(temporary_directory) / "AppIcon.iconset"
            result = subprocess.run(
                [
                    "iconutil",
                    "-c",
                    "iconset",
                    str(icon_path),
                    "-o",
                    str(iconset_path),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                sorted(EXPECTED_ICONSET_FILES),
                sorted(path.name for path in iconset_path.iterdir()),
            )

    def test_build_app_produces_a_valid_bundle_signature(self) -> None:
        subprocess.run([str(BUILD_SCRIPT)], cwd=BUILD_SCRIPT.parents[1], check=True)

        result = subprocess.run(
            ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(APP_PATH)],
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)

    def test_build_app_embeds_a_relocatable_capture_runtime(self) -> None:
        subprocess.run([str(BUILD_SCRIPT)], cwd=BUILD_SCRIPT.parents[1], check=True)
        resources = APP_PATH / "Contents" / "Resources"
        runtime = resources / "runtime"
        runtime_bin = runtime / "bin"

        for executable in ("python3", "uvicorn", "mitmweb", "frida", "frida-ps"):
            self.assertTrue(os.access(runtime_bin / executable, os.X_OK), executable)

        manifest = json.loads((runtime / "manifest.json").read_text(encoding="utf-8"))
        expected_requirements_hash = hashlib.sha256(
            (ROOT / "requirements-console.txt").read_bytes()
        ).hexdigest()
        self.assertEqual("arm64", manifest["architecture"])
        self.assertEqual(expected_requirements_hash, manifest["requirements_sha256"])
        absolute_links = [
            path
            for path in runtime.rglob("*")
            if path.is_symlink() and Path(os.readlink(path)).is_absolute()
        ]
        self.assertEqual([], absolute_links)

        with tempfile.TemporaryDirectory() as temporary_directory:
            relocated_app = Path(temporary_directory) / APP_PATH.name
            subprocess.run(["ditto", str(APP_PATH), str(relocated_app)], check=True)
            relocated_python = (
                relocated_app / "Contents" / "Resources" / "runtime" / "bin" / "python3"
            )
            result = subprocess.run(
                [
                    str(relocated_python),
                    "-c",
                    "import fastapi, frida, mitmproxy, uvicorn; print('runtime-ok')",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("runtime-ok", result.stdout.strip())

            with socket.socket() as port_socket:
                port_socket.bind(("127.0.0.1", 0))
                port = port_socket.getsockname()[1]

            relocated_resources = relocated_app / "Contents" / "Resources"
            backend = relocated_resources / "backend"
            runtime_bin = relocated_resources / "runtime" / "bin"
            runtime_data = Path(temporary_directory) / "runtime-data"
            forbidden_venv = Path(temporary_directory) / "must-not-create-venv"
            environment = {
                "HOME": str(Path.home()),
                "PATH": f"{runtime_bin}:/usr/bin:/bin",
                "LANG": "en_US.UTF-8",
                "TRACEDECK_DESKTOP": "1",
                "CAPTURE_RUNTIME_DIR": str(runtime_data),
                "CONSOLE_VENV_DIR": str(forbidden_venv),
                "CONSOLE_HOST": "127.0.0.1",
                "CONSOLE_PORT": str(port),
                "CONSOLE_PYTHON": str(runtime_bin / "python3"),
                "CONSOLE_SKIP_INSTALL": "1",
                "CONSOLE_USE_EMBEDDED_RUNTIME": "1",
                "TRACEDECK_RUNTIME_BIN": str(runtime_bin),
                "FRIDA_PYTHON_BIN": str(runtime_bin / "python3"),
                "MITMWEB_BIN": str(runtime_bin / "mitmweb"),
                "PYTHONNOUSERSITE": "1",
                "PYTHONPATH": str(backend),
            }
            backend_process = subprocess.Popen(
                ["/bin/bash", str(backend / "scripts" / "start_console.sh")],
                cwd=backend,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                status_url = f"http://127.0.0.1:{port}/api/status"
                response_body = None
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if backend_process.poll() is not None:
                        output = backend_process.stdout.read() if backend_process.stdout else ""
                        self.fail(f"embedded backend exited early:\n{output}")
                    try:
                        with opener.open(status_url, timeout=3) as response:
                            self.assertEqual(200, response.status)
                            response_body = json.load(response)
                            break
                    except (urllib.error.URLError, TimeoutError):
                        time.sleep(0.25)
                self.assertIsNotNone(response_body, "embedded backend did not become ready")
                self.assertFalse(forbidden_venv.exists())
                with opener.open(
                    f"http://127.0.0.1:{port}/api/system/env-check",
                    timeout=5,
                ) as response:
                    environment_report = json.load(response)["env"]
                environment_checks = {
                    check["name"]: check for check in environment_report["checks"]
                }
                self.assertNotIn("node", environment_checks)
                self.assertNotIn("npm", environment_checks)
                self.assertNotIn("xz", environment_checks)
                for command in ("python3", "mitmweb", "frida", "frida-ps"):
                    self.assertTrue(environment_checks[command]["ok"], command)
                    self.assertTrue(
                        environment_checks[command]["detail"].startswith(str(runtime_bin)),
                        environment_checks[command],
                    )
            finally:
                self._stop_process_group(backend_process)

    @staticmethod
    def _stop_process_group(process: subprocess.Popen[str]) -> None:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        if process.stdout is not None:
            process.stdout.close()

    def test_distribution_release_requires_developer_id_before_build(self) -> None:
        version = f"test-{uuid.uuid4().hex}"
        source_archive = RELEASE_DIR / f"TraceDeck-{version}.tar.gz"
        source_checksum = source_archive.with_suffix(source_archive.suffix + ".sha256")
        self.addCleanup(source_archive.unlink, missing_ok=True)
        self.addCleanup(source_checksum.unlink, missing_ok=True)
        env = os.environ.copy()
        env["TRACEDECK_RELEASE_KIND"] = "distribution"
        env["TRACEDECK_VERSION"] = version
        env.pop("MACOS_SIGN_IDENTITY", None)
        env.pop("MACOS_NOTARY_PROFILE", None)

        result = subprocess.run(
            [str(PACKAGE_SCRIPT)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("Developer ID Application", result.stderr)

    def test_development_release_creates_explicitly_labeled_app_zip(self) -> None:
        version = f"test-{uuid.uuid4().hex}"
        archive = RELEASE_DIR / f"AI-Capture-Desktop-{version}-development-arm64.zip"
        archive_checksum = archive.with_suffix(archive.suffix + ".sha256")
        source_archive = RELEASE_DIR / f"TraceDeck-{version}.tar.gz"
        source_checksum = source_archive.with_suffix(source_archive.suffix + ".sha256")
        self.addCleanup(archive.unlink, missing_ok=True)
        self.addCleanup(archive_checksum.unlink, missing_ok=True)
        self.addCleanup(source_archive.unlink, missing_ok=True)
        self.addCleanup(source_checksum.unlink, missing_ok=True)
        env = {
            **os.environ,
            "TRACEDECK_RELEASE_KIND": "development",
            "TRACEDECK_VERSION": version,
        }

        result = subprocess.run(
            [str(PACKAGE_SCRIPT)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(archive.is_file(), result.stdout)
        self.assertEqual(
            f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n",
            archive_checksum.read_text(encoding="utf-8"),
        )
        self.assertEqual(
            f"{hashlib.sha256(source_archive.read_bytes()).hexdigest()}  {source_archive.name}\n",
            source_checksum.read_text(encoding="utf-8"),
        )
        with tarfile.open(source_archive, "r:gz") as source_bundle:
            source_names = set(source_bundle.getnames())
        self.assertIn("INSTALL.md", source_names)
        self.assertIn("release/package.sh", source_names)
        self.assertIn("release/notarize-app.sh", source_names)
        with tempfile.TemporaryDirectory() as temporary_directory:
            extracted = Path(temporary_directory)
            subprocess.run(
                ["ditto", "-x", "-k", str(archive), str(extracted)],
                check=True,
            )
            extracted_app = extracted / "抓包工具.app"
            self.assertTrue(
                (extracted_app / "Contents" / "MacOS" / "抓包工具").is_file()
            )
            verification = subprocess.run(
                [
                    "codesign",
                    "--verify",
                    "--deep",
                    "--strict",
                    "--verbose=2",
                    str(extracted_app),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, verification.returncode, verification.stderr)

    def test_notarization_requires_a_keychain_profile(self) -> None:
        output = RELEASE_DIR / f"notary-test-{uuid.uuid4().hex}.zip"
        self.addCleanup(output.unlink, missing_ok=True)
        env = os.environ.copy()
        env["MACOS_SIGN_IDENTITY"] = "Developer ID Application: Example (TEAMID)"
        env.pop("MACOS_NOTARY_PROFILE", None)

        result = subprocess.run(
            [str(NOTARIZE_SCRIPT), str(APP_PATH), str(output)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("MACOS_NOTARY_PROFILE", result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()

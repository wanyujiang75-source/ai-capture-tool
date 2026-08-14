import sqlite3
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch


class CaptureConsoleCoreTests(unittest.TestCase):
    def make_system_image(self, sdk_root: Path, *, api: str, tag: str, abi: str) -> Path:
        path = sdk_root / "system-images" / api / tag / abi
        path.mkdir(parents=True)
        return path

    def add_test_device(
        self,
        store,
        *,
        device_id: str = "device-1",
        adb_serial: str = "emulator-5554",
        proxy_port: int = 9090,
        web_port: int = 9091,
        frida_port: int = 27042,
        resident: int = 1,
        idle_release_minutes: int = 0,
    ):
        return store.upsert_device(
            device_id=device_id,
            name=f"Test Device {device_id}",
            avd_name=f"Test_AVD_{device_id}",
            adb_serial=adb_serial,
            proxy_port=proxy_port,
            web_port=web_port,
            frida_port=frida_port,
            enabled=1,
            resident=resident,
            idle_release_minutes=idle_release_minutes,
        )

    def test_preflight_classifies_capture_ports_without_killing_other_projects(self):
        from capture_console.preflight import classify_port

        project = Path("/srv/ai-capture")

        self.assertEqual(
            classify_port(9090, [], project_root=project, runtime_dir=project / "runtime")["state"],
            "free",
        )
        self.assertEqual(
            classify_port(
                9090,
                [{"pid": 101, "command": "/srv/ai-capture/.venv/bin/mitmweb --listen-port 9090"}],
                project_root=project,
                runtime_dir=project / "runtime",
            )["state"],
            "owned_by_project",
        )
        self.assertEqual(
            classify_port(
                9090,
                [{"pid": 102, "command": "/opt/homebrew/bin/mitmweb --listen-port 9090 --set web_password=android-capture"}],
                project_root=project,
                runtime_dir=project / "runtime",
            )["state"],
            "owned_by_project",
        )
        self.assertEqual(
            classify_port(
                27142,
                [{"pid": 103, "command": "adb -L tcp:5038 fork-server server --reply-fd 4"}],
                project_root=project,
                runtime_dir=project / "runtime",
            )["state"],
            "owned_by_project",
        )
        occupied = classify_port(
            9090,
            [{"pid": 202, "command": "/Applications/Other.app/Contents/MacOS/service --port 9090"}],
            project_root=project,
            runtime_dir=project / "runtime",
        )
        self.assertEqual(occupied["state"], "occupied_by_other")
        self.assertFalse(occupied["ok"])

    def test_preflight_marks_configured_host_proxy_as_external_dependency(self):
        from capture_console.preflight import classify_port

        result = classify_port(
            7890,
            [{"pid": 303, "command": "/Applications/ClashX.app/Contents/MacOS/ClashX"}],
            project_root=Path("/srv/ai-capture"),
            runtime_dir=Path("/srv/ai-capture/runtime"),
            external_dependency_ports={7890},
        )

        self.assertEqual(result["state"], "external_dependency")
        self.assertTrue(result["ok"])

    def test_mitm_socks_stack_refuses_foreign_port_owners_instead_of_killing_them(self):
        script = Path("scripts/start_mitm_socks_stack.sh").read_text(encoding="utf-8")

        self.assertIn("refuse_foreign_port_owner", script)
        self.assertNotIn("lsof -tiTCP:\"$PROXY_PORT\"", script)
        self.assertNotIn("lsof -tiTCP:\"$WEB_PORT\"", script)

    def test_ai_capture_restart_mitm_refuses_foreign_port_owners_instead_of_killing_them(self):
        script = Path("scripts/ai_capture.sh").read_text(encoding="utf-8")

        self.assertIn("refuse_foreign_port_owner", script)
        self.assertNotIn("lsof -tiTCP:\"$PROXY_PORT\"", script)
        self.assertNotIn("lsof -tiTCP:\"$WEB_PORT\"", script)

    def test_console_launchers_reject_python_below_mitmproxy_requirement(self):
        helper = Path("scripts/console_python.sh").read_text(encoding="utf-8")

        self.assertIn("CONSOLE_MIN_PYTHON_MAJOR", helper)
        self.assertIn("CONSOLE_MIN_PYTHON_MINOR", helper)
        self.assertIn("python_supports_console_requirements", helper)
        self.assertIn("sys.version_info >= (major, minor)", helper)
        self.assertIn("recreate incompatible console venv", helper)
        for script_path in ["setup.sh", "scripts/start_console.sh", "scripts/start_web_services.sh"]:
            script = Path(script_path).read_text(encoding="utf-8")
            self.assertIn("scripts/console_python.sh", script)
            self.assertIn("ensure_console_venv", script)

    def test_ai_capture_flutter_socks_preserves_running_app_processes(self):
        script = Path("scripts/ai_capture.sh").read_text(encoding="utf-8")

        self.assertIn("--no-force-stop", script)
        self.assertIn("--pid-timeout", script)

    def test_stop_web_services_only_stops_owned_processes(self):
        script = Path("scripts/stop_web_services.sh").read_text(encoding="utf-8")

        self.assertIn("project_owns_pid", script)
        self.assertIn("skipped foreign", script)

    def test_store_defaults_to_android_platform_and_persists_session_platform(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
            self.add_test_device(store)
            app = store.create_app(
                name="MelodyCraft",
                package_name="com.meta.inno.monopoly_sticker",
                activity="com.meta.inno.monopoly_sticker/.MainActivity",
                default_mode="flutter-socks",
            )

            session = store.create_session(
                app_id=app["id"],
                mode="flutter-socks",
                outdir="/tmp/android-capture",
                status="running",
            )

            self.assertEqual(app["platform"], "android")
            self.assertEqual(session["platform"], "android")

    def test_store_starts_without_default_apps_or_capture_devices(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")

            self.assertEqual(store.list_apps(), [])
            self.assertEqual(store.list_devices(), [])
            with self.assertRaises(KeyError):
                store.default_device()

    def test_store_requires_known_device_before_creating_session(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
            app = store.create_app(
                name="Example",
                package_name="com.example.app",
                default_mode="flutter-socks",
            )

            with self.assertRaises(KeyError):
                store.create_session(
                    app_id=app["id"],
                    mode="flutter-socks",
                    outdir="/tmp/android-capture",
                    status="running",
                )

    def test_local_config_defaults_to_safe_macos_localhost_values(self):
        from capture_console.local_config import load_local_config

        with tempfile.TemporaryDirectory() as tmp:
            config = load_local_config(root_dir=Path(tmp), env={})

            self.assertEqual(config["console"]["host"], "127.0.0.1")
            self.assertEqual(config["console"]["port"], 7001)
            self.assertEqual(config["capture"]["proxy_port_start"], 9090)
            self.assertEqual(config["capture"]["mitmweb_token"], "android-capture")

    def test_adb_device_discovery_parses_online_devices_only(self):
        from capture_console.device_discovery import parse_adb_devices

        devices = parse_adb_devices(
            "List of devices attached\n"
            "emulator-5554\tdevice product:sdk_gphone model:sdk_gphone\n"
            "192.168.1.50:5555\toffline\n"
            "R5CT123ABC\tdevice usb:336592896X\n"
        )

        self.assertEqual([device["serial"] for device in devices], ["emulator-5554", "R5CT123ABC"])
        self.assertEqual(devices[0]["kind"], "emulator")
        self.assertEqual(devices[1]["kind"], "physical")

    def test_discovered_device_port_assignment_skips_occupied_slots(self):
        from capture_console.device_discovery import build_discovered_devices

        devices = build_discovered_devices(
            [{"serial": "emulator-5554", "kind": "emulator"}, {"serial": "R5CT123ABC", "kind": "physical"}],
            proxy_port_start=9090,
            web_port_start=9091,
            frida_port_start=27042,
            occupied_ports={9090, 9091, 27042},
        )

        self.assertEqual(devices[0]["device_id"], "device-1")
        self.assertEqual(devices[0]["proxy_port"], 9100)
        self.assertEqual(devices[0]["web_port"], 9101)
        self.assertEqual(devices[0]["frida_port"], 27142)
        self.assertEqual(devices[1]["device_id"], "device-2")
        self.assertEqual(devices[1]["proxy_port"], 9110)

    def test_release_package_script_excludes_local_runtime_state(self):
        script = Path("release/package.sh").read_text(encoding="utf-8")

        self.assertIn("--exclude=runtime", script)
        self.assertIn("--exclude=config/local.json", script)
        self.assertIn("--exclude=web/node_modules", script)
        self.assertIn("--exclude='.venv-*'", script)
        self.assertIn("--exclude='release/*.zip'", script)
        self.assertIn("--exclude=macos-native/build", script)
        self.assertIn("release/package.sh", script)
        self.assertIn("release/notarize-app.sh", script)
        self.assertIn("web/dist", script)

    def test_distribution_release_requires_apple_notarization_gates(self):
        package_script = Path("release/package.sh").read_text(encoding="utf-8")
        notarize_script = Path("release/notarize-app.sh").read_text(encoding="utf-8")

        self.assertIn("Developer ID Application", package_script)
        self.assertIn("MACOS_NOTARY_PROFILE", package_script)
        self.assertIn("release/notarize-app.sh", package_script)
        self.assertIn("xcrun notarytool submit", notarize_script)
        self.assertIn("xcrun stapler staple", notarize_script)
        self.assertIn("xcrun stapler validate", notarize_script)
        self.assertIn("spctl --assess --type execute", notarize_script)

    def test_embedded_console_mode_skips_venv_pip_and_npm(self):
        script = Path("scripts/start_console.sh").read_text(encoding="utf-8")
        runtime_manager = Path(
            "macos-native/Sources/AICaptureNativeApp/RuntimeManager.swift"
        ).read_text(encoding="utf-8")

        self.assertIn("CONSOLE_USE_EMBEDDED_RUNTIME", script)
        self.assertIn('SERVER_PYTHON="$CONSOLE_PYTHON"', script)
        self.assertIn('exec "$SERVER_PYTHON" -m uvicorn', script)
        self.assertIn('TRACEDECK_DESKTOP', script)
        self.assertIn('environment["CONSOLE_SKIP_INSTALL"] = "1"', runtime_manager)
        self.assertIn('environment["CONSOLE_USE_EMBEDDED_RUNTIME"] = "1"', runtime_manager)
        self.assertIn('environment["TRACEDECK_RUNTIME_BIN"]', runtime_manager)
        self.assertIn('environment["FRIDA_PYTHON_BIN"]', runtime_manager)
        self.assertIn('environment["MITMWEB_BIN"]', runtime_manager)

    def test_desktop_environment_check_requires_embedded_tools_not_node_or_xz(self):
        from capture_console.runner import ConsoleRunner

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "runtime" / "bin"
            sdk_root = root / "android-sdk"
            bin_dir.mkdir(parents=True)
            sdk_root.mkdir()
            required_commands = {
                "python3",
                "adb",
                "emulator",
                "sdkmanager",
                "avdmanager",
                "mitmweb",
                "frida",
                "frida-ps",
                "screen",
            }
            for command in required_commands:
                executable = bin_dir / command
                executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                executable.chmod(0o755)
            environment = {
                "PATH": str(bin_dir),
                "TRACEDECK_DESKTOP": "1",
                "TRACEDECK_RUNTIME_BIN": str(bin_dir),
                "ANDROID_SDK_ROOT": str(sdk_root),
            }
            runner = ConsoleRunner(root, allow_non_retained=True)

            with patch.object(runner, "_env", return_value=environment):
                report = runner.env_check()

            checks = {check["name"]: check for check in report["checks"]}
            self.assertTrue(report["ok"])
            self.assertTrue(required_commands.issubset(checks))
            self.assertNotIn("node", checks)
            self.assertNotIn("npm", checks)
            self.assertNotIn("xz", checks)

    def test_runner_prioritizes_embedded_runtime_bin(self):
        from capture_console.runner import ConsoleRunner

        runner = ConsoleRunner(Path.cwd(), allow_non_retained=True)
        environment = runner._env({"TRACEDECK_RUNTIME_BIN": "/App/Contents/Resources/runtime/bin"})

        self.assertTrue(environment["PATH"].startswith("/App/Contents/Resources/runtime/bin:"))

    def test_frida_server_can_decompress_with_embedded_python(self):
        script = Path("scripts/start_frida_server.sh").read_text(encoding="utf-8")

        self.assertNotIn("require_command xz", script)
        self.assertIn("FRIDA_PYTHON_BIN", script)
        self.assertIn("import lzma", script)

    def test_frida_start_script_does_not_require_adb_root_before_magisk_detection(self):
        script = Path("scripts/start_frida_server.sh").read_text(encoding="utf-8")

        self.assertIn("adb_wait_for_device", script)
        self.assertNotIn("adb_root_wait", script)
        self.assertIn("no root-capable Frida launch path", script)

    def test_frida_bootstrap_grants_shell_root_without_starting_frida_from_init(self):
        service = Path("tools/rootAVD/frida.rc").read_text(encoding="utf-8")
        grant_path = Path("tools/rootAVD/sbin/ai-capture-root-grant.sh")
        prepare_script = Path("scripts/prepare_frida_avd.sh").read_text(encoding="utf-8")
        start_script = Path("scripts/start_frida_server.sh").read_text(encoding="utf-8")

        self.assertTrue(grant_path.exists())
        grant = grant_path.read_text(encoding="utf-8")
        self.assertIn("/system/bin/sh /debug_ramdisk/ai-capture-root-grant.sh", service)
        self.assertNotIn("service frida_server", service)
        self.assertIn("REPLACE INTO policies", grant)
        self.assertIn("VALUES(2000, 2, 0, 1, 0)", grant)
        self.assertIn("root_access", grant)
        self.assertIn("/data/local/tmp/ai-capture-root-grant.log", grant)
        self.assertIn('cp "$ROOTAVD_SOURCE/sbin/ai-capture-root-grant.sh"', prepare_script)
        self.assertIn("ROOT_GRANT_SHA256", prepare_script)
        self.assertIn("/debug_ramdisk/magisk su", start_script)

    def test_console_runtime_pins_android_16_compatible_frida(self):
        requirements = Path("requirements-console.txt").read_text(encoding="utf-8")
        version_text = next(
            line.removeprefix("frida==")
            for line in requirements.splitlines()
            if line.startswith("frida==")
        )
        version = tuple(int(part) for part in version_text.split("."))

        self.assertGreaterEqual(version, (17, 17, 0))

    def test_frida_bootstrap_uses_project_owned_system_image_overlay(self):
        script_path = Path("scripts/prepare_frida_avd.sh")
        self.assertTrue(script_path.exists())
        script = script_path.read_text(encoding="utf-8")

        self.assertIn(".ai-capture/system-images", script)
        self.assertIn("ADB_SERIAL", script)
        self.assertIn("image.sysdir.1", script)
        self.assertIn("AddRCscripts", script)
        self.assertNotIn("-wipe-data", script)

    def test_native_build_bundles_frida_bootstrap_assets(self):
        script = Path("macos-native/scripts/build-app.sh").read_text(encoding="utf-8")

        self.assertIn('cp -R "$PROJECT_ROOT/tools/rootAVD" "$BACKEND_DIR/tools/rootAVD"', script)

    def test_store_defaults_to_production_and_persists_test_environment(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
            production = store.create_app(
                name="PokeHub",
                package_name="com.mi.poketrade",
                default_mode="flutter-socks",
            )
            test = store.create_app(
                name="MelodyCraft 测试包",
                package_name="com.meta.inno.monopoly_sticker",
                default_mode="flutter-socks",
                environment="test",
            )

            self.assertEqual(production["environment"], "production")
            self.assertEqual(test["environment"], "test")

    def test_store_migrates_existing_test_named_apps_to_test_environment(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "console.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE apps (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        platform TEXT NOT NULL DEFAULT 'android',
                        name TEXT NOT NULL,
                        package_name TEXT NOT NULL UNIQUE,
                        activity TEXT NOT NULL DEFAULT '',
                        default_mode TEXT NOT NULL DEFAULT 'system',
                        notes TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO apps (name, package_name, default_mode, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "MelodyCraft 测试包",
                        "com.meta.inno.monopoly_sticker",
                        "flutter-socks",
                        "旧抓包环境使用的包名，保留用于对比正式包。",
                        "2026-05-18T10:00:00+08:00",
                        "2026-05-18T10:00:00+08:00",
                    ),
                )

            store = CaptureStore(db_path)
            app = store.get_app_by_package("com.meta.inno.monopoly_sticker")

            self.assertEqual(app["environment"], "test")

    def test_store_allows_ios_reserved_apps_but_platform_marks_capture_unsupported(self):
        from capture_console.platforms import capture_supported, validate_platform
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
            app = store.create_app(
                platform="ios",
                name="Future iOS App",
                package_name="com.example.future.ios",
                default_mode="system",
            )

            self.assertEqual(app["platform"], "ios")
            self.assertFalse(capture_supported(app["platform"]))
            with self.assertRaises(ValueError):
                validate_platform("desktop")

    def test_runner_rejects_destructive_commands_that_can_destroy_login_state(self):
        from capture_console.runner import ConsoleRunner

        runner = ConsoleRunner("/tmp")

        for args in [
            ["emulator", "-avd", "Medium_Phone_API_36.1", "-wipe-data"],
            ["avdmanager", "delete", "avd", "-n", "Medium_Phone_API_36.1"],
            ["adb", "-s", "emulator-5554", "shell", "pm", "clear", "com.example.app"],
            ["adb", "-s", "emulator-5554", "uninstall", "com.example.app"],
        ]:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    runner.reject_destructive_command(args)

    def test_frida_start_script_cleans_stale_forward_and_pidof_process(self):
        script = Path("scripts/start_frida_server.sh").read_text(encoding="utf-8")

        self.assertIn('forward --remove "tcp:${FORWARD_PORT}"', script)
        self.assertIn("pidof frida-server", script)

    def test_runner_flags_non_retained_emulator_target_as_unsafe(self):
        from capture_console.runner import ConsoleRunner

        runner = ConsoleRunner("/tmp", adb_serial="emulator-5556", avd_name="Disposable_AVD")

        check = runner.retained_target_check()

        self.assertFalse(check["ok"])
        self.assertEqual(check["name"], "retained_emulator")
        self.assertIn("Medium_Phone_API_36.1", check["fix"])
        self.assertIn("emulator-5554", check["fix"])

    def test_runner_exports_emulator_port_from_adb_serial(self):
        from capture_console.runner import ConsoleRunner

        runner = ConsoleRunner("/tmp", adb_serial="emulator-5556", avd_name="Capture_AVD_02")

        self.assertEqual(runner._env()["EMULATOR_PORT"], "5556")

    def test_runner_uses_background_emulator_launch_for_server(self):
        from capture_console.runner import ConsoleRunner

        runner = ConsoleRunner("/tmp", adb_serial="emulator-5554", avd_name="Capture_AVD_01")

        self.assertEqual(runner._env()["EMULATOR_LAUNCH_MODE"], "background")

    def test_runner_can_request_visible_terminal_emulator_launch(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        class RecordingRunner(ConsoleRunner):
            def __init__(self):
                super().__init__("/tmp", adb_serial="emulator-5554", avd_name="Capture_AVD_01", allow_non_retained=True)
                self.extra_env = None

            def run(self, args, *, timeout=30, env=None):
                self.extra_env = env
                return CommandResult(0, "", "")

        runner = RecordingRunner()

        runner.start_emulator(visible=True)

        self.assertEqual(runner.extra_env, {"EMULATOR_LAUNCH_MODE": "terminal"})

    def test_device_ping_check_uses_direct_adb_command_exit_code(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        class RecordingRunner(ConsoleRunner):
            def __init__(self):
                super().__init__("/tmp", allow_non_retained=True)
                self.adb_args = []

            def adb(self, args, *, timeout=20):
                self.adb_args.append(args)
                return CommandResult(0, "64 bytes from 8.8.8.8", "")

        runner = RecordingRunner()

        check = runner._device_ping_check("emulator_ip", "8.8.8.8", required=True)

        self.assertTrue(check["ok"])
        self.assertEqual(runner.adb_args, [["shell", "ping", "-c", "1", "-W", "3", "8.8.8.8"]])

    def test_device_ping_check_retries_transient_cold_boot_failure(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        class ColdBootRunner(ConsoleRunner):
            def __init__(self):
                super().__init__("/tmp", allow_non_retained=True)
                self.attempts = 0

            def adb(self, args, *, timeout=20):
                self.attempts += 1
                if self.attempts == 1:
                    return CommandResult(1, "", "network is unreachable")
                return CommandResult(0, "64 bytes from 8.8.8.8", "")

        runner = ColdBootRunner()

        with patch("capture_console.runner.time.sleep"):
            check = runner._device_ping_check("emulator_ip", "8.8.8.8", required=True)

        self.assertTrue(check["ok"])
        self.assertEqual(runner.attempts, 2)

    def test_prepare_frida_reuses_running_root_server_and_repairs_forward(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        class ExistingFridaRunner(ConsoleRunner):
            def __init__(self):
                super().__init__(
                    "/tmp",
                    adb_serial="emulator-5564",
                    avd_name="AI_Capture_Clean_QA3_20260810",
                    frida_port=27242,
                    allow_non_retained=True,
                )
                self.adb_calls = []
                self.start_script_called = False
                self.forward_ready = False

            def emulator_status(self):
                return {"adb_online": True}

            def adb(self, args, *, timeout=20):
                self.adb_calls.append(args)
                if args[:3] == ["shell", "pidof", "frida-server"]:
                    return CommandResult(0, "9622\n", "")
                if args[:3] == ["shell", "ps", "-A"]:
                    return CommandResult(0, "root 9622 1 frida-server\n", "")
                if args == ["forward", "tcp:27242", "tcp:27042"]:
                    self.forward_ready = True
                    return CommandResult(0, "", "")
                return CommandResult(0, "", "")

            def run(self, args, *, timeout=30, env=None, input_text=None):
                if args and str(args[0]).endswith("start_frida_server.sh"):
                    self.start_script_called = True
                    return CommandResult(1, "", "adb root is unavailable")
                if args[-2:] == ["forward", "--list"]:
                    line = "emulator-5564 tcp:27242 tcp:27042\n" if self.forward_ready else ""
                    return CommandResult(0, line, "")
                if args[:2] == ["frida-ps", "-H"]:
                    return CommandResult(0, " PID  Name\n----  ----\n9622  frida-server\n", "")
                return CommandResult(0, "", "")

        runner = ExistingFridaRunner()

        result = runner.prepare_frida_server()

        self.assertTrue(result["ok"])
        self.assertTrue(result["reused"])
        self.assertFalse(runner.start_script_called)
        self.assertIn(["forward", "tcp:27242", "tcp:27042"], runner.adb_calls)

    def test_prepare_frida_bootstraps_isolated_ramdisk_and_restarts_target_avd(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        class BootstrapRunner(ConsoleRunner):
            def __init__(self):
                super().__init__(
                    "/tmp",
                    adb_serial="emulator-5564",
                    avd_name="AI_Capture_Clean_QA3_20260810",
                    frida_port=27542,
                    allow_non_retained=True,
                )
                self.bootstrap_called = False
                self.stopped = False
                self.started = False
                self.post_boot_start_called = False

            def emulator_status(self):
                return {
                    "adb_online": not self.stopped or self.started,
                    "process_running": not self.stopped or self.started,
                    "boot_completed": self.started,
                    "unlocked": self.started,
                }

            def adb(self, args, *, timeout=20):
                if args[:3] == ["shell", "pidof", "frida-server"]:
                    return CommandResult(0, "1850\n", "")
                return CommandResult(0, "", "")

            def frida_server_status(self, *, device_ok):
                if self.post_boot_start_called:
                    return True, "frida-ps reachable after isolated ramdisk restart"
                return False, "unable to load libart.so: libstatspull.so not found"

            def run(self, args, *, timeout=30, env=None, input_text=None):
                if args and str(args[0]).endswith("prepare_frida_avd.sh"):
                    self.bootstrap_called = True
                    return CommandResult(0, "prepared isolated ramdisk", "")
                if args and str(args[0]).endswith("start_frida_server.sh"):
                    self.post_boot_start_called = self.started
                    return CommandResult(0, "started Frida through Magisk root shell", "")
                return CommandResult(0, "", "")

            def stop_emulator(self):
                self.stopped = True
                return CommandResult(0, "stopped", "")

            def start_emulator(self, *, visible=False):
                self.started = True
                return CommandResult(0, "started", "")

        runner = BootstrapRunner()

        with patch("capture_console.runner.time.sleep"):
            result = runner.prepare_frida_server()

        self.assertTrue(result["ok"])
        self.assertTrue(result["bootstrapped"])
        self.assertTrue(runner.bootstrap_called)
        self.assertTrue(runner.stopped)
        self.assertTrue(runner.started)
        self.assertTrue(runner.post_boot_start_called)
        self.assertIn("started Frida through Magisk root shell", result["stdout"])

    def test_start_lab_emulator_supports_background_launch_mode(self):
        script = Path("scripts/start_lab_emulator.sh").read_text(encoding="utf-8")

        self.assertIn("EMULATOR_LAUNCH_MODE", script)
        self.assertIn("emulator_supports_arg", script)
        self.assertIn("maybe_add_emulator_arg", script)
        self.assertIn("maybe_add_emulator_arg -crash-report-mode never", script)
        self.assertIn('nohup "$LAUNCHER_FILE"', script)
        self.assertIn('"$EMULATOR_LAUNCH_MODE" == "terminal"', script)

    def test_store_recreates_missing_database_parent_before_connecting(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            db_dir = Path(tmp) / "runtime"
            store = CaptureStore(db_dir / "console.db")
            for path in db_dir.iterdir():
                path.unlink()
            db_dir.rmdir()

            state = store.get_system_state()

            self.assertEqual(state["state"], "running")
            self.assertTrue(db_dir.is_dir())

    def test_store_connect_closes_sqlite_connection_after_context(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
            with store.connect() as conn:
                conn.execute("SELECT 1")

            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")

    def test_preview_url_uses_configured_public_url_and_token(self):
        from capture_console.preview import preview_url

        url = preview_url(
            "http://192.168.77.150:19097/view?theme=light",
            "secret-token",
            device_id="device-1",
            adb_serial="emulator-5554",
        )

        self.assertEqual(
            url,
            "http://192.168.77.150:19097/view?theme=light&token=secret-token&device_id=device-1&serial=emulator-5554",
        )

    def test_preview_token_can_be_read_from_existing_preview_env_file(self):
        from capture_console.preview import preview_token

        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("PREVIEW_TOKEN=preview-secret\n", encoding="utf-8")

            token = preview_token({"EMULATOR_PREVIEW_ENV_FILE": str(env_file)}, home=Path(tmp))

            self.assertEqual(token, "preview-secret")

    def test_runner_accepts_saved_activity_when_launcher_resolution_fails(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        class SavedActivityRunner(ConsoleRunner):
            def run(self, args, *, timeout=30, env=None):
                if args and args[0] == "lsof":
                    return CommandResult(1, "", "")
                if args and args[-1] == "devices":
                    return CommandResult(0, "emulator-5554\tdevice\n", "")
                return CommandResult(0, "", "")

            def adb(self, args, *, timeout=20):
                if args[:3] == ["shell", "dumpsys", "account"]:
                    return CommandResult(0, "Account {name=user@example.com, type=com.google}\n", "")
                if args[:2] == ["shell", "dumpsys"]:
                    return CommandResult(0, "RUNNING_UNLOCKED", "")
                if args[:3] == ["shell", "pm", "path"]:
                    return CommandResult(0, "package:/data/app/example/base.apk\n", "")
                return CommandResult(0, "", "")

            def resolve_activity(self, package_name):
                return ""

        runner = SavedActivityRunner("/tmp")

        health = runner.health_check(
            package_name="com.example.app",
            mode="system",
            activity="com.example.app/.MainActivity",
        )

        self.assertTrue(health["ok"])
        self.assertEqual(health["resolved_activity"], "com.example.app/.MainActivity")

    def test_runner_launches_saved_activity_on_retained_emulator(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        class LaunchRunner(ConsoleRunner):
            def __init__(self, root_dir):
                super().__init__(root_dir)
                self.adb_calls = []

            def run(self, args, *, timeout=30, env=None):
                if args and args[0] == "lsof":
                    return CommandResult(1, "", "")
                if args and args[-1] == "devices":
                    return CommandResult(0, "emulator-5554\tdevice\n", "")
                return CommandResult(0, "", "")

            def adb(self, args, *, timeout=20):
                self.adb_calls.append(args)
                if args[:3] == ["shell", "dumpsys", "account"]:
                    return CommandResult(0, "Account {name=user@example.com, type=com.google}\n", "")
                if args[:2] == ["shell", "dumpsys"]:
                    return CommandResult(0, "RUNNING_UNLOCKED", "")
                if args[:3] == ["shell", "pm", "path"]:
                    return CommandResult(0, "package:/data/app/example/base.apk\n", "")
                if args[:3] == ["shell", "am", "start"]:
                    return CommandResult(0, "Starting: Intent\n", "")
                return CommandResult(0, "", "")

        runner = LaunchRunner("/tmp")

        result = runner.launch_app(
            package_name="com.meta.inno.monopoly_sticker",
            activity="com.meta.inno.monopoly_sticker/.MainActivity",
        )

        self.assertTrue(result.ok)
        self.assertIn(
            ["shell", "am", "start", "-W", "-n", "com.meta.inno.monopoly_sticker/.MainActivity"],
            runner.adb_calls,
        )

    def test_runner_checks_frida_by_reachable_forwarded_server_not_init_property(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        class FridaRunner(ConsoleRunner):
            def run(self, args, *, timeout=30, env=None):
                command = " ".join(args)
                if args and args[0] == "lsof":
                    return CommandResult(1, "", "")
                if args and args[-1] == "devices":
                    return CommandResult(0, "emulator-5554\tdevice\n", "")
                if "forward --list" in command:
                    return CommandResult(0, "emulator-5554 tcp:27042 tcp:27042\n", "")
                if args[:2] == ["frida-ps", "-H"]:
                    return CommandResult(0, " PID  Name\n----  ----\n1234  Example\n", "")
                return CommandResult(0, "", "")

            def adb(self, args, *, timeout=20):
                if args[:3] == ["shell", "dumpsys", "account"]:
                    return CommandResult(0, "Account {name=user@example.com, type=com.google}\n", "")
                if args[:2] == ["shell", "dumpsys"]:
                    return CommandResult(0, "RUNNING_UNLOCKED", "")
                if args[:3] == ["shell", "pm", "path"]:
                    return CommandResult(0, "package:/data/app/example/base.apk\n", "")
                if args[:2] == ["shell", "pidof"]:
                    return CommandResult(0, "1234\n", "")
                return CommandResult(0, "", "")

        runner = FridaRunner("/tmp")

        health = runner.health_check(
            package_name="com.example.app",
            mode="flutter-socks",
            activity="com.example.app/.MainActivity",
        )

        self.assertTrue(health["ok"])
        frida_check = next(check for check in health["checks"] if check["name"] == "frida_server")
        self.assertIn("frida-ps reachable", frida_check["detail"])

    def test_runner_reports_google_state_when_play_store_and_google_account_exist(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        class GoogleReadyRunner(ConsoleRunner):
            def adb(self, args, *, timeout=20):
                if args[:3] == ["shell", "pm", "path"]:
                    return CommandResult(0, "package:/system/priv-app/Phonesky/Phonesky.apk\n", "")
                if args[:3] == ["shell", "dumpsys", "account"]:
                    return CommandResult(0, "Account {name=user@example.com, type=com.google}\n", "")
                return CommandResult(0, "", "")

        state = GoogleReadyRunner("/tmp").google_state()

        self.assertTrue(state["ok"])
        self.assertTrue(state["play_store_installed"])
        self.assertTrue(state["google_account_present"])
        self.assertEqual(state["state"], "ok")

    def test_runner_reports_missing_google_login_when_account_is_absent(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        class NoGoogleAccountRunner(ConsoleRunner):
            def adb(self, args, *, timeout=20):
                if args[:3] == ["shell", "pm", "path"]:
                    return CommandResult(0, "package:/system/priv-app/Phonesky/Phonesky.apk\n", "")
                if args[:3] == ["shell", "dumpsys", "account"]:
                    return CommandResult(0, "Accounts: 0\n", "")
                if args[:4] == ["shell", "cmd", "account", "list"]:
                    return CommandResult(0, "No accounts\n", "")
                return CommandResult(0, "", "")

        state = NoGoogleAccountRunner("/tmp").google_state()

        self.assertFalse(state["ok"])
        self.assertTrue(state["play_store_installed"])
        self.assertFalse(state["google_account_present"])
        self.assertEqual(state["state"], "not_logged_in")
        self.assertIn("登录 Google", state["user_message"])

    def test_runner_reports_missing_google_play_image_when_play_store_is_absent(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        class NoPlayStoreRunner(ConsoleRunner):
            def adb(self, args, *, timeout=20):
                if args[:3] == ["shell", "pm", "path"]:
                    return CommandResult(1, "", "Error: package not found")
                return CommandResult(0, "", "")

        state = NoPlayStoreRunner("/tmp").google_state()

        self.assertFalse(state["ok"])
        self.assertFalse(state["play_store_installed"])
        self.assertEqual(state["state"], "missing_play_store")
        self.assertIn("Google Play AVD", state["fix"])

    def test_open_google_login_prepares_gboard_for_credential_input(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        class GoogleLoginRunner(ConsoleRunner):
            def __init__(self, root_dir):
                super().__init__(root_dir)
                self.commands = []

            def google_state(self, *, device_ok=True):
                return {
                    "ok": False,
                    "state": "not_logged_in",
                    "play_store_installed": False,
                    "google_account_present": False,
                }

            def adb(self, args, *, timeout=20):
                self.commands.append(args)
                return CommandResult(0, "ok", "")

        runner = GoogleLoginRunner("/tmp")

        result = runner.open_google_login()

        self.assertTrue(result["ok"])
        self.assertTrue(result["keyboard"]["ok"])
        self.assertEqual(
            runner.commands,
            [
                ["shell", "settings", "put", "secure", "show_ime_with_hard_keyboard", "1"],
                ["shell", "ime", "enable", "com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME"],
                ["shell", "ime", "set", "com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME"],
                ["shell", "am", "force-stop", "com.google.android.inputmethod.latin"],
                ["shell", "am", "start", "-a", "android.settings.ADD_ACCOUNT_SETTINGS"],
            ],
        )

    def test_runner_prefers_google_play_system_image_for_default_avd_creation(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        with tempfile.TemporaryDirectory() as tmp:
            sdk_root = Path(tmp)
            self.make_system_image(sdk_root, api="android-36", tag="google_apis", abi="arm64-v8a")
            self.make_system_image(sdk_root, api="android-35", tag="google_apis_playstore", abi="arm64-v8a")

            class CreateAvdRunner(ConsoleRunner):
                def __init__(self, root_dir):
                    super().__init__(root_dir, avd_name="AI_Capture_AVD_01")
                    self.sdk_root = sdk_root
                    self.avd_home = sdk_root / "avd"
                    self.created = False
                    self.created_package = ""
                    self.created_device = ""

                def avd_status(self):
                    return {"ok": self.created, "avd_name": self.avd_name, "available_avds": [self.avd_name] if self.created else []}

                def host_resource_status(self):
                    return {
                        "memory_mb": 32768,
                        "cpu_count": 10,
                        "system": "Darwin",
                        "machine": "arm64",
                    }

                def run(self, args, *, timeout=30, env=None, input_text=None):
                    if args[:3] == ["avdmanager", "create", "avd"]:
                        self.created_package = args[args.index("--package") + 1]
                        self.created_device = args[args.index("--device") + 1]
                        avd_dir = self.avd_home / f"{self.avd_name}.avd"
                        avd_dir.mkdir(parents=True)
                        (avd_dir / "config.ini").write_text(
                            "PlayStore.enabled = no\n"
                            "avd.id = <build>\n"
                            "avd.name = <build>\n"
                            "disk.dataPartition.path = <temp>\n"
                            "hw.device.name = medium_phone\n"
                            "image.sysdir.1 = system-images/android-35/google_apis_playstore/arm64-v8a/\n",
                            encoding="utf-8",
                        )
                        (self.avd_home / f"{self.avd_name}.ini").write_text(
                            f"path={avd_dir}\ntarget=android-0\n",
                            encoding="utf-8",
                        )
                        self.created = True
                        return CommandResult(0, "created", "")
                    return CommandResult(0, "", "")

            runner = CreateAvdRunner("/tmp")
            result = runner.create_avd_if_possible()

            self.assertTrue(result["ok"])
            self.assertEqual(runner.created_package, "system-images;android-35;google_apis_playstore;arm64-v8a")
            self.assertEqual(runner.created_device, "medium_phone")
            config = (runner.avd_home / "AI_Capture_AVD_01.avd" / "config.ini").read_text(encoding="utf-8")
            metadata = (runner.avd_home / "AI_Capture_AVD_01.ini").read_text(encoding="utf-8")
            self.assertIn("PlayStore.enabled=true", config)
            self.assertIn("AvdId=AI_Capture_AVD_01", config)
            self.assertIn("target=android-35", config)
            self.assertIn("disk.dataPartition.size=8G", config)
            self.assertIn("hw.cpu.ncore=4", config)
            self.assertIn("hw.gpu.mode=host", config)
            self.assertIn("hw.ramSize=4096", config)
            self.assertIn("vm.heapSize=512", config)
            self.assertNotIn("disk.dataPartition.path", config)
            self.assertIn("target=android-35", metadata)

    def test_runner_selects_high_performance_avd_profile_for_capable_mac(self):
        from capture_console.runner import ConsoleRunner

        class HighPerformanceHostRunner(ConsoleRunner):
            def host_resource_status(self):
                return {
                    "memory_mb": 32768,
                    "cpu_count": 10,
                    "system": "Darwin",
                    "machine": "arm64",
                }

        profile = HighPerformanceHostRunner("/tmp").recommended_avd_performance_profile()

        self.assertEqual(
            profile,
            {
                "tier": "high",
                "ram_mb": 4096,
                "cpu_cores": 4,
                "gpu_mode": "host",
                "data_partition_size": "8G",
                "vm_heap_mb": 512,
            },
        )

    def test_google_play_image_selection_ignores_non_native_host_abi(self):
        from capture_console.runner import ConsoleRunner

        class MixedArchitectureRunner(ConsoleRunner):
            def available_system_images(self):
                return [
                    {
                        "package": "system-images;android-37;google_apis_playstore;x86_64",
                        "tag": "google_apis_playstore",
                        "abi": "x86_64",
                        "score": 3700,
                    },
                    {
                        "package": "system-images;android-36.1;google_apis_playstore;arm64-v8a",
                        "tag": "google_apis_playstore",
                        "abi": "arm64-v8a",
                        "score": 3600,
                    },
                ]

        with patch("capture_console.runner.platform.machine", return_value="arm64"):
            status = MixedArchitectureRunner("/tmp").google_play_image_status()

        self.assertTrue(status["ok"])
        self.assertEqual(status["selected"]["abi"], "arm64-v8a")
        self.assertEqual(len(status["google_play_images"]), 1)

    def test_runner_rejects_non_google_play_avd_before_performance_rewrite(self):
        from capture_console.runner import ConsoleRunner

        with tempfile.TemporaryDirectory() as tmp:
            avd_home = Path(tmp) / "avd"
            avd_dir = avd_home / "AI_Capture_AVD_01.avd"
            avd_dir.mkdir(parents=True)
            config_path = avd_dir / "config.ini"
            original_config = (
                "PlayStore.enabled=no\n"
                "abi.type=arm64-v8a\n"
                "image.sysdir.1=system-images/android-36.1/google_apis/arm64-v8a/\n"
                "hw.ramSize=2048\n"
            )
            config_path.write_text(original_config, encoding="utf-8")
            (avd_home / "AI_Capture_AVD_01.ini").write_text(
                f"path={avd_dir}\ntarget=android-36.1\n",
                encoding="utf-8",
            )

            class IncompatibleAvdRunner(ConsoleRunner):
                def avd_status(self):
                    return {"ok": True, "avd_name": self.avd_name, "available_avds": [self.avd_name]}

                def emulator_status(self):
                    return {"process_running": False, "adb_online": False}

                def emulator_acceleration_status(self):
                    return {"ok": True, "detail": "Hypervisor.Framework is installed and usable."}

            runner = IncompatibleAvdRunner("/tmp", avd_name="AI_Capture_AVD_01", allow_non_retained=True)
            runner.avd_home = avd_home

            result = runner.prepare_avd_for_launch()

            self.assertFalse(result["ok"])
            self.assertIn("Google Play", result["user_message"])
            self.assertEqual(config_path.read_text(encoding="utf-8"), original_config)

    def test_runner_installs_missing_google_play_image_before_creating_performance_avd(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        with tempfile.TemporaryDirectory() as tmp:
            avd_home = Path(tmp) / "avd"

            class BootstrapAvdRunner(ConsoleRunner):
                def __init__(self):
                    super().__init__("/tmp", avd_name="AI_Capture_AVD_01", allow_non_retained=True)
                    self.avd_home = avd_home
                    self.image_installed = False
                    self.avd_exists = False
                    self.calls = []

                def avd_status(self):
                    return {"ok": self.avd_exists, "avd_name": self.avd_name, "available_avds": []}

                def create_avd_if_possible(self):
                    self.calls.append("create_avd")
                    if not self.image_installed:
                        return {
                            "ok": False,
                            "user_message": "缺少 Google Play system image。",
                            "fix": "install image",
                        }
                    avd_dir = self.avd_home / f"{self.avd_name}.avd"
                    avd_dir.mkdir(parents=True)
                    (avd_dir / "config.ini").write_text(
                        "PlayStore.enabled=true\n"
                        "abi.type=arm64-v8a\n"
                        "image.sysdir.1=system-images/android-36.1/google_apis_playstore/arm64-v8a/\n",
                        encoding="utf-8",
                    )
                    (self.avd_home / f"{self.avd_name}.ini").write_text(
                        f"path={avd_dir}\ntarget=android-36.1\n",
                        encoding="utf-8",
                    )
                    self.avd_exists = True
                    return {"ok": True, "created": True}

                def install_google_play_system_image(self):
                    self.calls.append("install_image")
                    self.image_installed = True
                    return {"ok": True, "installed": True}

                def emulator_acceleration_status(self):
                    return {"ok": True, "detail": "Hypervisor.Framework is installed and usable."}

                def emulator_status(self):
                    return {"process_running": False, "adb_online": False}

                def host_resource_status(self):
                    return {
                        "memory_mb": 32768,
                        "cpu_count": 10,
                        "system": "Darwin",
                        "machine": "arm64",
                    }

            runner = BootstrapAvdRunner()

            result = runner.prepare_avd_for_launch()

            self.assertTrue(result["ok"])
            self.assertEqual(runner.calls, ["create_avd", "install_image", "create_avd"])
            self.assertEqual(result["profile"]["tier"], "high")

    def test_runner_refuses_default_avd_creation_without_google_play_system_image(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        with tempfile.TemporaryDirectory() as tmp:
            sdk_root = Path(tmp)
            self.make_system_image(sdk_root, api="android-36", tag="google_apis", abi="arm64-v8a")

            class CreateAvdRunner(ConsoleRunner):
                def __init__(self, root_dir):
                    super().__init__(root_dir, avd_name="AI_Capture_AVD_01")
                    self.sdk_root = sdk_root
                    self.create_attempted = False

                def avd_status(self):
                    return {"ok": False, "avd_name": self.avd_name, "available_avds": []}

                def run(self, args, *, timeout=30, env=None, input_text=None):
                    if args[:3] == ["avdmanager", "create", "avd"]:
                        self.create_attempted = True
                    return CommandResult(0, "", "")

            runner = CreateAvdRunner("/tmp")
            result = runner.create_avd_if_possible()

            self.assertFalse(result["ok"])
            self.assertFalse(runner.create_attempted)
            self.assertIn("Google Play", result["user_message"])
            self.assertIn("google_apis_playstore", result["fix"])

    def test_runner_sorts_google_play_android_minor_versions_by_major_api_level(self):
        from capture_console.runner import ConsoleRunner

        with tempfile.TemporaryDirectory() as tmp:
            sdk_root = Path(tmp)
            self.make_system_image(sdk_root, api="android-35", tag="google_apis_playstore", abi="arm64-v8a")
            self.make_system_image(sdk_root, api="android-36.1", tag="google_apis_playstore", abi="arm64-v8a")

            runner = ConsoleRunner("/tmp", avd_name="AI_Capture_AVD_01")
            runner.sdk_root = sdk_root

            status = runner.google_play_image_status()

            self.assertTrue(status["ok"])
            self.assertEqual(status["selected"]["package"], "system-images;android-36.1;google_apis_playstore;arm64-v8a")
            self.assertEqual(status["selected"]["api_level"], 36)

    def test_runner_detects_google_account_before_long_dumpsys_tail_and_redacts_detail(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        class LongAccountRunner(ConsoleRunner):
            def adb(self, args, *, timeout=20):
                if args[:3] == ["shell", "pm", "path"]:
                    return CommandResult(0, "package:/system/priv-app/Phonesky/Phonesky.apk\n", "")
                if args[:3] == ["shell", "dumpsys", "account"]:
                    return CommandResult(
                        0,
                        "Account {name=real-user@example.com, type=com.google}\n" + ("visibility tail\n" * 400),
                        "",
                    )
                return CommandResult(0, "", "")

        state = LongAccountRunner("/tmp").google_state()

        self.assertTrue(state["ok"])
        self.assertTrue(state["google_account_present"])
        self.assertNotIn("real-user@example.com", state["detail"])
        self.assertIn("[redacted-email]", state["detail"])

    def test_health_check_includes_google_login_requirement(self):
        from capture_console import runner as runner_module
        from capture_console.runner import CommandResult, ConsoleRunner

        class MissingGoogleRunner(ConsoleRunner):
            def run(self, args, *, timeout=30, env=None):
                if args and args[0] == "lsof":
                    return CommandResult(1, "", "")
                if args and args[-1] == "devices":
                    return CommandResult(0, "emulator-5554\tdevice\n", "")
                return CommandResult(0, "", "")

            def adb(self, args, *, timeout=20):
                if args[:3] == ["shell", "dumpsys", "user"]:
                    return CommandResult(0, "RUNNING_UNLOCKED", "")
                if args[:3] == ["shell", "pm", "path"] and args[-1] == "com.example.app":
                    return CommandResult(0, "package:/data/app/example/base.apk\n", "")
                if args[:3] == ["shell", "pm", "path"] and args[-1] == "com.android.vending":
                    return CommandResult(1, "", "Error: package not found")
                return CommandResult(0, "", "")

        original_google_required = runner_module.GOOGLE_LOGIN_REQUIRED
        try:
            runner_module.GOOGLE_LOGIN_REQUIRED = True
            health = MissingGoogleRunner("/tmp").health_check(
                package_name="com.example.app",
                mode="system",
                activity="com.example.app/.MainActivity",
            )
        finally:
            runner_module.GOOGLE_LOGIN_REQUIRED = original_google_required

        self.assertFalse(health["ok"])
        google = next(check for check in health["checks"] if check["name"] == "google_login")
        self.assertFalse(google["ok"])
        self.assertIn("Google Play", google["user_message"])

    def test_health_check_allows_missing_google_account_when_login_is_optional(self):
        from capture_console import runner as runner_module
        from capture_console.runner import CommandResult, ConsoleRunner

        class OptionalGoogleRunner(ConsoleRunner):
            def run(self, args, *, timeout=30, env=None):
                if args and args[0] == "lsof":
                    return CommandResult(1, "", "")
                if args and args[-1] == "devices":
                    return CommandResult(0, "emulator-5554\tdevice\n", "")
                return CommandResult(0, "", "")

            def adb(self, args, *, timeout=20):
                if args[:3] == ["shell", "dumpsys", "user"]:
                    return CommandResult(0, "RUNNING_UNLOCKED", "")
                if args[:3] == ["shell", "pm", "path"] and args[-1] == "com.example.app":
                    return CommandResult(0, "package:/data/app/example/base.apk\n", "")
                if args[:3] == ["shell", "pm", "path"] and args[-1] == "com.android.vending":
                    return CommandResult(0, "package:/system/priv-app/Phonesky/Phonesky.apk\n", "")
                if args[:3] == ["shell", "dumpsys", "account"]:
                    return CommandResult(0, "Accounts: 0\n", "")
                return CommandResult(0, "", "")

        original_google_required = runner_module.GOOGLE_LOGIN_REQUIRED
        try:
            runner_module.GOOGLE_LOGIN_REQUIRED = False
            health = OptionalGoogleRunner("/tmp").health_check(
                package_name="com.example.app",
                mode="system",
                activity="com.example.app/.MainActivity",
            )
        finally:
            runner_module.GOOGLE_LOGIN_REQUIRED = original_google_required

        self.assertTrue(health["ok"])
        google = next(check for check in health["checks"] if check["name"] == "google_login")
        self.assertTrue(google["ok"])

    def test_health_check_requires_play_store_when_google_login_is_optional(self):
        from capture_console import runner as runner_module
        from capture_console.runner import CommandResult, ConsoleRunner

        class MissingPlayStoreRunner(ConsoleRunner):
            def run(self, args, *, timeout=30, env=None):
                if args and args[0] == "lsof":
                    return CommandResult(1, "", "")
                if args and args[-1] == "devices":
                    return CommandResult(0, "emulator-5554\tdevice\n", "")
                return CommandResult(0, "", "")

            def adb(self, args, *, timeout=20):
                if args[:3] == ["shell", "dumpsys", "user"]:
                    return CommandResult(0, "RUNNING_UNLOCKED", "")
                if args[:3] == ["shell", "pm", "path"] and args[-1] == "com.example.app":
                    return CommandResult(0, "package:/data/app/example/base.apk\n", "")
                if args[:3] == ["shell", "pm", "path"] and args[-1] == "com.android.vending":
                    return CommandResult(1, "", "Error: package not found")
                return CommandResult(0, "", "")

        original_google_required = runner_module.GOOGLE_LOGIN_REQUIRED
        try:
            runner_module.GOOGLE_LOGIN_REQUIRED = False
            health = MissingPlayStoreRunner("/tmp").health_check(
                package_name="com.example.app",
                mode="system",
                activity="com.example.app/.MainActivity",
            )
        finally:
            runner_module.GOOGLE_LOGIN_REQUIRED = original_google_required

        self.assertFalse(health["ok"])
        google = next(check for check in health["checks"] if check["name"] == "google_login")
        self.assertFalse(google["ok"])
        self.assertIn("Google Play", google["user_message"])

    def test_store_enforces_single_active_capture(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
            self.add_test_device(store)
            app = store.create_app(
                name="MelodyCraft",
                package_name="com.meta.inno.monopoly_sticker",
                activity="com.meta.inno.monopoly_sticker/.MainActivity",
                default_mode="flutter-socks",
                notes="logged in",
            )

            first = store.create_session(
                app_id=app["id"],
                mode="flutter-socks",
                outdir="/tmp/capture-one",
                status="running",
            )
            self.assertEqual(first["status"], "running")

            with self.assertRaises(ValueError):
                store.create_session(
                    app_id=app["id"],
                    mode="flutter-socks",
                    outdir="/tmp/capture-two",
                    status="running",
                )

            store.update_session_status(first["id"], "stopped")
            second = store.create_session(
                app_id=app["id"],
                mode="flutter-socks",
                outdir="/tmp/capture-two",
                status="running",
            )
            self.assertEqual(second["outdir"], "/tmp/capture-two")

    def test_store_allows_auto_default_mode_and_records_last_success_mode(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
            self.add_test_device(store)
            app = store.create_app(
                name="Generic App",
                package_name="com.example.generic",
                default_mode="auto",
            )

            self.assertEqual(app["default_mode"], "auto")
            self.assertEqual(app["last_success_mode"], "")

            store.mark_app_success(app["id"], mode="flutter-socks")
            updated = store.get_app(app["id"])

            self.assertEqual(updated["last_success_mode"], "flutter-socks")
            self.assertIsNotNone(updated["last_success_at"])

    def test_store_promotes_starting_session_to_running_without_unique_conflict(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
            self.add_test_device(store)
            app = store.create_app(
                name="MelodyCraft",
                package_name="com.meta.inno.monopoly_sticker",
                activity="com.meta.inno.monopoly_sticker/.MainActivity",
                default_mode="flutter-socks",
            )

            session = store.create_session(
                app_id=app["id"],
                mode="flutter-socks",
                outdir="/tmp/capture-starting",
                status="starting",
            )

            running = store.update_session_status(session["id"], "running")

            self.assertEqual(running["status"], "running")
            self.assertEqual(store.active_session("device-1")["id"], session["id"])

    def test_store_enforces_single_active_capture_at_database_level(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "console.db"
            store = CaptureStore(db_path)
            self.add_test_device(store)
            app = store.create_app(
                name="MelodyCraft",
                package_name="com.meta.inno.monopoly_sticker",
                default_mode="flutter-socks",
            )
            first = store.create_session(
                app_id=app["id"],
                mode="flutter-socks",
                outdir="/tmp/capture-one",
                status="running",
            )

            with sqlite3.connect(db_path) as conn:
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        """
                        INSERT INTO capture_sessions (
                            platform, device_id, device_name, avd_name, adb_serial, proxy_port, web_port, frida_port,
                            app_id, app_name, package_name, mode, outdir, status, web_url, error,
                            started_at, created_at, updated_at
                        )
                        SELECT
                            platform, device_id, device_name, avd_name, adb_serial, proxy_port, web_port, frida_port,
                            app_id, app_name, package_name, mode, ?, status, web_url, error,
                            started_at, created_at, updated_at
                        FROM capture_sessions
                        WHERE id=?
                        """,
                        ("/tmp/capture-racy-duplicate", first["id"]),
                    )

    def test_store_locks_active_sessions_per_discovered_device(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
            self.add_test_device(store, device_id="device-1", adb_serial="emulator-5554", proxy_port=9090, web_port=9091, frida_port=27042, resident=1, idle_release_minutes=0)
            self.add_test_device(store, device_id="device-2", adb_serial="emulator-5556", proxy_port=9100, web_port=9101, frida_port=27142, resident=0, idle_release_minutes=10)
            app = store.create_app(
                name="PokeHub",
                package_name="com.mi.poketrade",
                default_mode="flutter-socks",
            )

            devices = store.list_devices()
            self.assertEqual(len(devices), 2)
            self.assertEqual(devices[0]["device_id"], "device-1")
            self.assertEqual(devices[0]["adb_serial"], "emulator-5554")
            self.assertEqual(devices[0]["proxy_port"], 9090)
            self.assertEqual(devices[0]["resident"], 1)
            self.assertEqual(devices[0]["idle_release_minutes"], 0)
            self.assertEqual(devices[1]["device_id"], "device-2")
            self.assertEqual(devices[1]["resident"], 0)
            self.assertEqual(devices[1]["idle_release_minutes"], 10)

            first = store.create_session(
                app_id=app["id"],
                device_id="device-1",
                mode="flutter-socks",
                outdir="/tmp/device-one",
                status="running",
            )
            second = store.create_session(
                app_id=app["id"],
                device_id="device-2",
                mode="flutter-socks",
                outdir="/tmp/device-two",
                status="running",
            )

            self.assertEqual(first["device_id"], "device-1")
            self.assertEqual(first["proxy_port"], 9090)
            self.assertEqual(second["device_id"], "device-2")
            self.assertEqual(second["proxy_port"], 9100)
            with self.assertRaises(ValueError):
                store.create_session(
                    app_id=app["id"],
                    device_id="device-1",
                    mode="flutter-socks",
                    outdir="/tmp/device-one-again",
                    status="running",
                )

    def test_store_can_seed_device_pool_from_config_file(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "devices.json"
            config.write_text(
                json.dumps({
                    "devices": [
                        {
                            "device_id": "device-1",
                            "name": "Mac mini 设备 1",
                            "avd_name": "Capture_AVD_01",
                            "adb_serial": "emulator-5554",
                            "proxy_port": 9090,
                            "web_port": 9091,
                            "frida_port": 27042,
                            "enabled": 1,
                            "resident": 1,
                            "idle_release_minutes": 0,
                        }
                    ]
                }),
                encoding="utf-8",
            )
            store = CaptureStore(Path(tmp) / "console.db", devices_config_path=config)

            devices = store.list_devices()

            self.assertEqual(devices[0]["name"], "Mac mini 设备 1")
            self.assertEqual(devices[0]["avd_name"], "Capture_AVD_01")

    def test_store_persists_device_specific_app_state(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
            self.add_test_device(store, device_id="device-2", adb_serial="emulator-5556", proxy_port=9100, web_port=9101, frida_port=27142, resident=0, idle_release_minutes=10)
            app = store.create_app(
                name="PokeHub",
                package_name="com.mi.poketrade",
                default_mode="flutter-socks",
            )

            state = store.update_device_app_version(
                "device-2",
                app["id"],
                {
                    "package_name": "com.mi.poketrade",
                    "version_name": "1.12.5",
                    "version_code": "66",
                    "last_update_time": "2026-05-18 19:10:00",
                    "installer_package": "null",
                    "signature_hint": "d5515cda",
                    "activity": "com.mi.poketrade/.MainActivity",
                },
            )

            self.assertEqual(state["device_id"], "device-2")
            self.assertEqual(state["app_id"], app["id"])
            self.assertEqual(state["version_code"], "66")
            self.assertEqual(store.get_device_app_state("device-2", app["id"])["version_name"], "1.12.5")

    def test_store_clears_stopped_at_when_session_is_reopened(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
            self.add_test_device(store)
            app = store.create_app(
                name="MelodyCraft",
                package_name="com.meta.inno.monopoly_sticker",
                activity="com.meta.inno.monopoly_sticker/.MainActivity",
                default_mode="flutter-socks",
            )
            session = store.create_session(
                app_id=app["id"],
                mode="flutter-socks",
                outdir="/tmp/capture-one",
                status="running",
            )

            stopped = store.update_session_status(session["id"], "stopped")
            self.assertIsNotNone(stopped["stopped_at"])

            reopened = store.update_session_status(session["id"], "running")
            self.assertIsNone(reopened["stopped_at"])

    def test_store_clears_capture_records_without_deleting_apps(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
            self.add_test_device(store)
            app = store.create_app(
                name="MelodyCraft",
                package_name="com.meta.inno.monopoly_sticker",
                activity="com.meta.inno.monopoly_sticker/.MainActivity",
                default_mode="flutter-socks",
            )
            store.create_session(
                app_id=app["id"],
                mode="flutter-socks",
                outdir="/tmp/current-project-capture",
                status="stopped",
            )

            store.clear_capture_sessions()

            self.assertEqual(store.list_sessions(), [])
            self.assertEqual(store.list_apps()[0]["package_name"], "com.meta.inno.monopoly_sticker")

    def test_store_persists_android_version_metadata_and_validation_status(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
            app = store.create_app(
                name="PokeHub",
                package_name="com.mi.poketrade",
                activity="com.mi.poketrade/.MainActivity",
                default_mode="flutter-socks",
            )

            updated = store.update_app_version(
                app["id"],
                {
                    "version_name": "1.12.3",
                    "version_code": "64",
                    "last_update_time": "2026-05-07 11:58:33",
                    "installer_package": "com.android.vending",
                    "signature_hint": "d5515cda",
                    "apk_archive_path": "/tmp/apks/latest/com.mi.poketrade",
                    "activity": "com.mi.poketrade/.MainActivity",
                },
            )
            validated = store.update_app_validation(
                app["id"],
                status="passed",
                message="捕获到 3 条接口。",
            )

            self.assertEqual(updated["version_name"], "1.12.3")
            self.assertEqual(updated["version_code"], "64")
            self.assertEqual(updated["signature_hint"], "d5515cda")
            self.assertEqual(validated["last_validation_status"], "passed")
            self.assertEqual(validated["last_validation_message"], "捕获到 3 条接口。")
            self.assertIsNotNone(validated["last_validation_at"])

    def test_runner_parses_dumpsys_package_version_metadata(self):
        from capture_console.runner import CommandResult, ConsoleRunner

        class PackageInfoRunner(ConsoleRunner):
            def adb(self, args, *, timeout=20):
                if args[:3] == ["shell", "dumpsys", "package"]:
                    return CommandResult(
                        0,
                        """
Packages:
  Package [com.mi.poketrade] (dbf875f):
    versionCode=64 minSdk=24 targetSdk=36
    versionName=1.12.3
    lastUpdateTime=2026-05-07 11:58:33
    installerPackageName=com.android.vending
    signatures=PackageSignatures{7eea0e0 version:3, signatures:[d5515cda], past signatures:[]}
""",
                        "",
                    )
                return CommandResult(0, "", "")

            def resolve_activity(self, package_name):
                return "com.mi.poketrade/.MainActivity"

        runner = PackageInfoRunner("/tmp")

        info = runner.package_info("com.mi.poketrade")

        self.assertEqual(info["package_name"], "com.mi.poketrade")
        self.assertEqual(info["version_code"], "64")
        self.assertEqual(info["version_name"], "1.12.3")
        self.assertEqual(info["last_update_time"], "2026-05-07 11:58:33")
        self.assertEqual(info["installer_package"], "com.android.vending")
        self.assertEqual(info["signature_hint"], "d5515cda")
        self.assertEqual(info["activity"], "com.mi.poketrade/.MainActivity")

    def test_runner_parses_apk_badging_for_package_and_version(self):
        from capture_console.runner import ConsoleRunner

        badging = "package: name='com.mi.ai.music' versionCode='56' versionName='1.14.1' platformBuildVersionName='16'\n"

        info = ConsoleRunner.parse_apk_badging(badging)

        self.assertEqual(info["package_name"], "com.mi.ai.music")
        self.assertEqual(info["version_code"], "56")
        self.assertEqual(info["version_name"], "1.14.1")

    def test_result_indexer_reads_details_and_builds_curl(self):
        from capture_console.results import build_curl, get_flow_detail, scan_capture

        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            prefix = "20260509-151104_POST_200_www.blockdance-test.xyz__aisong_portal_mv_create_flow-1"
            meta_name = f"{prefix}.meta.json"
            request_name = f"{prefix}.request.bin"
            response_name = f"{prefix}.response.bin"

            (outdir / "candidates.tsv").write_text(
                "\t".join(
                    [
                        "time",
                        "score",
                        "method",
                        "status",
                        "host",
                        "pattern",
                        "url",
                        "meta",
                        "request_bin",
                        "response_bin",
                    ]
                )
                + "\n"
                + "\t".join(
                    [
                        "2026-05-09T15:11:04+08:00",
                        "133",
                        "POST",
                        "200",
                        "www.blockdance-test.xyz",
                        "https://www.blockdance-test.xyz/aisong/portal/mv/create",
                        "https://www.blockdance-test.xyz/aisong/portal/mv/create",
                        meta_name,
                        request_name,
                        response_name,
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (outdir / meta_name).write_text(
                json.dumps(
                    {
                        "summary": {
                            "id": "flow-1",
                            "method": "POST",
                            "url": "https://www.blockdance-test.xyz/aisong/portal/mv/create",
                            "status": 200,
                            "request_headers": [
                                ["authorization", "Bearer real-token"],
                                ["content-type", "application/json"],
                                ["x-device-id", "device-1"],
                            ],
                            "response_headers": [["content-type", "application/json; charset=utf-8"]],
                        }
                    }
                ),
                encoding="utf-8",
            )
            (outdir / f"{prefix}.request.json").write_text(
                json.dumps({"song_id": "2052590005034004480"}),
                encoding="utf-8",
            )
            (outdir / f"{prefix}.response.json").write_text(
                json.dumps({"code": "S000000", "data": {"task_id": "mv_1"}}),
                encoding="utf-8",
            )
            (outdir / request_name).write_bytes(b'{"song_id":"2052590005034004480"}')
            (outdir / response_name).write_bytes(b'{"code":"S000000"}')

            flows = scan_capture(outdir)
            self.assertEqual(len(flows), 1)
            self.assertEqual(flows[0]["path"], "/aisong/portal/mv/create")
            self.assertEqual(flows[0]["has_request_json"], True)
            self.assertEqual(flows[0]["has_response_json"], True)

            detail = get_flow_detail(outdir, flows[0]["id"])
            self.assertEqual(detail["request_json"]["song_id"], "2052590005034004480")
            self.assertEqual(detail["response_json"]["data"]["task_id"], "mv_1")

            curl = build_curl(detail)
            self.assertIn("curl", curl)
            self.assertIn("authorization: Bearer real-token", curl)
            self.assertIn("https://www.blockdance-test.xyz/aisong/portal/mv/create", curl)
            self.assertIn("--data-raw", curl)

    def test_result_indexer_exposes_request_and_response_timing(self):
        from capture_console.results import get_flow_detail, scan_capture

        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            prefix = "20260520-101500_POST_200_api.example.test_create_flow-1"
            meta_name = f"{prefix}.meta.json"
            request_name = f"{prefix}.request.bin"
            response_name = f"{prefix}.response.bin"

            (outdir / "all-flows.tsv").write_text(
                "\t".join(
                    [
                        "time",
                        "kind",
                        "score",
                        "method",
                        "status",
                        "host",
                        "pattern",
                        "url",
                        "noise_reason",
                        "meta",
                        "request_bin",
                        "response_bin",
                    ]
                )
                + "\n"
                + "\t".join(
                    [
                        "2026-05-20T10:15:00+08:00",
                        "candidate",
                        "120",
                        "POST",
                        "200",
                        "api.example.test",
                        "https://api.example.test/create",
                        "https://api.example.test/create",
                        "",
                        meta_name,
                        request_name,
                        response_name,
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (outdir / meta_name).write_text(
                json.dumps(
                    {
                        "summary": {
                            "id": "flow-1",
                            "url": "https://api.example.test/create",
                            "request_started_at": "2026-05-20T10:15:00.100+08:00",
                            "request_finished_at": "2026-05-20T10:15:00.120+08:00",
                            "response_started_at": "2026-05-20T10:15:00.350+08:00",
                            "response_finished_at": "2026-05-20T10:15:00.380+08:00",
                            "request_duration_ms": 20,
                            "response_duration_ms": 30,
                            "wait_duration_ms": 230,
                            "total_duration_ms": 280,
                        }
                    }
                ),
                encoding="utf-8",
            )
            (outdir / request_name).write_bytes(b"{}")
            (outdir / response_name).write_bytes(b"{}")

            flows = scan_capture(outdir)

            self.assertEqual(flows[0]["request_started_at"], "2026-05-20T10:15:00.100+08:00")
            self.assertEqual(flows[0]["request_duration_ms"], 20)
            self.assertEqual(flows[0]["response_duration_ms"], 30)
            self.assertEqual(flows[0]["wait_duration_ms"], 230)
            self.assertEqual(flows[0]["total_duration_ms"], 280)
            detail = get_flow_detail(outdir, flows[0]["id"])
            self.assertEqual(detail["response_finished_at"], "2026-05-20T10:15:00.380+08:00")
            self.assertEqual(detail["total_duration_ms"], 280)

    def test_result_indexer_does_not_decode_binary_image_response_as_text(self):
        from capture_console.results import get_flow_detail, scan_capture

        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            prefix = "20260603-172345_GET_200_assets.example__icons_v2_3351.png_flow-1"
            meta_name = f"{prefix}.meta.json"
            request_name = f"{prefix}.request.bin"
            response_name = f"{prefix}.response.bin"

            (outdir / "all-flows.tsv").write_text(
                "\t".join(
                    [
                        "time",
                        "kind",
                        "score",
                        "method",
                        "status",
                        "host",
                        "pattern",
                        "url",
                        "noise_reason",
                        "meta",
                        "request_bin",
                        "response_bin",
                    ]
                )
                + "\n"
                + "\t".join(
                    [
                        "2026-06-03T17:23:45+08:00",
                        "candidate",
                        "28",
                        "GET",
                        "200",
                        "assets.example",
                        "https://assets.example/icons_v2/3351.png",
                        "https://assets.example/icons_v2/3351.png",
                        "",
                        meta_name,
                        request_name,
                        response_name,
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (outdir / meta_name).write_text(
                json.dumps(
                    {
                        "summary": {
                            "id": "flow-1",
                            "url": "https://assets.example/icons_v2/3351.png",
                            "response_content_type": "image/png",
                            "response_headers": [["Content-Type", "image/png"], ["Content-Length", "16"]],
                        }
                    }
                ),
                encoding="utf-8",
            )
            png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            (outdir / request_name).write_bytes(b"")
            (outdir / response_name).write_bytes(png_bytes)

            flows = scan_capture(outdir)
            detail = get_flow_detail(outdir, flows[0]["id"])

            self.assertEqual(detail["response_body_kind"], "binary")
            self.assertEqual(detail["response_text"], "")
            self.assertEqual(detail["response_body"]["content_type"], "image/png")
            self.assertEqual(detail["response_body"]["size_bytes"], len(png_bytes))

    def test_exporter_does_not_render_image_content_as_latin1_text(self):
        from scripts.ai_capture_export import render_text_content

        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"

        self.assertEqual(render_text_content(png_bytes, "image/png"), "")

    def test_result_indexer_reads_all_exported_flows_not_only_candidates(self):
        from capture_console.results import get_flow_detail, scan_capture

        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            business_prefix = "20260519-120000_POST_200_api.example.test_profile_flow-1"
            noise_prefix = "20260519-120001_GET_NO_RESPONSE_graph.facebook.com_event_flow-2"
            (outdir / "all-flows.tsv").write_text(
                "\t".join(
                    [
                        "time",
                        "kind",
                        "score",
                        "method",
                        "status",
                        "host",
                        "pattern",
                        "url",
                        "noise_reason",
                        "meta",
                        "request_bin",
                        "response_bin",
                    ]
                )
                + "\n"
                + "\t".join(
                    [
                        "2026-05-19T12:00:00+08:00",
                        "candidate",
                        "98",
                        "POST",
                        "200",
                        "api.example.test",
                        "https://api.example.test/profile",
                        "https://api.example.test/profile",
                        "",
                        f"{business_prefix}.meta.json",
                        f"{business_prefix}.request.bin",
                        f"{business_prefix}.response.bin",
                    ]
                )
                + "\n"
                + "\t".join(
                    [
                        "2026-05-19T12:00:01+08:00",
                        "noise",
                        "20",
                        "GET",
                        "NO_RESPONSE",
                        "graph.facebook.com",
                        "https://graph.facebook.com/event",
                        "https://graph.facebook.com/event",
                        "noise-host",
                        f"{noise_prefix}.meta.json",
                        f"{noise_prefix}.request.bin",
                        f"{noise_prefix}.response.bin",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (outdir / f"{business_prefix}.meta.json").write_text(
                json.dumps({"summary": {"id": "flow-1", "url": "https://api.example.test/profile"}}),
                encoding="utf-8",
            )
            (outdir / f"{noise_prefix}.meta.json").write_text(
                json.dumps({"summary": {"id": "flow-2", "url": "https://graph.facebook.com/event"}}),
                encoding="utf-8",
            )
            (outdir / f"{business_prefix}.request.bin").write_bytes(b'{"profile":true}')
            (outdir / f"{business_prefix}.request.json").write_text(json.dumps({"profile": True}), encoding="utf-8")
            (outdir / f"{business_prefix}.response.bin").write_bytes(b'{"ok":true}')
            (outdir / f"{noise_prefix}.request.bin").write_bytes(b"")
            (outdir / f"{noise_prefix}.response.bin").write_bytes(b"")

            flows = scan_capture(outdir)

            self.assertEqual([flow["kind"] for flow in flows], ["candidate", "noise"])
            self.assertEqual(flows[1]["noise_reason"], "noise-host")
            detail = get_flow_detail(outdir, flows[0]["id"])
            self.assertEqual(detail["request_json"], {"profile": True})

    def test_result_indexer_prefers_completed_duplicate_flow(self):
        from capture_console.results import scan_capture

        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            pending_prefix = "20260806-194907_GET_NO_RESPONSE_api.example.test_profile_flow-1"
            complete_prefix = "20260806-194908_GET_200_api.example.test_profile_flow-1"
            header = [
                "time",
                "kind",
                "score",
                "method",
                "status",
                "host",
                "pattern",
                "url",
                "noise_reason",
                "meta",
                "request_bin",
                "response_bin",
            ]
            rows = [
                [
                    "2026-08-06T19:49:07+08:00",
                    "candidate",
                    "40",
                    "GET",
                    "NO_RESPONSE",
                    "api.example.test",
                    "https://api.example.test/rest/v1/profile",
                    "https://api.example.test/rest/v1/profile",
                    "",
                    f"{pending_prefix}.meta.json",
                    f"{pending_prefix}.request.bin",
                    f"{pending_prefix}.response.bin",
                ],
                [
                    "2026-08-06T19:49:08+08:00",
                    "candidate",
                    "58",
                    "GET",
                    "200",
                    "api.example.test",
                    "https://api.example.test/rest/v1/profile",
                    "https://api.example.test/rest/v1/profile",
                    "",
                    f"{complete_prefix}.meta.json",
                    f"{complete_prefix}.request.bin",
                    f"{complete_prefix}.response.bin",
                ],
            ]
            (outdir / "all-flows.tsv").write_text(
                "\n".join("\t".join(row) for row in [header, *rows]) + "\n",
                encoding="utf-8",
            )
            for prefix in (pending_prefix, complete_prefix):
                (outdir / f"{prefix}.meta.json").write_text(
                    json.dumps({"summary": {"id": "flow-1", "url": "https://api.example.test/rest/v1/profile"}}),
                    encoding="utf-8",
                )
                (outdir / f"{prefix}.request.bin").write_bytes(b"")
                (outdir / f"{prefix}.response.bin").write_bytes(b"")

            flows = scan_capture(outdir)

            self.assertEqual(len(flows), 1)
            self.assertEqual(flows[0]["status"], "200")
            self.assertEqual(flows[0]["score"], 58)

    def test_status_parser_detects_dirty_state(self):
        from capture_console.status import parse_capture_status

        status = parse_capture_status(
            """AI capture status
web: http://127.0.0.1:9091/?token=android-capture
outdir: /tmp/capture
mode: flutter-socks
package: com.example
proxy: listening on 9090
exporter: running pid=111
frida hook: no pid file
android serial: emulator-5554
android proxy: null
foreground:   mCurrentFocus=Window{abc u0 com.example/.MainActivity}
"""
        )

        self.assertEqual(status["mode"], "flutter-socks")
        self.assertEqual(status["exporter"], "running")
        self.assertEqual(status["frida_hook"], "missing")
        self.assertEqual(status["health"], "dirty")


if __name__ == "__main__":
    unittest.main()

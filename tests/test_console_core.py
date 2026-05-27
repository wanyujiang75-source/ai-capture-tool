import json
import sqlite3
import tempfile
import unittest
import json
from pathlib import Path


class CaptureConsoleCoreTests(unittest.TestCase):
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

    def test_stop_web_services_only_stops_owned_processes(self):
        script = Path("scripts/stop_web_services.sh").read_text(encoding="utf-8")

        self.assertIn("project_owns_pid", script)
        self.assertIn("skipped foreign", script)

    def test_store_defaults_to_android_platform_and_persists_session_platform(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
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

        health = MissingGoogleRunner("/tmp").health_check(
            package_name="com.example.app",
            mode="system",
            activity="com.example.app/.MainActivity",
        )

        self.assertFalse(health["ok"])
        google = next(check for check in health["checks"] if check["name"] == "google_login")
        self.assertFalse(google["ok"])
        self.assertIn("Google Play", google["user_message"])

    def test_store_enforces_single_active_capture(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
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

    def test_store_seeds_device_pool_and_locks_active_sessions_per_device(self):
        from capture_console.store import CaptureStore

        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureStore(Path(tmp) / "console.db")
            app = store.create_app(
                name="PokeHub",
                package_name="com.mi.poketrade",
                default_mode="flutter-socks",
            )

            devices = store.list_devices()
            self.assertGreaterEqual(len(devices), 3)
            self.assertEqual(devices[0]["device_id"], "device-1")
            self.assertEqual(devices[0]["adb_serial"], "emulator-5554")
            self.assertEqual(devices[0]["proxy_port"], 9090)
            self.assertEqual(devices[0]["resident"], 1)
            self.assertEqual(devices[0]["idle_release_minutes"], 0)
            self.assertEqual(devices[1]["device_id"], "device-2")
            self.assertEqual(devices[1]["resident"], 1)
            self.assertEqual(devices[2]["device_id"], "device-3")
            self.assertEqual(devices[2]["resident"], 0)
            self.assertEqual(devices[2]["idle_release_minutes"], 10)

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

import asyncio
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from capture_console import app as app_module
from capture_console.runner import CommandResult
from capture_console.store import CaptureStore


class CaptureConsoleApiTests(unittest.TestCase):
    def test_reconcile_replaces_stale_active_session_with_runtime_outdir(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class RuntimeRunner:
            def for_device(self, device):
                return self

            def capture_status(self):
                return {
                    "health": "running",
                    "exporter": "running",
                    "frida_hook": "running",
                    "outdir": "/tmp/current-runtime-capture",
                    "package": "com.example.app",
                    "mode": "flutter-socks",
                    "web": "http://127.0.0.1:9091/?token=android-capture",
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = RuntimeRunner()
                app = app_module.store.create_app(
                    name="Example",
                    package_name="com.example.app",
                    default_mode="flutter-socks",
                )
                stale = app_module.store.create_session(
                    app_id=app["id"],
                    device_id="device-1",
                    mode="flutter-socks",
                    outdir="/tmp/stale-db-capture",
                    status="running",
                )
                current = app_module.store.create_session(
                    app_id=app["id"],
                    device_id="device-1",
                    mode="flutter-socks",
                    outdir="/tmp/current-runtime-capture",
                    status="stopped",
                )

                app_module.reconcile_active_session("device-1")

                self.assertEqual(app_module.store.get_session(stale["id"])["status"], "stopped")
                self.assertEqual(app_module.store.get_session(current["id"])["status"], "running")
                self.assertEqual(app_module.store.active_session("device-1")["id"], current["id"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_system_preflight_api_reports_port_conflicts(self):
        original_store = app_module.store
        original_collect = app_module.collect_port_listeners

        def fake_collect(port, *args, **kwargs):
            if port == 9090:
                return [{"pid": 202, "command": "/usr/local/bin/other-service --port 9090"}]
            return []

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.collect_port_listeners = fake_collect

                result = app_module.api_system_preflight()

                self.assertFalse(result["preflight"]["ok"])
                proxy_port = next(item for item in result["preflight"]["ports"] if item["port"] == 9090)
                self.assertEqual(proxy_port["state"], "occupied_by_other")
                self.assertIn("other-service", proxy_port["detail"])
            finally:
                app_module.store = original_store
                app_module.collect_port_listeners = original_collect

    def test_device_network_api_switches_between_maintenance_and_capture_proxy_modes(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class NetworkRunner:
            def __init__(self):
                self.proxy = "null"

            def for_device(self, device):
                return self

            def emulator_status(self):
                return {
                    "adb_online": True,
                    "boot_completed": True,
                    "unlocked": True,
                    "android_proxy": self.proxy,
                }

            def set_android_proxy(self, proxy):
                self.proxy = proxy
                return CommandResult(0, proxy, "")

            def clear_android_proxy(self):
                self.proxy = "null"
                return CommandResult(0, "proxy cleared", "")

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                runner = NetworkRunner()
                app_module.runner = runner

                state = app_module.api_device_network_state("device-1")
                self.assertEqual(state["network"]["mode"], "direct")

                maintenance = app_module.api_device_network_maintenance("device-1", proxy="127.0.0.1:7890")
                self.assertEqual(maintenance["network"]["mode"], "maintenance_proxy")
                self.assertEqual(runner.proxy, "127.0.0.1:7890")

                capture = app_module.api_device_network_capture("device-1")
                self.assertEqual(capture["network"]["mode"], "direct")
                self.assertEqual(runner.proxy, "null")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_setup_state_defaults_to_incomplete_until_marked_complete(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class SetupRunner:
            def for_device(self, device):
                return self

            def emulator_status(self):
                return {"adb_online": False, "boot_completed": False, "unlocked": False}

            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

            def google_state(self, **kwargs):
                return {
                    "ok": False,
                    "state": "adb_unavailable",
                    "play_store_installed": False,
                    "google_account_present": False,
                    "user_message": "模拟器未在线。",
                    "fix": "请先启动模拟器。",
                }

            def frida_server_status(self, *, device_ok):
                return False, "adb unavailable"

            def env_check(self):
                return {"ok": True, "checks": []}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = SetupRunner()

                result = app_module.api_setup_state()

                self.assertFalse(result["setup"]["completed"])
                self.assertEqual(result["setup"]["current_step"], "env")
                self.assertEqual(result["setup"]["steps"][0]["key"], "env")
                self.assertFalse(result["setup"]["ready_to_complete"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_setup_mark_complete_requires_ready_device_and_passed_validation(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class ReadyRunner:
            def for_device(self, device):
                return self

            def emulator_status(self):
                return {"adb_online": True, "boot_completed": True, "unlocked": True}

            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

            def google_state(self, **kwargs):
                return {
                    "ok": True,
                    "state": "ok",
                    "play_store_installed": True,
                    "google_account_present": True,
                    "user_message": "Google 已登录。",
                    "fix": "",
                }

            def frida_server_status(self, *, device_ok):
                return True, "frida-ps reachable"

            def env_check(self):
                return {"ok": True, "checks": []}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = ReadyRunner()

                with self.assertRaises(HTTPException) as ctx:
                    app_module.api_setup_mark_complete()

                self.assertEqual(ctx.exception.status_code, 409)

                app = app_module.store.create_app(
                    platform="android",
                    name="MelodyCraft",
                    package_name="com.mi.ai.music",
                    default_mode="flutter-socks",
                )
                app_module.store.update_app_validation(app["id"], status="passed", message="抓包校验通过。")

                result = app_module.api_setup_mark_complete()

                self.assertTrue(result["setup"]["completed"])
                self.assertEqual(app_module.api_setup_state()["setup"]["current_step"], "complete")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_setup_state_requires_unlocked_device_for_readiness(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class LockedRunner:
            def for_device(self, device):
                return self

            def emulator_status(self):
                return {"adb_online": True, "boot_completed": True, "unlocked": False}

            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

            def google_state(self, **kwargs):
                return {
                    "ok": True,
                    "state": "ok",
                    "play_store_installed": True,
                    "google_account_present": True,
                    "user_message": "Google 已登录。",
                    "fix": "",
                }

            def frida_server_status(self, *, device_ok):
                return True, "frida-ps reachable"

            def env_check(self):
                return {"ok": True, "checks": []}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = LockedRunner()
                app_module.store.set_system_value(app_module.SETUP_CHECKED_KEY, "1")

                result = app_module.api_setup_state()["setup"]

                self.assertEqual(result["current_step"], "emulator")
                self.assertFalse(result["devices"][0]["ready"])
                self.assertFalse(result["ready_to_complete"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_prepare_frida_api_uses_selected_device_runner(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class FridaRunner:
            def __init__(self):
                self.prepared = []

            def for_device(self, device):
                return self

            def emulator_status(self):
                return {"adb_online": True, "boot_completed": True, "unlocked": True}

            def prepare_frida_server(self):
                self.prepared.append("device")
                return {
                    "ok": True,
                    "stdout": "frida ok",
                    "stderr": "",
                    "frida": {"ok": True, "detail": "frida-ps reachable"},
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                runner = FridaRunner()
                app_module.runner = runner

                result = app_module.api_prepare_frida("device-2")

                self.assertTrue(result["ok"])
                self.assertEqual(result["device_id"], "device-2")
                self.assertEqual(runner.prepared, ["device"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_system_env_check_returns_runner_environment_summary(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class EnvRunner:
            def env_check(self):
                return {
                    "ok": False,
                    "checks": [
                        {
                            "name": "mitmweb",
                            "ok": False,
                            "detail": "not found",
                            "user_message": "mitmweb 未安装。",
                            "fix": "brew install mitmproxy",
                        }
                    ],
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = EnvRunner()

                result = app_module.api_system_env_check()

                self.assertFalse(result["env"]["ok"])
                self.assertEqual(result["env"]["checks"][0]["name"], "mitmweb")
                self.assertIn("brew install", result["env"]["checks"][0]["fix"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_status_recovers_running_capture_after_backend_restart(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class RestartedRunner:
            def __init__(self, outdir):
                self.outdir = outdir

            def capture_status(self):
                return {
                    "web": "http://127.0.0.1:9091/?token=android-capture",
                    "outdir": str(self.outdir),
                    "mode": "flutter-socks",
                    "package": "com.meta.inno.monopoly_sticker",
                    "proxy": "listening on 9090",
                    "exporter": "running",
                    "frida_hook": "running",
                    "health": "running",
                }

            def emulator_status(self):
                return {"adb_serial": "emulator-5554"}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.store.create_app(
                    platform="android",
                    name="MelodyCraft 测试包",
                    package_name="com.meta.inno.monopoly_sticker",
                    activity="com.meta.inno.monopoly_sticker/.MainActivity",
                    default_mode="flutter-socks",
                )
                outdir = Path(tmp) / "capture"
                outdir.mkdir()
                app_module.runner = RestartedRunner(outdir)

                result = app_module.api_status()

                self.assertIsNotNone(result["active_session"])
                self.assertEqual(result["active_session"]["package_name"], "com.meta.inno.monopoly_sticker")
                self.assertEqual(result["active_session"]["status"], "running")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_app_readiness_returns_capture_status_for_selected_app(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class ReadinessRunner:
            def capture_status(self):
                return {"exporter": "running", "frida_hook": "running", "proxy": "listening on 9090"}

            def health_check(self, *, package_name, mode, activity=""):
                return {
                    "ok": True,
                    "checks": [
                        {"name": "retained_emulator", "ok": True, "detail": "ok", "user_message": "保留模拟器正确。"},
                        {"name": "adb_device", "ok": True, "detail": "emulator-5554", "user_message": "模拟器在线。"},
                        {"name": "android_unlocked", "ok": True, "detail": "RUNNING_UNLOCKED", "user_message": "模拟器已解锁。"},
                        {"name": "package_activity", "ok": True, "detail": activity, "user_message": "应用可启动。"},
                        {"name": "frida_server", "ok": True, "detail": "frida reachable", "user_message": "Frida 可用。"},
                    ],
                }

            def emulator_status(self):
                return {"foreground": "mCurrentFocus=Window{abc u0 com.mi.ai.music/com.mi.ai.music.MainActivity}"}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = ReadinessRunner()
                app = app_module.store.create_app(
                    platform="android",
                    name="MelodyCraft 正式包",
                    package_name="com.mi.ai.music",
                    activity="com.mi.ai.music/.MainActivity",
                    default_mode="flutter-socks",
                )
                outdir = Path(tmp) / "capture"
                outdir.mkdir()
                (outdir / "candidates.tsv").write_text(
                    "time\tscore\tmethod\tstatus\thost\tpattern\turl\tmeta\trequest_bin\tresponse_bin\n"
                    "2026-05-18T10:00:00+08:00\t90\tPOST\t200\texample.test\t/api\t/api\t\t\t\n",
                    encoding="utf-8",
                )
                app_module.store.create_session(
                    app_id=app["id"],
                    mode="flutter-socks",
                    outdir=str(outdir),
                    status="running",
                )

                result = app_module.api_app_readiness(app["id"])

                self.assertEqual(result["readiness"]["state"], "ok")
                self.assertEqual(result["readiness"]["flow_count"], 1)
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_launch_app_starts_selected_android_app_by_id(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class LaunchRunner:
            def __init__(self):
                self.calls = []

            def launch_app(self, *, package_name, activity):
                self.calls.append((package_name, activity))
                return CommandResult(0, "started", "")

            def google_state(self, **kwargs):
                return {
                    "ok": True,
                    "state": "ok",
                    "play_store_installed": True,
                    "google_account_present": True,
                    "user_message": "Google 已登录。",
                    "fix": "",
                }

            def emulator_status(self):
                return {"adb_serial": "emulator-5554", "foreground": "com.meta.inno.monopoly_sticker/.MainActivity"}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                runner = LaunchRunner()
                app_module.runner = runner
                app = app_module.store.create_app(
                    platform="android",
                    name="MelodyCraft",
                    package_name="com.meta.inno.monopoly_sticker",
                    activity="com.meta.inno.monopoly_sticker/.MainActivity",
                    default_mode="flutter-socks",
                )

                result = app_module.api_launch_app(app["id"])

                self.assertTrue(result["ok"])
                self.assertEqual(
                    runner.calls,
                    [("com.meta.inno.monopoly_sticker", "com.meta.inno.monopoly_sticker/.MainActivity")],
                )
                self.assertEqual(result["app"]["name"], "MelodyCraft")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_devices_api_lists_seeded_device_pool_and_system_state(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class DeviceStatusRunner:
            def for_device(self, device):
                return self

            def emulator_status(self):
                return {"adb_serial": "emulator-5554", "adb_online": False, "boot_completed": False, "unlocked": False}

            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

            def google_state(self, **kwargs):
                return {
                    "ok": True,
                    "state": "ok",
                    "play_store_installed": True,
                    "google_account_present": True,
                    "user_message": "Google 已登录。",
                    "fix": "",
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = DeviceStatusRunner()

                result = app_module.api_list_devices()

                self.assertEqual(result["system"]["state"], "running")
                self.assertGreaterEqual(len(result["devices"]), 3)
                self.assertEqual(result["devices"][0]["device_id"], "device-1")
                self.assertIn("emulator", result["devices"][0])
                self.assertEqual(result["devices"][0]["resident"], 1)
                self.assertEqual(result["devices"][0]["runtime_policy"], "resident")
                self.assertEqual(result["devices"][0]["release_behavior"], "keep_emulator")
                self.assertFalse(result["devices"][0]["can_shutdown"])
                self.assertEqual(result["devices"][2]["runtime_policy"], "on_demand")
                self.assertEqual(result["devices"][2]["release_behavior"], "shutdown_emulator")
                self.assertTrue(result["devices"][2]["can_shutdown"])
                self.assertEqual(result["devices"][0]["google_state"]["state"], "ok")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_device_google_state_api_returns_runner_google_status(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class GoogleStateRunner:
            def google_state(self, **kwargs):
                return {
                    "ok": False,
                    "state": "not_logged_in",
                    "play_store_installed": True,
                    "google_account_present": False,
                    "user_message": "请先在模拟器内登录 Google 账号。",
                    "fix": "点击“去登录 Google”，完成登录后刷新状态。",
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = GoogleStateRunner()

                result = app_module.api_device_google_state("device-1")

                self.assertFalse(result["google_state"]["ok"])
                self.assertEqual(result["google_state"]["state"], "not_logged_in")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_open_google_login_api_uses_selected_device_runner(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class GoogleLoginRunner:
            def __init__(self):
                self.opened = False

            def open_google_login(self):
                self.opened = True
                return {
                    "ok": True,
                    "stdout": "Events injected",
                    "stderr": "",
                    "google_state": {
                        "ok": False,
                        "state": "not_logged_in",
                        "play_store_installed": True,
                        "google_account_present": False,
                    },
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                runner = GoogleLoginRunner()
                app_module.runner = runner

                result = app_module.api_open_google_login("device-1")

                self.assertTrue(result["ok"])
                self.assertTrue(runner.opened)
                self.assertEqual(result["google_state"]["state"], "not_logged_in")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_start_capture_rejects_when_google_account_is_missing(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_google_required = app_module.GOOGLE_LOGIN_REQUIRED

        class MissingGoogleRunner:
            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

            def google_state(self, **kwargs):
                return {
                    "ok": False,
                    "state": "not_logged_in",
                    "play_store_installed": True,
                    "google_account_present": False,
                    "user_message": "请先在模拟器内登录 Google 账号。",
                    "fix": "点击“去登录 Google”，完成登录后刷新状态。",
                }

            def start_capture(self, **kwargs):
                raise AssertionError("capture must not start without Google login")

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = MissingGoogleRunner()
                app_module.GOOGLE_LOGIN_REQUIRED = True
                app = app_module.store.create_app(
                    platform="android",
                    name="MelodyCraft",
                    package_name="com.mi.ai.music",
                    activity="com.mi.ai.music/.MainActivity",
                    default_mode="flutter-socks",
                )

                with self.assertRaises(HTTPException) as ctx:
                    app_module.api_start_capture(app_module.CaptureStartPayload(app_id=app["id"]))

                self.assertEqual(ctx.exception.status_code, 409)
                self.assertEqual(ctx.exception.detail["state"], "not_logged_in")
                self.assertIn("登录 Google", ctx.exception.detail["user_message"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.GOOGLE_LOGIN_REQUIRED = original_google_required

    def test_launch_app_rejects_when_google_play_is_missing(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_google_required = app_module.GOOGLE_LOGIN_REQUIRED

        class MissingPlayStoreRunner:
            def emulator_status(self):
                return {"adb_online": True, "boot_completed": True, "unlocked": True}

            def google_state(self, **kwargs):
                return {
                    "ok": False,
                    "state": "missing_play_store",
                    "play_store_installed": False,
                    "google_account_present": False,
                    "user_message": "当前模拟器缺少 Google Play。",
                    "fix": "请使用 Google Play AVD 重建该设备。",
                }

            def launch_app(self, **kwargs):
                raise AssertionError("app must not launch without Google Play")

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = MissingPlayStoreRunner()
                app_module.GOOGLE_LOGIN_REQUIRED = True
                app = app_module.store.create_app(
                    platform="android",
                    name="MelodyCraft",
                    package_name="com.mi.ai.music",
                    activity="com.mi.ai.music/.MainActivity",
                    default_mode="flutter-socks",
                )

                with self.assertRaises(HTTPException) as ctx:
                    app_module.api_launch_app(app["id"])

                self.assertEqual(ctx.exception.status_code, 409)
                self.assertEqual(ctx.exception.detail["state"], "missing_play_store")
                self.assertIn("Google Play", ctx.exception.detail["user_message"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.GOOGLE_LOGIN_REQUIRED = original_google_required

    def test_package_install_readiness_rejects_when_google_login_is_missing(self):
        original_runner = app_module.runner
        original_google_required = app_module.GOOGLE_LOGIN_REQUIRED

        class MissingGoogleRunner:
            def emulator_status(self):
                return {"adb_online": True, "boot_completed": True, "unlocked": True}

            def google_state(self, **kwargs):
                return {
                    "ok": False,
                    "state": "not_logged_in",
                    "play_store_installed": True,
                    "google_account_present": False,
                    "user_message": "请先在模拟器内登录 Google 账号。",
                    "fix": "点击“去登录 Google”，完成登录后刷新状态。",
                }

        try:
            app_module.runner = MissingGoogleRunner()
            app_module.GOOGLE_LOGIN_REQUIRED = True

            with self.assertRaises(HTTPException) as ctx:
                app_module.ensure_emulator_ready_for_install(device_id="device-1")

            self.assertEqual(ctx.exception.status_code, 409)
            self.assertEqual(ctx.exception.detail["state"], "not_logged_in")
        finally:
            app_module.runner = original_runner
            app_module.GOOGLE_LOGIN_REQUIRED = original_google_required

    def test_devices_api_recovers_running_capture_for_each_device(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class DeviceRunner:
            def __init__(self, device, outdir):
                self.device = device
                self.outdir = outdir

            def emulator_status(self):
                return {
                    "adb_serial": self.device["adb_serial"],
                    "adb_online": True,
                    "boot_completed": True,
                    "unlocked": True,
                }

            def capture_status(self):
                if self.device["device_id"] != "device-2":
                    return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}
                return {
                    "web": "http://127.0.0.1:9101/?token=android-capture",
                    "outdir": str(self.outdir),
                    "mode": "flutter-socks",
                    "package": "com.meta.inno.monopoly_sticker",
                    "proxy": "listening on 9100",
                    "exporter": "running",
                    "frida_hook": "running",
                    "health": "running",
                }

            def google_state(self, **kwargs):
                return {
                    "ok": True,
                    "state": "ok",
                    "play_store_installed": True,
                    "google_account_present": True,
                    "user_message": "Google 已登录。",
                    "fix": "",
                }

        class DevicePoolRunner:
            def __init__(self, outdir):
                self.outdir = outdir

            def for_device(self, device):
                return DeviceRunner(device, self.outdir)

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.store.create_app(
                    platform="android",
                    name="MelodyCraft 测试包",
                    package_name="com.meta.inno.monopoly_sticker",
                    default_mode="flutter-socks",
                )
                outdir = Path(tmp) / "capture-device-2"
                outdir.mkdir()
                app_module.runner = DevicePoolRunner(outdir)

                result = app_module.api_list_devices()
                device_two = next(device for device in result["devices"] if device["device_id"] == "device-2")

                self.assertIsNotNone(device_two["active_session"])
                self.assertEqual(device_two["active_session"]["device_id"], "device-2")
                self.assertEqual(device_two["active_session"]["proxy_port"], 9100)
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_create_app_api_persists_environment_for_test_package(self):
        original_store = app_module.store

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")

                result = app_module.api_create_app(
                    app_module.AppPayload(
                        platform="android",
                        environment="test",
                        name="MelodyCraft 测试包",
                        package_name="com.meta.inno.monopoly_sticker",
                        default_mode="flutter-socks",
                    )
                )

                self.assertEqual(result["app"]["environment"], "test")
            finally:
                app_module.store = original_store

    def test_update_app_api_preserves_environment_when_payload_omits_it(self):
        original_store = app_module.store

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app = app_module.store.create_app(
                    platform="android",
                    environment="test",
                    name="MelodyCraft 测试包",
                    package_name="com.meta.inno.monopoly_sticker",
                    default_mode="flutter-socks",
                )

                result = app_module.api_update_app(
                    app["id"],
                    app_module.AppPayload(
                        platform="android",
                        name="MelodyCraft 测试包",
                        package_name="com.meta.inno.monopoly_sticker",
                        default_mode="flutter-socks",
                        notes="更新备注但不改变包类型",
                    ),
                )

                self.assertEqual(result["app"]["environment"], "test")
                self.assertEqual(result["app"]["notes"], "更新备注但不改变包类型")
            finally:
                app_module.store = original_store

    def test_launch_app_rejects_ios_reserved_app_without_touching_runner(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class RunnerShouldNotRun:
            def launch_app(self, **kwargs):
                raise AssertionError("runner should not be touched for iOS reserved apps")

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = RunnerShouldNotRun()
                app = app_module.store.create_app(
                    platform="ios",
                    name="Future iOS App",
                    package_name="com.example.future.ios",
                    default_mode="system",
                )

                with self.assertRaises(HTTPException) as ctx:
                    app_module.api_launch_app(app["id"])

                self.assertEqual(ctx.exception.status_code, 501)
                self.assertEqual(ctx.exception.detail["platform"], "ios")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_start_capture_rejects_ios_reserved_app_without_touching_runner(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class RunnerShouldNotRun:
            def capture_status(self):
                raise AssertionError("runner should not be touched for iOS reserved apps")

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = RunnerShouldNotRun()
                app = app_module.store.create_app(
                    platform="ios",
                    name="Future iOS App",
                    package_name="com.example.future.ios",
                    default_mode="system",
                )

                with self.assertRaises(HTTPException) as ctx:
                    app_module.api_start_capture(app_module.CaptureStartPayload(app_id=app["id"]))

                self.assertEqual(ctx.exception.status_code, 501)
                self.assertEqual(ctx.exception.detail["platform"], "ios")
                self.assertIn("只支持 Android", ctx.exception.detail["user_message"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_sync_version_updates_selected_android_app_from_device(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class VersionRunner:
            def package_info(self, package_name):
                return {
                    "package_name": package_name,
                    "version_name": "1.14.1",
                    "version_code": "56",
                    "last_update_time": "2026-05-15 18:30:00",
                    "installer_package": "null",
                    "signature_hint": "8fb12e64",
                    "activity": "com.mi.ai.music/.MainActivity",
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = VersionRunner()
                app = app_module.store.create_app(
                    platform="android",
                    name="MelodyCraft 正式包",
                    package_name="com.mi.ai.music",
                    default_mode="flutter-socks",
                )

                result = app_module.api_sync_app_version(app["id"])

                self.assertEqual(result["app"]["version_name"], "1.14.1")
                self.assertEqual(result["app"]["version_code"], "56")
                self.assertEqual(result["app"]["activity"], "com.mi.ai.music/.MainActivity")
                self.assertFalse(result["version"]["drift"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_app_version_reports_drift_between_database_and_device(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class VersionRunner:
            def package_info(self, package_name):
                return {
                    "package_name": package_name,
                    "version_name": "1.14.2",
                    "version_code": "57",
                    "last_update_time": "2026-05-18 12:00:00",
                    "installer_package": "null",
                    "signature_hint": "8fb12e64",
                    "activity": "com.mi.ai.music/.MainActivity",
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = VersionRunner()
                app = app_module.store.create_app(
                    platform="android",
                    name="MelodyCraft 正式包",
                    package_name="com.mi.ai.music",
                    default_mode="flutter-socks",
                )
                app_module.store.update_app_version(app["id"], {"version_name": "1.14.1", "version_code": "56"})

                result = app_module.api_get_app_version(app["id"])

                self.assertTrue(result["version"]["drift"])
                self.assertEqual(result["version"]["device"]["version_code"], "57")
                self.assertEqual(result["version"]["database"]["version_code"], "56")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_install_app_rejects_when_capture_session_is_active(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class RunnerShouldNotInstall:
            def capture_status(self):
                return {"exporter": "running", "frida_hook": "running", "health": "running"}

            def install_apks(self, *args, **kwargs):
                raise AssertionError("install should not run while capture is active")

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = RunnerShouldNotInstall()
                app = app_module.store.create_app(
                    platform="android",
                    name="PokeHub",
                    package_name="com.mi.poketrade",
                    default_mode="flutter-socks",
                )
                app_module.store.create_session(
                    app_id=app["id"],
                    mode="flutter-socks",
                    outdir=str(Path(tmp) / "capture"),
                    status="running",
                )

                with self.assertRaises(HTTPException) as ctx:
                    app_module.ensure_no_active_capture_for_update()

                self.assertEqual(ctx.exception.status_code, 409)
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_install_uploaded_package_creates_app_in_selected_environment(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class UploadRequest:
            headers = {"x-filename": "pokehub-test.apk"}

            async def body(self):
                return b"fake apk bytes"

        class UploadRunner:
            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

            def emulator_status(self):
                return {"adb_online": True, "boot_completed": True, "unlocked": True}

            def google_state(self, **kwargs):
                return {
                    "ok": True,
                    "state": "ok",
                    "play_store_installed": True,
                    "google_account_present": True,
                    "user_message": "Google 已登录。",
                    "fix": "",
                }

            def inspect_apk(self, apk_path):
                return {
                    "package_name": "com.mi.poketrade.test",
                    "version_name": "1.12.4-test",
                    "version_code": "65",
                }

            def package_info(self, package_name):
                if package_name == "com.mi.poketrade.test":
                    return {
                        "package_name": package_name,
                        "installed": True,
                        "version_name": "1.12.4-test",
                        "version_code": "65",
                        "last_update_time": "2026-05-18 19:00:00",
                        "installer_package": "null",
                        "signature_hint": "abc12345",
                        "activity": "com.mi.poketrade.test/.MainActivity",
                    }
                return {"package_name": package_name, "installed": False}

            def install_apks(self, apk_paths):
                return CommandResult(0, "Success", "")

        with tempfile.TemporaryDirectory() as tmp:
            original_uploads = app_module.UPLOADS_DIR
            original_latest = app_module.LATEST_APKS_DIR
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = UploadRunner()
                app_module.UPLOADS_DIR = Path(tmp) / "uploads"
                app_module.LATEST_APKS_DIR = Path(tmp) / "latest"

                result = asyncio.run(app_module.api_install_uploaded_app(UploadRequest(), environment="test", device_id="device-2"))

                self.assertTrue(result["ok"])
                self.assertEqual(result["app"]["package_name"], "com.mi.poketrade.test")
                self.assertEqual(result["app"]["environment"], "test")
                self.assertEqual(result["app"]["default_mode"], "flutter-socks")
                self.assertEqual(result["app"]["version_code"], "65")
                self.assertEqual(result["device_app_state"]["device_id"], "device-2")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.UPLOADS_DIR = original_uploads
                app_module.LATEST_APKS_DIR = original_latest

    def test_install_uploaded_package_updates_existing_app_environment(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class UploadRequest:
            headers = {"x-filename": "pokehub.apk"}

            async def body(self):
                return b"fake apk bytes"

        class UploadRunner:
            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

            def emulator_status(self):
                return {"adb_online": True, "boot_completed": True, "unlocked": True}

            def google_state(self, **kwargs):
                return {
                    "ok": True,
                    "state": "ok",
                    "play_store_installed": True,
                    "google_account_present": True,
                    "user_message": "Google 已登录。",
                    "fix": "",
                }

            def inspect_apk(self, apk_path):
                return {"package_name": "com.mi.poketrade", "version_name": "1.12.5", "version_code": "66"}

            def package_info(self, package_name):
                return {
                    "package_name": package_name,
                    "installed": True,
                    "version_name": "1.12.5",
                    "version_code": "66",
                    "last_update_time": "2026-05-18 19:10:00",
                    "installer_package": "null",
                    "signature_hint": "d5515cda",
                    "activity": "com.mi.poketrade/.MainActivity",
                }

            def install_apks(self, apk_paths):
                return CommandResult(0, "Success", "")

        with tempfile.TemporaryDirectory() as tmp:
            original_uploads = app_module.UPLOADS_DIR
            original_latest = app_module.LATEST_APKS_DIR
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = UploadRunner()
                app_module.UPLOADS_DIR = Path(tmp) / "uploads"
                app_module.LATEST_APKS_DIR = Path(tmp) / "latest"
                app_module.store.create_app(
                    platform="android",
                    environment="production",
                    name="PokeHub",
                    package_name="com.mi.poketrade",
                    default_mode="flutter-socks",
                )

                result = asyncio.run(app_module.api_install_uploaded_app(UploadRequest(), environment="test", device_id="device-1"))

                self.assertEqual(result["app"]["name"], "PokeHub")
                self.assertEqual(result["app"]["environment"], "test")
                self.assertEqual(result["app"]["version_code"], "66")
                self.assertEqual(result["device_app_state"]["device_id"], "device-1")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.UPLOADS_DIR = original_uploads
                app_module.LATEST_APKS_DIR = original_latest

    def test_install_uploaded_package_rejects_when_emulator_is_not_ready(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class UploadRequest:
            headers = {"x-filename": "pokehub.apk"}

            async def body(self):
                return b"fake apk bytes"

        class OfflineRunner:
            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

            def emulator_status(self):
                return {"adb_online": False, "boot_completed": False, "unlocked": False}

            def install_apks(self, apk_paths):
                raise AssertionError("install should not run when emulator is offline")

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = OfflineRunner()

                with self.assertRaises(HTTPException) as ctx:
                    asyncio.run(app_module.api_install_uploaded_app(UploadRequest(), environment="production"))

                self.assertEqual(ctx.exception.status_code, 400)
                self.assertIn("请先启动模拟器", ctx.exception.detail["user_message"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_release_resident_device_stops_capture_without_closing_emulator(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class ReleaseRunner:
            def __init__(self):
                self.stopped = False
                self.killed = False
                self.cleared_proxy = False

            def for_device(self, device):
                return self

            def stop_capture(self):
                self.stopped = True
                return CommandResult(0, "stopped", "")

            def clear_android_proxy(self):
                self.cleared_proxy = True
                return CommandResult(0, "proxy cleared", "")

            def stop_emulator(self):
                self.killed = True
                return CommandResult(0, "OK", "")

            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                runner = ReleaseRunner()
                app_module.runner = runner
                app = app_module.store.create_app(
                    platform="android",
                    name="PokeHub",
                    package_name="com.mi.poketrade",
                    default_mode="flutter-socks",
                )
                session = app_module.store.create_session(
                    app_id=app["id"],
                    device_id="device-1",
                    mode="flutter-socks",
                    outdir=str(Path(tmp) / "capture"),
                    status="running",
                )
                app_module.store.update_device("device-1", lease_status="leased", current_session_id=session["id"])

                result = app_module.api_release_device("device-1")

                self.assertTrue(result["ok"])
                self.assertTrue(runner.stopped)
                self.assertTrue(runner.cleared_proxy)
                self.assertFalse(runner.killed)
                self.assertEqual(result["release_behavior"], "keep_emulator")
                self.assertEqual(app_module.store.get_session(session["id"])["status"], "stopped")
                self.assertEqual(app_module.store.get_device("device-1")["lease_status"], "idle")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_release_on_demand_device_closes_selected_emulator(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class ReleaseRunner:
            def __init__(self):
                self.killed = False
                self.stopped = False
                self.cleared_proxy = False

            def for_device(self, device):
                return self

            def stop_capture(self):
                self.stopped = True
                return CommandResult(0, "stopped", "")

            def clear_android_proxy(self):
                self.cleared_proxy = True
                return CommandResult(0, "proxy cleared", "")

            def stop_emulator(self):
                self.killed = True
                return CommandResult(0, "OK", "")

            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                runner = ReleaseRunner()
                app_module.runner = runner

                result = app_module.api_release_device("device-3")

                self.assertTrue(result["ok"])
                self.assertTrue(runner.stopped)
                self.assertTrue(runner.cleared_proxy)
                self.assertTrue(runner.killed)
                self.assertEqual(result["release_behavior"], "shutdown_emulator")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_force_release_resident_device_closes_emulator(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class ReleaseRunner:
            def __init__(self):
                self.killed = False

            def for_device(self, device):
                return self

            def stop_capture(self):
                return CommandResult(0, "stopped", "")

            def clear_android_proxy(self):
                return CommandResult(0, "proxy cleared", "")

            def stop_emulator(self):
                self.killed = True
                return CommandResult(0, "OK", "")

            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                runner = ReleaseRunner()
                app_module.runner = runner

                result = app_module.api_release_device("device-1", force_shutdown=True)

                self.assertTrue(result["ok"])
                self.assertTrue(runner.killed)
                self.assertEqual(result["release_behavior"], "shutdown_emulator")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_system_sleep_rejects_when_any_device_has_active_capture(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class SleepRunner:
            def for_device(self, device):
                return self

            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = SleepRunner()
                app = app_module.store.create_app(
                    platform="android",
                    name="MelodyCraft",
                    package_name="com.meta.inno.monopoly_sticker",
                    default_mode="flutter-socks",
                )
                app_module.store.create_session(
                    app_id=app["id"],
                    device_id="device-2",
                    mode="flutter-socks",
                    outdir=str(Path(tmp) / "capture"),
                    status="running",
                )

                with self.assertRaises(HTTPException) as ctx:
                    app_module.api_system_sleep()

                self.assertEqual(ctx.exception.status_code, 409)
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_resources_api_summarizes_capture_process_memory(self):
        original_process_rows = app_module.process_resource_rows

        try:
            app_module.process_resource_rows = lambda: [
                {"pid": 1, "rss_kb": 2048, "command": "qemu-system-aarch64 -avd device-1"},
                {"pid": 2, "rss_kb": 1024, "command": "mitmweb --listen-port 9090"},
                {"pid": 3, "rss_kb": 512, "command": "flutter_proxy_unpin_capture.py"},
                {"pid": 4, "rss_kb": 256, "command": "ai_capture_export.py --cookie-file runtime/capture_instances/device-1/mitmweb.cookies"},
                {"pid": 5, "rss_kb": 128, "command": "uvicorn capture_console.app:app"},
                {"pid": 6, "rss_kb": 64, "command": "unrelated"},
            ]

            result = app_module.api_system_resources()

            self.assertEqual(result["totals"]["emulator_mb"], 2.0)
            self.assertEqual(result["totals"]["mitm_mb"], 1.0)
            self.assertEqual(result["totals"]["frida_mb"], 0.5)
            self.assertEqual(result["totals"]["exporter_mb"], 0.25)
            self.assertEqual(result["totals"]["web_mb"], 0.12)
            self.assertEqual(result["totals"]["capture_related_mb"], 3.88)
        finally:
            app_module.process_resource_rows = original_process_rows

    def test_validate_capture_rejects_when_capture_session_is_active(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class RunnerShouldNotValidate:
            def capture_status(self):
                return {"exporter": "running", "frida_hook": "running", "health": "running"}

            def start_capture(self, **kwargs):
                raise AssertionError("validation should not start while capture is active")

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = RunnerShouldNotValidate()
                app = app_module.store.create_app(
                    platform="android",
                    name="PokeHub",
                    package_name="com.mi.poketrade",
                    default_mode="flutter-socks",
                )
                app_module.store.create_session(
                    app_id=app["id"],
                    mode="flutter-socks",
                    outdir=str(Path(tmp) / "capture"),
                    status="running",
                )

                with self.assertRaises(HTTPException) as ctx:
                    app_module.api_validate_capture(app["id"])

                self.assertEqual(ctx.exception.status_code, 409)
            finally:
                app_module.store = original_store
                app_module.runner = original_runner


if __name__ == "__main__":
    unittest.main()

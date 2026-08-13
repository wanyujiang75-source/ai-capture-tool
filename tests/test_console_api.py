import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

from capture_console import app as app_module
from capture_console.runner import CommandResult
from capture_console.store import CaptureStore


class CaptureConsoleApiTests(unittest.TestCase):
    def add_test_device(
        self,
        store,
        *,
        device_id: str = "device-1",
        adb_serial: str = "emulator-5554",
        proxy_port: int = 9090,
        web_port: int = 9091,
        frida_port: int = 27042,
        enabled: int = 1,
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
            enabled=enabled,
            resident=resident,
            idle_release_minutes=idle_release_minutes,
        )

    def test_foreground_target_resolve_registers_unknown_installed_app(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class ForegroundRunner:
            def for_device(self, device):
                return self

            def foreground_app_state(self):
                return {
                    "state": "ready",
                    "package_name": "com.example.newapp",
                    "activity": "com.example.newapp/.MainActivity",
                    "component": "com.example.newapp/.MainActivity",
                }

            def package_info(self, package_name):
                return {
                    "package_name": package_name,
                    "installed": True,
                    "activity": "com.example.newapp/.MainActivity",
                    "version_name": "2.4.0",
                    "version_code": "24",
                    "last_update_time": "2026-08-13 17:00:00",
                    "installer_package": "com.android.shell",
                    "signature_hint": "abc123",
                    "error": "",
                }

            def capture_status(self):
                return {"health": "idle", "exporter": "stopped", "frida_hook": "stopped"}

            def emulator_status(self):
                return {"foreground": "com.example.newapp/.MainActivity"}

            def health_check(self, **kwargs):
                return {
                    "ok": True,
                    "resolved_activity": "com.example.newapp/.MainActivity",
                    "checks": [
                        {"name": "retained_emulator", "ok": True},
                        {"name": "adb_device", "ok": True},
                        {"name": "android_unlocked", "ok": True},
                        {"name": "package_activity", "ok": True},
                    ],
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = ForegroundRunner()

                result = app_module.api_resolve_foreground_target("device-1")

                self.assertEqual(result["state"], "ready")
                self.assertEqual(result["capture_state"], "ready")
                self.assertEqual(result["app"]["package_name"], "com.example.newapp")
                self.assertEqual(result["app"]["default_mode"], "auto")
                self.assertEqual(result["app"]["environment"], "production")
                self.assertEqual(result["version"]["version_name"], "2.4.0")
                self.assertEqual(len(app_module.store.list_apps()), 1)
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_foreground_target_resolve_preserves_existing_app_metadata(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class ForegroundRunner:
            def for_device(self, device):
                return self

            def foreground_app_state(self):
                return {
                    "state": "ready",
                    "package_name": "com.example.known",
                    "activity": "com.example.known/.UpdatedActivity",
                    "component": "com.example.known/.UpdatedActivity",
                }

            def package_info(self, package_name):
                return {
                    "package_name": package_name,
                    "installed": True,
                    "activity": "com.example.known/.UpdatedActivity",
                    "version_name": "3.0.0",
                    "version_code": "30",
                    "last_update_time": "",
                    "installer_package": "",
                    "signature_hint": "",
                    "error": "",
                }

            def capture_status(self):
                return {"health": "idle", "exporter": "stopped", "frida_hook": "stopped"}

            def emulator_status(self):
                return {"foreground": "com.example.known/.UpdatedActivity"}

            def health_check(self, **kwargs):
                return {
                    "ok": True,
                    "resolved_activity": "com.example.known/.UpdatedActivity",
                    "checks": [
                        {"name": "retained_emulator", "ok": True},
                        {"name": "adb_device", "ok": True},
                        {"name": "android_unlocked", "ok": True},
                        {"name": "package_activity", "ok": True},
                    ],
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                existing = app_module.store.create_app(
                    name="Human Name",
                    package_name="com.example.known",
                    activity="",
                    environment="test",
                    default_mode="flutter-socks",
                    notes="keep this note",
                )
                app_module.store.update_app(existing["id"], last_success_mode="flutter-socks")
                app_module.runner = ForegroundRunner()

                result = app_module.api_resolve_foreground_target("device-1")

                self.assertEqual(result["app"]["name"], "Human Name")
                self.assertEqual(result["app"]["environment"], "test")
                self.assertEqual(result["app"]["default_mode"], "flutter-socks")
                self.assertEqual(result["app"]["notes"], "keep this note")
                self.assertEqual(result["app"]["last_success_mode"], "flutter-socks")
                self.assertEqual(result["app"]["activity"], "com.example.known/.UpdatedActivity")
                self.assertEqual(len(app_module.store.list_apps()), 1)
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_foreground_target_does_not_register_system_or_missing_package(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class ForegroundRunner:
            package_installed = True

            def for_device(self, device):
                return self

            def foreground_app_state(self):
                if self.package_installed:
                    return {"state": "no_target", "package_name": "", "activity": "", "component": ""}
                return {
                    "state": "ready",
                    "package_name": "com.example.missing",
                    "activity": "com.example.missing/.MainActivity",
                    "component": "com.example.missing/.MainActivity",
                }

            def package_info(self, package_name):
                return {"package_name": package_name, "installed": False, "error": "not found"}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                fake_runner = ForegroundRunner()
                app_module.runner = fake_runner

                no_target = app_module.api_resolve_foreground_target("device-1")
                fake_runner.package_installed = False
                missing = app_module.api_resolve_foreground_target("device-1")

                self.assertEqual(no_target["state"], "no_target")
                self.assertEqual(missing["state"], "package_missing")
                self.assertEqual(app_module.store.list_apps(), [])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_devices_api_seeds_single_downloadable_default_device_for_new_project(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class DefaultDeviceRunner:
            def for_device(self, device):
                return self

            def emulator_status(self):
                return {"adb_online": False, "boot_completed": False, "unlocked": False}

            def capture_status(self):
                return {"health": "idle"}

            def google_state(self, device_ok=False):
                return {"ok": False}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                with mock.patch.dict(os.environ, {"TRACEDECK_DESKTOP": "1"}):
                    app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = DefaultDeviceRunner()

                result = app_module.api_list_devices()

                self.assertEqual(len(result["devices"]), 1)
                self.assertEqual(result["devices"][0]["device_id"], "device-1")
                self.assertEqual(result["devices"][0]["avd_name"], "AI_Capture_AVD_01")
                self.assertEqual(result["system"]["state"], "running")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_status_api_treats_disabled_default_device_as_empty_state(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class RunnerShouldNotBeCalled:
            def for_device(self, device):
                raise AssertionError("disabled default device must not be used for status")

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store, enabled=0)
                app_module.runner = RunnerShouldNotBeCalled()

                result = app_module.api_status()

                self.assertEqual(result["health"], "idle")
                self.assertIsNone(result["active_session"])
                self.assertIn("未发现在线设备", result["user_message"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_status_api_exposes_desktop_runtime_metadata(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_runtime_dir = app_module.RUNTIME_DIR

        class RunnerShouldNotBeCalled:
            def for_device(self, device):
                raise AssertionError("empty device list must not build device runners")

        with tempfile.TemporaryDirectory() as tmp:
            try:
                runtime_dir = Path(tmp) / "Application Support" / "AI抓包工具" / "runtime"
                app_module.RUNTIME_DIR = runtime_dir
                app_module.store = CaptureStore(runtime_dir / "console.db")
                app_module.runner = RunnerShouldNotBeCalled()

                with mock.patch.dict(
                    os.environ,
                    {
                        "TRACEDECK_DESKTOP": "1",
                        "TRACEDECK_CONFIG": str(runtime_dir.parent / "config" / "local.json"),
                    },
                ):
                    result = app_module.api_status()

                self.assertTrue(result["desktop"]["enabled"])
                self.assertEqual(result["desktop"]["runtime_dir"], str(runtime_dir))
                self.assertEqual(
                    result["desktop"]["config_path"],
                    str(runtime_dir.parent / "config" / "local.json"),
                )
            finally:
                app_module.RUNTIME_DIR = original_runtime_dir
                app_module.store = original_store
                app_module.runner = original_runner

    def test_discover_devices_api_persists_adb_devices_without_fixed_avd_pool(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class DiscoverRunner:
            def discover_adb_devices(self):
                return [
                    {"serial": "emulator-5554", "kind": "emulator"},
                    {"serial": "R5CT123ABC", "kind": "physical"},
                ]

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.runner = DiscoverRunner()

                result = app_module.api_discover_devices()

                self.assertEqual([device["device_id"] for device in result["devices"]], ["device-1", "device-2"])
                self.assertEqual(result["devices"][0]["adb_serial"], "emulator-5554")
                self.assertEqual(app_module.store.list_devices()[1]["adb_serial"], "R5CT123ABC")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_discover_devices_api_disables_stale_legacy_devices(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class DiscoverRunner:
            def discover_adb_devices(self):
                return [{"serial": "emulator-5556", "kind": "emulator"}]

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store, device_id="device-2", adb_serial="emulator-5556", proxy_port=9100, web_port=9101, frida_port=27142)
                self.add_test_device(app_module.store, device_id="device-3", adb_serial="emulator-5558", proxy_port=9110, web_port=9111, frida_port=27242)
                app_module.runner = DiscoverRunner()

                result = app_module.api_discover_devices()

                self.assertEqual([device["device_id"] for device in result["devices"]], ["device-1"])
                self.assertEqual(app_module.store.get_device("device-1")["adb_serial"], "emulator-5556")
                self.assertEqual(app_module.store.list_devices(include_disabled=False)[0]["device_id"], "device-1")
                self.assertEqual(app_module.store.get_device("device-2")["enabled"], 0)
                self.assertEqual(app_module.store.get_device("device-3")["enabled"], 0)
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_discover_devices_api_refreshes_existing_device_activity(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class DiscoverRunner:
            def discover_adb_devices(self):
                return [{"serial": "emulator-5554", "kind": "emulator"}]

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store, resident=0, idle_release_minutes=10)
                stale_at = "2000-01-01T00:00:00+00:00"
                app_module.store.update_device("device-1", last_active_at=stale_at, sleep_state="sleeping", error="old")
                app_module.runner = DiscoverRunner()

                result = app_module.api_discover_devices()

                self.assertEqual(result["devices"][0]["device_id"], "device-1")
                self.assertEqual(result["devices"][0]["sleep_state"], "awake")
                self.assertEqual(result["devices"][0]["error"], "")
                self.assertNotEqual(result["devices"][0]["last_active_at"], stale_at)
                self.assertEqual(app_module.store.get_device("device-1")["sleep_state"], "awake")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_device_status_backfills_missing_avd_name_from_running_emulator(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class StatusRunner:
            def for_device(self, device):
                return self

            def emulator_status(self):
                return {
                    "adb_online": True,
                    "current_avd": "Capture_AVD_02",
                    "foreground": "",
                }

            def capture_status(self):
                return {"health": "idle"}

            def google_state(self, device_ok=False):
                return {"ok": True}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                app_module.store.upsert_device(
                    device_id="device-1",
                    name="Discovered Device",
                    avd_name="",
                    adb_serial="emulator-5554",
                    proxy_port=9100,
                    web_port=9101,
                    frida_port=27142,
                )
                app_module.runner = StatusRunner()

                result = app_module.build_device_status(app_module.store.get_device("device-1"))

                self.assertEqual(result["avd_name"], "Capture_AVD_02")
                self.assertEqual(app_module.store.get_device("device-1")["avd_name"], "Capture_AVD_02")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_apps_installed_api_uses_selected_discovered_device(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class InstalledRunner:
            def __init__(self):
                self.device_ids = []

            def for_device(self, device):
                self.device_ids.append(device["device_id"])
                return self

            def scan_installed_apps(self, query=""):
                return [{"package_name": "com.example.app", "activity": "com.example.app/.MainActivity"}]

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                runner = InstalledRunner()
                app_module.runner = runner

                result = app_module.api_apps_installed(device_id="device-1")

                self.assertEqual(result["apps"][0]["package_name"], "com.example.app")
                self.assertEqual(runner.device_ids, ["device-1"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

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
                self.add_test_device(app_module.store)
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

    def test_reconcile_leaves_starting_session_untouched_during_capture_start(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class IdleRunner:
            def for_device(self, device):
                return self

            def capture_status(self):
                return {
                    "health": "idle",
                    "exporter": "missing",
                    "frida_hook": "missing",
                    "outdir": "/tmp/previous-runtime-capture",
                    "package": "com.example.app",
                    "mode": "flutter-socks",
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = IdleRunner()
                app = app_module.store.create_app(
                    name="Example",
                    package_name="com.example.app",
                    default_mode="flutter-socks",
                )
                starting = app_module.store.create_session(
                    app_id=app["id"],
                    device_id="device-1",
                    mode="flutter-socks",
                    outdir="/tmp/new-starting-capture",
                    status="starting",
                )

                app_module.reconcile_active_session("device-1")

                self.assertEqual(app_module.store.get_session(starting["id"])["status"], "starting")
                self.assertEqual(app_module.store.active_session("device-1")["id"], starting["id"])
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
                self.add_test_device(app_module.store)
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
                self.add_test_device(app_module.store)
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

    def test_system_doctor_summarizes_environment_ports_network_and_devices(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_network_check = app_module.build_host_network_check
        original_preflight = app_module.system_port_preflight

        class DoctorRunner:
            def for_device(self, device):
                return self

            def env_check(self):
                return {"ok": True, "checks": [{"name": "adb", "ok": True}]}

            def emulator_status(self):
                return {
                    "adb_online": True,
                    "boot_completed": True,
                    "unlocked": True,
                    "android_proxy": "127.0.0.1:7890",
                }

            def capture_status(self):
                return {"health": "idle", "exporter": "missing", "frida_hook": "missing"}

            def google_state(self, **kwargs):
                return {"ok": True, "state": "ok", "play_store_installed": True, "google_account_present": True}

            def frida_server_status(self, *, device_ok):
                return True, "frida-ps reachable"

            def device_network_check(self):
                return {"ok": True, "checks": [{"name": "emulator_dns", "ok": True}], "mode": "maintenance_proxy"}

            def google_play_image_status(self):
                return {
                    "ok": True,
                    "selected": {"package": "system-images;android-36.1;google_apis_playstore;arm64-v8a"},
                    "user_message": "已找到 Google Play system image。",
                    "fix": "",
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = DoctorRunner()
                app_module.build_host_network_check = lambda env: {"ok": True, "checks": [{"name": "host_direct", "ok": True}]}
                app_module.system_port_preflight = lambda: {"ok": True, "ports": []}

                result = app_module.api_system_doctor()

                self.assertTrue(result["doctor"]["ok"])
                self.assertTrue(result["doctor"]["env"]["ok"])
                self.assertTrue(result["doctor"]["ports"]["ok"])
                self.assertTrue(result["doctor"]["host_network"]["ok"])
                self.assertEqual(result["doctor"]["devices"][0]["device_id"], "device-1")
                self.assertEqual(result["doctor"]["devices"][0]["network"]["mode"], "maintenance_proxy")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.build_host_network_check = original_network_check
                app_module.system_port_preflight = original_preflight

    def test_google_play_image_api_reports_selected_playstore_image(self):
        original_runner = app_module.runner

        class GooglePlayImageRunner:
            def google_play_image_status(self):
                return {
                    "ok": True,
                    "selected": {
                        "package": "system-images;android-36.1;google_apis_playstore;arm64-v8a",
                        "tag": "google_apis_playstore",
                    },
                    "user_message": "已找到 Google Play system image。",
                    "fix": "",
                }

        try:
            app_module.runner = GooglePlayImageRunner()

            result = app_module.api_system_google_play_image()

            self.assertTrue(result["google_play_image"]["ok"])
            self.assertEqual(
                result["google_play_image"]["selected"]["package"],
                "system-images;android-36.1;google_apis_playstore;arm64-v8a",
            )
        finally:
            app_module.runner = original_runner

    def test_system_doctor_includes_google_play_image_status(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_network_check = app_module.build_host_network_check
        original_preflight = app_module.system_port_preflight

        class DoctorRunner:
            def for_device(self, device):
                return self

            def env_check(self):
                return {"ok": True, "checks": []}

            def emulator_status(self):
                return {"adb_online": False, "boot_completed": False, "unlocked": False}

            def capture_status(self):
                return {"health": "idle"}

            def google_state(self, **kwargs):
                return {"ok": False, "state": "adb_unavailable"}

            def frida_server_status(self, *, device_ok):
                return False, "adb unavailable"

            def device_network_check(self):
                return {"ok": False, "checks": []}

            def google_play_image_status(self):
                return {
                    "ok": False,
                    "selected": None,
                    "recommended_package": "system-images;android-36.1;google_apis_playstore;arm64-v8a",
                    "user_message": "缺少可用于 Google 登录的 Google Play system image。",
                    "fix": "sdkmanager install",
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = DoctorRunner()
                app_module.build_host_network_check = lambda env: {"ok": True, "checks": []}
                app_module.system_port_preflight = lambda: {"ok": True, "ports": []}

                result = app_module.api_system_doctor()

                self.assertFalse(result["doctor"]["google_play_image"]["ok"])
                self.assertIn("google_apis_playstore", result["doctor"]["google_play_image"]["recommended_package"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.build_host_network_check = original_network_check
                app_module.system_port_preflight = original_preflight

    def test_install_google_play_image_api_uses_runner(self):
        original_runner = app_module.runner

        class GooglePlayImageRunner:
            def install_google_play_system_image(self):
                return {
                    "ok": True,
                    "installed": True,
                    "package": "system-images;android-36.1;google_apis_playstore;arm64-v8a",
                    "user_message": "Google Play system image 安装完成。",
                }

        try:
            app_module.runner = GooglePlayImageRunner()

            result = app_module.api_system_install_google_play_image()

            self.assertTrue(result["google_play_image"]["ok"])
            self.assertTrue(result["google_play_image"]["installed"])
        finally:
            app_module.runner = original_runner

    def test_ensure_google_play_avd_api_uses_selected_device_runner(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class DeviceRunner:
            def create_avd_if_possible(self):
                return {"ok": True, "created": True, "user_message": "已创建默认 AVD。"}

            def avd_status(self):
                return {"ok": True, "avd_name": "AI_Capture_AVD_01"}

        class PoolRunner:
            def for_device(self, device):
                return DeviceRunner()

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = PoolRunner()

                result = app_module.api_ensure_google_play_avd("device-1")

                self.assertTrue(result["avd"]["ok"])
                self.assertTrue(result["create_avd"]["created"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_device_doctor_reports_network_and_frida_state(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class DeviceDoctorRunner:
            def for_device(self, device):
                return self

            def emulator_status(self):
                return {
                    "adb_online": True,
                    "boot_completed": True,
                    "unlocked": True,
                    "android_proxy": "null",
                }

            def capture_status(self):
                return {"health": "idle"}

            def google_state(self, **kwargs):
                return {"ok": True, "state": "ok", "play_store_installed": True, "google_account_present": True}

            def frida_server_status(self, *, device_ok):
                return False, "frida-ps failed"

            def device_network_check(self):
                return {
                    "ok": False,
                    "mode": "direct",
                    "checks": [
                        {
                            "name": "emulator_google",
                            "ok": False,
                            "user_message": "模拟器无法访问 Google。",
                            "fix": "进入维护模式后重试。",
                        }
                    ],
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = DeviceDoctorRunner()

                result = app_module.api_device_doctor("device-1")

                self.assertFalse(result["doctor"]["ok"])
                self.assertFalse(result["doctor"]["frida"]["ok"])
                self.assertFalse(result["doctor"]["network"]["ok"])
                self.assertIn("Google", result["doctor"]["network"]["checks"][0]["user_message"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_device_doctor_accepts_play_store_without_account_in_optional_mode(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_google_required = app_module.GOOGLE_LOGIN_REQUIRED

        class DeviceDoctorRunner:
            def for_device(self, device):
                return self

            def emulator_status(self):
                return {"adb_online": True, "boot_completed": True, "unlocked": True, "android_proxy": "null"}

            def avd_status(self):
                return {"ok": True, "avd_name": "AI_Capture_AVD_01"}

            def capture_status(self):
                return {"health": "idle"}

            def google_state(self, **kwargs):
                return {
                    "ok": False,
                    "state": "not_logged_in",
                    "play_store_installed": True,
                    "google_account_present": False,
                    "user_message": "当前未登录 Google。",
                }

            def frida_server_status(self, *, device_ok):
                return True, "frida-ps reachable"

            def device_network_check(self):
                return {"ok": True, "mode": "direct", "checks": []}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = DeviceDoctorRunner()
                app_module.GOOGLE_LOGIN_REQUIRED = False

                result = app_module.api_device_doctor("device-1")

                self.assertTrue(result["doctor"]["ok"])
                self.assertEqual(result["doctor"]["google"]["state"], "not_logged_in")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.GOOGLE_LOGIN_REQUIRED = original_google_required

    def test_system_prepare_starts_emulator_enters_capture_network_and_prepares_frida(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_preflight = app_module.system_port_preflight

        class PrepareRunner:
            def __init__(self):
                self.calls = []
                self.started = False
                self.frida_ready = False

            def for_device(self, device):
                return self

            def env_check(self):
                return {"ok": True, "checks": []}

            def emulator_status(self):
                return {
                    "adb_online": self.started,
                    "boot_completed": self.started,
                    "unlocked": self.started,
                    "android_proxy": "127.0.0.1:7890" if not self.calls or self.calls[-1] != "capture_network" else "null",
                }

            def start_emulator(self, visible=False):
                self.calls.append("start_emulator")
                self.started = True
                return CommandResult(0, "started", "")

            def capture_status(self):
                return {"health": "idle", "exporter": "missing", "frida_hook": "missing"}

            def google_state(self, **kwargs):
                return {"ok": True, "state": "ok", "play_store_installed": True, "google_account_present": True}

            def frida_server_status(self, *, device_ok):
                return (self.frida_ready, "frida ready" if self.frida_ready else "frida missing")

            def enter_capture_network(self):
                self.calls.append("capture_network")
                return {"ok": True, "network": {"mode": "direct"}}

            def prepare_frida_server(self):
                self.calls.append("prepare_frida")
                self.frida_ready = True
                return {"ok": True, "frida": {"ok": True, "detail": "frida-ps reachable"}}

            def device_network_check(self):
                return {"ok": True, "mode": "direct", "checks": []}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                runner = PrepareRunner()
                app_module.runner = runner
                app_module.system_port_preflight = lambda: {"ok": True, "ports": []}

                result = app_module.api_system_prepare(device_id="device-1", visible=False)

                self.assertTrue(result["prepare"]["ok"])
                self.assertEqual(runner.calls, ["start_emulator", "capture_network", "prepare_frida"])
                self.assertEqual([step["key"] for step in result["prepare"]["steps"]], ["env", "ports", "emulator", "network", "frida"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.system_port_preflight = original_preflight

    def test_system_prepare_waits_for_new_emulator_to_finish_booting(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_preflight = app_module.system_port_preflight
        original_sleep = app_module.time.sleep

        class DelayedBootRunner:
            def __init__(self):
                self.calls = []
                self.status_checks = 0
                self.started = False

            def for_device(self, device):
                return self

            def env_check(self):
                return {"ok": True, "checks": []}

            def emulator_status(self):
                self.status_checks += 1
                ready = self.started and self.status_checks >= 4
                return {
                    "process_running": self.started,
                    "adb_online": ready,
                    "boot_completed": ready,
                    "unlocked": ready,
                    "android_proxy": "null",
                }

            def avd_status(self):
                return {"ok": True, "avd_name": "AI_Capture_AVD_01"}

            def start_emulator(self, visible=False):
                self.calls.append("start_emulator")
                self.started = True
                return CommandResult(0, "started", "")

            def capture_status(self):
                return {"health": "idle", "exporter": "missing", "frida_hook": "missing"}

            def google_state(self, **kwargs):
                return {"ok": True, "state": "ok", "play_store_installed": True, "google_account_present": True}

            def frida_server_status(self, *, device_ok):
                return (True, "frida ready")

            def enter_capture_network(self):
                self.calls.append("capture_network")
                return {"ok": True, "network": {"mode": "direct"}}

            def device_network_check(self):
                return {"ok": True, "mode": "direct", "checks": []}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                runner = DelayedBootRunner()
                app_module.runner = runner
                app_module.system_port_preflight = lambda: {"ok": True, "ports": []}
                app_module.time.sleep = lambda _seconds: None

                result = app_module.api_system_prepare(device_id="device-1", visible=True)

                self.assertTrue(result["prepare"]["ok"])
                self.assertGreaterEqual(runner.status_checks, 4)
                self.assertEqual(runner.calls, ["start_emulator", "capture_network"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.system_port_preflight = original_preflight
                app_module.time.sleep = original_sleep

    def test_system_prepare_waits_for_cold_boot_network_to_become_ready(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_preflight = app_module.system_port_preflight
        original_sleep = app_module.time.sleep

        class DelayedNetworkRunner:
            def __init__(self):
                self.calls = []
                self.network_checks = 0

            def for_device(self, device):
                return self

            def env_check(self):
                return {"ok": True, "checks": []}

            def emulator_status(self):
                return {
                    "adb_online": True,
                    "boot_completed": True,
                    "unlocked": True,
                    "android_proxy": "null",
                }

            def capture_status(self):
                return {"health": "idle", "exporter": "missing", "frida_hook": "missing"}

            def google_state(self, **kwargs):
                return {"ok": True, "state": "ok", "play_store_installed": True, "google_account_present": True}

            def frida_server_status(self, *, device_ok):
                return (True, "frida ready")

            def enter_capture_network(self):
                self.calls.append("capture_network")
                return {"ok": True, "network": {"mode": "direct"}}

            def device_network_check(self):
                self.network_checks += 1
                return {
                    "ok": self.network_checks >= 2,
                    "mode": "direct",
                    "checks": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                runner = DelayedNetworkRunner()
                app_module.runner = runner
                app_module.system_port_preflight = lambda: {"ok": True, "ports": []}
                app_module.time.sleep = lambda _seconds: None

                result = app_module.api_system_prepare(device_id="device-1", visible=False)

                self.assertTrue(result["prepare"]["ok"])
                self.assertGreaterEqual(runner.network_checks, 2)
                self.assertEqual(runner.calls, ["capture_network"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.system_port_preflight = original_preflight
                app_module.time.sleep = original_sleep

    def test_system_prepare_creates_default_avd_when_system_image_is_available(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_preflight = app_module.system_port_preflight

        class PrepareRunner:
            def __init__(self):
                self.calls = []
                self.avd_exists = False
                self.started = False

            def for_device(self, device):
                return self

            def env_check(self):
                return {"ok": True, "checks": []}

            def emulator_status(self):
                return {"adb_online": self.started, "boot_completed": self.started, "unlocked": self.started}

            def avd_status(self):
                return {
                    "ok": self.avd_exists,
                    "avd_name": "AI_Capture_AVD_01",
                    "user_message": "AVD exists" if self.avd_exists else "AVD missing",
                    "fix": "create AVD",
                }

            def create_avd_if_possible(self):
                self.calls.append("create_avd")
                self.avd_exists = True
                return {"ok": True, "created": True, "user_message": "created"}

            def start_emulator(self, visible=False):
                self.calls.append("start_emulator")
                self.started = True
                return CommandResult(0, "started", "")

            def capture_status(self):
                return {"health": "idle", "exporter": "missing", "frida_hook": "missing"}

            def google_state(self, **kwargs):
                return {"ok": True, "state": "ok", "play_store_installed": True, "google_account_present": True}

            def frida_server_status(self, *, device_ok):
                return (True, "frida ready")

            def enter_capture_network(self):
                self.calls.append("capture_network")
                return {"ok": True, "network": {"mode": "direct"}}

            def device_network_check(self):
                return {"ok": True, "mode": "direct", "checks": []}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                runner = PrepareRunner()
                app_module.runner = runner
                app_module.system_port_preflight = lambda: {"ok": True, "ports": []}

                result = app_module.api_system_prepare(device_id="device-1", visible=False)

                self.assertTrue(result["prepare"]["ok"])
                self.assertEqual(runner.calls, ["create_avd", "start_emulator", "capture_network"])
                emulator_step = next(step for step in result["prepare"]["steps"] if step["key"] == "emulator")
                self.assertEqual(emulator_step["create_avd"]["user_message"], "created")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.system_port_preflight = original_preflight

    def test_system_prepare_blocks_with_clear_message_when_default_avd_cannot_be_created(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_preflight = app_module.system_port_preflight

        class PrepareRunner:
            def __init__(self):
                self.calls = []

            def for_device(self, device):
                return self

            def env_check(self):
                return {"ok": True, "checks": []}

            def emulator_status(self):
                return {"adb_online": False, "boot_completed": False, "unlocked": False}

            def avd_status(self):
                return {"ok": False, "avd_name": "AI_Capture_AVD_01", "user_message": "AVD missing", "fix": "create AVD"}

            def create_avd_if_possible(self):
                self.calls.append("create_avd")
                return {
                    "ok": False,
                    "created": False,
                    "user_message": "没有找到可直接创建模拟器的 Android system image。",
                    "fix": "请安装 Google APIs system image。",
                }

            def capture_status(self):
                return {"health": "idle", "exporter": "missing", "frida_hook": "missing"}

            def google_state(self, **kwargs):
                return {"ok": False, "state": "adb_unavailable"}

            def frida_server_status(self, *, device_ok):
                return (False, "adb unavailable")

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                runner = PrepareRunner()
                app_module.runner = runner
                app_module.system_port_preflight = lambda: {"ok": True, "ports": []}

                result = app_module.api_system_prepare(device_id="device-1", visible=False)

                self.assertFalse(result["prepare"]["ok"])
                self.assertEqual(runner.calls, ["create_avd"])
                self.assertIn("Google APIs system image", result["prepare"]["user_message"])
                self.assertEqual([step["key"] for step in result["prepare"]["steps"]], ["env", "ports", "emulator"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.system_port_preflight = original_preflight

    def test_system_prepare_installs_google_play_image_before_creating_default_avd(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_preflight = app_module.system_port_preflight

        class PrepareRunner:
            def __init__(self):
                self.calls = []
                self.image_installed = False
                self.avd_exists = False
                self.started = False

            def for_device(self, device):
                return self

            def env_check(self):
                return {"ok": True, "checks": []}

            def emulator_status(self):
                return {"adb_online": self.started, "boot_completed": self.started, "unlocked": self.started}

            def avd_status(self):
                return {"ok": self.avd_exists, "avd_name": "AI_Capture_AVD_01", "available_avds": []}

            def create_avd_if_possible(self):
                self.calls.append("create_avd")
                if not self.image_installed:
                    return {
                        "ok": False,
                        "created": False,
                        "user_message": "没有找到可用于 Google 登录的 Google Play system image。",
                        "fix": "sdkmanager google_apis_playstore",
                    }
                self.avd_exists = True
                return {"ok": True, "created": True, "user_message": "created"}

            def install_google_play_system_image(self):
                self.calls.append("install_image")
                self.image_installed = True
                return {"ok": True, "installed": True, "user_message": "installed"}

            def start_emulator(self, visible=False):
                self.calls.append("start_emulator")
                self.started = True
                return CommandResult(0, "started", "")

            def capture_status(self):
                return {"health": "idle", "exporter": "missing", "frida_hook": "missing"}

            def google_state(self, **kwargs):
                return {"ok": True, "state": "ok", "play_store_installed": True, "google_account_present": True}

            def frida_server_status(self, *, device_ok):
                return True, "frida ready"

            def enter_capture_network(self):
                self.calls.append("capture_network")
                return {"ok": True, "network": {"mode": "direct"}}

            def device_network_check(self):
                return {"ok": True, "mode": "direct", "checks": []}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                runner = PrepareRunner()
                app_module.runner = runner
                app_module.system_port_preflight = lambda: {"ok": True, "ports": []}

                result = app_module.api_system_prepare(device_id="device-1", visible=False)

                self.assertTrue(result["prepare"]["ok"])
                self.assertEqual(runner.calls, ["create_avd", "install_image", "create_avd", "start_emulator", "capture_network"])
                emulator_step = next(step for step in result["prepare"]["steps"] if step["key"] == "emulator")
                self.assertTrue(emulator_step["install_google_play_image"]["ok"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.system_port_preflight = original_preflight

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
                self.add_test_device(app_module.store)
                app_module.runner = SetupRunner()

                result = app_module.api_setup_state()

                self.assertFalse(result["setup"]["completed"])
                self.assertEqual(result["setup"]["current_step"], "env")
                self.assertEqual(result["setup"]["steps"][0]["key"], "env")
                self.assertFalse(result["setup"]["ready_to_complete"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_setup_state_treats_google_account_as_optional_when_login_is_not_required(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_google_required = app_module.GOOGLE_LOGIN_REQUIRED

        class SetupRunner:
            def for_device(self, device):
                return self

            def emulator_status(self):
                return {"adb_online": True, "boot_completed": True, "unlocked": True}

            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

            def google_state(self, **kwargs):
                return {
                    "ok": False,
                    "state": "not_logged_in",
                    "play_store_installed": True,
                    "google_account_present": False,
                    "user_message": "请先登录 Google。",
                    "fix": "打开 Google 登录入口。",
                }

            def frida_server_status(self, *, device_ok):
                return True, "frida-ps reachable"

            def env_check(self):
                return {"ok": True, "checks": []}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = SetupRunner()
                app_module.GOOGLE_LOGIN_REQUIRED = False
                app_module.store.set_system_value(app_module.SETUP_CHECKED_KEY, "1")

                result = app_module.api_setup_state()["setup"]
                google_step = next(step for step in result["steps"] if step["key"] == "google")

                self.assertTrue(google_step["ok"])
                self.assertEqual(result["current_step"], "app")
                self.assertFalse(result["google_login_required"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.GOOGLE_LOGIN_REQUIRED = original_google_required

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
                self.add_test_device(app_module.store)
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
                self.add_test_device(app_module.store)
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
                self.add_test_device(app_module.store)
                self.add_test_device(app_module.store, device_id="device-2", adb_serial="emulator-5556", proxy_port=9100, web_port=9101, frida_port=27142, resident=0, idle_release_minutes=10)
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
                self.add_test_device(app_module.store)
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
                self.add_test_device(app_module.store)
                self.add_test_device(app_module.store, device_id="device-2", adb_serial="emulator-5556", proxy_port=9100, web_port=9101, frida_port=27142, resident=0, idle_release_minutes=10)
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
                self.add_test_device(app_module.store)
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
                self.add_test_device(app_module.store)
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

    def test_devices_api_lists_connected_devices_and_system_state(self):
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
                self.add_test_device(app_module.store)
                app_module.runner = DeviceStatusRunner()

                result = app_module.api_list_devices()

                self.assertEqual(result["system"]["state"], "running")
                self.assertEqual(len(result["devices"]), 1)
                self.assertEqual(result["devices"][0]["device_id"], "device-1")
                self.assertIn("emulator", result["devices"][0])
                self.assertEqual(result["devices"][0]["resident"], 1)
                self.assertEqual(result["devices"][0]["runtime_policy"], "resident")
                self.assertEqual(result["devices"][0]["release_behavior"], "keep_emulator")
                self.assertFalse(result["devices"][0]["can_shutdown"])
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
                self.add_test_device(app_module.store)
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
                self.add_test_device(app_module.store)
                runner = GoogleLoginRunner()
                app_module.runner = runner

                result = app_module.api_open_google_login("device-1")

                self.assertTrue(result["ok"])
                self.assertTrue(runner.opened)
                self.assertEqual(result["google_state"]["state"], "not_logged_in")
                device = app_module.store.get_device("device-1")
                self.assertEqual(device["lease_status"], "leased")
                self.assertIsNotNone(device["last_lease_at"])
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
                self.add_test_device(app_module.store)
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

    def test_start_capture_auto_falls_back_to_flutter_socks_when_system_is_not_ready(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class AutoFallbackRunner:
            def __init__(self):
                self.health_modes = []
                self.started_modes = []
                self.network_switches = 0

            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

            def google_state(self, **kwargs):
                return {"ok": True, "state": "ok", "play_store_installed": True, "google_account_present": True}

            def enter_capture_network(self):
                self.network_switches += 1
                return {"ok": True, "mode": "direct"}

            def health_check(self, *, package_name, mode, activity=""):
                self.health_modes.append(mode)
                if mode == "system":
                    return {"ok": False, "checks": [{"name": "proxy", "ok": False}], "resolved_activity": activity}
                return {"ok": True, "checks": [], "resolved_activity": activity}

            def make_outdir(self, app_name):
                return Path(tempfile.gettempdir()) / f"{app_name}-{len(self.started_modes)}"

            def start_capture(self, **kwargs):
                self.started_modes.append(kwargs["mode"])
                return CommandResult(0, f"mode: {kwargs['mode']}\n", "")

            def stop_capture(self):
                return CommandResult(0, "", "")

            def clear_android_proxy(self):
                return CommandResult(0, "", "")

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                runner = AutoFallbackRunner()
                app_module.runner = runner
                app = app_module.store.create_app(
                    platform="android",
                    name="Generic",
                    package_name="com.example.generic",
                    activity="com.example.generic/.MainActivity",
                    default_mode="auto",
                )

                result = app_module.api_start_capture(
                    app_module.CaptureStartPayload(app_id=app["id"], device_id="device-1", mode="auto")
                )

                self.assertEqual(result["session"]["mode"], "flutter-socks")
                self.assertEqual(result["requested_mode"], "auto")
                self.assertEqual(result["mode_attempts"][0]["mode"], "system")
                self.assertEqual(result["mode_attempts"][0]["status"], "failed")
                self.assertEqual(result["mode_attempts"][1]["mode"], "flutter-socks")
                self.assertEqual(result["mode_attempts"][1]["status"], "running")
                self.assertEqual(runner.health_modes, ["system", "flutter-socks"])
                self.assertEqual(runner.started_modes, ["flutter-socks"])
                self.assertEqual(runner.network_switches, 1)
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

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
                self.add_test_device(app_module.store)
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
        original_store = app_module.store
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

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = MissingGoogleRunner()
                app_module.GOOGLE_LOGIN_REQUIRED = True

                with self.assertRaises(HTTPException) as ctx:
                    app_module.ensure_emulator_ready_for_install(device_id="device-1")

                self.assertEqual(ctx.exception.status_code, 409)
                self.assertEqual(ctx.exception.detail["state"], "not_logged_in")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.GOOGLE_LOGIN_REQUIRED = original_google_required

    def test_package_install_readiness_allows_missing_google_account_in_optional_mode(self):
        original_store = app_module.store
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

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = MissingGoogleRunner()
                app_module.GOOGLE_LOGIN_REQUIRED = False

                app_module.ensure_emulator_ready_for_install(device_id="device-1")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.GOOGLE_LOGIN_REQUIRED = original_google_required

    def test_package_install_readiness_still_rejects_missing_play_store_in_optional_mode(self):
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
                    "fix": "请使用 Google Play AVD 重建设备。",
                }

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = MissingPlayStoreRunner()
                app_module.GOOGLE_LOGIN_REQUIRED = False

                with self.assertRaises(HTTPException) as ctx:
                    app_module.ensure_emulator_ready_for_install(device_id="device-1")

                self.assertEqual(ctx.exception.status_code, 409)
                self.assertEqual(ctx.exception.detail["state"], "missing_play_store")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.GOOGLE_LOGIN_REQUIRED = original_google_required

    def test_jenkins_install_reuses_matching_archive_already_installed_on_device(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_source = app_module.jenkins_source
        original_latest_apks_dir = app_module.LATEST_APKS_DIR
        original_google_required = app_module.GOOGLE_LOGIN_REQUIRED

        class CachedInstallRunner:
            def for_device(self, device):
                return self

            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

            def emulator_status(self):
                return {"adb_online": True, "boot_completed": True, "unlocked": True}

            def google_state(self, **kwargs):
                return {
                    "ok": False,
                    "state": "not_logged_in",
                    "play_store_installed": True,
                    "google_account_present": False,
                }

            def package_info(self, package_name):
                return {
                    "package_name": package_name,
                    "installed": True,
                    "version_code": "1",
                    "version_name": "1.0.0",
                    "last_update_time": "2026-08-10 18:13:40",
                    "installer_package": "null",
                    "signature_hint": "3e53e186",
                    "activity": "com.example.glp1_tracker/.MainActivity",
                    "error": "",
                }

        class UnexpectedDownloadSource:
            def download_package(self, **kwargs):
                raise AssertionError("matching installed Jenkins build must not be downloaded again")

        with tempfile.TemporaryDirectory() as tmp:
            try:
                root = Path(tmp)
                app_module.store = CaptureStore(root / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = CachedInstallRunner()
                app_module.jenkins_source = UnexpectedDownloadSource()
                app_module.LATEST_APKS_DIR = root / "apks" / "latest"
                app_module.GOOGLE_LOGIN_REQUIRED = False
                app = app_module.store.create_app(
                    platform="android",
                    environment="test",
                    name="GLP Tracker 测试包",
                    package_name="com.example.glp1_tracker",
                    activity="com.example.glp1_tracker/.MainActivity",
                    default_mode="flutter-socks",
                )
                archive_dir = app_module.LATEST_APKS_DIR / "com.example.glp1_tracker"
                archive_dir.mkdir(parents=True)
                (archive_dir / "glp-1-tracker_158.apk").write_bytes(b"apk")
                (archive_dir / "metadata.json").write_text(
                    json.dumps(
                        {
                            "package_name": "com.example.glp1_tracker",
                            "environment": "test",
                            "uploaded_filename": "glp-1-tracker_158.apk",
                            "apk_info": {"version_code": "1", "version_name": "1.0.0"},
                            "apk_files": ["glp-1-tracker_158.apk"],
                        }
                    ),
                    encoding="utf-8",
                )
                app_module.store.update_app_version(app["id"], {"apk_archive_path": str(archive_dir)})

                result = app_module.api_install_jenkins_package(
                    app_module.JenkinsInstallPayload(
                        device_id="device-1",
                        job_name="glp-1-tracker",
                        build_number=158,
                        artifact_relative_path="glp-1-tracker_158.apk",
                        environment="test",
                    )
                )

                self.assertTrue(result["ok"])
                self.assertTrue(result["install"]["cached"])
                self.assertEqual(result["app"]["package_name"], "com.example.glp1_tracker")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.jenkins_source = original_source
                app_module.LATEST_APKS_DIR = original_latest_apks_dir
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
                self.add_test_device(app_module.store)
                self.add_test_device(app_module.store, device_id="device-2", adb_serial="emulator-5556", proxy_port=9100, web_port=9101, frida_port=27142, resident=0, idle_release_minutes=10)
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
                self.add_test_device(app_module.store)

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
                self.add_test_device(app_module.store)
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
                self.add_test_device(app_module.store)
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
                self.add_test_device(app_module.store)
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
                self.add_test_device(app_module.store)
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
                self.add_test_device(app_module.store)
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
                self.add_test_device(app_module.store)
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
                self.add_test_device(app_module.store)
                self.add_test_device(app_module.store, device_id="device-2", adb_serial="emulator-5556", proxy_port=9100, web_port=9101, frida_port=27142, resident=0, idle_release_minutes=10)
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
                self.add_test_device(app_module.store)
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
                self.add_test_device(app_module.store)
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
                self.add_test_device(app_module.store)
                self.add_test_device(app_module.store, device_id="device-3", adb_serial="emulator-5558", proxy_port=9110, web_port=9111, frida_port=27242, resident=0, idle_release_minutes=10)
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

    def test_stop_capture_clears_android_proxy(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class StopRunner:
            def __init__(self):
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

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store, resident=0, idle_release_minutes=10)
                app = app_module.store.create_app(
                    platform="android",
                    name="Chrome",
                    package_name="com.android.chrome",
                    activity="com.android.chrome/com.google.android.apps.chrome.Main",
                    default_mode="system",
                )
                session = app_module.store.create_session(
                    app_id=app["id"],
                    device_id="device-1",
                    mode="system",
                    outdir=str(Path(tmp) / "capture"),
                    status="running",
                )
                app_module.store.update_device("device-1", current_session_id=session["id"], lease_status="running")
                runner = StopRunner()
                app_module.runner = runner

                result = app_module.api_stop_capture(device_id="device-1")

                self.assertTrue(result["ok"])
                self.assertTrue(runner.stopped)
                self.assertTrue(runner.cleared_proxy)
                self.assertEqual(result["proxy"]["stdout"], "proxy cleared")
                self.assertEqual(result["session"]["status"], "stopped")
                self.assertIsNone(app_module.store.active_session(device_id="device-1"))
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_stop_capture_session_clears_android_proxy(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class StopRunner:
            def __init__(self):
                self.cleared_proxy = False

            def for_device(self, device):
                return self

            def stop_capture(self):
                return CommandResult(0, "stopped", "")

            def clear_android_proxy(self):
                self.cleared_proxy = True
                return CommandResult(0, "proxy cleared", "")

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store, resident=0, idle_release_minutes=10)
                app = app_module.store.create_app(
                    platform="android",
                    name="Chrome",
                    package_name="com.android.chrome",
                    activity="com.android.chrome/com.google.android.apps.chrome.Main",
                    default_mode="system",
                )
                session = app_module.store.create_session(
                    app_id=app["id"],
                    device_id="device-1",
                    mode="system",
                    outdir=str(Path(tmp) / "capture"),
                    status="running",
                )
                app_module.store.update_device("device-1", current_session_id=session["id"], lease_status="running")
                runner = StopRunner()
                app_module.runner = runner

                result = app_module.api_stop_capture_session(session["id"])

                self.assertTrue(result["ok"])
                self.assertTrue(runner.cleared_proxy)
                self.assertEqual(result["proxy"]["stdout"], "proxy cleared")
                self.assertEqual(result["session"]["status"], "stopped")
                self.assertIsNone(app_module.store.active_session(device_id="device-1"))
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
                self.add_test_device(app_module.store)
                self.add_test_device(app_module.store, device_id="device-3", adb_serial="emulator-5558", proxy_port=9110, web_port=9111, frida_port=27242, resident=0, idle_release_minutes=10)
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

    def test_auto_release_preserves_recent_interactive_lease(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_lease_seconds = app_module.INTERACTIVE_LEASE_SECONDS

        class ReleaseRunner:
            def __init__(self):
                self.killed = False

            def for_device(self, device):
                return self

            def emulator_status(self):
                return {"adb_online": True, "process_running": True}

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
                self.add_test_device(app_module.store, resident=0, idle_release_minutes=10)
                leased_at = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat(timespec="seconds")
                app_module.store.update_device(
                    "device-1",
                    lease_status="leased",
                    last_active_at=leased_at,
                    last_lease_at=leased_at,
                )
                runner = ReleaseRunner()
                app_module.runner = runner
                app_module.INTERACTIVE_LEASE_SECONDS = 30 * 60

                result = app_module.auto_release_idle_on_demand_devices()

                self.assertEqual(result, [])
                self.assertFalse(runner.killed)
                self.assertEqual(app_module.store.get_device("device-1")["lease_status"], "leased")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.INTERACTIVE_LEASE_SECONDS = original_lease_seconds

    def test_auto_release_expires_stale_interactive_lease(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_lease_seconds = app_module.INTERACTIVE_LEASE_SECONDS

        class ReleaseRunner:
            def __init__(self):
                self.killed = False

            def for_device(self, device):
                return self

            def emulator_status(self):
                return {"adb_online": True, "process_running": True}

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
                self.add_test_device(app_module.store, resident=0, idle_release_minutes=10)
                leased_at = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat(timespec="seconds")
                app_module.store.update_device(
                    "device-1",
                    lease_status="leased",
                    last_active_at=leased_at,
                    last_lease_at=leased_at,
                )
                runner = ReleaseRunner()
                app_module.runner = runner
                app_module.INTERACTIVE_LEASE_SECONDS = 30 * 60

                result = app_module.auto_release_idle_on_demand_devices()

                self.assertEqual(len(result), 1)
                self.assertTrue(runner.killed)
                self.assertEqual(app_module.store.get_device("device-1")["lease_status"], "idle")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.INTERACTIVE_LEASE_SECONDS = original_lease_seconds

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
                self.add_test_device(app_module.store)
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
                self.add_test_device(app_module.store)
                self.add_test_device(app_module.store, device_id="device-2", adb_serial="emulator-5556", proxy_port=9100, web_port=9101, frida_port=27142, resident=0, idle_release_minutes=10)
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
                self.add_test_device(app_module.store)
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

    def test_validate_capture_auto_falls_back_to_flutter_socks(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_scan_capture = app_module.scan_capture

        class AutoValidateRunner:
            def __init__(self, root):
                self.root = Path(root)
                self.health_modes = []
                self.started_modes = []
                self.stopped = 0
                self.cleared = 0

            def capture_status(self):
                return {"exporter": "missing", "frida_hook": "missing", "health": "idle"}

            def google_state(self, **kwargs):
                return {"ok": True, "state": "ok", "play_store_installed": True, "google_account_present": True}

            def enter_capture_network(self):
                return {"ok": True}

            def health_check(self, *, package_name, mode, activity=""):
                self.health_modes.append(mode)
                if mode == "system":
                    return {"ok": False, "checks": [], "resolved_activity": activity}
                return {"ok": True, "checks": [], "resolved_activity": activity}

            def launch_app(self, **kwargs):
                return CommandResult(0, "launched", "")

            def make_outdir(self, app_name):
                return self.root / app_name

            def start_capture(self, **kwargs):
                self.started_modes.append(kwargs["mode"])
                return CommandResult(0, "started", "")

            def stop_capture(self):
                self.stopped += 1
                return CommandResult(0, "stopped", "")

            def clear_android_proxy(self):
                self.cleared += 1
                return CommandResult(0, "cleared", "")

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                runner = AutoValidateRunner(tmp)
                app_module.runner = runner
                app_module.scan_capture = lambda outdir: [
                    {"has_response_json": True, "has_request_json": False}
                ]
                app = app_module.store.create_app(
                    platform="android",
                    name="Generic",
                    package_name="com.example.generic",
                    activity="com.example.generic/.MainActivity",
                    default_mode="auto",
                )

                result = app_module.api_validate_capture(app["id"], device_id="device-1")

                self.assertTrue(result["ok"])
                self.assertEqual(result["validation"]["status"], "passed")
                self.assertEqual(result["validation"]["session"]["mode"], "flutter-socks")
                self.assertEqual(result["mode_attempts"][0]["mode"], "system")
                self.assertEqual(result["mode_attempts"][0]["status"], "failed")
                self.assertEqual(result["mode_attempts"][1]["mode"], "flutter-socks")
                self.assertEqual(runner.health_modes, ["system", "flutter-socks"])
                self.assertEqual(runner.started_modes, ["flutter-socks"])
                self.assertEqual(runner.cleared, 2)
                self.assertEqual(app_module.store.get_app(app["id"])["last_success_mode"], "flutter-socks")
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.scan_capture = original_scan_capture

    def test_logcat_app_source_requires_valid_package_name(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class OnlineRunner:
            def for_device(self, device):
                return self

            def emulator_status(self):
                return {"adb_online": True}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = OnlineRunner()

                for package_name in ("", "com.example.app;rm -rf /", "com..example"):
                    with self.subTest(package_name=package_name):
                        with self.assertRaises(HTTPException) as ctx:
                            app_module.api_start_logcat(
                                "device-1",
                                app_module.LogcatStartPayload(
                                    source="app",
                                    package_name=package_name,
                                ),
                            )

                        self.assertEqual(ctx.exception.status_code, 422)
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_logcat_start_rejects_offline_device(self):
        original_store = app_module.store
        original_runner = app_module.runner

        class OfflineRunner:
            def for_device(self, device):
                return self

            def emulator_status(self):
                return {"adb_online": False, "boot_completed": False}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = OfflineRunner()

                with self.assertRaises(HTTPException) as ctx:
                    app_module.api_start_logcat(
                        "device-1",
                        app_module.LogcatStartPayload(source="system"),
                    )

                self.assertEqual(ctx.exception.status_code, 409)
                self.assertEqual(
                    {
                        "message": "emulator is not online",
                        "user_message": "当前设备未连接，无法读取 Android 日志。",
                        "fix": "请先启动模拟器并等待设备进入在线状态。",
                    },
                    ctx.exception.detail,
                )
            finally:
                app_module.store = original_store
                app_module.runner = original_runner

    def test_logcat_lifecycle_is_device_scoped(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_service = app_module.logcat_service

        class OnlineRunner:
            def for_device(self, device):
                return self

            def emulator_status(self):
                return {"adb_online": True}

            def adb_command_prefix(self):
                return ["adb", "-s", "emulator-5554"]

            def process_environment(self):
                return {"DEVICE": "device-1"}

            def adb(self, args, timeout=20):
                self.last_adb = args
                return CommandResult(0, "2468\n", "")

        class FakeLogcatService:
            def __init__(self):
                self.calls = []

            def start(self, **kwargs):
                self.calls.append(("start", kwargs))
                return {
                    "device_id": kwargs["device_id"],
                    "source": kwargs["source"],
                    "state": "streaming",
                    "package_name": kwargs["package_name"],
                    "next_cursor": 0,
                    "truncated": False,
                    "entries": [],
                }

            def poll(self, device_id, *, after, limit):
                self.calls.append(("poll", {"device_id": device_id, "after": after, "limit": limit}))
                return {
                    "device_id": device_id,
                    "source": "app",
                    "state": "streaming",
                    "package_name": "com.example.app",
                    "next_cursor": 12,
                    "truncated": False,
                    "entries": [{"cursor": 12, "message": "ready"}],
                }

            def clear(self, device_id):
                self.calls.append(("clear", {"device_id": device_id}))
                return {"device_id": device_id, "state": "streaming", "next_cursor": 12}

            def stop(self, device_id):
                self.calls.append(("stop", {"device_id": device_id}))
                return {"device_id": device_id, "state": "stopped", "next_cursor": 12}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                online_runner = OnlineRunner()
                app_module.runner = online_runner
                service = FakeLogcatService()
                app_module.logcat_service = service

                started = app_module.api_start_logcat(
                    "device-1",
                    app_module.LogcatStartPayload(
                        source="app",
                        package_name="com.example.app",
                    ),
                )
                polled = app_module.api_poll_logcat("device-1", after=5, limit=5000)
                cleared = app_module.api_clear_logcat("device-1")
                stopped = app_module.api_stop_logcat("device-1")

                start_call = dict(service.calls[0][1])
                pid_resolver = start_call.pop("pid_resolver")
                self.assertEqual(
                    {
                        "device_id": "device-1",
                        "adb_command": ["adb", "-s", "emulator-5554"],
                        "process_environment": {"DEVICE": "device-1"},
                        "source": "app",
                        "package_name": "com.example.app",
                    },
                    start_call,
                )
                self.assertEqual(2468, pid_resolver("com.example.app"))
                self.assertEqual(
                    [
                        ("poll", {"device_id": "device-1", "after": 5, "limit": 1000}),
                        ("clear", {"device_id": "device-1"}),
                        ("stop", {"device_id": "device-1"}),
                    ],
                    service.calls[1:],
                )
                self.assertEqual("streaming", started["state"])
                self.assertEqual([{"cursor": 12, "message": "ready"}], polled["entries"])
                self.assertEqual(
                    {"device_id": "device-1", "state": "streaming", "next_cursor": 12},
                    cleared,
                )
                self.assertEqual(
                    {"device_id": "device-1", "state": "stopped", "next_cursor": 12},
                    stopped,
                )
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.logcat_service = original_service

    def test_release_device_stops_only_that_device_logcat(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_service = app_module.logcat_service

        class ReleaseRunner:
            def for_device(self, device):
                return self

            def stop_capture(self):
                return CommandResult(0, "stopped capture", "")

            def clear_android_proxy(self):
                return CommandResult(0, "cleared proxy", "")

        class FakeLogcatService:
            def __init__(self):
                self.stopped = []

            def stop(self, device_id):
                self.stopped.append(device_id)
                return {"device_id": device_id, "state": "stopped"}

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store, resident=1)
                app_module.runner = ReleaseRunner()
                service = FakeLogcatService()
                app_module.logcat_service = service

                result = app_module.release_device_runtime("device-1")

                self.assertEqual(["device-1"], service.stopped)
                self.assertTrue(result["ok"])
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.logcat_service = original_service

    def test_shutdown_stops_all_logcat_sessions(self):
        original_service = app_module.logcat_service
        original_clear = app_module.clear_project_capture_records

        class FakeLogcatService:
            def __init__(self):
                self.stop_all_calls = 0

            def stop_all(self):
                self.stop_all_calls += 1

        try:
            service = FakeLogcatService()
            app_module.logcat_service = service
            app_module.clear_project_capture_records = lambda: None

            app_module.shutdown()

            self.assertEqual(1, service.stop_all_calls)
        finally:
            app_module.logcat_service = original_service
            app_module.clear_project_capture_records = original_clear

    def test_system_sleep_stops_all_logcat_sessions(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_service = app_module.logcat_service

        class SleepRunner:
            def for_device(self, device):
                return self

            def stop_capture(self):
                return CommandResult(0, "stopped capture", "")

            def clear_android_proxy(self):
                return CommandResult(0, "cleared proxy", "")

            def stop_emulator(self):
                return CommandResult(0, "stopped emulator", "")

        class FakeLogcatService:
            def __init__(self):
                self.stop_all_calls = 0

            def stop_all(self):
                self.stop_all_calls += 1

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = SleepRunner()
                service = FakeLogcatService()
                app_module.logcat_service = service

                app_module.api_system_sleep()

                self.assertEqual(1, service.stop_all_calls)
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.logcat_service = original_service

    def test_cleanup_stops_device_logcat_session(self):
        original_store = app_module.store
        original_runner = app_module.runner
        original_service = app_module.logcat_service

        class CleanupRunner:
            def for_device(self, device):
                return self

            def stop_capture(self):
                return CommandResult(0, "stopped capture", "")

            def clear_android_proxy(self):
                return CommandResult(0, "cleared proxy", "")

        class FakeLogcatService:
            def __init__(self):
                self.stopped = []

            def stop(self, device_id):
                self.stopped.append(device_id)

        with tempfile.TemporaryDirectory() as tmp:
            try:
                app_module.store = CaptureStore(Path(tmp) / "console.db")
                self.add_test_device(app_module.store)
                app_module.runner = CleanupRunner()
                service = FakeLogcatService()
                app_module.logcat_service = service

                app_module.api_cleanup("device-1")

                self.assertEqual(["device-1"], service.stopped)
            finally:
                app_module.store = original_store
                app_module.runner = original_runner
                app_module.logcat_service = original_service


if __name__ == "__main__":
    unittest.main()

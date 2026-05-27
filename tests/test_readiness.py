import unittest

from capture_console.readiness import build_readiness_report


class ReadinessTests(unittest.TestCase):
    def test_reports_green_when_target_app_capture_has_flows(self):
        app = {
            "id": 1,
            "name": "MelodyCraft 正式包",
            "package_name": "com.mi.ai.music",
            "default_mode": "flutter-socks",
        }
        health = {
            "ok": True,
            "checks": [
                {"name": "retained_emulator", "ok": True, "detail": "ok", "user_message": "保留模拟器正确。"},
                {"name": "adb_device", "ok": True, "detail": "emulator-5554", "user_message": "模拟器在线。"},
                {"name": "android_unlocked", "ok": True, "detail": "RUNNING_UNLOCKED", "user_message": "模拟器已解锁。"},
                {"name": "package_activity", "ok": True, "detail": "com.mi.ai.music/.MainActivity", "user_message": "应用可启动。"},
                {"name": "frida_server", "ok": True, "detail": "frida reachable", "user_message": "Frida 可用。"},
            ],
        }
        capture_status = {"exporter": "running", "frida_hook": "running", "proxy": "listening on 9090"}
        session = {"id": 3, "package_name": "com.mi.ai.music", "status": "running"}

        report = build_readiness_report(
            app=app,
            health=health,
            capture_status=capture_status,
            active_session=session,
            flow_count=4,
            foreground="mCurrentFocus=Window{abc u0 com.mi.ai.music/com.mi.ai.music.MainActivity}",
        )

        self.assertEqual(report["state"], "ok")
        self.assertEqual(report["checks"][-1]["name"], "target_traffic")
        self.assertEqual(report["checks"][-1]["state"], "ok")

    def test_reports_warning_while_capture_waits_for_target_traffic(self):
        app = {"id": 1, "name": "MelodyCraft", "package_name": "com.mi.ai.music", "default_mode": "flutter-socks"}
        health = {
            "ok": True,
            "checks": [
                {"name": "retained_emulator", "ok": True, "detail": "ok", "user_message": "保留模拟器正确。"},
                {"name": "adb_device", "ok": True, "detail": "emulator-5554", "user_message": "模拟器在线。"},
                {"name": "android_unlocked", "ok": True, "detail": "RUNNING_UNLOCKED", "user_message": "模拟器已解锁。"},
                {"name": "package_activity", "ok": True, "detail": "com.mi.ai.music/.MainActivity", "user_message": "应用可启动。"},
                {"name": "frida_server", "ok": True, "detail": "frida reachable", "user_message": "Frida 可用。"},
            ],
        }

        report = build_readiness_report(
            app=app,
            health=health,
            capture_status={"exporter": "running", "frida_hook": "running", "proxy": "listening on 9090"},
            active_session={"id": 3, "package_name": "com.mi.ai.music", "status": "running"},
            flow_count=0,
            foreground="mCurrentFocus=Window{abc u0 com.mi.ai.music/com.mi.ai.music.MainActivity}",
        )

        self.assertEqual(report["state"], "warn")
        traffic = next(check for check in report["checks"] if check["name"] == "target_traffic")
        self.assertEqual(traffic["state"], "warn")
        self.assertIn("等待", traffic["summary"])

    def test_running_hook_pid_does_not_override_unreachable_frida_server(self):
        app = {"id": 1, "name": "MelodyCraft", "package_name": "com.mi.ai.music", "default_mode": "flutter-socks"}
        health = {
            "ok": False,
            "checks": [
                {"name": "retained_emulator", "ok": True, "detail": "ok", "user_message": "保留模拟器正确。"},
                {"name": "adb_device", "ok": True, "detail": "emulator-5554", "user_message": "模拟器在线。"},
                {"name": "android_unlocked", "ok": True, "detail": "RUNNING_UNLOCKED", "user_message": "模拟器已解锁。"},
                {"name": "package_activity", "ok": True, "detail": "com.mi.ai.music/.MainActivity", "user_message": "应用可启动。"},
                {
                    "name": "frida_server",
                    "ok": False,
                    "detail": "pidof=not found",
                    "user_message": "Frida server 未运行，无法启动 flutter-socks 抓包。",
                },
            ],
        }

        report = build_readiness_report(
            app=app,
            health=health,
            capture_status={"exporter": "running", "frida_hook": "running", "proxy": "listening on 9090"},
            active_session={"id": 3, "package_name": "com.mi.ai.music", "status": "running"},
            flow_count=2,
            foreground="mCurrentFocus=Window{abc u0 com.mi.ai.music/com.mi.ai.music.MainActivity}",
        )

        self.assertEqual(report["state"], "fail")
        frida = next(check for check in report["checks"] if check["name"] == "frida")
        self.assertEqual(frida["state"], "fail")
        self.assertIn("Frida server", frida["summary"])

    def test_reports_red_when_required_health_check_fails(self):
        app = {"id": 1, "name": "MelodyCraft", "package_name": "com.mi.ai.music", "default_mode": "flutter-socks"}
        health = {
            "ok": False,
            "checks": [
                {"name": "adb_device", "ok": False, "detail": "no devices", "user_message": "保留模拟器未在线。"},
            ],
        }

        report = build_readiness_report(
            app=app,
            health=health,
            capture_status={"exporter": "missing", "frida_hook": "missing", "proxy": "not listening on 9090"},
            active_session=None,
            flow_count=0,
            foreground="",
        )

        self.assertEqual(report["state"], "fail")
        emulator = next(check for check in report["checks"] if check["name"] == "emulator")
        self.assertEqual(emulator["state"], "fail")

    def test_reports_red_when_google_login_check_fails(self):
        app = {"id": 1, "name": "MelodyCraft", "package_name": "com.mi.ai.music", "default_mode": "flutter-socks"}
        health = {
            "ok": False,
            "checks": [
                {"name": "retained_emulator", "ok": True, "detail": "ok", "user_message": "保留模拟器正确。"},
                {"name": "adb_device", "ok": True, "detail": "emulator-5554", "user_message": "模拟器在线。"},
                {"name": "android_unlocked", "ok": True, "detail": "RUNNING_UNLOCKED", "user_message": "模拟器已解锁。"},
                {"name": "package_activity", "ok": True, "detail": "com.mi.ai.music/.MainActivity", "user_message": "应用可启动。"},
                {
                    "name": "google_login",
                    "ok": False,
                    "detail": "not_logged_in",
                    "user_message": "请先在模拟器内登录 Google 账号。",
                    "fix": "点击“去登录 Google”，完成登录后刷新状态。",
                },
            ],
        }

        report = build_readiness_report(
            app=app,
            health=health,
            capture_status={"exporter": "missing", "frida_hook": "missing", "proxy": "not listening on 9090"},
            active_session=None,
            flow_count=0,
            foreground="",
        )

        self.assertEqual(report["state"], "fail")
        google = next(check for check in report["checks"] if check["name"] == "google_login")
        self.assertEqual(google["state"], "fail")
        self.assertIn("登录 Google", google["summary"])


if __name__ == "__main__":
    unittest.main()

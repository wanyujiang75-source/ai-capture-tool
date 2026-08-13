import unittest

from capture_console.foreground import capture_state, parse_foreground_component


class ForegroundTargetTests(unittest.TestCase):
    def test_parses_supported_resumed_component_formats(self):
        samples = [
            "topResumedActivity=ActivityRecord{a1 u0 com.example.music/.MainActivity t19}",
            "mResumedActivity: ActivityRecord{a2 u0 com.example.music/com.example.music.HomeActivity t19}",
            "mCurrentFocus=Window{a3 u0 com.example.music/.LoginActivity}",
        ]

        parsed = [parse_foreground_component(sample) for sample in samples]

        self.assertEqual(
            parsed,
            [
                {
                    "state": "ready",
                    "package_name": "com.example.music",
                    "activity": "com.example.music/.MainActivity",
                    "component": "com.example.music/.MainActivity",
                },
                {
                    "state": "ready",
                    "package_name": "com.example.music",
                    "activity": "com.example.music/com.example.music.HomeActivity",
                    "component": "com.example.music/com.example.music.HomeActivity",
                },
                {
                    "state": "ready",
                    "package_name": "com.example.music",
                    "activity": "com.example.music/.LoginActivity",
                    "component": "com.example.music/.LoginActivity",
                },
            ],
        )

    def test_excludes_launcher_system_ui_and_lock_screen(self):
        samples = [
            "topResumedActivity=ActivityRecord{a1 u0 com.google.android.apps.nexuslauncher/.NexusLauncherActivity t1}",
            "mCurrentFocus=Window{a2 u0 com.android.systemui/.keyguard.KeyguardViewMediator}",
            "mResumedActivity: ActivityRecord{a3 u0 com.android.launcher3/.Launcher t1}",
        ]

        self.assertEqual(
            [parse_foreground_component(sample)["state"] for sample in samples],
            ["no_target", "no_target", "no_target"],
        )

    def test_capture_state_requires_actual_target_traffic(self):
        app = {"package_name": "com.example.music"}

        self.assertEqual(capture_state(app=app, active_session=None, flow_count=0), "ready")
        self.assertEqual(
            capture_state(
                app=app,
                active_session={"package_name": "com.example.music"},
                flow_count=0,
            ),
            "waiting_traffic",
        )
        self.assertEqual(
            capture_state(
                app=app,
                active_session={"package_name": "com.example.music"},
                flow_count=2,
            ),
            "capturable",
        )
        self.assertEqual(
            capture_state(
                app=app,
                active_session={"package_name": "com.other.app"},
                flow_count=0,
            ),
            "blocked",
        )


if __name__ == "__main__":
    unittest.main()

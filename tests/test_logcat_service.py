import time
import tempfile
import unittest
from collections import deque
from pathlib import Path

from capture_console.logcat import BoundedLogBuffer, LogcatService, parse_threadtime_line
from capture_console.runner import ConsoleRunner


def wait_until(predicate, *, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("condition was not met before timeout")


class FakeStdout:
    def __init__(self, process, lines):
        self.process = process
        self.lines = deque(lines)

    def readline(self):
        if self.lines:
            return self.lines.popleft()
        return ""


class FakeProcess:
    def __init__(self, command, *, lines=()):
        self.command = command
        self.returncode = None
        self.terminated = False
        self.killed = False
        self.stdout = FakeStdout(self, lines)

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def wait(self, timeout=None):
        if self.returncode is None:
            raise TimeoutError("process is still running")
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9

    def finish(self):
        self.returncode = 0


class FakeProcessFactory:
    def __init__(self, lines_by_spawn=()):
        self.commands = []
        self.environments = []
        self.processes = []
        self.lines_by_spawn = deque(lines_by_spawn)

    def __call__(self, command, **kwargs):
        lines = self.lines_by_spawn.popleft() if self.lines_by_spawn else ()
        process = FakeProcess(command, lines=lines)
        self.commands.append(command)
        self.environments.append(kwargs.get("env"))
        self.processes.append(process)
        return process


class LogcatParserTests(unittest.TestCase):
    def test_parses_threadtime_entry(self) -> None:
        entry = parse_threadtime_line(
            "08-11 15:24:01.337  2468  2501 E flutter : example message\n"
        )

        self.assertEqual(
            {
                "timestamp": "08-11 15:24:01.337",
                "pid": 2468,
                "tid": 2501,
                "level": "E",
                "tag": "flutter",
                "message": "example message",
                "raw": "",
            },
            entry,
        )

    def test_preserves_unstructured_line_as_raw_message(self) -> None:
        entry = parse_threadtime_line("--------- beginning of main\n")

        self.assertEqual(
            {
                "timestamp": "",
                "pid": None,
                "tid": None,
                "level": "",
                "tag": "",
                "message": "--------- beginning of main",
                "raw": "--------- beginning of main",
            },
            entry,
        )


class BoundedLogBufferTests(unittest.TestCase):
    def test_reports_truncation_for_cursor_older_than_retained_entries(self) -> None:
        buffer = BoundedLogBuffer(max_entries=2, max_bytes=1024)
        for index in range(3):
            buffer.append({"message": f"line-{index}"})

        snapshot = buffer.snapshot(after=0, limit=50)

        self.assertEqual(
            {
                "entries": [
                    {"message": "line-1", "cursor": 2},
                    {"message": "line-2", "cursor": 3},
                ],
                "next_cursor": 3,
                "truncated": True,
            },
            snapshot,
        )

    def test_byte_limit_evicts_oldest_entries(self) -> None:
        buffer = BoundedLogBuffer(max_entries=10, max_bytes=40)
        buffer.append({"message": "123456"})
        buffer.append({"message": "abcdef"})

        snapshot = buffer.snapshot(after=0, limit=10)

        self.assertEqual([2], [entry["cursor"] for entry in snapshot["entries"]])
        self.assertTrue(snapshot["truncated"])

    def test_clear_keeps_cursor_monotonic(self) -> None:
        buffer = BoundedLogBuffer(max_entries=10, max_bytes=1024)
        buffer.append({"message": "before"})
        buffer.clear()
        buffer.append({"message": "after"})

        snapshot = buffer.snapshot(after=1, limit=10)

        self.assertEqual(
            {
                "entries": [{"message": "after", "cursor": 2}],
                "next_cursor": 2,
                "truncated": False,
            },
            snapshot,
        )

    def test_reports_truncation_when_oversized_entry_cannot_be_retained(self) -> None:
        buffer = BoundedLogBuffer(max_entries=10, max_bytes=10)
        buffer.append({"message": "entry larger than the entire buffer"})

        snapshot = buffer.snapshot(after=0, limit=10)

        self.assertEqual(
            {"entries": [], "next_cursor": 1, "truncated": True},
            snapshot,
        )

    def test_next_cursor_advances_only_through_returned_page(self) -> None:
        buffer = BoundedLogBuffer(max_entries=10, max_bytes=1024)
        for index in range(3):
            buffer.append({"message": f"line-{index}"})

        first_page = buffer.snapshot(after=0, limit=2)
        second_page = buffer.snapshot(after=first_page["next_cursor"], limit=2)

        self.assertEqual([1, 2], [entry["cursor"] for entry in first_page["entries"]])
        self.assertEqual(2, first_page["next_cursor"])
        self.assertEqual([3], [entry["cursor"] for entry in second_page["entries"]])
        self.assertEqual(3, second_page["next_cursor"])


class LogcatServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = FakeProcessFactory()
        self.service = LogcatService(process_factory=self.factory, retry_interval=0.01)

    def tearDown(self) -> None:
        self.service.stop_all()

    def start(self, *, device_id="device-1", source="system", package_name="", pid_resolver=None):
        return self.service.start(
            device_id=device_id,
            adb_command=["adb", "-s", "emulator-5554"],
            process_environment={"TEST_ENV": device_id},
            source=source,
            package_name=package_name,
            pid_resolver=pid_resolver,
        )

    def test_builds_exact_commands_for_all_sources(self) -> None:
        self.start(source="system")
        wait_until(lambda: len(self.factory.commands) == 1)
        self.service.stop("device-1")

        self.start(source="crash")
        wait_until(lambda: len(self.factory.commands) == 2)
        self.service.stop("device-1")

        self.start(source="app", package_name="com.example.app", pid_resolver=lambda _package: 2468)
        wait_until(lambda: len(self.factory.commands) == 3)

        self.assertEqual(
            [
                ["adb", "-s", "emulator-5554", "logcat", "-v", "threadtime"],
                ["adb", "-s", "emulator-5554", "logcat", "-b", "crash", "-v", "threadtime"],
                [
                    "adb",
                    "-s",
                    "emulator-5554",
                    "logcat",
                    "--pid",
                    "2468",
                    "-v",
                    "threadtime",
                ],
            ],
            self.factory.commands,
        )
        self.assertEqual(
            [{"TEST_ENV": "device-1"}] * 3,
            self.factory.environments,
        )

    def test_switching_source_stops_only_same_device_process(self) -> None:
        self.start(device_id="device-1")
        self.start(device_id="device-2")
        wait_until(lambda: len(self.factory.processes) == 2)
        device_1_process, device_2_process = self.factory.processes

        self.start(device_id="device-1", source="crash")
        wait_until(lambda: len(self.factory.processes) == 3)

        self.assertTrue(device_1_process.terminated)
        self.assertFalse(device_2_process.terminated)
        self.assertEqual("streaming", self.service.poll("device-2", after=0, limit=10)["state"])

    def test_app_source_waits_for_process_then_attaches(self) -> None:
        current_pid = {"value": None}
        self.start(
            source="app",
            package_name="com.example.app",
            pid_resolver=lambda _package: current_pid["value"],
        )

        wait_until(
            lambda: self.service.poll("device-1", after=0, limit=10)["state"] == "waiting_app"
        )
        self.assertEqual([], self.factory.commands)

        current_pid["value"] = 1357
        wait_until(lambda: len(self.factory.commands) == 1)

        self.assertEqual(
            ["adb", "-s", "emulator-5554", "logcat", "--pid", "1357", "-v", "threadtime"],
            self.factory.commands[0],
        )

    def test_app_source_reattaches_when_pid_changes(self) -> None:
        current_pid = {"value": 1111}
        self.start(
            source="app",
            package_name="com.example.app",
            pid_resolver=lambda _package: current_pid["value"],
        )
        wait_until(lambda: len(self.factory.processes) == 1)

        current_pid["value"] = 2222
        self.factory.processes[0].finish()
        wait_until(lambda: len(self.factory.processes) == 2)

        self.assertEqual(
            ["adb", "-s", "emulator-5554", "logcat", "--pid", "2222", "-v", "threadtime"],
            self.factory.commands[1],
        )

    def test_poll_returns_parsed_incremental_entries(self) -> None:
        self.factory.lines_by_spawn.append(
            ["08-11 15:24:01.337  2468  2501 I flutter : ready\n"]
        )
        self.start()
        wait_until(
            lambda: self.service.poll("device-1", after=0, limit=10)["next_cursor"] == 1
        )

        response = self.service.poll("device-1", after=0, limit=10)

        self.assertEqual(
            [
                {
                    "timestamp": "08-11 15:24:01.337",
                    "pid": 2468,
                    "tid": 2501,
                    "level": "I",
                    "tag": "flutter",
                    "message": "ready",
                    "raw": "",
                    "cursor": 1,
                }
            ],
            response["entries"],
        )

    def test_reaps_session_after_thirty_seconds_without_poll(self) -> None:
        clock = {"value": 10.0}
        service = LogcatService(
            process_factory=self.factory,
            clock=lambda: clock["value"],
            retry_interval=0.01,
            idle_timeout=30.0,
        )
        self.addCleanup(service.stop_all)
        service.start(
            device_id="device-1",
            adb_command=["adb", "-s", "emulator-5554"],
            process_environment={},
            source="system",
        )
        wait_until(lambda: len(self.factory.processes) == 1)

        reaped = service.reap_idle(now=40.1)

        self.assertEqual(["device-1"], reaped)
        self.assertTrue(self.factory.processes[0].terminated)
        self.assertEqual("stopped", service.poll("device-1", after=0, limit=10)["state"])


class LogcatRunnerAccessTests(unittest.TestCase):
    def test_exposes_safe_adb_prefix_and_process_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runner = ConsoleRunner(
                Path(tmp),
                adb_serial="emulator-5580",
                capture_instance="device-9",
            )

            self.assertEqual(
                [str(runner.adb_bin), "-s", "emulator-5580"],
                runner.adb_command_prefix(),
            )
            environment = runner.process_environment()
            self.assertEqual("emulator-5580", environment["ADB_SERIAL"])
            self.assertEqual("device-9", environment["CAPTURE_INSTANCE"])


if __name__ == "__main__":
    unittest.main()

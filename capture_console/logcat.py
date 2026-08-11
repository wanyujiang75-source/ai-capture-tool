from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Optional


THREADTIME_PATTERN = re.compile(
    r"^(?P<timestamp>\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d+)\s+"
    r"(?P<pid>\d+)\s+(?P<tid>\d+)\s+(?P<level>[VDIWEF])\s+"
    r"(?P<tag>.*?)\s*:\s(?P<message>.*)$"
)


def parse_threadtime_line(line: str) -> Dict[str, Any]:
    value = line.rstrip("\r\n")
    match = THREADTIME_PATTERN.match(value)
    if match is None:
        return {
            "timestamp": "",
            "pid": None,
            "tid": None,
            "level": "",
            "tag": "",
            "message": value,
            "raw": value,
        }

    fields = match.groupdict()
    return {
        "timestamp": fields["timestamp"],
        "pid": int(fields["pid"]),
        "tid": int(fields["tid"]),
        "level": fields["level"],
        "tag": fields["tag"].strip(),
        "message": fields["message"],
        "raw": "",
    }


class BoundedLogBuffer:
    def __init__(self, *, max_entries: int = 5000, max_bytes: int = 2 * 1024 * 1024):
        if max_entries <= 0 or max_bytes <= 0:
            raise ValueError("log buffer limits must be positive")
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._entries: Deque[tuple[Dict[str, Any], int]] = deque()
        self._next_cursor = 0
        self._discarded_through = 0
        self._retained_bytes = 0
        self._lock = threading.Lock()

    @staticmethod
    def _entry_size(entry: Dict[str, Any]) -> int:
        payload = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
        return len(payload.encode("utf-8"))

    def append(self, entry: Dict[str, Any]) -> int:
        with self._lock:
            self._next_cursor += 1
            retained = dict(entry)
            retained["cursor"] = self._next_cursor
            entry_size = self._entry_size(retained)
            self._entries.append((retained, entry_size))
            self._retained_bytes += entry_size
            while self._entries and (
                len(self._entries) > self.max_entries or self._retained_bytes > self.max_bytes
            ):
                removed, removed_size = self._entries.popleft()
                self._discarded_through = max(self._discarded_through, int(removed["cursor"]))
                self._retained_bytes -= removed_size
            return self._next_cursor

    def snapshot(self, *, after: int, limit: int) -> Dict[str, Any]:
        if after < 0:
            raise ValueError("after must be non-negative")
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._lock:
            entries = [
                dict(entry)
                for entry, _size in self._entries
                if int(entry["cursor"]) > after
            ][:limit]
            next_cursor = int(entries[-1]["cursor"]) if entries else max(after, self._next_cursor)
            return {
                "entries": entries,
                "next_cursor": next_cursor,
                "truncated": after < self._discarded_through,
            }

    def clear(self) -> int:
        with self._lock:
            self._entries.clear()
            self._retained_bytes = 0
            self._discarded_through = self._next_cursor
            return self._next_cursor

    def cursor(self) -> int:
        with self._lock:
            return self._next_cursor


@dataclass
class _LogcatSession:
    device_id: str
    adb_command: list[str]
    process_environment: Dict[str, str]
    source: str
    package_name: str
    pid_resolver: Optional[Callable[[str], Optional[int]]]
    buffer: BoundedLogBuffer
    last_polled_at: float
    stop_event: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)
    state: str = "starting"
    process: Any = None
    worker_thread: Optional[threading.Thread] = None
    reader_thread: Optional[threading.Thread] = None


class LogcatService:
    SOURCES = {"app", "system", "crash"}

    def __init__(
        self,
        *,
        process_factory: Callable[..., Any] = subprocess.Popen,
        clock: Callable[[], float] = time.monotonic,
        retry_interval: float = 1.0,
        idle_timeout: float = 30.0,
        max_entries: int = 5000,
        max_bytes: int = 2 * 1024 * 1024,
    ):
        self._process_factory = process_factory
        self._clock = clock
        self._retry_interval = retry_interval
        self._idle_timeout = idle_timeout
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._sessions: Dict[str, _LogcatSession] = {}
        self._lock = threading.Lock()

    def start(
        self,
        *,
        device_id: str,
        adb_command: list[str],
        process_environment: Dict[str, str],
        source: str,
        package_name: str = "",
        pid_resolver: Optional[Callable[[str], Optional[int]]] = None,
    ) -> Dict[str, Any]:
        if source not in self.SOURCES:
            raise ValueError(f"unsupported logcat source: {source}")
        if source == "app" and (not package_name or pid_resolver is None):
            raise ValueError("app logcat requires a package name and PID resolver")
        if not adb_command:
            raise ValueError("adb command prefix is required")

        self.stop(device_id)
        session = _LogcatSession(
            device_id=device_id,
            adb_command=list(adb_command),
            process_environment=dict(process_environment),
            source=source,
            package_name=package_name if source == "app" else "",
            pid_resolver=pid_resolver if source == "app" else None,
            buffer=BoundedLogBuffer(max_entries=self._max_entries, max_bytes=self._max_bytes),
            last_polled_at=self._clock(),
        )
        worker = threading.Thread(
            target=self._supervise,
            args=(session,),
            name=f"logcat-{device_id}",
            daemon=True,
        )
        session.worker_thread = worker
        with self._lock:
            self._sessions[device_id] = session
        worker.start()
        return self._response(session, after=session.buffer.cursor(), limit=1)

    def poll(self, device_id: str, *, after: int, limit: int) -> Dict[str, Any]:
        session = self._session(device_id)
        if session is None:
            return self._stopped_response(device_id)
        with session.lock:
            session.last_polled_at = self._clock()
        return self._response(session, after=after, limit=limit)

    def clear(self, device_id: str) -> Dict[str, Any]:
        session = self._session(device_id)
        if session is None:
            return self._stopped_response(device_id)
        cursor = session.buffer.clear()
        return self._response(session, after=cursor, limit=1)

    def stop(self, device_id: str) -> Dict[str, Any]:
        with self._lock:
            session = self._sessions.pop(device_id, None)
        if session is None:
            return self._stopped_response(device_id)
        self._stop_session(session)
        cursor = session.buffer.cursor()
        return {
            "device_id": device_id,
            "source": session.source,
            "state": "stopped",
            "package_name": session.package_name,
            "next_cursor": cursor,
            "truncated": False,
            "entries": [],
        }

    def stop_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            self._stop_session(session)

    def reap_idle(self, *, now: Optional[float] = None) -> list[str]:
        checked_at = self._clock() if now is None else now
        expired: list[_LogcatSession] = []
        with self._lock:
            for device_id, session in list(self._sessions.items()):
                with session.lock:
                    idle_for = checked_at - session.last_polled_at
                if idle_for > self._idle_timeout:
                    expired.append(session)
                    del self._sessions[device_id]
        for session in expired:
            self._stop_session(session)
        return [session.device_id for session in expired]

    def _session(self, device_id: str) -> Optional[_LogcatSession]:
        with self._lock:
            return self._sessions.get(device_id)

    def _response(self, session: _LogcatSession, *, after: int, limit: int) -> Dict[str, Any]:
        snapshot = session.buffer.snapshot(after=after, limit=limit)
        with session.lock:
            state = session.state
        return {
            "device_id": session.device_id,
            "source": session.source,
            "state": state,
            "package_name": session.package_name,
            **snapshot,
        }

    @staticmethod
    def _stopped_response(device_id: str) -> Dict[str, Any]:
        return {
            "device_id": device_id,
            "source": "",
            "state": "stopped",
            "package_name": "",
            "next_cursor": 0,
            "truncated": False,
            "entries": [],
        }

    def _supervise(self, session: _LogcatSession) -> None:
        if session.source == "app":
            self._supervise_app(session)
        else:
            self._supervise_device_buffer(session)

    def _supervise_device_buffer(self, session: _LogcatSession) -> None:
        command = [*session.adb_command, "logcat"]
        if session.source == "crash":
            command.extend(["-b", "crash"])
        command.extend(["-v", "threadtime"])
        process = self._spawn(session, command)
        if process is None:
            return
        self._wait_for_process(session, process)
        if not session.stop_event.is_set():
            self._set_state(session, "error")

    def _supervise_app(self, session: _LogcatSession) -> None:
        while not session.stop_event.is_set():
            pid = self._resolve_pid(session)
            if pid is None:
                self._set_state(session, "waiting_app")
                session.stop_event.wait(self._retry_interval)
                continue

            command = [
                *session.adb_command,
                "logcat",
                "--pid",
                str(pid),
                "-v",
                "threadtime",
            ]
            process = self._spawn(session, command)
            if process is None:
                session.stop_event.wait(self._retry_interval)
                continue

            while not session.stop_event.wait(self._retry_interval):
                if process.poll() is not None:
                    break
                if self._resolve_pid(session) != pid:
                    self._terminate_process(process)
                    break
            self._finish_process(session, process)

    def _resolve_pid(self, session: _LogcatSession) -> Optional[int]:
        resolver = session.pid_resolver
        if resolver is None:
            return None
        try:
            pid = resolver(session.package_name)
        except Exception:
            return None
        return pid if pid and pid > 0 else None

    def _spawn(self, session: _LogcatSession, command: list[str]):
        if session.stop_event.is_set():
            return None
        try:
            process = self._process_factory(
                command,
                env=session.process_environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except (OSError, ValueError):
            self._set_state(session, "error")
            return None

        reader = threading.Thread(
            target=self._read_process,
            args=(session, process),
            name=f"logcat-reader-{session.device_id}",
            daemon=True,
        )
        with session.lock:
            session.process = process
            session.reader_thread = reader
            session.state = "streaming"
        reader.start()
        return process

    def _read_process(self, session: _LogcatSession, process: Any) -> None:
        stdout = process.stdout
        if stdout is None:
            return
        while not session.stop_event.is_set():
            line = stdout.readline()
            if line:
                session.buffer.append(parse_threadtime_line(line))
                continue
            if process.poll() is not None:
                return
            session.stop_event.wait(0.05)

    def _wait_for_process(self, session: _LogcatSession, process: Any) -> None:
        while not session.stop_event.wait(0.05):
            if process.poll() is not None:
                break
        self._finish_process(session, process)

    def _finish_process(self, session: _LogcatSession, process: Any) -> None:
        if process.poll() is None:
            self._terminate_process(process)
        with session.lock:
            reader = session.reader_thread if session.process is process else None
            if session.process is process:
                session.process = None
                session.reader_thread = None
        if reader and reader is not threading.current_thread():
            reader.join(timeout=1.0)

    @staticmethod
    def _terminate_process(process: Any) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=1.0)
        except (subprocess.TimeoutExpired, TimeoutError):
            process.kill()
            try:
                process.wait(timeout=1.0)
            except (subprocess.TimeoutExpired, TimeoutError):
                pass
        except ProcessLookupError:
            pass

    def _stop_session(self, session: _LogcatSession) -> None:
        session.stop_event.set()
        with session.lock:
            process = session.process
            worker = session.worker_thread
            reader = session.reader_thread
            session.state = "stopped"
        if process is not None:
            self._terminate_process(process)
        current = threading.current_thread()
        if worker and worker is not current:
            worker.join(timeout=2.0)
        if reader and reader is not current:
            reader.join(timeout=1.0)

    @staticmethod
    def _set_state(session: _LogcatSession, state: str) -> None:
        with session.lock:
            if not session.stop_event.is_set():
                session.state = state

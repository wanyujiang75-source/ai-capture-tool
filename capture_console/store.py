from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .platforms import validate_platform


ACTIVE_STATUSES = {"starting", "running", "stopping"}
APP_ENVIRONMENTS = {"production", "test"}
DEFAULT_DEVICE_ID = "device-1"
DEFAULT_CAPTURE_DEVICES = [
    {
        "device_id": "device-1",
        "name": "本机保留模拟器 1",
        "avd_name": "Medium_Phone_API_36.1",
        "adb_serial": "emulator-5554",
        "proxy_port": 9090,
        "web_port": 9091,
        "frida_port": 27042,
        "enabled": 1,
        "resident": 1,
        "idle_release_minutes": 0,
    },
    {
        "device_id": "device-2",
        "name": "扩展模拟器 2",
        "avd_name": "Capture_AVD_02",
        "adb_serial": "emulator-5556",
        "proxy_port": 9100,
        "web_port": 9101,
        "frida_port": 27142,
        "enabled": 1,
        "resident": 1,
        "idle_release_minutes": 0,
    },
    {
        "device_id": "device-3",
        "name": "扩展模拟器 3",
        "avd_name": "Capture_AVD_03",
        "adb_serial": "emulator-5558",
        "proxy_port": 9110,
        "web_port": 9111,
        "frida_port": 27242,
        "enabled": 1,
        "resident": 0,
        "idle_release_minutes": 10,
    },
    {
        "device_id": "device-4",
        "name": "扩展模拟器 4",
        "avd_name": "Capture_AVD_04",
        "adb_serial": "emulator-5560",
        "proxy_port": 9120,
        "web_port": 9121,
        "frida_port": 27342,
        "enabled": 0,
        "resident": 0,
        "idle_release_minutes": 10,
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def row_to_dict(row: sqlite3.Row | None) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


def validate_app_environment(value: str | None) -> str:
    environment = value or "production"
    if environment not in APP_ENVIRONMENTS:
        raise ValueError("environment must be production or test")
    return environment


class CaptureStore:
    def __init__(self, db_path: str | Path, *, devices_config_path: str | Path | None = None):
        self.db_path = Path(db_path)
        self.devices_config_path = Path(devices_config_path or os.environ.get("CAPTURE_DEVICES_CONFIG") or "") if (devices_config_path or os.environ.get("CAPTURE_DEVICES_CONFIG")) else None
        self._migrating = False
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        db_missing = not self.db_path.exists()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        if db_missing and not self._migrating:
            conn.close()
            self._migrate()
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _migrate(self) -> None:
        previous_migrating = self._migrating
        self._migrating = True
        try:
            self._migrate_inner()
        finally:
            self._migrating = previous_migrating

    def _migrate_inner(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS apps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL DEFAULT 'android',
                    environment TEXT NOT NULL DEFAULT 'production',
                    name TEXT NOT NULL,
                    package_name TEXT NOT NULL UNIQUE,
                    activity TEXT NOT NULL DEFAULT '',
                    default_mode TEXT NOT NULL DEFAULT 'system',
                    notes TEXT NOT NULL DEFAULT '',
                    version_name TEXT NOT NULL DEFAULT '',
                    version_code TEXT NOT NULL DEFAULT '',
                    last_update_time TEXT NOT NULL DEFAULT '',
                    installer_package TEXT NOT NULL DEFAULT '',
                    signature_hint TEXT NOT NULL DEFAULT '',
                    apk_archive_path TEXT NOT NULL DEFAULT '',
                    last_version_check_at TEXT,
                    last_validation_status TEXT NOT NULL DEFAULT '',
                    last_validation_message TEXT NOT NULL DEFAULT '',
                    last_validation_at TEXT,
                    last_success_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS capture_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL DEFAULT 'android',
                    device_id TEXT NOT NULL DEFAULT 'device-1',
                    device_name TEXT NOT NULL DEFAULT '',
                    avd_name TEXT NOT NULL DEFAULT '',
                    adb_serial TEXT NOT NULL DEFAULT '',
                    proxy_port INTEGER NOT NULL DEFAULT 9090,
                    web_port INTEGER NOT NULL DEFAULT 9091,
                    frida_port INTEGER NOT NULL DEFAULT 27042,
                    app_id INTEGER REFERENCES apps(id) ON DELETE SET NULL,
                    app_name TEXT NOT NULL DEFAULT '',
                    package_name TEXT NOT NULL DEFAULT '',
                    mode TEXT NOT NULL,
                    outdir TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    web_url TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    started_at TEXT,
                    stopped_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_capture_sessions_status
                    ON capture_sessions(status);
                CREATE INDEX IF NOT EXISTS idx_capture_sessions_created
                    ON capture_sessions(created_at DESC);

                CREATE TABLE IF NOT EXISTS capture_devices (
                    device_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    avd_name TEXT NOT NULL,
                    adb_serial TEXT NOT NULL,
                    proxy_port INTEGER NOT NULL,
                    web_port INTEGER NOT NULL,
                    frida_port INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    resident INTEGER NOT NULL DEFAULT 0,
                    idle_release_minutes INTEGER NOT NULL DEFAULT 10,
                    lease_status TEXT NOT NULL DEFAULT 'idle',
                    lease_owner TEXT NOT NULL DEFAULT '',
                    current_session_id INTEGER REFERENCES capture_sessions(id) ON DELETE SET NULL,
                    last_active_at TEXT,
                    last_lease_at TEXT,
                    last_release_at TEXT,
                    sleep_state TEXT NOT NULL DEFAULT 'awake',
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS device_app_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL REFERENCES capture_devices(device_id) ON DELETE CASCADE,
                    app_id INTEGER REFERENCES apps(id) ON DELETE CASCADE,
                    package_name TEXT NOT NULL,
                    activity TEXT NOT NULL DEFAULT '',
                    version_name TEXT NOT NULL DEFAULT '',
                    version_code TEXT NOT NULL DEFAULT '',
                    last_update_time TEXT NOT NULL DEFAULT '',
                    installer_package TEXT NOT NULL DEFAULT '',
                    signature_hint TEXT NOT NULL DEFAULT '',
                    apk_archive_path TEXT NOT NULL DEFAULT '',
                    last_version_check_at TEXT,
                    last_validation_status TEXT NOT NULL DEFAULT '',
                    last_validation_message TEXT NOT NULL DEFAULT '',
                    last_validation_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(device_id, package_name)
                );

                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            self._ensure_column(conn, "apps", "platform", "TEXT NOT NULL DEFAULT 'android'")
            self._ensure_column(conn, "apps", "environment", "TEXT NOT NULL DEFAULT 'production'")
            self._normalize_app_environments(conn)
            self._ensure_column(conn, "apps", "version_name", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "apps", "version_code", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "apps", "last_update_time", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "apps", "installer_package", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "apps", "signature_hint", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "apps", "apk_archive_path", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "apps", "last_version_check_at", "TEXT")
            self._ensure_column(conn, "apps", "last_validation_status", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "apps", "last_validation_message", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "apps", "last_validation_at", "TEXT")
            self._ensure_column(conn, "capture_sessions", "platform", "TEXT NOT NULL DEFAULT 'android'")
            self._ensure_column(conn, "capture_sessions", "device_id", "TEXT NOT NULL DEFAULT 'device-1'")
            self._ensure_column(conn, "capture_sessions", "device_name", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "capture_sessions", "avd_name", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "capture_sessions", "adb_serial", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "capture_sessions", "proxy_port", "INTEGER NOT NULL DEFAULT 9090")
            self._ensure_column(conn, "capture_sessions", "web_port", "INTEGER NOT NULL DEFAULT 9091")
            self._ensure_column(conn, "capture_sessions", "frida_port", "INTEGER NOT NULL DEFAULT 27042")
            self._ensure_column(conn, "capture_devices", "resident", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "capture_devices", "idle_release_minutes", "INTEGER NOT NULL DEFAULT 10")
            self._ensure_column(conn, "capture_devices", "last_lease_at", "TEXT")
            self._ensure_column(conn, "capture_devices", "last_release_at", "TEXT")
            self._seed_default_devices(conn)
            self._ensure_system_state(conn)

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _normalize_app_environments(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            UPDATE apps
            SET environment='production'
            WHERE environment IS NULL
               OR environment=''
               OR environment NOT IN ('production', 'test')
            """
        )
        conn.execute(
            """
            UPDATE apps
            SET environment='test'
            WHERE environment='production'
              AND (
                name LIKE '%测试%'
                OR notes LIKE '%测试%'
                OR LOWER(name) LIKE '%test%'
                OR LOWER(notes) LIKE '%test%'
              )
            """
        )

    def _seed_default_devices(self, conn: sqlite3.Connection) -> None:
        timestamp = now_iso()
        for device in self._configured_devices():
            conn.execute(
                """
                INSERT INTO capture_devices (
                    device_id, name, avd_name, adb_serial, proxy_port, web_port, frida_port,
                    enabled, resident, idle_release_minutes, lease_status, sleep_state, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'idle', 'awake', ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    name=excluded.name,
                    avd_name=excluded.avd_name,
                    adb_serial=excluded.adb_serial,
                    proxy_port=excluded.proxy_port,
                    web_port=excluded.web_port,
                    frida_port=excluded.frida_port,
                    enabled=excluded.enabled,
                    resident=excluded.resident,
                    idle_release_minutes=excluded.idle_release_minutes,
                    updated_at=excluded.updated_at
                """,
                (
                    device["device_id"],
                    device["name"],
                    device["avd_name"],
                    device["adb_serial"],
                    device["proxy_port"],
                    device["web_port"],
                    device["frida_port"],
                    device["enabled"],
                    device["resident"],
                    device["idle_release_minutes"],
                    timestamp,
                    timestamp,
                ),
            )

    def _configured_devices(self) -> List[Dict[str, Any]]:
        if not self.devices_config_path:
            return DEFAULT_CAPTURE_DEVICES
        try:
            payload = json.loads(self.devices_config_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValueError(f"failed to read capture devices config: {self.devices_config_path}") from exc
        devices = payload.get("devices") if isinstance(payload, dict) else payload
        if not isinstance(devices, list) or not devices:
            raise ValueError("capture devices config must contain a non-empty devices list")
        required = {"device_id", "name", "avd_name", "adb_serial", "proxy_port", "web_port", "frida_port"}
        configured = []
        seen_ids = set()
        seen_ports = set()
        for device in devices:
            if not isinstance(device, dict):
                raise ValueError("capture device config entries must be objects")
            missing = sorted(required - set(device))
            if missing:
                raise ValueError(f"capture device config missing fields: {', '.join(missing)}")
            if device["device_id"] in seen_ids:
                raise ValueError(f"duplicate capture device id: {device['device_id']}")
            ports = {int(device["proxy_port"]), int(device["web_port"]), int(device["frida_port"])}
            if seen_ports & ports:
                raise ValueError("capture device config contains duplicate ports")
            seen_ids.add(device["device_id"])
            seen_ports.update(ports)
            configured.append({
                **device,
                "enabled": int(device.get("enabled", 1)),
                "resident": int(device.get("resident", 0)),
                "idle_release_minutes": int(device.get("idle_release_minutes", 10)),
            })
        return configured

    def _ensure_system_state(self, conn: sqlite3.Connection) -> None:
        timestamp = now_iso()
        conn.execute(
            """
            INSERT INTO system_state (key, value, updated_at)
            VALUES ('state', 'running', ?)
            ON CONFLICT(key) DO NOTHING
            """,
            (timestamp,),
        )

    def create_app(
        self,
        *,
        platform: str = "android",
        environment: str = "production",
        name: str,
        package_name: str,
        activity: str = "",
        default_mode: str = "system",
        notes: str = "",
    ) -> Dict[str, Any]:
        platform = validate_platform(platform)
        environment = validate_app_environment(environment)
        if default_mode not in {"system", "flutter-socks"}:
            raise ValueError("default_mode must be system or flutter-socks")
        timestamp = now_iso()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO apps (platform, environment, name, package_name, activity, default_mode, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(package_name) DO UPDATE SET
                    platform=excluded.platform,
                    environment=excluded.environment,
                    name=excluded.name,
                    activity=excluded.activity,
                    default_mode=excluded.default_mode,
                    notes=excluded.notes,
                    updated_at=excluded.updated_at
                RETURNING *
                """,
                (platform, environment, name, package_name, activity, default_mode, notes, timestamp, timestamp),
            )
            return dict(cur.fetchone())

    def update_app(self, app_id: int, **fields: Any) -> Dict[str, Any]:
        allowed = {
            "platform",
            "environment",
            "name",
            "package_name",
            "activity",
            "default_mode",
            "notes",
            "version_name",
            "version_code",
            "last_update_time",
            "installer_package",
            "signature_hint",
            "apk_archive_path",
            "last_version_check_at",
            "last_validation_status",
            "last_validation_message",
            "last_validation_at",
            "last_success_at",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if "platform" in updates:
            updates["platform"] = validate_platform(updates["platform"])
        if "environment" in updates:
            updates["environment"] = validate_app_environment(updates["environment"])
        if "default_mode" in updates and updates["default_mode"] not in {"system", "flutter-socks"}:
            raise ValueError("default_mode must be system or flutter-socks")
        if not updates:
            app = self.get_app(app_id)
            if app is None:
                raise KeyError(f"app not found: {app_id}")
            return app
        updates["updated_at"] = now_iso()
        assignments = ", ".join(f"{key}=?" for key in updates)
        values = list(updates.values()) + [app_id]
        with self.connect() as conn:
            cur = conn.execute(f"UPDATE apps SET {assignments} WHERE id=? RETURNING *", values)
            row = cur.fetchone()
            if row is None:
                raise KeyError(f"app not found: {app_id}")
            return dict(row)

    def delete_app(self, app_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM apps WHERE id=?", (app_id,))

    def get_app(self, app_id: int) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            return row_to_dict(conn.execute("SELECT * FROM apps WHERE id=?", (app_id,)).fetchone())

    def get_app_by_package(self, package_name: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            return row_to_dict(conn.execute("SELECT * FROM apps WHERE package_name=?", (package_name,)).fetchone())

    def list_apps(self) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM apps ORDER BY updated_at DESC, id DESC")]

    def list_devices(self, *, include_disabled: bool = True) -> List[Dict[str, Any]]:
        query = "SELECT * FROM capture_devices"
        params: tuple[Any, ...] = ()
        if not include_disabled:
            query += " WHERE enabled=1"
        query += " ORDER BY device_id"
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(query, params)]

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            return row_to_dict(conn.execute("SELECT * FROM capture_devices WHERE device_id=?", (device_id,)).fetchone())

    def default_device(self) -> Dict[str, Any]:
        device = self.get_device(DEFAULT_DEVICE_ID)
        if device is None:
            raise KeyError(f"default device not found: {DEFAULT_DEVICE_ID}")
        return device

    def update_device(self, device_id: str, **fields: Any) -> Dict[str, Any]:
        allowed = {
            "name",
            "avd_name",
            "adb_serial",
            "proxy_port",
            "web_port",
            "frida_port",
            "enabled",
            "resident",
            "idle_release_minutes",
            "lease_status",
            "lease_owner",
            "current_session_id",
            "last_active_at",
            "last_lease_at",
            "last_release_at",
            "sleep_state",
            "error",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            device = self.get_device(device_id)
            if device is None:
                raise KeyError(f"device not found: {device_id}")
            return device
        updates["updated_at"] = now_iso()
        assignments = ", ".join(f"{key}=?" for key in updates)
        values = list(updates.values()) + [device_id]
        with self.connect() as conn:
            cur = conn.execute(f"UPDATE capture_devices SET {assignments} WHERE device_id=? RETURNING *", values)
            row = cur.fetchone()
            if row is None:
                raise KeyError(f"device not found: {device_id}")
            return dict(row)

    def touch_device(self, device_id: str) -> Dict[str, Any]:
        return self.update_device(device_id, last_active_at=now_iso())

    def lease_device(self, device_id: str, owner: str = "") -> Dict[str, Any]:
        device = self.get_device(device_id)
        if device is None:
            raise KeyError(f"device not found: {device_id}")
        if not device.get("enabled"):
            raise ValueError("device is disabled")
        if device.get("lease_status") not in {"idle", "sleeping"}:
            raise ValueError("device is already leased")
        return self.update_device(
            device_id,
            lease_status="leased",
            lease_owner=owner,
            sleep_state="awake",
            last_active_at=now_iso(),
            last_lease_at=now_iso(),
            error="",
        )

    def release_device(self, device_id: str) -> Dict[str, Any]:
        return self.update_device(
            device_id,
            lease_status="idle",
            lease_owner="",
            current_session_id=None,
            last_active_at=now_iso(),
            last_release_at=now_iso(),
            sleep_state="awake",
            error="",
        )

    def get_system_state(self) -> Dict[str, Any]:
        with self.connect() as conn:
            rows = {row["key"]: dict(row) for row in conn.execute("SELECT * FROM system_state")}
        state = rows.get("state", {"value": "running", "updated_at": now_iso()})
        return {"state": state["value"], "updated_at": state["updated_at"]}

    def set_system_state(self, state: str) -> Dict[str, Any]:
        timestamp = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO system_state (key, value, updated_at)
                VALUES ('state', ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (state, timestamp),
            )
        return {"state": state, "updated_at": timestamp}

    def get_system_value(self, key: str, default: str = "") -> Dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM system_state WHERE key=?", (key,)).fetchone()
        if row is None:
            return {"key": key, "value": default, "updated_at": ""}
        return dict(row)

    def set_system_value(self, key: str, value: str) -> Dict[str, Any]:
        timestamp = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO system_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, value, timestamp),
            )
        return {"key": key, "value": value, "updated_at": timestamp}

    def active_session(self, device_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        params: list[Any] = list(ACTIVE_STATUSES)
        device_clause = ""
        if device_id is not None:
            device_clause = " AND device_id=?"
            params.append(device_id)
        with self.connect() as conn:
            row = conn.execute(
                f"SELECT * FROM capture_sessions WHERE status IN ({placeholders}){device_clause} ORDER BY id DESC LIMIT 1",
                tuple(params),
            ).fetchone()
            return row_to_dict(row)

    def list_active_sessions(self) -> List[Dict[str, Any]]:
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        with self.connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    f"SELECT * FROM capture_sessions WHERE status IN ({placeholders}) ORDER BY id DESC",
                    tuple(ACTIVE_STATUSES),
                )
            ]

    def create_session(
        self,
        *,
        app_id: Optional[int],
        device_id: str = DEFAULT_DEVICE_ID,
        mode: str,
        outdir: str,
        status: str = "starting",
        web_url: str = "",
        error: str = "",
    ) -> Dict[str, Any]:
        if status in ACTIVE_STATUSES and self.active_session(device_id=device_id) is not None:
            raise ValueError("another capture session is already active on this device")
        if mode not in {"system", "flutter-socks"}:
            raise ValueError("mode must be system or flutter-socks")

        app = self.get_app(app_id) if app_id else None
        device = self.get_device(device_id) or self.default_device()
        timestamp = now_iso()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO capture_sessions (
                    platform, device_id, device_name, avd_name, adb_serial, proxy_port, web_port, frida_port,
                    app_id, app_name, package_name, mode, outdir, status, web_url, error,
                    started_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING *
                """,
                (
                    app["platform"] if app else "android",
                    device["device_id"],
                    device.get("name", ""),
                    device["avd_name"],
                    device["adb_serial"],
                    device["proxy_port"],
                    device["web_port"],
                    device["frida_port"],
                    app_id,
                    app["name"] if app else "",
                    app["package_name"] if app else "",
                    mode,
                    outdir,
                    status,
                    web_url,
                    error,
                    timestamp if status in ACTIVE_STATUSES else None,
                    timestamp,
                    timestamp,
                ),
            )
            session = dict(cur.fetchone())
            if status in ACTIVE_STATUSES:
                conn.execute(
                    "UPDATE capture_devices SET current_session_id=?, lease_status='running', last_active_at=?, updated_at=? WHERE device_id=?",
                    (session["id"], timestamp, timestamp, session["device_id"]),
                )
            return session

    def update_session_status(
        self,
        session_id: int,
        status: str,
        *,
        error: str = "",
        web_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        timestamp = now_iso()
        updates = {
            "status": status,
            "error": error,
            "updated_at": timestamp,
        }
        if status in {"stopped", "failed"}:
            updates["stopped_at"] = timestamp
        elif status in ACTIVE_STATUSES:
            updates["stopped_at"] = None
        if web_url is not None:
            updates["web_url"] = web_url
        assignments = ", ".join(f"{key}=?" for key in updates)
        values = list(updates.values()) + [session_id]
        with self.connect() as conn:
            cur = conn.execute(f"UPDATE capture_sessions SET {assignments} WHERE id=? RETURNING *", values)
            row = cur.fetchone()
            if row is None:
                raise KeyError(f"session not found: {session_id}")
            session = dict(row)
            if status in {"stopped", "failed"}:
                conn.execute(
                    """
                    UPDATE capture_devices
                    SET current_session_id=NULL,
                        lease_status=CASE WHEN lease_status='running' THEN 'leased' ELSE lease_status END,
                        last_active_at=?,
                        updated_at=?
                    WHERE device_id=? AND current_session_id=?
                    """,
                    (timestamp, timestamp, session["device_id"], session_id),
                )
            elif status in ACTIVE_STATUSES:
                conn.execute(
                    "UPDATE capture_devices SET current_session_id=?, lease_status='running', last_active_at=?, updated_at=? WHERE device_id=?",
                    (session_id, timestamp, timestamp, session["device_id"]),
                )
            return session

    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            return row_to_dict(conn.execute("SELECT * FROM capture_sessions WHERE id=?", (session_id,)).fetchone())

    def get_session_by_outdir(self, outdir: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            return row_to_dict(conn.execute("SELECT * FROM capture_sessions WHERE outdir=?", (outdir,)).fetchone())

    def list_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM capture_sessions ORDER BY COALESCE(started_at, created_at) DESC, id DESC LIMIT ?",
                    (limit,),
                )
            ]

    def clear_capture_sessions(self) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM capture_sessions")
            conn.execute("UPDATE capture_devices SET current_session_id=NULL, lease_status='idle', updated_at=?", (now_iso(),))

    def update_app_version(self, app_id: int, version: Dict[str, Any]) -> Dict[str, Any]:
        fields = {
            "version_name": str(version.get("version_name") or ""),
            "version_code": str(version.get("version_code") or ""),
            "last_update_time": str(version.get("last_update_time") or ""),
            "installer_package": str(version.get("installer_package") or ""),
            "signature_hint": str(version.get("signature_hint") or ""),
            "apk_archive_path": str(version.get("apk_archive_path") or ""),
            "last_version_check_at": now_iso(),
        }
        activity = str(version.get("activity") or "")
        if activity:
            fields["activity"] = activity
        return self.update_app(app_id, **fields)

    def update_device_app_version(self, device_id: str, app_id: int, version: Dict[str, Any]) -> Dict[str, Any]:
        app = self.get_app(app_id)
        if app is None:
            raise KeyError(f"app not found: {app_id}")
        if self.get_device(device_id) is None:
            raise KeyError(f"device not found: {device_id}")

        timestamp = now_iso()
        package_name = str(version.get("package_name") or app["package_name"])
        activity = str(version.get("activity") or app.get("activity") or "")
        values = {
            "device_id": device_id,
            "app_id": app_id,
            "package_name": package_name,
            "activity": activity,
            "version_name": str(version.get("version_name") or ""),
            "version_code": str(version.get("version_code") or ""),
            "last_update_time": str(version.get("last_update_time") or ""),
            "installer_package": str(version.get("installer_package") or ""),
            "signature_hint": str(version.get("signature_hint") or ""),
            "apk_archive_path": str(version.get("apk_archive_path") or ""),
            "last_version_check_at": now_iso(),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO device_app_states (
                    device_id, app_id, package_name, activity, version_name, version_code,
                    last_update_time, installer_package, signature_hint, apk_archive_path,
                    last_version_check_at, created_at, updated_at
                )
                VALUES (
                    :device_id, :app_id, :package_name, :activity, :version_name, :version_code,
                    :last_update_time, :installer_package, :signature_hint, :apk_archive_path,
                    :last_version_check_at, :created_at, :updated_at
                )
                ON CONFLICT(device_id, package_name) DO UPDATE SET
                    app_id=excluded.app_id,
                    activity=excluded.activity,
                    version_name=excluded.version_name,
                    version_code=excluded.version_code,
                    last_update_time=excluded.last_update_time,
                    installer_package=excluded.installer_package,
                    signature_hint=excluded.signature_hint,
                    apk_archive_path=excluded.apk_archive_path,
                    last_version_check_at=excluded.last_version_check_at,
                    updated_at=excluded.updated_at
                RETURNING *
                """,
                values,
            )
            return dict(cur.fetchone())

    def update_device_app_validation(self, device_id: str, app_id: int, *, status: str, message: str) -> Dict[str, Any]:
        app = self.get_app(app_id)
        if app is None:
            raise KeyError(f"app not found: {app_id}")
        existing = self.get_device_app_state(device_id, app_id)
        if existing is None:
            existing = self.update_device_app_version(
                device_id,
                app_id,
                {
                    "package_name": app["package_name"],
                    "activity": app.get("activity", ""),
                },
            )
        timestamp = now_iso()
        with self.connect() as conn:
            cur = conn.execute(
                """
                UPDATE device_app_states
                SET last_validation_status=?,
                    last_validation_message=?,
                    last_validation_at=?,
                    updated_at=?
                WHERE id=?
                RETURNING *
                """,
                (status, message, timestamp, timestamp, existing["id"]),
            )
            row = cur.fetchone()
            if row is None:
                raise KeyError(f"device app state not found: {device_id}/{app_id}")
            return dict(row)

    def get_device_app_state(self, device_id: str, app_id: int) -> Optional[Dict[str, Any]]:
        app = self.get_app(app_id)
        if app is None:
            return None
        with self.connect() as conn:
            return row_to_dict(
                conn.execute(
                    "SELECT * FROM device_app_states WHERE device_id=? AND package_name=?",
                    (device_id, app["package_name"]),
                ).fetchone()
            )

    def update_app_validation(self, app_id: int, *, status: str, message: str) -> Dict[str, Any]:
        return self.update_app(
            app_id,
            last_validation_status=status,
            last_validation_message=message,
            last_validation_at=now_iso(),
        )

    def mark_app_success(self, app_id: Optional[int]) -> None:
        if not app_id:
            return
        self.update_app(app_id, last_success_at=now_iso())

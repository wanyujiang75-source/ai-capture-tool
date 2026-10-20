"""Persistent, device-scoped ownership of temporary network shaping rules."""

import hashlib
import json
import os
import threading
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class NetworkProfile:
    upload_kbps: int
    download_kbps: int
    latency_ms: int

    def __post_init__(self):
        for value, low, high in (
            (self.upload_kbps, 32, 100000),
            (self.download_kbps, 32, 100000),
            (self.latency_ms, 0, 5000),
        ):
            if type(value) is not int or not low <= value <= high:
                raise ValueError("速率应为 32–100000 kbps，额外往返延迟应为 0–5000 ms。")


class WeakNetworkService:
    def __init__(self, directory: Path, device_factory, recovery_factory):
        self.directory = directory
        self.device_factory = device_factory
        self.recovery_factory = recovery_factory
        self.lock = threading.RLock()
        self.records = {}
        self.errors = {}
        self.load_error = ""
        if directory.exists():
            for path in directory.glob("*.json"):
                try:
                    if path.stat().st_size > 65536:
                        raise ValueError("oversized recovery record")
                    record = json.loads(path.read_text())
                    key = record.get("device_key", record["device_id"])
                    if path != self.path(key) or not isinstance(record["saved"], dict):
                        raise ValueError("invalid recovery record")
                    NetworkProfile(**record["profile"])
                    record["pending"] = True
                    stable_key = self.identity_key(record["saved"])
                    record["device_key"] = stable_key
                    if key != stable_key:
                        self.persist(record)
                        path.unlink()
                    self.records[stable_key] = record
                except (ValueError, KeyError, TypeError, OSError) as exc:
                    self.load_error = f"无法读取弱网恢复记录：{path.name}: {exc}"

    def path(self, device_id):
        key = hashlib.sha256(device_id.encode()).hexdigest()[:24]
        return self.directory / f"{key}.json"

    @staticmethod
    def identity_key(target):
        return json.dumps([target["serial"], target["avd"]])

    def persist(self, record):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path(record["device_key"])
        temporary = path.with_suffix(".tmp")
        with temporary.open("w") as output:
            os.chmod(temporary, 0o600)
            json.dump(record, output)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)

    def state(self, device_id):
        record = self.records.get(device_id)
        pending = bool(record and record["pending"])
        error = self.errors.get(device_id, "") or self.load_error
        enabled = bool(record and not pending and not error)
        message = (
            "弱网已开启，当前模拟器中的所有应用都会受到影响。"
            if enabled else "网络已恢复，未启用弱网模拟。"
        )
        if pending:
            message = "网络设置尚未恢复。请保持模拟器在线，工具将自动重试；也可点击恢复网络。"
        elif error:
            message = "无法启用弱网。请确认模拟器已启动并完成环境准备，且没有其他限速规则。"
        return {
            "enabled": enabled,
            "pending_restore": pending,
            "available": not error and not pending,
            "profile": record["profile"] if record else None,
            "message": message,
            "technical_detail": error,
        }

    def status(self, device_id):
        with self.lock:
            key = self.identity_key(self.device_factory(device_id).target())
            self.check_record(key)
            return self.state(key)

    def check_record(self, key):
        record = self.records.get(key)
        if record and not record["pending"]:
            try:
                self.recovery_factory(record["saved"]).verify(record["saved"], NetworkProfile(**record["profile"]))
            except Exception as exc:
                record["pending"] = True
                self.errors[key] = str(exc)

    def apply(self, device_id, profile: NetworkProfile):
        with self.lock:
            device = self.device_factory(device_id)
            key = self.identity_key(device.target())
            if self.load_error:
                return self.state(key)
            if key in self.records:
                self.restore_record(key)
                if key in self.records:
                    return self.state(key)
            self.errors.pop(key, None)
            try:
                saved = device.snapshot()
                record = {"device_id": device_id, "device_key": key, "saved": saved, "profile": asdict(profile), "pending": True}
                # Durable intent precedes the first device mutation.
                self.persist(record)
                self.records[key] = record
                device.apply(saved, profile)
                device.verify(saved, profile)
                record["pending"] = False
                self.persist(record)
            except Exception as exc:
                failure = str(exc)
                if key in self.records:
                    self.restore_record(key)
                self.errors[key] = failure + ("; " + self.errors[key] if key in self.errors else "")
            return self.state(key)

    def restore(self, device_id):
        with self.lock:
            key = self.identity_key(self.device_factory(device_id).target())
            self.restore_record(key)
            return self.state(key)

    def restore_record(self, key):
        record = self.records.get(key)
        try:
            if record:
                record["pending"] = True
                self.recovery_factory(record["saved"]).restore(record["saved"])
                self.path(key).unlink(missing_ok=True)
                del self.records[key]
            self.errors.pop(key, None)
        except Exception as exc:
            self.errors[key] = str(exc)

    def recover(self):
        with self.lock:
            for key in list(self.records):
                self.check_record(key)
                if self.records[key]["pending"]:
                    self.restore_record(key)

    def restore_all(self):
        with self.lock:
            for key in list(self.records):
                self.restore_record(key)

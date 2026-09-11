from __future__ import annotations

from hashlib import sha256
from typing import Any, Iterable


def parse_adb_devices(output: str) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("list of devices"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        metadata = {}
        for token in parts[2:]:
            key, separator, value = token.partition(":")
            if separator:
                metadata[key] = value
        kind = "emulator" if serial.startswith("emulator-") else "physical"
        connection_type = _connection_type(serial, kind)
        devices.append({
            "serial": serial,
            "status": state,
            "kind": kind,
            "connection_type": connection_type,
            "model": metadata.get("model", ""),
        })
    return devices


def _stable_device_id(serial: str, kind: str) -> str:
    digest = sha256(serial.encode("utf-8")).hexdigest()[:12]
    return f"adb-{kind}-{digest}"


def _connection_type(serial: str, kind: str) -> str:
    if kind == "emulator":
        return "emulator"
    if ":" in serial or "._adb-tls-connect._tcp" in serial:
        return "wireless"
    return "usb"


def _device_name(kind: str, model: str) -> str:
    if model:
        return model.replace("_", " ")
    return "Android 模拟器" if kind == "emulator" else "Android 真机"


def _slot_ports(slot: int, *, proxy_port_start: int, web_port_start: int, frida_port_start: int) -> tuple[int, int, int]:
    return proxy_port_start + slot * 10, web_port_start + slot * 10, frida_port_start + slot * 100


def _next_free_slot(
    occupied_ports: set[int],
    *,
    proxy_port_start: int,
    web_port_start: int,
    frida_port_start: int,
) -> tuple[int, int, int]:
    slot = 0
    while True:
        ports = _slot_ports(
            slot,
            proxy_port_start=proxy_port_start,
            web_port_start=web_port_start,
            frida_port_start=frida_port_start,
        )
        if not any(port in occupied_ports for port in ports):
            occupied_ports.update(ports)
            return ports
        slot += 1


def build_discovered_devices(
    adb_devices: Iterable[dict[str, Any]],
    *,
    proxy_port_start: int,
    web_port_start: int,
    frida_port_start: int,
    occupied_ports: Iterable[int] | None = None,
) -> list[dict[str, Any]]:
    occupied = {int(port) for port in occupied_ports or []}
    devices: list[dict[str, Any]] = []
    online_devices = [
        device
        for device in adb_devices
        if str(device.get("serial") or "").strip()
        and str(device.get("status") or "device").strip() == "device"
    ]
    for index, adb_device in enumerate(online_devices, start=1):
        serial = str(adb_device["serial"]).strip()
        kind = str(adb_device.get("kind") or ("emulator" if serial.startswith("emulator-") else "physical"))
        proxy_port, web_port, frida_port = _next_free_slot(
            occupied,
            proxy_port_start=proxy_port_start,
            web_port_start=web_port_start,
            frida_port_start=frida_port_start,
        )
        label = "Android Emulator" if kind == "emulator" else "Android Device"
        devices.append({
            "device_id": f"device-{index}",
            "name": f"{label} {serial}",
            "avd_name": "",
            "adb_serial": serial,
            "proxy_port": proxy_port,
            "web_port": web_port,
            "frida_port": frida_port,
            "enabled": 1,
            "resident": 0,
            "idle_release_minutes": 10,
        })
    return devices


def build_log_devices(
    adb_devices: Iterable[dict[str, Any]],
    *,
    proxy_port_start: int,
    web_port_start: int,
    frida_port_start: int,
    occupied_ports: Iterable[int] | None = None,
    existing_devices: Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    occupied = {int(port) for port in occupied_ports or []}
    existing_by_serial = {
        str(device.get("adb_serial") or "").strip(): dict(device)
        for device in existing_devices or []
        if str(device.get("adb_serial") or "").strip()
    }
    devices: list[dict[str, Any]] = []
    for adb_device in adb_devices:
        serial = str(adb_device.get("serial") or "").strip()
        status = str(adb_device.get("status") or "device").strip()
        if not serial or status != "device":
            continue
        kind = str(adb_device.get("kind") or ("emulator" if serial.startswith("emulator-") else "physical"))
        connection_type = str(
            adb_device.get("connection_type")
            or _connection_type(serial, kind)
        )
        model = str(adb_device.get("model") or "").strip()
        existing = existing_by_serial.get(serial)
        if existing is not None:
            devices.append({
                **existing,
                "source": "adb",
                "kind": kind,
                "connection_type": connection_type,
                "adb_state": status,
                "model": model,
            })
            continue
        proxy_port, web_port, frida_port = _next_free_slot(
            occupied,
            proxy_port_start=proxy_port_start,
            web_port_start=web_port_start,
            frida_port_start=frida_port_start,
        )
        devices.append({
            "device_id": _stable_device_id(serial, kind),
            "name": _device_name(kind, model),
            "avd_name": "",
            "adb_serial": serial,
            "proxy_port": proxy_port,
            "web_port": web_port,
            "frida_port": frida_port,
            "enabled": 0,
            "resident": 0,
            "idle_release_minutes": 10,
            "source": "adb",
            "kind": kind,
            "connection_type": connection_type,
            "adb_state": status,
            "model": model,
        })
    return devices

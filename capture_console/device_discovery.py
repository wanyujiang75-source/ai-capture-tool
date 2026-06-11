from __future__ import annotations

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
        if state != "device":
            continue
        devices.append({
            "serial": serial,
            "status": state,
            "kind": "emulator" if serial.startswith("emulator-") else "physical",
        })
    return devices


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
    for index, adb_device in enumerate(adb_devices, start=1):
        serial = str(adb_device.get("serial") or "").strip()
        if not serial:
            continue
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
            "source": "adb",
            "kind": kind,
        })
    return devices

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import urlparse


PROJECT_PROCESS_MARKERS = (
    "ai_capture",
    "capture_console",
    "flutter_proxy_unpin_capture.py",
    "mitmweb-socks",
    "mitmweb-",
    "launch-mitmweb",
    "web_password=android-capture",
    "adb -L tcp:5037 fork-server",
)


def parse_proxy_port(value: str | None) -> Optional[int]:
    if not value:
        return None
    raw = value.strip()
    if not raw or raw.lower() in {"none", "null", "direct", ":0"}:
        return None
    if "://" not in raw:
        raw = f"http://{raw}"
    parsed = urlparse(raw)
    if parsed.port:
        return int(parsed.port)
    match = re.search(r":(\d+)$", value.strip())
    return int(match.group(1)) if match else None


def external_dependency_ports_from_env(env: Dict[str, str] | None = None) -> set[int]:
    env = env or os.environ
    ports: set[int] = set()
    for key in (
        "CAPTURE_HOST_PROXY",
        "CAPTURE_EMULATOR_PROXY",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        port = parse_proxy_port(env.get(key))
        if port is not None:
            ports.add(port)
    return ports


def _run_text(args: list[str], *, timeout: int = 5) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", exc.stderr or "command timed out"


def _parse_lsof_pids(output: str) -> list[int]:
    pids: list[int] = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.upper().startswith("COMMAND"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            pids.append(int(parts[1]))
        except ValueError:
            continue
    return sorted(set(pids))


def collect_port_listeners(port: int, *, command_runner: Callable[[list[str]], tuple[int, str, str]] | None = None) -> list[Dict[str, Any]]:
    run = command_runner or (lambda args: _run_text(args, timeout=5))
    code, stdout, stderr = run(["lsof", "-n", "-P", f"-iTCP:{int(port)}", "-sTCP:LISTEN"])
    if code == 1 and not stdout:
        return []
    if code not in {0, 1} and not stdout:
        return [{"pid": 0, "command": "", "error": stderr or f"lsof failed with code {code}"}]

    listeners: list[Dict[str, Any]] = []
    for pid in _parse_lsof_pids(stdout):
        ps_code, ps_stdout, ps_stderr = run(["ps", "-p", str(pid), "-o", "command="])
        command = ps_stdout.strip() if ps_code == 0 else ""
        listeners.append({
            "pid": pid,
            "command": command,
            "error": "" if ps_code == 0 else ps_stderr.strip(),
        })
    return listeners


def command_owned_by_project(command: str, *, project_root: Path, runtime_dir: Path) -> bool:
    normalized = command or ""
    roots = {str(project_root.resolve()), str(runtime_dir.resolve())}
    if any(root and root in normalized for root in roots):
        return True
    return any(marker in normalized for marker in PROJECT_PROCESS_MARKERS)


def classify_port(
    port: int,
    listeners: Iterable[Dict[str, Any]],
    *,
    project_root: Path,
    runtime_dir: Path,
    external_dependency_ports: set[int] | None = None,
    label: str = "",
) -> Dict[str, Any]:
    listener_list = list(listeners)
    external_dependency_ports = external_dependency_ports or set()
    if not listener_list:
        return {
            "port": int(port),
            "label": label,
            "state": "free",
            "ok": True,
            "detail": "port is free",
            "listeners": [],
        }

    if any(listener.get("error") for listener in listener_list if int(listener.get("pid") or 0) <= 0):
        detail = "; ".join(str(listener.get("error")) for listener in listener_list if listener.get("error"))
        return {
            "port": int(port),
            "label": label,
            "state": "unknown",
            "ok": False,
            "detail": detail or "unable to inspect listeners",
            "listeners": listener_list,
        }

    if int(port) in external_dependency_ports:
        return {
            "port": int(port),
            "label": label,
            "state": "external_dependency",
            "ok": True,
            "detail": "; ".join(listener.get("command", "") for listener in listener_list) or "configured external dependency",
            "listeners": listener_list,
        }

    if all(
        command_owned_by_project(str(listener.get("command") or ""), project_root=project_root, runtime_dir=runtime_dir)
        for listener in listener_list
    ):
        return {
            "port": int(port),
            "label": label,
            "state": "owned_by_project",
            "ok": True,
            "detail": "; ".join(listener.get("command", "") for listener in listener_list),
            "listeners": listener_list,
        }

    return {
        "port": int(port),
        "label": label,
        "state": "occupied_by_other",
        "ok": False,
        "detail": "; ".join(listener.get("command", "") for listener in listener_list),
        "listeners": listener_list,
    }


def _unique_port_items(devices: Iterable[Dict[str, Any]], env: Dict[str, str]) -> list[tuple[int, str]]:
    items: list[tuple[int, str]] = []
    for device in devices:
        device_id = device.get("device_id", "device")
        for field, suffix in (("proxy_port", "proxy"), ("web_port", "mitmweb"), ("frida_port", "frida")):
            value = device.get(field)
            if value:
                items.append((int(value), f"{device_id} {suffix}"))
    for key, fallback, label in (
        ("CONSOLE_PORT", "7001", "web backend"),
        ("FRONTEND_PORT", "7002", "web frontend"),
        ("EMULATOR_PREVIEW_PORT", "19097", "emulator preview"),
        ("EMULATOR_PREVIEW_WS_PORT", "19098", "emulator preview ws"),
    ):
        value = env.get(key, fallback)
        if str(value).isdigit():
            items.append((int(value), label))

    labels_by_port: dict[int, list[str]] = {}
    for port, label in items:
        labels_by_port.setdefault(port, []).append(label)
    return [(port, ", ".join(labels)) for port, labels in sorted(labels_by_port.items())]


def build_port_preflight(
    devices: Iterable[Dict[str, Any]],
    *,
    env: Dict[str, str] | None = None,
    project_root: Path,
    runtime_dir: Path,
    collect: Callable[[int], list[Dict[str, Any]]] = collect_port_listeners,
) -> Dict[str, Any]:
    env = env or os.environ
    external_ports = external_dependency_ports_from_env(env)
    ports = [
        classify_port(
            port,
            collect(port),
            project_root=project_root,
            runtime_dir=runtime_dir,
            external_dependency_ports=external_ports,
            label=label,
        )
        for port, label in _unique_port_items(devices, env)
    ]
    blocking = [item for item in ports if not item["ok"]]
    return {
        "ok": not blocking,
        "ports": ports,
        "blocking": blocking,
        "external_dependency_ports": sorted(external_ports),
    }

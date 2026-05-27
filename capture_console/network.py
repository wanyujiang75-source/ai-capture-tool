from __future__ import annotations

import os
import subprocess
from typing import Any, Dict
from urllib.parse import urlparse


DIRECT_PROXY_VALUES = {"", "null", "none", ":0", "0.0.0.0:0"}


def normalize_android_proxy(value: str | None) -> str:
    return (value or "").strip().replace("\r", "")


def android_proxy_mode(value: str | None) -> str:
    proxy = normalize_android_proxy(value).lower()
    return "direct" if proxy in DIRECT_PROXY_VALUES else "maintenance_proxy"


def build_device_network_state(emulator: Dict[str, Any]) -> Dict[str, Any]:
    proxy = normalize_android_proxy(emulator.get("android_proxy"))
    online = bool(emulator.get("adb_online") and emulator.get("boot_completed"))
    return {
        "ok": online,
        "mode": android_proxy_mode(proxy),
        "android_proxy": proxy or "null",
        "adb_online": bool(emulator.get("adb_online")),
        "boot_completed": bool(emulator.get("boot_completed")),
        "user_message": "模拟器网络可检查。" if online else "模拟器未在线或系统未启动完成，无法确认网络。",
    }


def proxy_from_env(env: Dict[str, str] | None = None) -> str:
    env = env or os.environ
    raw = env.get("CAPTURE_EMULATOR_PROXY") or env.get("CAPTURE_HOST_PROXY") or ""
    if not raw:
        return ""
    candidate = raw if "://" in raw else f"http://{raw}"
    parsed = urlparse(candidate)
    if parsed.hostname and parsed.port:
        return f"{parsed.hostname}:{parsed.port}"
    return raw


def _curl(url: str, *, proxy: str = "", timeout: int = 8) -> Dict[str, Any]:
    args = ["curl", "-L", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(timeout)]
    if proxy:
        args.extend(["--proxy", proxy])
    args.append(url)
    try:
        proc = subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout + 2)
    except FileNotFoundError as exc:
        return {"ok": False, "status": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "status": "", "stderr": exc.stderr or "curl timed out"}
    status = proc.stdout.strip()
    return {
        "ok": proc.returncode == 0 and status.startswith(("2", "3")),
        "status": status,
        "stderr": proc.stderr.strip(),
    }


def build_host_network_check(env: Dict[str, str] | None = None) -> Dict[str, Any]:
    env = env or os.environ
    url = env.get("CAPTURE_NETWORK_TEST_URL", "https://www.google.com/generate_204")
    configured_proxy = proxy_from_env(env)
    direct = _curl(url)
    proxy = _curl(url, proxy=configured_proxy) if configured_proxy else None
    checks = [{"name": "host_direct", "target": url, **direct}]
    if proxy is not None:
        checks.append({"name": "host_proxy", "target": url, "proxy": configured_proxy, **proxy})
    return {
        "ok": any(check.get("ok") for check in checks),
        "checks": checks,
        "configured_proxy": configured_proxy,
    }

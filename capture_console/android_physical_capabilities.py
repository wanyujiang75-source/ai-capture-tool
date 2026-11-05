"""Read-only AP-0 evidence collection, deliberately disconnected from capture startup."""

import re
import selectors
import subprocess
import time
from datetime import datetime, timezone

from .device_discovery import parse_adb_devices


def run_readonly(key, argv):
    """Bound both output and duration; never return raw command errors or credentials."""
    del key
    with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:
        chunks = bytearray()
        deadline = time.monotonic() + 8
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("read-only probe timed out")
                    if not selector.select(remaining):
                        raise TimeoutError("read-only probe timed out")
                    chunk = proc.stdout.read1(4096)
                    if not chunk:
                        break
                    chunks.extend(chunk)
                    if len(chunks) > 65536:
                        raise ValueError("read-only probe output limit")
            if proc.wait(timeout=max(0.01, deadline - time.monotonic())) != 0:
                raise RuntimeError("read-only probe failed")
            return chunks.decode("utf-8", errors="replace").strip()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


def inspect_device(adb, serial, package, *, execute=run_readonly):
    """Collect exact-device evidence without granting root or selecting a capture route.

    Package installer metadata is a hint, not proof of original APK provenance.
    TLS, app HTTP, and breakpoint readiness require subsequent authorized validation.
    """
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", serial):
        raise ValueError("invalid device serial")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", package):
        raise ValueError("invalid package name")
    result = {
        "status": "blocked", "device_kind": "physical", "serial": serial,
        "capture_ready": False, "recommended_mode": None,
        "tls_state": "unknown", "app_http_state": "unknown",
        "breakpoint_state": "unknown", "transport_state": "unknown",
        "evidence_at": datetime.now(timezone.utc).isoformat(), "issues": [],
    }
    try:
        devices = parse_adb_devices(execute("devices", [adb, "devices", "-l"]))
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError):
        result["status"] = "unknown"
        result["issues"].append("device_inventory_unavailable")
        return result
    matches = [device for device in devices if device["serial"] == serial]
    if len(matches) != 1:
        result["status"] = "disconnected" if not matches else "ambiguous_device"
        return result
    device = matches[0]
    if device["status"] != "device":
        result["status"] = device["status"]
        return result
    if device["kind"] != "physical":
        result["device_kind"] = device["kind"]
        result["status"] = "wrong_device_kind"
        return result

    # Fixed read-only command set. Validated identifiers cannot add shell syntax.
    probes = {
        "model": "getprop ro.product.model",
        "android": "getprop ro.build.version.release",
        "sdk": "getprop ro.build.version.sdk",
        "abi": "getprop ro.product.cpu.abi",
        "boot": "getprop sys.boot_completed",
        "uid": "id -u",
        "verified_boot": "getprop ro.boot.verifiedbootstate",
        "boot_locked": "getprop ro.boot.flash.locked",
        "user": "am get-current-user",
        "package": f"dumpsys package {package} | grep -E 'versionCode=|versionName=|flags=|pkgFlags=|installerPackageName=' | head -c 16384",
        "paths": f"pm path {package} | head -c 8192",
        "proxy": "settings get global http_proxy",
        "vpn": "dumpsys connectivity | grep -E 'Transports:.*VPN|Active default network:' | head -c 8192",
        "policy": "dumpsys device_policy | grep -E 'no_config_vpn=true|no_debugging_features=true|no_config_credentials=true' | head -c 2048",
    }
    evidence = {}
    for key, command in probes.items():
        if key in ("package", "paths") and evidence.get("user") != "0":
            evidence[key] = None
            if key == "package":
                result["issues"].append("unsupported_android_user")
            continue
        try:
            evidence[key] = execute(key, [adb, "-s", serial, "shell", command])
        except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError):
            evidence[key] = None
            result["issues"].append(f"{key}_unavailable")

    def field(pattern):
        match = re.search(pattern, evidence["package"] or "")
        return match.group(1) if match else None

    flags = field(r"(?:pkgFlags|flags)=\[([^\]]*)\]")
    result["package_identity"] = {
        "package_name": package,
        "version_name": field(r"versionName=([^\s]+)"),
        "version_code": field(r"versionCode=(\d+)"),
        "target_sdk": field(r"targetSdk=(\d+)"),
        "installer": field(r"installerPackageName=([^\s]+)"),
        "debuggable": "DEBUGGABLE" in flags.split() if flags is not None else None,
        "apk_paths": [line[8:] for line in (evidence["paths"] or "").splitlines() if line.startswith("package:/")],
        "provenance": "unverified",
    }
    result["device"] = {key: evidence[key] for key in ("model", "android", "sdk", "abi", "boot", "user", "verified_boot", "boot_locked")}
    result["root_state"] = "adb_uid_zero" if evidence["uid"] == "0" else ("not_observed" if evidence["uid"] == "2000" else "unknown")
    result["vpn_state"] = "transport_observed" if re.search(r"Transports:.*\bVPN\b", evidence["vpn"] or "") else "unknown"
    result["global_proxy_state"] = "unset" if evidence["proxy"] in ("null", ":0") else ("configured" if evidence["proxy"] else "unknown")
    result["transport_state"] = "adb_authorized_only"
    result["issues"].append("no_verified_capture_path")
    if not result["package_identity"]["apk_paths"]:
        result["issues"].append("package_not_confirmed")
    if evidence["policy"]:
        result["issues"].append("device_policy_present")
    result["required_actions"] = ["Verify original APK identity and an authorized transport/TLS path before capture."]
    return result

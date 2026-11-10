"""Opt-in node delivery; never selects a node or changes VPN routing."""

import base64
import ipaddress
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import time


class IOSShadowrocket:
    def __init__(self, service, *, runner=subprocess.run):
        self.service, self.runner = service, runner

    def _snapshot(self, *, importing=False):
        with self.service.lock:
            state = self.service.status()
            cfg = self.service.config
            if (not cfg or not self.service.process or self.service.process.poll() is not None
                    or state.get("phase") in {"idle", "failed", "stopped", "preparing"}):
                raise ValueError("请先准备 iPhone 连接，再获取本机节点参数。")
            if importing and state.get("recording_state") == "recording":
                raise ValueError("请先停止抓包，再导入节点；现有连接不会被修改。")
            if (self.service.host_provider() != cfg["host"]
                    or cfg.get("expires_at", time.time() + 1) <= time.time()):
                raise ValueError("本机连接信息已变化，请重新准备连接后再导入节点。")
            ip = ipaddress.ip_address(cfg["host"])
            if ip.version != 4 or not ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ValueError("本机局域网地址不可用，请重新准备连接。")
            return {key: cfg[key] for key in ("host", "port", "username", "password")}

    def _devices(self):
        try:
            with tempfile.TemporaryDirectory(prefix="capture-device-list-") as tmp:
                path = Path(tmp) / "devices.json"
                result = self.runner(["/usr/bin/xcrun", "devicectl", "list", "devices", "--timeout", "5",
                                      "--json-output", str(path)], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, timeout=8, check=False)
                if result.returncode or path.stat().st_size > 2_000_000:
                    return []
                rows = json.loads(path.read_text())["result"]["devices"]
            devices = []
            for row in rows[:256]:
                if not isinstance(row, dict):
                    continue
                props = row.get("properties", {})
                hardware = props.get("hardware", row.get("hardwareProperties", {}))
                connection = props.get("connection", row.get("connectionProperties", {}))
                name = props.get("state", row.get("deviceProperties", {})).get("name", "iPhone")
                identifier = hardware.get("udid", "")
                if (hardware.get("reality", "physical") == "physical" and hardware.get("deviceType") == "iPhone"
                        and connection.get("transportType") == "wired" and connection.get("pairingState") == "paired"
                        and connection.get("state", connection.get("tunnelState")) == "connected"
                        and isinstance(identifier, str) and 1 <= len(identifier) <= 80
                        and all(c.isalnum() or c == "-" for c in identifier)):
                    devices.append({"id": identifier, "name": str(name)[:80]})
            return devices
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired, TimeoutError):
            return []

    def _certificate_profile(self):
        root = Path(self.service.directory)
        source = root / "iPhone.mobileconfig"
        target = root / "shadowrocket"
        if source.is_symlink() or target.is_symlink() or source.stat().st_size > 2_000_000:
            raise ValueError("测试配置不可读取，请重新准备连接。")
        profile = plistlib.loads(source.read_bytes())
        profile["PayloadContent"] = [p for p in profile["PayloadContent"] if p["PayloadType"] in {
            "com.apple.security.root", "com.apple.webClip.managed"}]
        if [p["PayloadType"] for p in profile["PayloadContent"]] != ["com.apple.security.root", "com.apple.webClip.managed"]:
            raise ValueError("测试证书配置不完整，请重新准备连接。")
        profile["PayloadDescription"] = "仅含测试证书和检查入口，不包含 Wi-Fi、VPN 或代理设置。"
        target.mkdir(mode=0o700, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                os.chmod(temporary, 0o600)
                stream.write(plistlib.dumps(profile, sort_keys=False))
                stream.close()
                temporary.replace(target / "iPhone.mobileconfig")
            finally:
                temporary.unlink(missing_ok=True)
        return str(target / "iPhone.mobileconfig")

    def connection(self):
        config = self._snapshot()
        authority = f"{config['username']}:{config['password']}@{config['host']}:{config['port']}"
        encoded = base64.urlsafe_b64encode(authority.encode()).decode().rstrip("=")
        devices = self._devices()
        with self.service.lock:
            if self._snapshot() != config:
                raise ValueError("连接参数已变化，请刷新节点信息。")
            profile = self._certificate_profile()
        return {**config, "import_url": f"shadowrocket://add/http://{encoded}?remarks=Capture-Mac",
                "profile_path": profile, "devices": devices}

    def send(self, device_id):
        config = self._snapshot(importing=True)
        devices = self._devices()
        if self._snapshot(importing=True) != config:
            raise ValueError("连接参数已变化，请刷新节点信息。")
        if not devices:
            return {"state": "manual_required"}
        if device_id not in {item["id"] for item in devices}:
            raise ValueError("所选 iPhone 已断开，请刷新设备后重新选择。")
        authority = f"{config['username']}:{config['password']}@{config['host']}:{config['port']}"
        encoded = base64.urlsafe_b64encode(authority.encode()).decode().rstrip("=")
        url = f"shadowrocket://add/http://{encoded}?remarks=Capture-Mac"
        try:
            result = self.runner(["/usr/bin/xcrun", "devicectl", "device", "process", "launch", "--device", device_id,
                                  "--payload-url", url, "com.liguangming.Shadowrocket"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12, check=False)
            return {"state": "confirmation_required" if result.returncode == 0 else "manual_required"}
        except (OSError, subprocess.TimeoutExpired, TimeoutError):
            return {"state": "manual_required"}

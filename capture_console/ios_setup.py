"""Isolated, opt-in iPhone proxy setup; never mutates device or Mac settings."""

import ipaddress
import json
import os
import plistlib
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path


POKEHUB_HOSTS = ["yqctnvcripabohfhzgya.supabase.co"]


def process_identity(pid):
    if not isinstance(pid, int) or pid <= 1:
        return None
    result = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "uid=,lstart="],
                            capture_output=True, text=True, timeout=2)
    fields = result.stdout.strip().split(maxsplit=1)
    if result.returncode or len(fields) != 2 or fields[0] != str(os.getuid()):
        return None
    return result.stdout.strip()


def validate_ssid(value):
    if not value or len(value.encode("utf-8")) > 32 or any(ord(c) < 32 for c in value):
        raise ValueError("请填写完整 Wi-Fi 名称，长度不能超过 32 字节。")
    return value


def make_profile(config, certificate):
    ssid = validate_ssid(config["ssid"])
    identifier = "com.local.capture.ios." + config["check_token"]
    def payload(kind, name, **values):
        return {"PayloadType": kind, "PayloadVersion": 1,
                "PayloadIdentifier": identifier + "." + kind,
                "PayloadUUID": str(uuid.uuid4()), "PayloadDisplayName": name, **values}
    return plistlib.dumps(payload(
        "Configuration", "抓包工具 iPhone 临时配置", PayloadRemovalDisallowed=False,
        DurationUntilRemoval=86400,
        PayloadDescription="仅用于 PokeHub 测试。会配置当前 Wi-Fi 代理和测试证书；结束后请删除此描述文件。24 小时后自动移除。",
        PayloadContent=[
            payload("com.apple.wifi.managed", "测试网络", SSID_STR=ssid, EncryptionType="Any",
                    AutoJoin=True, ProxyType="Manual", ProxyServer=config["host"],
                    ProxyServerPort=config["port"], ProxyUsername=config["username"],
                    ProxyPassword=config["password"]),
            payload("com.apple.security.root", "抓包工具 iPhone 测试证书", PayloadContent=certificate,
                    PayloadCertificateFileName="capture-ios.cer"),
            payload("com.apple.webClip.managed", "检查抓包连接", Label="检查抓包连接", IsRemovable=True,
                    URL=f"https://capture-check.invalid/{config['check_token']}", FullScreen=False),
        ],
    ), sort_keys=False)


def local_wifi_address():
    # Do not use a VPN's default route or query any public discovery service.
    for interface in ("en0", "en1"):
        result = subprocess.run(["/usr/sbin/ipconfig", "getifaddr", interface],
                                capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            address = result.stdout.strip()
            ip = ipaddress.ip_address(address)
            if ip.is_private and not ip.is_loopback and not ip.is_link_local:
                return address
    raise ValueError("未找到可用局域网地址，请让 Mac 与 iPhone 连接同一 Wi-Fi。")


class IOSSetupService:
    def __init__(self, root, host_provider=local_wifi_address):
        self.root = Path(root)
        self.host_provider = host_provider
        self.process = None
        self.config = None
        self.directory = None
        self.lock = threading.RLock()
        self.last = {"phase": "idle", "flow_count": 0, "flows": []}
        self.marker = self.root / "cleanup-required"
        if self.marker.exists():
            self.last["phase"] = "failed"
            name = self.marker.read_text()[:256]
            candidate = self.root / name
            if (name.startswith("session-") and Path(name).name == name
                    and candidate.is_dir() and not candidate.is_symlink()):
                self.directory = candidate

    def status(self):
        with self.lock:
            if self.process:
                if self.process.poll() is not None:
                    return {**self.last, "phase": "failed", "profile_path": None,
                            "message": "测试代理已退出，请先删除手机测试配置，再重新准备。"}
                path = Path(self.config["state_path"])
                try:
                    if path.stat().st_size >= 2_000_000:
                        raise ValueError("oversized status")
                    self.last = json.loads(path.read_text())
                except (OSError, ValueError):
                    if self.last["phase"] != "preparing":
                        return {**self.last, "phase": "failed", "profile_path": None, "check_url": None}
            return dict(self.last)

    def prepare(self, ssid, owner_pid=None):
        validate_ssid(ssid)
        with self.lock:
            if self.process and self.process.poll() is None:
                if self.config["ssid"] != ssid:
                    raise ValueError("已有连接配置，请先从手机删除旧配置并结束测试，再更换 Wi-Fi。")
                return self.status()
            if self.directory or self.marker.exists():
                raise ValueError("上次测试已中断，请先删除手机配置并结束测试，再重新准备。")
            owner_pid = owner_pid or os.getpid()
            owner_identity = process_identity(owner_pid)
            if not owner_identity:
                raise ValueError("桌面端连接已失效，请重新打开连接助手。")
            host = self.host_provider()
            ip = ipaddress.ip_address(host)
            if not ip.is_private or ip.is_loopback or ip.is_link_local or ip.version != 4:
                raise ValueError("没有可供 iPhone 连接的局域网地址，请检查 Mac Wi-Fi。")
            with socket.socket() as probe:
                probe.bind((host, 0))
                port = probe.getsockname()[1]
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.directory = Path(tempfile.mkdtemp(prefix="session-", dir=self.root))
            self.marker.write_text(self.directory.name)
            self.marker.chmod(0o600)
            self.config = {
                "host": host, "port": port, "ssid": ssid, "username": "ios",
                "password": secrets.token_urlsafe(24), "check_token": secrets.token_hex(16),
                "hosts": POKEHUB_HOSTS, "parent_pid": os.getpid(),
                "owner_pid": owner_pid, "owner_identity": owner_identity,
                "confdir": str(self.directory / "ca"),
                "profile_path": str(self.directory / "iPhone.mobileconfig"),
                "state_path": str(self.directory / "state.json"),
            }
            config_path = self.directory / "config.json"
            config_path.write_text(json.dumps(self.config))
            config_path.chmod(0o600)
            self.last = {"phase": "preparing", "flow_count": 0, "flows": []}
            try:
                with (self.directory / "worker.log").open("ab") as log:
                    self.process = subprocess.Popen(
                        [sys.executable, "-m", "capture_console.ios_pairing_proxy", str(config_path)],
                        cwd=Path(__file__).resolve().parents[1], stdin=subprocess.DEVNULL,
                        stdout=log, stderr=log, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    )
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    state = self.status()
                    if state["phase"] == "waiting_phone":
                        return state
                    if state["phase"] == "failed":
                        break
                    time.sleep(0.1)
                raise RuntimeError("未能启动 iPhone 测试代理，请检查运行组件后重试。")
            except Exception:
                self.stop()
                self.last["phase"] = "failed"
                raise

    def shutdown(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
            self.process = None
            if self.marker.exists():
                self.last = {"phase": "failed", "flow_count": 0, "flows": []}
            if self.directory and self.directory.exists():
                shutil.rmtree(self.directory)

    def stop(self):
        with self.lock:
            self.shutdown()
            self.last = {"phase": "stopped", "flow_count": 0, "flows": []}
            self.marker.unlink(missing_ok=True)
            if self.directory:
                self.directory = None
            return dict(self.last)

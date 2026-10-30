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

from .ios_projects import IOSProjects
from .ios_results import IOSCaptureArchive

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
        PayloadDescription="仅用于授权应用测试。会配置当前 Wi-Fi 代理和测试证书；结束连接后请删除此描述文件。24 小时后自动移除。",
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
    command_timeout = 5

    def __init__(self, root, host_provider=local_wifi_address, *, store=None):
        self.root = Path(root)
        self.host_provider = host_provider
        self.store = store
        self.projects = IOSProjects(self.root.parent / "ios-projects.json")
        self.session = None
        self.revision = 0
        self.last_network_check = 0
        self.process = None
        self.config = None
        self.directory = None
        self.lock = threading.RLock()
        self.last = {"phase": "idle", "connection_state": "idle", "recording_state": "idle",
                     "session_id": None, "flow_count": 0, "flows": []}
        self.marker = self.root / "cleanup-required"
        if self.marker.exists():
            self.last["phase"] = "failed"
            self.last["connection_state"] = "needs_cleanup"
            name = self.marker.read_text()[:256]
            candidate = self.root / name
            if (name.startswith("session-") and Path(name).name == name
                    and candidate.is_dir() and not candidate.is_symlink()):
                self.directory = candidate

    def status(self):
        with self.lock:
            if self.process:
                if self.process.poll() is not None:
                    self._set_session_status("failed")
                    return {**self.last, "phase": "failed", "connection_state": "needs_cleanup",
                            "recording_state": "failed", "profile_path": None,
                            "message": "测试代理已退出，请先删除手机测试配置，再重新准备。"}
                path = Path(self.config["state_path"])
                try:
                    if path.stat().st_size >= 2_000_000:
                        raise ValueError("oversized status")
                    self.last = json.loads(path.read_text())
                    if (self.session and self.last.get("session_id") == self.session["id"]
                            and self.last.get("recording_state") in {"stopped", "limit_reached", "failed"}):
                        self._set_session_status("failed" if self.last["recording_state"] == "failed" else "stopped")
                except (OSError, ValueError):
                    if self.last["phase"] != "preparing":
                        self._set_session_status("failed")
                        self.shutdown()
                        return {**self.last, "phase": "failed", "connection_state": "needs_cleanup",
                                "recording_state": "failed", "profile_path": None, "check_url": None}
                if self.config.get("expires_at") and time.monotonic() - self.last_network_check > 5:
                    self.last_network_check = time.monotonic()
                    try:
                        changed = self.host_provider() != self.config["host"]
                    except (OSError, ValueError, subprocess.TimeoutExpired):
                        changed = True
                    if changed or time.time() >= self.config["expires_at"]:
                        self._set_session_status("failed")
                        self.shutdown()
                        self.last.update(phase="failed", connection_state="needs_cleanup", recording_state="failed",
                                         message="网络地址已改变或连接配置已过期，请在手机删除旧配置后重新连接。")
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
            self.session = None
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
                "parent_pid": os.getpid(), "expires_at": time.time() + 86400,
                "owner_pid": owner_pid, "owner_identity": owner_identity,
                "confdir": str(self.directory / "ca"),
                "profile_path": str(self.directory / "iPhone.mobileconfig"),
                "state_path": str(self.directory / "state.json"),
                "control_path": str(self.directory / "control.json"),
                "capture_root": str((self.root.parent / "captures").resolve()),
            }
            config_path = self.directory / "config.json"
            config_path.write_text(json.dumps(self.config))
            config_path.chmod(0o600)
            self.last = {"phase": "preparing", "connection_state": "preparing", "recording_state": "idle",
                         "session_id": None, "flow_count": 0, "flows": []}
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

    def _set_session_status(self, status):
        if (self.session and self.store and self.session["status"] in {"starting", "running", "stopping"}
                and self.session["status"] != status):
            self.session = self.store.update_session_status(self.session["id"], status)

    def _write_control(self, command):
        path = Path(self.config["control_path"])
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(command))
        temporary.chmod(0o600)
        temporary.replace(path)

    def _command(self, action, **values):
        self.revision += 1
        command = {"revision": self.revision, "action": action, **values}
        try:
            self._write_control(command)
            deadline = time.monotonic() + self.command_timeout
            while time.monotonic() < deadline:
                state = self.status()
                if state["phase"] == "failed" or state.get("connection_state") != "ready" or not self.process:
                    break
                if state.get("applied_revision") == self.revision:
                    expected = {"recording", "limit_reached"} if action == "start" else {"stopped", "limit_reached"}
                    if (state.get("recording_state") in expected and self.session
                            and state.get("session_id") == self.session["id"]):
                        return state
                    break
                time.sleep(0.05)
        except (OSError, ValueError):
            pass
        self._set_session_status("failed")
        self.shutdown()
        self.last.update(phase="failed", connection_state="needs_cleanup", recording_state="failed")
        raise RuntimeError("手机连接中断，已停止本次抓包。请删除手机中的测试配置后重新连接。")

    def start_recording(self, project_id):
        with self.lock:
            state = self.status()
            project = self.projects.get(project_id)
            if state.get("recording_state") == "recording":
                if state.get("project", {}).get("id") == project_id:
                    return state
                raise ValueError("其他项目正在抓包，请先停止当前抓包再切换项目。")
            if state.get("connection_state") != "ready" or not self.process:
                raise ValueError("请先在 iPhone 完成配置安装、证书信任和 HTTPS 连接检查。")
            if self.store is None:
                from .store import CaptureStore
                self.store = CaptureStore(self.root.parent / "console.db")
            outdir = (self.root.parent / "captures" / ("ios-" + uuid.uuid4().hex)).resolve()
            IOSCaptureArchive(outdir).close()
            self.session = self.store.create_ios_session(connection_id=self.directory.name,
                                                        project_name=project["name"], outdir=str(outdir))
            state = self._command("start", session_id=self.session["id"], outdir=str(outdir), project=project)
            self._set_session_status("running" if state["recording_state"] == "recording" else "stopped")
            return state

    def stop_recording(self, session_id=None):
        with self.lock:
            state = self.status()
            if session_id is not None and state.get("session_id") != session_id:
                raise ValueError("该抓包已结束，请刷新后选择当前抓包。")
            if state.get("recording_state") != "recording":
                return state
            state = self._command("stop")
            self._set_session_status("stopped")
            return state

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
            self._set_session_status("stopped")
            if self.marker.exists():
                self.last.update(phase="failed", connection_state="needs_cleanup", recording_state="stopped",
                                 profile_path=None, check_url=None)
            if self.directory and self.directory.exists():
                shutil.rmtree(self.directory)

    def stop(self):
        with self.lock:
            self.shutdown()
            self.last = {"phase": "stopped", "connection_state": "idle", "recording_state": "stopped",
                         "session_id": None, "flow_count": 0, "flows": []}
            self.marker.unlink(missing_ok=True)
            self.session = None
            if self.directory:
                self.directory = None
            return dict(self.last)

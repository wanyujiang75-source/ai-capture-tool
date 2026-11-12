"""Desktop-owned physical Android capture and explicit network recovery."""

import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import uuid

from .android_physical_device import BRIDGE, PhysicalDevice, devices
from .android_physical_recovery import PendingRecoveries
from .ios_setup import local_wifi_address, process_identity
from .ios_results import IOSCaptureArchive

MODE = 'android-physical-wireguard'
ROOT = Path(__file__).resolve().parents[1]


def existing_upstream():
    result = subprocess.run(['/usr/sbin/scutil', '--proxy'], capture_output=True, text=True, timeout=5)
    text = result.stdout
    for prefix in ('HTTPS', 'HTTP'):
        if re.search(rf'\b{prefix}Enable\s*:\s*1\b', text):
            host = re.search(rf'\b{prefix}Proxy\s*:\s*([^\s]+)', text)
            port = re.search(rf'\b{prefix}Port\s*:\s*(\d+)', text)
            if not host or not port or not 0 < int(port[1]) < 65536:
                raise ValueError('当前电脑代理参数无效，请检查已有代理。')
            with socket.create_connection((host[1], int(port[1])), timeout=3):
                pass
            return [host[1], int(port[1])]
    if re.search(r'\b(?:SOCKSEnable|ProxyAutoConfigEnable)\s*:\s*1\b', text):
        raise ValueError('当前电脑仅有 SOCKS/PAC 代理，真机实验模式需要可用的 HTTP 代理；工具不会修改原配置。')
    return None


class PhysicalCaptureService:
    def __init__(self, root, store, adb):
        self.root, self.store, self.adb = Path(root), store, str(adb)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.marker = self.root / 'recovery.json'
        self.pending = PendingRecoveries(self.root)
        self.terminating = False
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.thread = self.process = self.device = self.directory = None
        self.info = {}
        self.last = {'phase': 'idle', 'flow_count': 0, 'response_count': 0, 'tls_failures': 0}
        if self.marker.exists():
            self.info = json.loads(self.marker.read_text())
            self.last.update(phase='recovery_required', serial=self.info['serial'], device_name=self.info.get('name'),
                             original_vpn=self.info.get('original_vpn'),
                             message='上次连接未完成恢复。请连接原手机，点击恢复网络。')

    def status(self):
        with self.lock:
            result = {**self.last, 'pending_recoveries': self.pending.summaries()}
            if self.terminating:
                result.update(phase='terminating', message='正在终止当前任务…完成后将重新检测手机，抓包记录会保留。')
            return result

    def update(self, **values):
        with self.lock:
            self.last.update(values)

    def journal(self, info):
        temporary = self.root / 'recovery.tmp'
        temporary.write_text(json.dumps(info))
        temporary.chmod(0o600)
        temporary.replace(self.marker)

    def start(self, serial, desktop_pid, experimental_consent):
        with self.lock:
            if not experimental_consent:
                raise ValueError('请先确认实验能力边界和临时 VPN 接管。')
            if self.terminating or self.marker.exists() or self.thread and self.thread.is_alive():
                raise ValueError('已有连接尚未结束，请先停止抓包并恢复原网络。')
            if self.pending.path(serial).exists():
                raise ValueError('这台手机的原网络尚未确认恢复，请先点击对应的“检查网络恢复”。')
            owner = process_identity(desktop_pid)
            if not owner:
                raise ValueError('桌面端进程已退出，请重新打开桌面端。')
            self.device = PhysicalDevice(self.adb, serial)
            self.info = {}
            self.process = self.directory = None
            self.cancel.clear()
            self.last = {'phase': 'preparing', 'flow_count': 0, 'response_count': 0, 'tls_failures': 0, 'serial': serial}
            self.thread = threading.Thread(target=self._run, args=(desktop_pid, owner), daemon=True)
            self.thread.start()
            return self.status()

    def _run(self, owner_pid, owner_identity):
        failed = None
        try:
            self.info = self.device.inspect()
            if self.info['original_vpn'] == BRIDGE:
                raise ValueError('手机已有临时抓包连接，请先在连接助手中停止。')
            self.update(package=self.info['package'], original_vpn=self.info['original_vpn'], device_name=self.info.get('name'))
            resources = ROOT.parent
            python = resources / 'physical-runtime/bin/python3'
            apk = resources / 'android-bridge.apk'
            if not python.exists():
                python = ROOT / 'macos-native/build/physical-runtime/bin/python3'
                apk = ROOT / 'android-bridge/app/build/outputs/apk/debug/app-debug.apk'
            if not python.is_file() or not apk.is_file():
                raise ValueError('此安装包缺少真机连接组件，请使用包含真机实验功能的完整桌面安装包。')
            upstream = existing_upstream()
            host = local_wifi_address()
            if not ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback:
                raise ValueError('未找到可用局域网，请将手机与 Mac 连接同一 Wi-Fi。')
            self.journal(self.info)
            self.update(phase='waiting_install', message='正在校验连接助手。如手机提示，请确认安装“抓包连接助手”；不会覆盖测试应用。')
            # PackageManager verifies the existing helper signer before we send keys.
            # A package-name-only check could trust an unrelated app using our ID.
            self.device.install(apk)
            if self.cancel.is_set():
                return
            self.device.cleanup()
            self.device.require_single_uid(self.info['package'])
            self.update(phase='preparing', message='正在准备单应用抓包连接…')
            self.directory = Path(tempfile.mkdtemp(prefix='connection-', dir=self.root))
            outdir = self.root.parent / 'captures' / ('web-physical-' + uuid.uuid4().hex)
            # History remains readable even if the child cannot start.
            IOSCaptureArchive(outdir).close()
            session = self.store.create_physical_session(serial=self.info['serial'], package=self.info['package'], outdir=str(outdir))
            self.info.update(session_id=session['id'], directory=self.directory.name)
            self.journal(self.info)
            self.update(session_id=session['id'], upstream='电脑现有代理' if upstream else '电脑直连')
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.bind((host, 0))
                port = probe.getsockname()[1]
            config = {**self.info, 'directory': str(self.directory), 'host': host, 'port': port, 'outdir': str(outdir),
                      'upstream': upstream, 'owner_pid': owner_pid, 'owner_identity': owner_identity, 'parent_pid': os.getpid()}
            config_path = self.directory / 'config.json'
            config_path.write_text(json.dumps(config))
            config_path.chmod(0o600)
            (self.directory / 'lease').touch(mode=0o600)
            with (self.directory / 'worker.log').open('wb') as log:
                self.process = subprocess.Popen([str(python), '-m', 'capture_console.android_physical_worker', str(config_path)],
                                                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            for _ in range(100):
                if self.cancel.wait(0.1):
                    return
                if self.process.poll() is not None:
                    raise ValueError('真机抓包组件启动失败，请检查运行组件后重试。')
                if (self.directory / 'tunnel.conf').exists():
                    break
            else:
                raise ValueError('真机抓包组件启动超时，请检查电脑网络后重试。')
            self.device.write('tunnel.conf', (self.directory / 'tunnel.conf').read_text())
            self.device.renew()
            self.update(phase='waiting_vpn', message='请在手机允许“抓包连接助手”创建 VPN 连接；原节点和配置不会更改。')
            self.device.launch(BRIDGE)
            activated = False
            while not self.cancel.wait(2):
                if process_identity(owner_pid) != owner_identity:
                    break
                if self.process.poll() is not None:
                    raise ValueError('真机抓包组件已停止，请先恢复网络再重试。')
                phase = self.device.state()
                if phase in {'denied', 'failed', 'stopped', 'cancelled'}:
                    raise ValueError('手机未授权或已停止临时连接，请检查手机提示。')
                (self.directory / 'lease').touch()
                self.device.renew()
                if phase == 'connected' and not activated:
                    if self.device.vpn() != BRIDGE:
                        raise ValueError('手机转发未接入连接助手，请检查 VPN 授权。')
                    activated = True
                    self.store.update_session_status(session['id'], 'running')
                    self.update(phase='capturing', message='请操作手机应用以触发接口请求。')
                    self.device.launch(self.info['package'])
                state_path = self.directory / 'state.json'
                if state_path.exists():
                    state = json.loads(state_path.read_text())
                    self.update(**{key: state[key] for key in ('flow_count', 'response_count', 'tls_failures')})
                    if state.get('limit'):
                        raise ValueError('本次记录已达到安全容量上限，请恢复网络后开始新的抓包。')
        except ValueError as exc:
            failed = str(exc)
        except (OSError, RuntimeError, KeyError, subprocess.TimeoutExpired):
            failed = '手机或电脑连接中断，请重新连接原手机并恢复网络。'
        finally:
            self.update(phase='stopping')
            self._finish_recovery()
            if failed:
                self.update(message=failed, phase='recovery_required' if self.marker.exists() else 'failed')

    def _finish_recovery(self, wait_seconds=22):
        restored = not self.marker.exists()
        try:
            if self.device and self.marker.exists():
                self.device.stop()
                deadline = time.monotonic() + wait_seconds
                while self.device.vpn() == BRIDGE and time.monotonic() < deadline:
                    time.sleep(0.5)
                restored = self.device.restore(self.info.get('original_vpn'))
                if restored:
                    self.device.cleanup()
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired):
            restored = False
        self._close_local_capture()
        if restored:
            self.marker.unlink(missing_ok=True)
            self.update(phase='stopped', message='抓包已停止，原网络连接已恢复。')
        else:
            self.update(phase='recovery_required', message='抓包已停止。请连接原手机，打开原 VPN 并恢复连接，再点击“检查网络恢复”。')

    def _close_local_capture(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()  # Only the exact Popen child owned by this service.
                self.process.wait(timeout=3)
        if self.info.get('session_id') and self.store.get_session(self.info['session_id']):
            self.store.update_session_status(self.info['session_id'], 'stopped')
        directory = self.directory or (self.root / self.info['directory'] if self.info.get('directory') else None)
        if directory and directory.parent == self.root and directory.name.startswith('connection-'):
            shutil.rmtree(directory, ignore_errors=True)

    def stop(self):
        with self.lock:
            self.cancel.set()
            if self.thread and self.thread.is_alive():
                self.update(phase='stopping', message='正在停止抓包并恢复原网络…')
            return self.status()

    def recover(self, serial=None):
        with self.lock:
            if self.terminating or self.thread and self.thread.is_alive():
                if serial:
                    raise ValueError('请先结束当前任务，再检查其他手机的网络恢复。')
                return self.status()
            if serial:
                path = self.pending.path(serial)
                if self.marker.exists() or not path.exists():
                    raise ValueError('该手机没有可检查的待恢复记录，或当前任务尚未结束。')
                if not any(item['serial'] == serial and item['status'] == 'device' for item in devices(self.adb)):
                    raise ValueError('请连接这条恢复记录对应的原手机，并允许 USB 调试；不会操作其他手机。')
                device = PhysicalDevice(self.adb, serial)
                info = json.loads(path.read_text())
                path.replace(self.marker)
                self.info, self.device = info, device
                self.process = self.directory = None
                self.last = {'phase': 'recovery_required', 'serial': serial, 'device_name': info.get('name')}
            if not self.marker.exists():
                return self.status()
            if serial is None:
                self.device = PhysicalDevice(self.adb, self.info['serial'])
            self.update(phase='stopping', message='正在检查原网络连接…')
            self.thread = threading.Thread(target=self._finish_recovery, daemon=True)
            self.thread.start()
            return self.status()

    def terminate(self):
        with self.lock:
            if self.terminating:
                return self.status()
            self.cancel.set()
            self.terminating = True
            previous = self.thread
            self.thread = threading.Thread(target=self._terminate, args=(previous,), daemon=True)
            self.thread.start()
            return self.status()

    def _terminate(self, previous):
        try:
            # Never let a late completion from the old task modify a new one.
            if previous:
                previous.join()
            self._close_local_capture()
            with self.lock:
                self.pending.defer(self.marker)
                self.info = {}
                self.device = self.process = self.directory = None
                self.last = {'phase': 'idle', 'message': '任务已终止，抓包记录已保留。请选择已连接的手机重新开始。'}
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired):
            self.update(phase='recovery_required', message='当前任务未能完全终止，已保留恢复记录，请重试终止任务。')
        finally:
            with self.lock:
                self.terminating = False

    def shutdown(self):
        self.stop()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

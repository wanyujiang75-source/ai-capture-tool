"""Authorized USB operations. Never write to the target app or the user's VPN."""

import json
import re
import shlex
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

from .device_discovery import parse_adb_devices

BRIDGE = "com.local.capture.bridge"
PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+")


def parse_vpn(text):
    # Android 16 exposes per-user blocks; never restore a work-profile VPN as user 0.
    if "Active package name:" in text:
        block = re.search(r"(?ms)^  0:.*?(?=^  \d+:|\Z)", text)
        if not block:
            raise ValueError("无法确认当前用户的 VPN 状态，请停止后重试。")
        active = re.search(r"Active package name: (\S+)", block[0])
        kind = re.search(r"Active vpn type: (-?\d+)", block[0])
        if kind and kind[1] == "-1":
            return None
        if active and kind and "Transports: VPN" in block[0] and PACKAGE.fullmatch(active[1]):
            return active[1]
    match = re.search(r"mPackage=([\w.]+)", text)
    if match and "state: CONNECTED/CONNECTED" in text:
        return match[1]
    if "state: DISCONNECTED/DISCONNECTED" in text:
        return None
    raise ValueError("无法确认原 VPN 状态，暂不切换手机网络。")


def foreground_package(text):
    match = re.search(r"(?:topResumedActivity=|mResumedActivity:).*?\bu0 ([\w.]+)/", text)
    if not match or not PACKAGE.fullmatch(match[1]):
        raise ValueError("请在手机主用户中打开需要分析的应用后重试。")
    package = match[1]
    if package in {BRIDGE, 'com.github.metacubex.clash.meta', 'com.wireguard.android'} or package.startswith(('com.android.', 'com.oplus.', 'com.google.android.')):
        raise ValueError("请先在手机中打开需要分析的应用，不要停留在桌面或设置。")
    return package


class PhysicalDevice:
    def __init__(self, adb, serial):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", serial) or serial.startswith("emulator-"):
            raise ValueError("请选择通过 USB 连接的 Android 真机。")
        self.adb, self.serial = str(adb), serial

    def call(self, *args, timeout=12, data=None):
        result = subprocess.run([self.adb, '-s', self.serial, *args], input=data,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        if result.returncode:
            raise RuntimeError("手机连接中断或未授权，请检查 USB 连接并解锁手机。")
        if len(result.stdout) > 2 * 1024 * 1024:
            raise RuntimeError("设备诊断输出过大，已停止读取。")
        return result.stdout.decode('utf-8', errors='replace')

    def shell(self, *args, timeout=12):
        return self.call('shell', shlex.join(args), timeout=timeout)

    def inspect(self):
        if self.call('get-state').strip() != 'device':
            raise ValueError("请解锁手机并允许 USB 调试。")
        if self.shell('getprop', 'ro.kernel.qemu').strip() == '1':
            raise ValueError("当前是模拟器，请使用模拟器入口。")
        if self.shell('am', 'get-current-user').strip() != '0':
            raise ValueError("暂不支持工作资料或多用户空间，请切回手机主用户。")
        for setting in ('always_on_vpn_app', 'always_on_vpn_lockdown'):
            value = self.shell('settings', '--user', '0', 'get', 'secure', setting).strip()
            if value not in {'', 'null', '0'}:
                raise ValueError("手机启用了始终开启 VPN 或阻止无 VPN 连接，工具不会自动修改此设置。")
        window = self.shell('dumpsys', 'window', 'policy')
        if re.search(r'(?:showing|mShowingLockscreen|isStatusBarKeyguard)=(?:true)', window):
            raise ValueError("请先解锁手机，再开始抓包。")
        package = foreground_package(self.shell('dumpsys', 'activity', 'activities'))
        self.require_single_uid(package)
        return {'serial': self.serial, 'name': self.shell('getprop', 'ro.product.model').strip(),
                'package': package,
                'original_vpn': self.vpn()}

    def require_single_uid(self, package):
        lines = self.shell('pm', 'list', 'packages', '-U', '--user', '0').splitlines()
        entries = [re.fullmatch(r'package:([\w.]+) uid:(\d+)', line) for line in lines]
        if not entries or not all(entries):
            raise ValueError('无法确认应用隔离范围，暂不接管手机网络。')
        packages = {entry[1]: int(entry[2]) for entry in entries}
        uid = packages.get(package, -1)
        if not 10000 <= uid < 100000 or list(packages.values()).count(uid) != 1:
            raise ValueError('该应用与其他应用共享系统身份，无法保证仅采集当前应用，暂不支持抓包。')

    def vpn(self):
        return parse_vpn(self.shell('dumpsys', 'vpn_management'))

    def installed(self):
        # Unlike `pm path`, an empty package list is a successful absence check.
        packages = self.shell('pm', 'list', 'packages', '--user', '0', BRIDGE)
        return f'package:{BRIDGE}' in packages.splitlines()

    def install(self, apk):
        if 'Success' not in self.call('install', '-r', '-t', str(apk), timeout=180):
            raise ValueError("连接助手未安装，请在手机确认安装后重试；不会替换原应用。")

    def write(self, name, value):
        if name not in {'tunnel.conf', 'lease', 'stop'}:
            raise ValueError('invalid bridge file')
        # Only our own debuggable companion is used for private USB configuration.
        script = f'umask 077; mkdir -p files; cat > files/{name}.tmp && mv files/{name}.tmp files/{name}'
        self.call('shell', f'run-as {BRIDGE} sh -c {shlex.quote(script)}', data=value.encode())

    def renew(self):
        self.write('lease', uuid.uuid4().hex)

    def state(self):
        script = 'if [ -f files/status.json ]; then cat files/status.json; else printf \'{"phase":"absent"}\'; fi'
        return json.loads(self.shell('run-as', BRIDGE, 'sh', '-c', script))['phase']

    def launch(self, package):
        if not PACKAGE.fullmatch(package):
            raise ValueError('invalid package')
        result = self.shell('cmd', 'package', 'resolve-activity', '--brief', package)
        component = next((line.strip() for line in result.splitlines() if re.fullmatch(r'[\w.]+/[\w.$]+', line.strip())), None)
        if not component:
            raise ValueError("无法打开手机应用，请在手机手动打开。")
        self.shell('am', 'start', '-W', '-n', component)

    def stop(self):
        if self.installed():
            token = uuid.uuid4().hex
            self.write('stop', token)
            # Serialize cancellation on the helper's main thread, close its own
            # consent activity, then drain any in-flight service startup by stopping
            # only our package. Old status files cannot acknowledge a new stop.
            self.shell('am', 'start', '-W', '--user', '0', '-n', BRIDGE + '/.MainActivity',
                       '-a', BRIDGE + '.STOP')
            for _ in range(12):
                try:
                    ack = self.shell('run-as', BRIDGE, 'cat', 'files/stop_ack').strip()
                except RuntimeError:
                    ack = ''
                if ack == token:
                    self.shell('am', 'force-stop', '--user', '0', BRIDGE)
                    if self.shell('sh', '-c', f'pidof {BRIDGE} || true').strip():
                        raise ValueError('临时连接仍在停止，请稍后检查网络恢复。')
                    return
                time.sleep(0.5)
            raise ValueError('请先取消手机上的 VPN 授权提示，再检查网络恢复。')

    def cleanup(self):
        if self.installed():
            self.shell('run-as', BRIDGE, 'rm', '-f', 'files/tunnel.conf', 'files/lease', 'files/stop', 'files/stop_ack')

    def restore(self, original):
        current = self.vpn()
        if current == original:
            return True
        if current not in {None, BRIDGE}:
            return False  # User selected another VPN; do not override their choice.
        if original is None or current == BRIDGE:
            return False
        self.launch(original)
        if original == 'com.github.metacubex.clash.meta':
            try:
                text = self.shell('uiautomator', 'dump', '/dev/tty', timeout=10)
                root = ET.fromstring(text[text.index('<?xml'):text.index('</hierarchy>') + 12])
                parents = {child: parent for parent in root.iter() for child in parent}
                for node in root.iter('node'):
                    if node.get('package') != original or node.get('text') not in {'已停止', 'Stopped'}:
                        continue
                    while node.get('clickable') != 'true' and node in parents:
                        node = parents[node]
                    bounds = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
                    if bounds and node.get('clickable') == 'true':
                        x1, y1, x2, y2 = map(int, bounds.groups())
                        self.shell('input', 'tap', str((x1 + x2) // 2), str((y1 + y2) // 2))
                        break
            except (ValueError, ET.ParseError, RuntimeError, subprocess.TimeoutExpired):
                pass
        for _ in range(10):
            current = self.vpn()
            if current == original:
                return True
            if current not in {None, BRIDGE}:
                break
            time.sleep(0.5)
        return False


def devices(adb):
    result = subprocess.run([str(adb), 'devices', '-l'], capture_output=True, text=True, timeout=8)
    return [item for item in parse_adb_devices(result.stdout) if item['kind'] == 'physical' and item['connection_type'] == 'usb']

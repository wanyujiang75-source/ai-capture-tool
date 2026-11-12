"""Bounded network admission without modifying phone or host proxy settings."""

import ipaddress
import os
import re
import secrets
import socket
import subprocess
import threading
import time


class NetworkIssue(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class PreparationCancelled(Exception):
    pass


def check_https(upstream):
    host, port = upstream
    if not re.fullmatch(r'[A-Za-z0-9.:-]+', host) or not 0 < int(port) < 65536:
        raise NetworkIssue('upstream_unreachable', '电脑代理参数无效，请检查已有代理后重试。')
    authority = f'[{host}]' if ':' in host else host
    try:
        result = subprocess.run([
            '/usr/bin/curl', '-q', '--silent', '--head', '--output', '/dev/null',
            '--proxy', f'http://{authority}:{port}', '--noproxy', '',
            '--connect-timeout', '3', '--max-time', '4', '--write-out', '%{http_connect} %{http_code}',
            'https://www.google.com/generate_204',
        ], capture_output=True, text=True, timeout=5,
            env={key: value for key, value in os.environ.items() if not key.lower().endswith('_proxy')})
        if result.returncode == 0 and result.stdout.strip() == '200 204':
            return
    except (OSError, subprocess.TimeoutExpired):
        pass
    raise NetworkIssue('upstream_unreachable', '电脑代理无法完成 Google HTTPS 连接检查。请确认电脑代理可访问外网后重试；工具不会切换为直连。')


def check_phone(device, host, cancelled=lambda: False):
    host = str(ipaddress.IPv4Address(host))
    try:
        wifi = device.shell('cmd', 'wifi', 'status', timeout=3)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        raise NetworkIssue('phone_wifi_unavailable', '无法确认手机 Wi-Fi，请检查 USB 授权并将手机与 Mac 连接同一 Wi-Fi。') from exc
    if 'Wifi is enabled' not in wifi or 'Wifi is connected' not in wifi:
        raise NetworkIssue('phone_wifi_unavailable', '手机尚未连接 Wi-Fi。请将手机与 Mac 连接同一 Wi-Fi 后重试，USB 仅用于控制连接。')
    nonce = secrets.token_hex(16)
    matched = threading.Event()
    done = threading.Event()
    peers = []
    peer_lock = threading.Lock()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind((host, 0))
            listener.listen(1)
            listener.settimeout(.2)
            port = listener.getsockname()[1]
            deadline = time.monotonic() + 4

            def echo():
                while not done.is_set() and not cancelled() and time.monotonic() < deadline:
                    try:
                        peer, _ = listener.accept()
                        with peer_lock:
                            peers.append(peer)
                        with peer:
                            data = b''
                            while len(data) < 128 and not data.endswith(b'\n') and not done.is_set() and not cancelled():
                                remaining = deadline - time.monotonic()
                                if remaining <= 0:
                                    break
                                peer.settimeout(min(.2, remaining))
                                chunk = peer.recv(128 - len(data))
                                if not chunk:
                                    break
                                data += chunk
                            if data == (nonce + '\n').encode():
                                peer.sendall(data)
                                matched.set()
                                return
                    except socket.timeout:
                        continue
                    except OSError:
                        return

            thread = threading.Thread(target=echo, daemon=True)
            thread.start()
            try:
                output = device.shell('sh', '-c', f"printf '%s\\n' {nonce} | toybox nc -w 3 {host} {port}", timeout=5)
                if output.strip() != nonce or not matched.wait(.1):
                    raise OSError('roundtrip failed')
            finally:
                done.set()
                with peer_lock:
                    for peer in peers:
                        peer.close()
                thread.join(timeout=.5)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        raise NetworkIssue('phone_lan_unreachable', '手机无法连接此 Mac。请确认两者连接同一 Wi-Fi，且网络允许设备间通信；不需要修改 VPN 节点。') from exc


class NetworkReadiness:
    def __init__(self, device, host, upstream, read_upstream):
        if not upstream:
            raise NetworkIssue('upstream_required', '未检测到电脑 HTTP 代理。请先开启电脑已有代理的系统代理功能，再开始真机抓包；工具不会修改原节点或配置。')
        self.device, self.host, self.upstream, self.read_upstream = device, host, list(upstream), read_upstream
        self.phone = self.external = 'checking'

    def check(self, heartbeat=lambda: None, cancelled=lambda: False):
        previously_connected = self.phone == 'ready'
        self.phone = self.external = 'checking'
        heartbeat()
        try:
            current = self.read_upstream()
            if current != self.upstream:
                raise NetworkIssue('upstream_changed', '电脑代理已关闭或连接地址已变化。请确认已有代理可用后重新开始抓包，工具不会自动切换出口。')
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            self.external = 'failed'
            if isinstance(exc, NetworkIssue):
                raise
            raise NetworkIssue('upstream_unreachable', '无法读取电脑代理，请检查已有代理后重新开始抓包。') from exc
        try:
            heartbeat()
            try:
                check_phone(self.device, self.host, cancelled)
            except NetworkIssue as exc:
                if not previously_connected or exc.code != 'phone_lan_unreachable' or cancelled():
                    raise
                # One fresh, bounded roundtrip tolerates transient scheduler/Wi-Fi delay.
                # Never ignore a second failure or replace it with a cached success.
                heartbeat()
                check_phone(self.device, self.host, cancelled)
            self.phone = 'ready'
        except NetworkIssue:
            self.phone = 'failed'
            if cancelled():
                raise PreparationCancelled() from None
            raise
        try:
            heartbeat()
            check_https(self.upstream)
            self.external = 'ready'
            heartbeat()
        except NetworkIssue:
            self.external = 'failed'
            if cancelled():
                raise PreparationCancelled() from None
            raise

    def summary(self):
        return {'phone_network': self.phone, 'upstream_network': self.external}


class TunnelReadiness:
    def __init__(self):
        self.started = self.sampled = self.sequence = None

    def observe(self, snapshot, now):
        phase = snapshot.get('phase')
        if phase not in {'connecting', 'connected', 'disconnected'}:
            return False
        if self.started is None:
            self.started = self.sampled = now
        sequence = snapshot.get('sequence')
        if isinstance(sequence, int) and sequence > 0 and (self.sequence is None or sequence > self.sequence):
            self.sequence, self.sampled = sequence, now
        if phase == 'disconnected' or now - self.sampled > 12:
            raise NetworkIssue('tunnel_lost', '手机转发连接已中断，已停止抓包并保留结果。请检查手机 Wi-Fi 和 USB 连接后重试。')
        if phase == 'connected' and self.sequence is not None:
            return True
        if now - self.started >= 30:
            raise NetworkIssue('tunnel_timeout', '手机与 Mac 未能建立抓包连接。请确认 Wi-Fi 允许设备间通信和 UDP 连接，再重新开始。')
        return False

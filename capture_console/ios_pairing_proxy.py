"""Dedicated authenticated proxy worker for the iPhone setup assistant."""

import asyncio
from contextlib import suppress
import ipaddress
import json
import os
import re
import signal
import shutil
import ssl
import subprocess
import sys
import time
from pathlib import Path

from mitmproxy import certs, http, options
from mitmproxy.tools.dump import DumpMaster

from .ios_setup import make_profile, process_identity
from .ios_recording import IOSRecording


class PairingMonitor:
    def __init__(self, config):
        self.config = config
        self.state = {"phase": "waiting_phone", "connection_state": "waiting_phone", "flow_count": 0, "flows": [],
                      "profile_path": config["profile_path"], "ssid": config["ssid"],
                      "check_url": "https://capture-check.invalid/" + config["check_token"],
                      "identity_reused": config.get('identity_reused', False),
                      "route_changed": config.get('route_changed', False),
                      "certificate_expires_at": config.get('expires_at'),
                      "certificate_name": "Capture iPhone Test " + config["check_token"][:6]}
        self.dirty = True
        self.recording = IOSRecording(config, self.state)

    def authenticated(self, flow):
        return flow.metadata.get("proxyauth") == (self.config["username"], self.config["password"])

    def eligible_phone(self, flow):
        peer = flow.client_conn.peername
        if not peer or not self.authenticated(flow):
            return False
        ip = ipaddress.ip_address(peer[0])
        return ip.is_private and not ip.is_loopback and peer[0] != self.config["host"]

    def phone(self, flow):
        if not self.eligible_phone(flow):
            return False
        peer = flow.client_conn.peername[0]
        if peer != self.state.get("client_ip", peer):
            self.recording.invalidate_phone()
            self.dirty = True
            return False
        return True

    def http_connect(self, flow):
        if self.phone(flow) and self.state["phase"] == "waiting_phone":
            self.state["phase"] = "waiting_trust"
            self.state["connection_state"] = "waiting_trust"
            self.dirty = True

    def requestheaders(self, flow):
        if self.phone(flow):
            self.recording.requestheaders(flow)
            self.dirty = True

    def request(self, flow):
        self.recording.request(flow)
        if flow.request.host != "capture-check.invalid" or not self.authenticated(flow):
            return
        valid = flow.client_conn.tls and flow.request.path == "/" + self.config["check_token"]
        flow.response = http.Response.make(
            200 if valid else 404,
            "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            "<h1>连接检查完成</h1><p>HTTPS 已通过。请返回桌面端选择项目并点击开始抓包，再操作手机应用。</p>"
            if valid else "Not found", {"content-type": "text/html; charset=utf-8", "cache-control": "no-store"},
        )

    def responseheaders(self, flow):
        self.recording.responseheaders(flow)

    def error(self, flow):
        self.recording.finish(flow)
        self.dirty = True

    def response(self, flow):
        self.recording.finish(flow)
        self.dirty = True
        if not self.eligible_phone(flow) or not flow.client_conn.tls or not flow.response:
            return
        probe = (flow.request.host == "capture-check.invalid"
                 and flow.request.path == "/" + self.config["check_token"] and flow.response.status_code == 200)
        if not probe:
            return
        self.state["client_ip"] = flow.client_conn.peername[0]
        self.state["connection_state"] = "ready"
        self.state.pop("message", None)
        if self.state["phase"] != "capturing":
            self.state["phase"] = "ready"
        self.dirty = True

    def tcp_message(self, flow):
        # WebSocket upgrades use raw TCP passthrough; never retain their message history.
        flow.messages.clear()

    def flush(self):
        if self.dirty:
            path = Path(self.config["state_path"])
            temporary = path.with_suffix(".tmp")
            data = json.dumps(self.state, ensure_ascii=False).encode()
            while len(data) >= 1_500_000 and self.state["flows"]:
                self.state["flows"].pop(0)
                data = json.dumps(self.state, ensure_ascii=False).encode()
            temporary.write_bytes(data)
            temporary.chmod(0o600)
            temporary.replace(path)
            self.dirty = False


def owner_is_alive(config):
    try:
        return process_identity(config["owner_pid"]) == config["owner_identity"]
    except (OSError, subprocess.TimeoutExpired):
        return False


async def run(config):
    os.umask(0o077)
    confdir = Path(config["confdir"])
    confdir.mkdir(mode=0o700, exist_ok=True)
    if config.get('persistent_identity'):
        if not (confdir / 'mitmproxy-ca.pem').is_file():
            raise ValueError('Saved iPhone identity missing; refusing certificate rotation')
    else:
        certs.CertStore.create_store(confdir, "mitmproxy", 2048, organization="Capture Tool",
                                    cn="Capture iPhone Test " + config["check_token"][:6])
    ca = certs.CertStore.from_store(confdir, "mitmproxy", 2048)
    public_der = ssl.PEM_cert_to_DER_cert(ca.default_ca.to_pem().decode("ascii"))
    Path(config["profile_path"]).write_bytes(make_profile(config, public_der))
    opts = options.Options(listen_host=config["host"], listen_port=config["port"], confdir=str(confdir))
    master = DumpMaster(opts, with_termlog=False, with_dumper=False)
    opts.update(proxyauth=config["username"] + ":" + config["password"], block_global=True,
                connection_strategy="lazy", upstream_cert=False, ssl_insecure=False, stream_large_bodies="256k",
                websocket=False, rawtcp=True,
                allow_hosts=[r"^capture-check\.invalid(:443)?$"])
    monitor = PairingMonitor(config)
    master.addons.add(monitor)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, master.shutdown)

    def switch(domains):
        hosts = [r"capture-check\.invalid"]
        hosts.extend((r"[^.:]+(?:\.[^.:]+)*\." + re.escape(h[2:])) if h.startswith("*.") else re.escape(h)
                     for h in domains)
        opts.update(allow_hosts=["^(" + "|".join(hosts) + r")(:\d+)?$"])
        # This master owns only this iPhone proxy, never an Android or foreign listener.
        proxy = master.addons.get("proxyserver")
        for handler in list(proxy.connections.values()):
            for transport in list(handler.transports.values()):
                if transport.handler:
                    transport.handler.cancel("iPhone recording mode changed")
                if transport.writer:
                    transport.writer.close()

    async def maintain():
        try:
            await asyncio.sleep(0.5)
            while True:
                if (os.getppid() != config["parent_pid"] or not owner_is_alive(config)
                        or time.time() >= config.get("expires_at", float("inf"))):
                    master.shutdown()
                    return
                control = Path(config.get("control_path", Path(config["state_path"]).with_name("control.json")))
                if control.exists():
                    if control.stat().st_size > 65536:
                        raise ValueError("oversized recording command")
                    monitor.recording.apply(json.loads(control.read_text()), switch)
                monitor.recording.check_limit(switch)
                monitor.dirty = True
                monitor.flush()
                await asyncio.sleep(0.2)
        except Exception:
            # Losing status persistence or lifecycle monitoring must stop interception.
            master.shutdown()

    task = asyncio.create_task(maintain())
    try:
        await master.run()
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        monitor.state = {"phase": "failed", "flow_count": 0, "flows": []}
        monitor.dirty = True
        try:
            with suppress(OSError):
                monitor.flush()
        finally:
            try:
                Path(config["profile_path"]).unlink(missing_ok=True)
            finally:
                try:
                    Path(config["state_path"]).with_name("config.json").unlink(missing_ok=True)
                finally:
                    shutil.rmtree(confdir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(run(json.loads(Path(sys.argv[1]).read_text())))

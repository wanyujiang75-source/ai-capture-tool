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
import zlib
from pathlib import Path

from mitmproxy import certs, http, options
from mitmproxy.tools.dump import DumpMaster

from .ios_setup import make_profile, process_identity


class PairingMonitor:
    def __init__(self, config):
        self.config = config
        self.state = {"phase": "waiting_phone", "flow_count": 0, "flows": [],
                      "profile_path": config["profile_path"], "ssid": config["ssid"],
                      "check_url": "https://capture-check.invalid/" + config["check_token"],
                      "certificate_name": "Capture iPhone Test " + config["check_token"][:6]}
        self.dirty = True

    def authenticated(self, flow):
        return flow.metadata.get("proxyauth") == (self.config["username"], self.config["password"])

    def phone(self, flow):
        peer = flow.client_conn.peername
        if not peer or not self.authenticated(flow):
            return False
        ip = ipaddress.ip_address(peer[0])
        return ip.is_private and not ip.is_loopback and peer[0] != self.config["host"]

    def http_connect(self, flow):
        if self.phone(flow) and self.state["phase"] == "waiting_phone":
            self.state["phase"] = "waiting_trust"
            self.dirty = True

    def request(self, flow):
        if flow.request.host != "capture-check.invalid" or not self.authenticated(flow):
            return
        valid = flow.client_conn.tls and flow.request.path == "/" + self.config["check_token"]
        flow.response = http.Response.make(
            200 if valid else 404,
            "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            "<h1>连接检查完成</h1><p>HTTPS 已通过。请返回 PokeHub 操作业务页面，桌面端会自动显示收到的接口。</p>"
            if valid else "Not found", {"content-type": "text/html; charset=utf-8", "cache-control": "no-store"},
        )

    def response(self, flow):
        if not self.phone(flow) or not flow.client_conn.tls or not flow.response:
            return
        probe = (flow.request.host == "capture-check.invalid"
                 and flow.request.path == "/" + self.config["check_token"] and flow.response.status_code == 200)
        target = flow.request.host in self.config["hosts"]
        if not probe and not target:
            return
        self.state["client_ip"] = flow.client_conn.peername[0]
        if self.state["phase"] != "capturing":
            self.state["phase"] = "ready"
        if target:
            request, request_truncated = body_preview(flow.request)
            response, response_truncated = body_preview(flow.response)
            self.state["phase"] = "capturing"
            self.state["flow_count"] += 1
            self.state["flows"].append({
                "id": flow.id, "method": flow.request.method[:32],
                "url": f"https://{flow.request.host}{flow.request.path.split('?')[0]}".encode()[:2048].decode("utf-8", "ignore"),
                "status": flow.response.status_code,
                "request_body": request,
                "response_body": response,
                "truncated": request_truncated or response_truncated,
            })
            self.state["flows"] = self.state["flows"][-20:]
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


def body_preview(message):
    value = message.raw_content
    if value is None:
        return "", True
    encoding = message.headers.get("content-encoding", "identity").lower()
    if encoding in {"gzip", "deflate"}:
        try:
            inflater = zlib.decompressobj(31 if encoding == "gzip" else 15)
            value = inflater.decompress(value, 16385)
        except zlib.error:
            return "压缩正文无法预览。", True
    elif encoding not in {"identity", ""}:
        return "此压缩格式暂不提供正文预览。", True
    # Replacement characters can expand invalid UTF-8 threefold; bound the displayed bytes too.
    text = (value or b"")[:16384].decode("utf-8", "replace")
    encoded = text.encode("utf-8")
    return encoded[:16384].decode("utf-8", "ignore"), len(value) > 16384 or len(encoded) > 16384


async def run(config):
    os.umask(0o077)
    confdir = Path(config["confdir"])
    confdir.mkdir(mode=0o700)
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
                allow_hosts=["^(" + "|".join(re.escape(h) for h in ["capture-check.invalid", *config["hosts"]]) + ")(:443)?$"])
    monitor = PairingMonitor(config)
    master.addons.add(monitor)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, master.shutdown)

    async def maintain():
        try:
            await asyncio.sleep(0.5)
            while True:
                if os.getppid() != config["parent_pid"] or not owner_is_alive(config):
                    master.shutdown()
                    return
                monitor.flush()
                await asyncio.sleep(1)
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

"""Isolated experimental WireGuard worker; existing proxy runtimes are untouched."""

import asyncio
import json
import os
from pathlib import Path
import re
import signal
import sys
import time

from mitmproxy import options
from mitmproxy.tools.dump import DumpMaster
from .ios_recording import IOSRecording
from .ios_setup import process_identity
from .android_physical_evidence import ApplicationNetworkEvidence
from .android_physical_routing import ConnectionRouting, OwnerClient


def single_app_config(config, package, login_forwarding=False):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+', package):
        raise ValueError('invalid target package')
    config = re.sub(r'(?m)^PersistentKeepalive\s*=.*\n?', '', config)
    if login_forwarding:
        package += ', com.google.android.gms'
    return config.replace('[Peer]\n', '[Peer]\nPersistentKeepalive = 5\n', 1).replace(
        '[Interface]\n', '[Interface]\nIncludedApplications = ' + package + '\n', 1).replace(
        'AllowedIPs = 0.0.0.0/0', 'AllowedIPs = 0.0.0.0/0, ::/0')


class PhysicalRecorder:
    def __init__(self, config):
        self.config = config
        self.application_network = ApplicationNetworkEvidence()
        self.state = {'phase': 'preparing', 'flow_count': 0, 'response_count': 0, 'tls_failures': 0,
                      'connection_state': 'ready'}
        self.recording = IOSRecording({'capture_root': str(Path(config['outdir']).parent),
                                       'state_path': str(Path(config['outdir']) / 'state.json')}, self.state)
        self.recording.apply({'revision': 1, 'action': 'start', 'capture_scope': 'device',
                              'outdir': config['outdir'], 'session_id': config['session_id'],
                              'project': {'name': 'Android physical'}}, lambda hosts: None)

    def requestheaders(self, flow):
        sni = (flow.client_conn.sni or '').lower().rstrip('.')
        authority = flow.request.headers.get('host', flow.request.authority or flow.request.host).lower()
        host = sni if flow.request.scheme == 'https' else flow.request.host.lower().rstrip('.')
        allowed_authorities = {f'{host}:{flow.request.port}'}
        if flow.request.port == 443:
            allowed_authorities.add(host)
        if flow.request.scheme == 'https' and (not sni or authority not in allowed_authorities):
            flow.kill()
            return
        # VPN fake-IP destinations may be stale. Route by authenticated TLS SNI,
        # without changing HTTP authority, headers, URL or body bytes.
        flow.request.data.host = host
        flow.server_conn.address = (host, flow.request.port)
        flow.server_conn.sni = sni or None
        if self.config['upstream']:
            flow.server_conn.via = ('http', tuple(self.config['upstream']))
        self.recording.requestheaders(flow)

    def request(self, flow):
        self.recording.request(flow)

    def responseheaders(self, flow):
        self.recording.responseheaders(flow)

    def response(self, flow):
        self.recording.finish(flow)
        self.state['response_count'] += 1
        # A proxy-generated/replayed response is not evidence of phone-to-server HTTPS.
        if (flow.request.scheme == 'https' and not flow.is_replay and not flow.error
                and flow.server_conn.timestamp_tcp_setup is not None):
            self.application_network.response(flow.response.status_code)

    def error(self, flow):
        self.recording.finish(flow)
        self.application_network.failure()

    def tls_failed_client(self, data):
        self.state['tls_failures'] += 1
        self.application_network.failure()

    def tcp_message(self, flow):
        flow.messages.clear()


def duration_expired(started, now):
    return now - started >= 1800


async def run(config):
    os.umask(0o077)
    root = Path(config['directory'])
    opts = options.Options(listen_host=config['host'], listen_port=config['port'],
                           confdir=str(root / 'ca'), mode=['wireguard:' + str(root / 'wireguard.json')])
    master = DumpMaster(opts, with_termlog=False, with_dumper=False)
    opts.update(emudhra=True, connection_strategy='lazy', upstream_cert=False, ssl_insecure=False,
                stream_large_bodies='256k', websocket=False, rawtcp=True)
    recorder = PhysicalRecorder(config)
    master.addons.add(recorder)
    routing = None
    if config.get('owner_port'):
        routing = ConnectionRouting(OwnerClient(config['owner_port'], config['owner_token']),
                                    config['upstream'], package=config['package'],
                                    ad_compatibility_probe=config.get('ad_compatibility_probe') is True)
        master.addons.add(routing)
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, master.shutdown)

    async def maintain():
        started = time.monotonic()
        exported = False
        try:
            while True:
                if (os.getppid() != config['parent_pid'] or duration_expired(started, time.monotonic())
                        or time.time() - (root / 'lease').stat().st_mtime > 20
                        or await asyncio.to_thread(process_identity, config['owner_pid']) != config['owner_identity']):
                    break
                if not exported:
                    for server in master.addons.get('proxyserver').servers:
                        if hasattr(server, 'client_conf') and server.listen_addrs:
                            (root / 'tunnel.conf').write_text(single_app_config(server.client_conf(), config['package'], bool(config.get('owner_port'))))
                            exported = True
                recorder.recording.check_limit(lambda hosts: None)
                state = {key: recorder.state[key] for key in ('flow_count', 'response_count', 'tls_failures')}
                state['application_network'] = recorder.application_network.summary()
                if routing:
                    state['routing_diagnostics'] = routing.diagnostics.summary()
                state['ready'] = exported
                state['limit'] = recorder.recording.archive.limit_reason
                temporary = root / 'state.tmp'
                temporary.write_text(json.dumps(state))
                temporary.replace(root / 'state.json')
                if state['limit']:
                    break
                await asyncio.sleep(1)
        finally:
            recorder.recording.archive.close()
            master.shutdown()

    task = asyncio.create_task(maintain())
    try:
        await master.run()
    finally:
        task.cancel()
        recorder.recording.archive.close()


if __name__ == '__main__':
    asyncio.run(run(json.loads(Path(sys.argv[1]).read_text())))

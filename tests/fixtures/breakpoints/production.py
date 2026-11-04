"""Disposable loopback process using product hooks, worker IPC and archive."""

import asyncio
import json
import logging
import os
from pathlib import Path
import resource
import sys

from mitmproxy import options
from mitmproxy.tools.dump import DumpMaster

from capture_console.breakpoints.runtime import RecordingRuntime
from capture_console.breakpoints.android import AndroidBreakpoints
from capture_console.ios_setup import process_identity
from capture_console.ios_pairing_proxy import PairingBreakpointMonitor
from tests.fixtures.breakpoints.probe import ErrorEvidence, emit


class Fixture:
    def __init__(self, master, root, mode):
        self.master, self.root, self.mode = master, root, mode
        self.runtime = None
        self.monitor = None
        self.android = None

    async def running(self):
        if self.mode == 'ios':
            config = dict(state_path=str(self.root / 'state.json'), capture_root=str(self.root),
                          profile_path=str(self.root/'unused'), ssid='isolated', check_token='test',
                          username='fixture', password='fixture', host='127.0.0.1')
            self.monitor = PairingBreakpointMonitor(config, self.master)
            # A real iPhone is intentionally not involved. Only this test subclass
            # admits an authenticated loopback client as the bound phone.
            self.monitor.eligible_phone = lambda flow: self.monitor.authenticated(flow)
            self.monitor.state.update(connection_state='ready', client_ip='127.0.0.1')
            await self.monitor.recording.apply(dict(action='start', revision=1, session_id=1,
                outdir=str(self.root/'archive'), project={'name': 'test'}, capture_scope='device'), lambda _: None)
            self.runtime = self.monitor.recording.runtime
        else:
            self.android = AndroidBreakpoints(dict(outdir=str(self.root/'archive'), capture_id='1',
                device_id='device-1', owner_pid=os.getppid(), owner_identity=process_identity(os.getppid())))
            await self.android.running()
            self.runtime = self.android.runtime
        emit('ready', port=self.master.addons.get('proxyserver').listen_addrs()[0][1])

    def next_layer(self, layer):
        self.runtime.addon.next_layer(layer)

    def requestheaders(self, flow):
        (self.monitor or self.runtime).requestheaders(flow)

    async def request(self, flow):
        await (self.monitor or self.runtime).request(flow)

    def responseheaders(self, flow):
        (self.monitor or self.runtime).responseheaders(flow)

    async def response(self, flow):
        await (self.monitor or self.runtime).response(flow)

    def error(self, flow):
        (self.monitor or self.runtime).error(flow)

    def client_disconnected(self, client):
        if self.runtime:
            self.runtime.addon.client_disconnected(client)

    async def controls(self):
        reader = asyncio.StreamReader()
        await asyncio.get_running_loop().connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
        while line := await reader.readline():
            command = json.loads(line)['action']
            if command == 'stats':
                rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                emit('stats', maxrss_bytes=rss if sys.platform == 'darwin' else rss*1024,
                     **self.runtime.addon.engine.status())
            elif command == 'stop':
                if self.monitor:
                    await self.monitor.recording.apply(dict(action='stop', revision=2), lambda _: None)
                else:
                    await self.runtime.close()
                emit('stopped')
            elif command == 'shutdown':
                break
        if self.runtime:
            await self.runtime.close()
        self.master.shutdown()


async def run(root, mode):
    opts = options.Options(listen_host='127.0.0.1', listen_port=0, confdir=str(root/'ca'),
                           mode=['socks5' if mode == 'socks' else 'regular'])
    master = DumpMaster(opts, with_termlog=False, with_dumper=False)
    opts.update(connection_strategy='lazy', stream_large_bodies='256k',
                ssl_verify_upstream_trusted_ca=str(root/'origin.pem'))
    if mode == 'ios':
        opts.update(proxyauth='fixture:fixture')
    fixture = Fixture(master, root, mode)
    master.addons.add(fixture)
    errors = ErrorEvidence(level=logging.ERROR)
    logging.getLogger().addHandler(errors)
    task = asyncio.create_task(fixture.controls())
    try:
        await master.run()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        if fixture.runtime:
            await fixture.runtime.close()
        if fixture.android:
            await fixture.android.done()
        logging.getLogger().removeHandler(errors)


if __name__ == '__main__':
    asyncio.run(run(Path(sys.argv[1]), sys.argv[2]))

"""Disposable transport experiment, NOT a production breakpoint addon.

Controls use inherited pipes only. All forwarding is restricted to loopback.
Unsafe candidates are measured explicitly, never enabled in the desktop app.
"""

import asyncio
import base64
import json
import logging
import resource
import sys
import weakref
from pathlib import Path

from mitmproxy import http, options
from mitmproxy.net.http.http1 import expected_http_body_size
from mitmproxy.tools.dump import DumpMaster
from tests.fixtures.breakpoints.decoding import editable


def emit(kind, **fields):
    print(json.dumps({'kind': kind, **fields}), flush=True)


class ErrorEvidence(logging.Handler):
    def emit(self, record):
        emit('addon_error', message=logging.Formatter().format(record)[-4096:])


class Probe:
    def __init__(self, master, origin):
        self.master, self.origin = master, origin
        self.config = {'stage': 'both', 'mode': 'body', 'enabled': True, 'limit': 20}
        self.active = {}
        self.pending = {}
        self.timers = {}
        self.peak_active = 0
        self.guards = weakref.WeakSet()

    def running(self):
        ports = self.master.addons.get('proxyserver').listen_addrs()
        emit('ready', port=ports[0][1])

    def next_layer(self, nextlayer):
        if self.config.get('guard'):
            from tests.fixtures.breakpoints.guard import install
            install(nextlayer, self, emit)
            from tests.fixtures.breakpoints.guard import GuardLayer
            if isinstance(nextlayer.layer, GuardLayer):
                self.guards.add(nextlayer.layer)

    def matched(self, flow):
        return (self.config['enabled'] and flow.request.scheme == self.config.get('scheme', 'https')
                and flow.request.host == '127.0.0.1'
                and flow.request.port == self.config.get('port', self.origin)
                and flow.request.path.startswith('/hit'))

    def http_connect(self, flow):
        if flow.request.host != '127.0.0.1':
            flow.response = http.Response.make(403, b'BP0 loopback only')

    async def requestheaders(self, flow):
        if flow.request.host != '127.0.0.1':
            flow.response = http.Response.make(403, b'BP0 loopback only')
            return
        if not self.matched(flow):
            return
        if len(self.active) >= self.config['limit']:
            flow.request.stream = True
            emit('bypass', reason='capacity', id=flow.id)
            return
        self.active[flow.id] = dict(self.config)
        self.peak_active = max(self.peak_active, len(self.active))
        emit('collecting', id=flow.id, stage='request', path=flow.request.path)
        if self.config.get('collect_timeout') and not self.config.get('guard'):
            self.timers[flow.id] = asyncio.create_task(self.expire(flow))
        if self.config['mode'] == 'headers' and self.config['stage'] in {'request', 'both'}:
            if not self.header_bypass(flow, 'request'):
                await self.pause(flow, 'request')

    def header_bypass(self, flow, stage):
        if not self.active[flow.id].get('guard'):
            return False
        message = getattr(flow, stage)
        size = expected_http_body_size(flow.request, flow.response if stage == 'response' else None)
        if message.is_http2 and 'content-length' not in message.headers:
            size = 0 if flow.metadata.get(f'bp0_end_{stage}') else None
        if size is None or size < 0 or size >= 128 * 1024:
            message.stream = True
            emit('header_bypass', id=flow.id, stage=stage, reason='large_or_unknown_body')
            return True
        return False

    async def expire(self, flow):
        await asyncio.sleep(self.active[flow.id]['collect_timeout'])
        flow.kill()
        emit('kill_called', id=flow.id)

    def cancel_timer(self, flow):
        timer = self.timers.pop(flow.id, None)
        if timer:
            timer.cancel()

    async def pause(self, flow, stage):
        flow.intercept()
        self.pending[flow.id] = flow
        message = getattr(flow, stage)
        emit('paused', id=flow.id, stage=stage, raw_size=len(message.raw_content or b''),
             protocol=message.http_version)
        try:
            await asyncio.wait_for(flow.wait_for_resume(), self.active[flow.id].get('pause_timeout', 15))
        except TimeoutError:
            flow.resume()
            emit('timeout', id=flow.id)
        finally:
            self.pending.pop(flow.id, None)

    async def request(self, flow):
        self.cancel_timer(flow)
        config = self.active.get(flow.id)
        if config and config['mode'] == 'body' and config['stage'] in {'request', 'both'}:
            if flow.request.stream:
                emit('bypass', id=flow.id, reason='streamed_request')
            elif not editable(flow.request):
                emit('bypass', id=flow.id, stage='request', reason='body_not_editable')
            else:
                await self.pause(flow, 'request')

    async def responseheaders(self, flow):
        config = self.active.get(flow.id)
        if config and config['mode'] == 'headers' and config['stage'] in {'response', 'both'}:
            if not self.header_bypass(flow, 'response'):
                await self.pause(flow, 'response')
        elif config and config.get('collect_timeout') and not config.get('guard'):
            self.timers[flow.id] = asyncio.create_task(self.expire(flow))

    async def response(self, flow):
        self.cancel_timer(flow)
        config = self.active.get(flow.id)
        if config and config['mode'] == 'body' and config['stage'] in {'response', 'both'}:
            if flow.response.stream:
                emit('bypass', id=flow.id, reason='streamed_response')
            elif not editable(flow.response):
                emit('bypass', id=flow.id, stage='response', reason='body_not_editable')
            else:
                await self.pause(flow, 'response')
        self.active.pop(flow.id, None)
        emit('finished', id=flow.id)

    def error(self, flow):
        self.cancel_timer(flow)
        self.active.pop(flow.id, None)
        emit('flow_error', id=flow.id)

    async def control(self):
        reader = asyncio.StreamReader(limit=1048576)
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_running_loop().connect_read_pipe(lambda: protocol, sys.stdin)
        while line := await reader.readline():
            data = json.loads(line)
            action = data['action']
            if action == 'config':
                if data['values'].get('guard'):
                    from tests.fixtures.breakpoints.guard import check_version
                    check_version()
                self.config.update(data['values'])
                emit('configured')
            elif action == 'stats':
                rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                emit('stats', maxrss_bytes=rss if sys.platform == 'darwin' else rss * 1024,
                     active=len(self.active), pending=len(self.pending), peak_active=self.peak_active,
                     connections=len(self.master.addons.get('proxyserver').connections),
                     queued_events=sum(len(stream._paused_event_queue) for guard in self.guards
                                       for stream in guard.streams.values()) +
                                   sum(len(queue) for guard in self.guards for conn in guard.h2_layers
                                       for queue in getattr(conn, 'stream_queue', {}).values()))
            elif action == 'resolve':
                flow = self.pending[data['id']]
                message = getattr(flow, data['stage'])
                if 'body' in data:
                    message.content = base64.b64decode(data['body'])
                if 'path' in data:
                    flow.request.path = data['path']
                if 'status' in data:
                    flow.response.status_code = data['status']
                for key, value in data.get('headers', []):
                    message.headers.add(key, value)
                flow.resume()
                if data.get('abort'):
                    flow.kill()
                emit('resolved', id=flow.id)
            elif action == 'release':
                self.config['enabled'] = False
                for flow in list(self.pending.values()):
                    flow.resume()
                emit('released')
            elif action == 'shutdown':
                for flow in list(self.pending.values()):
                    flow.resume()
                self.master.shutdown()
                return
        self.master.shutdown()


async def run(root, origin):
    opts = options.Options(listen_host='127.0.0.1', listen_port=0, confdir=str(root / 'ca'))
    master = DumpMaster(opts, with_termlog=False, with_dumper=False)
    opts.update(connection_strategy='lazy', stream_large_bodies='256k',
                ssl_verify_upstream_trusted_ca=str(root / 'origin.pem'))
    probe = Probe(master, origin)
    master.addons.add(probe)
    errors = ErrorEvidence(level=logging.ERROR)
    logging.getLogger().addHandler(errors)
    task = asyncio.create_task(probe.control())
    try:
        await master.run()
    finally:
        task.cancel()
        for timer in probe.timers.values():
            timer.cancel()
        await asyncio.gather(task, *probe.timers.values(), return_exceptions=True)
        logging.getLogger().removeHandler(errors)


if __name__ == '__main__':
    asyncio.run(run(Path(sys.argv[1]), int(sys.argv[2])))

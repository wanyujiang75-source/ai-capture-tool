"""Isolated native UI acceptance: real product proxy/UDS, synthetic loopback app.

No phone, VPN, ADB or production runtime. All HTTP services bind 127.0.0.1.
"""

import argparse
import asyncio
import json
import secrets
import socket
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse
import uvicorn

from capture_console.breakpoints.api import create_control_app
from capture_console.breakpoints.runtime import private_json
from tests.test_breakpoint_integration import ProductionTests


async def run(args):
    runtime = Path(args.runtime_dir)
    runtime.mkdir(mode=0o700, parents=True, exist_ok=False)
    fixture = ProductionTests()
    await fixture.asyncSetUp()
    fixture.origin.responses['/hit'] = {'body': b'{"reply":1}'}
    token = secrets.token_urlsafe(32)
    private_json(runtime / 'breakpoint-desktop.json', {'token': token})
    app = create_control_app({'1': fixture.control}, token)
    mode = 'normal'
    results = []
    tasks = set()

    @app.middleware('http')
    async def control_scenario(request, call_next):
        if '/breakpoints' in request.url.path:
            if mode == 'failed-control':
                return JSONResponse({'detail': 'PRIVATE SYNTHETIC FAILURE'}, status_code=503)
            if mode == 'loading' and '/pending/' in request.url.path:
                await asyncio.sleep(2)
        return await call_next(request)

    async def trigger():
        try:
            exchange = await fixture.begin()
            outcome = await asyncio.wait_for(exchange.task, 150)
            results.append(dict(outcome=outcome, response=bytes(exchange.preview).decode(), headers=exchange.headers,
                                origin=[bytes(v['preview']).decode() for v in fixture.origin.records]))
        except Exception as error:
            results.append({'error_type': type(error).__name__})

    @app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT'])
    async def other(request: Request, path: str):
        nonlocal mode
        if path == '__trigger':
            task = asyncio.create_task(trigger()); tasks.add(task); task.add_done_callback(tasks.discard)
            return {'accepted': True}
        if path == '__results':
            return {'results': results, 'pending': await fixture.control.call('pending')}
        if path == '__scenario':
            mode = (await request.json())['mode']
            return {'mode': mode}
        if path == '__shutdown':
            server.should_exit = True
            return {'stopping': True}
        if path == 'api/status':
            return {'desktop': {'enabled': True, 'build_id': args.build_id}}
        if mode == 'loading':
            await asyncio.sleep(2)
        if mode == 'failed':
            return JSONResponse({'detail': 'PRIVATE SYNTHETIC FAILURE'}, status_code=503)
        if path == 'api/captures':
            return {'sessions': [] if mode == 'empty' else [dict(id=1, platform='ios', status='running',
                app_name='[隔离验收] HTTP 源站', mode='ios-http-proxy')]}
        if path == 'api/captures/1/flows':
            return fixture.archive.page(cursor=int(request.query_params.get('cursor', 0)))
        if path.startswith('api/captures/1/flows/'):
            ident = path.split('/')[4]
            if path.endswith('/curl'):
                return PlainTextResponse(fixture.archive.curl(ident))
            return fixture.archive.detail(ident)
        if path == 'api/ios-setup':
            return dict(phase='ready', connection_state='ready', recording_state='recording', session_id=1, flow_count=0, flows=[])
        if path == 'api/ios-setup/projects':
            return {'projects': []}
        if path == 'api/package-sources/jenkins/packages':
            return {'packages': []}
        if path == 'api/apps':
            return {'apps': []}
        if path in {'api/devices', 'api/log-devices/discover'}:
            return {'devices': [], 'blocked_devices': [], 'count': 0}
        return JSONResponse({}, status_code=404)

    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    private_json(runtime / 'fixture-info.json', dict(port=port, origin_url=f'https://127.0.0.1:{fixture.origin.port}/hit'))
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False))
    print(json.dumps(dict(port=port, origin_port=fixture.origin.port, runtime=str(runtime))), flush=True)
    try:
        await server.serve(sockets=[listener])
    finally:
        for task in list(tasks):
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await fixture.cleanup()
        fixture.tmp.cleanup()
        listener.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-dir', required=True)
    parser.add_argument('--build-id', default='bp3-isolated')
    asyncio.run(run(parser.parse_args()))

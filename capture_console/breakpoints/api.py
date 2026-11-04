"""Authenticated control factory; backend mounting requires the explicit BP flag."""

import asyncio
import hmac
import ipaddress
import json
from types import MappingProxyType
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .control import error_json, validate
from .models import FRAME_LIMIT, Issue


def create_control_app(targets, desktop_token):
    if not isinstance(desktop_token, str) or len(desktop_token) < 32:
        raise ValueError('desktop token must be independently generated')
    targets = targets if callable(targets) else MappingProxyType(dict(targets))
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    capacity = asyncio.Semaphore(8)

    def authorize(request, capture_id):
        try:
            peer = ipaddress.ip_address(request.client.host)
            host = urlsplit('http://' + request.headers.get('host', '')).hostname
        except (ValueError, AttributeError):
            raise Issue('invalid_source', 403) from None
        if (not peer.is_loopback or host not in {'localhost', '127.0.0.1', '::1'}
                or 'origin' in request.headers or 'referer' in request.headers
                or request.headers.get('sec-fetch-site', 'none') != 'none'):
            raise Issue('invalid_source', 403)
        for name in ('authorization', 'x-device-id', 'x-breakpoint-epoch', 'host'):
            if len(request.headers.getlist(name)) != 1:
                raise Issue('unauthorized', 401)
        if not hmac.compare_digest(request.headers['authorization'].encode(), ('Bearer ' + desktop_token).encode()):
            raise Issue('unauthorized', 401)
        target = targets(capture_id) if callable(targets) else targets.get(capture_id)
        if not target:
            raise Issue('capture_not_found', 404)
        if (request.headers['x-device-id'], request.headers['x-breakpoint-epoch']) != (target.device_id, target.epoch):
            raise Issue('target_conflict')
        return target

    async def execute(request, capture_id, command, extra=None):
        acquired = False
        try:
            target = authorize(request, capture_id)
            if capacity.locked():
                raise Issue('control_busy', 429)
            await capacity.acquire()
            acquired = True
            async with asyncio.timeout(3):
                payload = {}
                if request.method != 'GET':
                    if int(request.headers.get('content-length', '0')) > FRAME_LIMIT:
                        raise Issue('frame_too_large', 413)
                    raw = bytearray()
                    async for part in request.stream():
                        if len(raw) + len(part) > FRAME_LIMIT:
                            raise Issue('frame_too_large', 413)
                        raw.extend(part)
                    payload = json.loads(raw) if raw else {}
                    if not isinstance(payload, dict):
                        raise Issue('invalid_command', 422)
                elif command == 'pending':
                    if set(request.query_params) - {'cursor', 'limit'}:
                        raise Issue('invalid_page', 422)
                    payload = {key: int(value) for key, value in request.query_params.items()}
                if extra:
                    if set(payload) & set(extra):
                        raise Issue('invalid_command', 422)
                    payload.update(extra)
                validate(command, payload)
                return JSONResponse(await target.call(command, payload), headers={'Cache-Control': 'no-store'})
        except Issue as issue:
            return JSONResponse(error_json(issue), status_code=issue.status, headers={'Cache-Control': 'no-store'})
        except (ValueError, UnicodeError, RecursionError):
            return JSONResponse(error_json(Issue('invalid_command', 422)), status_code=422)
        except (TimeoutError, OSError):
            return JSONResponse(error_json(Issue('control_timeout', 503)), status_code=503)
        finally:
            if acquired:
                capacity.release()

    prefix = '/api/captures/{capture_id}/breakpoints'

    @app.get(prefix)
    async def status(request: Request, capture_id: str):
        return await execute(request, capture_id, 'status')

    @app.put(prefix + '/rules/{rule_id}')
    async def rule(request: Request, capture_id: str, rule_id: str):
        return await execute(request, capture_id, 'rule', {'id': rule_id})

    @app.post(prefix + '/{action}')
    async def action(request: Request, capture_id: str, action: str):
        if action not in {'enable', 'disable', 'heartbeat', 'release-all'}:
            return JSONResponse(error_json(Issue('invalid_command', 404)), status_code=404)
        return await execute(request, capture_id, action)

    @app.get(prefix + '/pending')
    async def pending(request: Request, capture_id: str):
        return await execute(request, capture_id, 'pending')

    @app.get(prefix + '/pending/{pending_id}')
    async def detail(request: Request, capture_id: str, pending_id: str):
        return await execute(request, capture_id, 'detail', {'id': pending_id})

    @app.post(prefix + '/pending/{pending_id}/resolve')
    async def resolve(request: Request, capture_id: str, pending_id: str):
        return await execute(request, capture_id, 'resolve', {'id': pending_id})

    return app

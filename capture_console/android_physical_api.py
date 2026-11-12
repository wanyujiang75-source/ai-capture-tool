"""Loopback-only desktop control for the experimental Android companion."""

import subprocess
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from .android_physical_device import devices


class PhysicalStart(BaseModel):
    model_config = ConfigDict(extra='forbid')
    serial: str = Field(min_length=1, max_length=128)
    desktop_pid: int = Field(gt=1)
    experimental_consent: bool = False


def physical_router(service):
    router = APIRouter(prefix='/api/android-physical')

    def desktop(request):
        origin = request.headers.get('origin')
        if (not request.client or request.client.host not in {'127.0.0.1', '::1', 'localhost'}
                or request.url.hostname not in {'127.0.0.1', '::1', 'localhost'}
                or request.headers.get('x-capture-desktop') != 'android-physical'
                or origin and origin != f'{request.url.scheme}://{request.url.netloc}'):
            raise HTTPException(403, detail='此操作仅供本机桌面端使用。')

    @router.get('')
    def status(request: Request):
        desktop(request)
        return service.status()

    @router.get('/devices')
    def available(request: Request):
        desktop(request)
        try:
            return {'devices': devices(service.adb)}
        except (OSError, subprocess.TimeoutExpired):
            raise HTTPException(503, detail={'user_message': '无法检测 USB 设备，请检查 Android 连接组件。'}) from None

    @router.post('/start')
    def start(request: Request, payload: PhysicalStart):
        desktop(request)
        try:
            return service.start(payload.serial, payload.desktop_pid, payload.experimental_consent)
        except ValueError as exc:
            raise HTTPException(409, detail={'user_message': str(exc)}) from exc

    @router.post('/stop')
    def stop(request: Request):
        desktop(request)
        return service.stop()

    @router.post('/recover')
    def recover(request: Request):
        desktop(request)
        return service.recover()

    @router.post('/terminate')
    def terminate(request: Request):
        desktop(request)
        return service.terminate()

    @router.post('/recover/{serial}')
    def recover_device(request: Request, serial: str):
        desktop(request)
        try:
            return service.recover(serial)
        except ValueError as exc:
            raise HTTPException(409, detail={'user_message': str(exc)}) from exc
        except (OSError, subprocess.TimeoutExpired):
            raise HTTPException(503, detail={'user_message': '无法检测原手机，请检查 USB 连接后重试。'}) from None

    return router

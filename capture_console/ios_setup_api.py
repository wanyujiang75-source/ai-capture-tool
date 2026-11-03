"""Local desktop control plane; profile files never served on the LAN."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .ios_keychain import IOSPairingError


class IOSPreparePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ssid: str
    desktop_pid: int = Field(gt=1)


class IOSStopPayload(BaseModel):
    phone_configuration_removed: bool = False


class IOSProjectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    name: str = Field(min_length=1, max_length=80)
    domains: list[str] = Field(min_length=1, max_length=64)


class IOSRecordingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str


def ios_operation(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except IOSPairingError as exc:
        raise HTTPException(400, detail={"code": exc.code, "user_message": str(exc),
                                         "recovery_action": "检查连接后重试"}) from exc
    except ValueError as exc:
        raise HTTPException(400, detail={"user_message": str(exc), "recovery_action": "检查手机连接"}) from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(503, detail={"user_message": "手机连接或本地记录异常，请检查连接后重试。",
                                         "recovery_action": "检查手机连接"}) from exc


def ios_setup_router(service):
    router = APIRouter(prefix="/api/ios-setup")

    @router.get("")
    def status():
        return service.status()

    @router.get("/projects")
    def projects():
        return {"projects": ios_operation(service.projects.list)}

    @router.post("/projects")
    def save_project(payload: IOSProjectPayload):
        return ios_operation(service.projects.save, project_id=payload.id, name=payload.name, domains=payload.domains)

    @router.post("/recording/start")
    def start_recording(payload: IOSRecordingPayload):
        return ios_operation(service.start_recording, payload.project_id)

    @router.post("/recording/stop")
    def stop_recording():
        return ios_operation(service.stop_recording)

    @router.post("/prepare")
    def prepare(payload: IOSPreparePayload):
        return ios_operation(service.prepare, payload.ssid, owner_pid=payload.desktop_pid)

    @router.post("/stop")
    def stop(payload: IOSStopPayload):
        if not payload.phone_configuration_removed:
            raise HTTPException(409, detail={"user_message": "请先在 iPhone 删除本次测试描述文件，再结束测试，避免手机断网。"})
        return ios_operation(service.stop)

    return router

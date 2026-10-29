"""Local desktop control plane; profile files never served on the LAN."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field


class IOSPreparePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ssid: str
    desktop_pid: int = Field(gt=1)


class IOSStopPayload(BaseModel):
    phone_configuration_removed: bool = False


def ios_setup_router(service):
    router = APIRouter(prefix="/api/ios-setup")

    @router.get("")
    def status():
        return service.status()

    @router.post("/prepare")
    def prepare(payload: IOSPreparePayload):
        try:
            return service.prepare(payload.ssid, owner_pid=payload.desktop_pid)
        except ValueError as exc:
            raise HTTPException(400, detail={"user_message": str(exc)}) from exc
        except (OSError, RuntimeError) as exc:
            raise HTTPException(503, detail={"user_message": "无法准备 iPhone 连接，请检查本机网络与运行组件。"}) from exc

    @router.post("/stop")
    def stop(payload: IOSStopPayload):
        if not payload.phone_configuration_removed:
            raise HTTPException(409, detail={"user_message": "请先在 iPhone 删除本次测试描述文件，再结束测试，避免手机断网。"})
        return service.stop()

    return router

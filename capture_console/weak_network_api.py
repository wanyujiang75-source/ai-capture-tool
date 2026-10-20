"""Device-scoped weak-network endpoints, independent of capture session state."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from .weak_network import NetworkProfile


class WeakNetworkPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_kbps: int = Field(ge=32, le=100000, strict=True)
    download_kbps: int = Field(ge=32, le=100000, strict=True)
    latency_ms: int = Field(ge=0, le=5000, strict=True)


def weak_network_router(service, validate_device):
    router = APIRouter()

    @router.post("/api/desktop/recover-weak-network")
    def recover_desktop():
        service.restore_all()
        return {"ok": not service.records, "pending_devices": list(service.records)}

    @router.get("/api/devices/{device_id}/weak-network")
    def status(device_id: str):
        validate_device(device_id)
        return service.status(device_id)

    @router.put("/api/devices/{device_id}/weak-network")
    def apply(device_id: str, payload: WeakNetworkPayload):
        validate_device(device_id)
        return service.apply(device_id, NetworkProfile(**payload.model_dump()))

    @router.delete("/api/devices/{device_id}/weak-network")
    def restore(device_id: str):
        validate_device(device_id)
        return service.restore(device_id)

    return router

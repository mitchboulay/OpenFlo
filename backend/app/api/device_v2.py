from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Header, Request
from fastapi.responses import JSONResponse

from ..config import Settings
from ..models import (
    GetFwRequest,
    HealthcheckRequest,
    QcReportRequest,
    RegisterRequest,
    UpdateDeviceRequest,
)
from ..persistence.repository import Repository
from ..services import device_policy
from ..services.registry import RegistryService
from ..services.synchronization import SynchronizationService
from ..services.telemetry import TelemetryService


router = APIRouter(prefix="/device-api/v2", tags=["device-v2"])

DeviceId = Annotated[str | None, Header(alias="x-device-id")]
DeviceOtt = Annotated[str | None, Header(alias="x-device-ott")]


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _repo(request: Request) -> Repository:
    return request.app.state.repo


def _client(request: Request) -> str | None:
    return request.client.host if request.client else None


def _registry(request: Request) -> RegistryService:
    return RegistryService(_repo(request))


def _telemetry(request: Request) -> TelemetryService:
    return TelemetryService(_repo(request))


def _sync(request: Request) -> SynchronizationService:
    return SynchronizationService(_repo(request), _settings(request))


@router.post("/register")
def register(
    request: Request,
    body: RegisterRequest,
    ott: DeviceOtt = None,
) -> JSONResponse:
    _registry(request).register(body.deviceId, ott, _client(request))
    # The firmware only checks HTTP 200 for registration; the body is unused.
    return JSONResponse({}, status_code=200)


@router.post("/update-device")
def update_device(
    request: Request,
    body: UpdateDeviceRequest,
    device_id: DeviceId = None,
) -> dict[str, Any]:
    _registry(request).require(device_id)
    assert device_id is not None
    payload = body.model_dump(mode="json", exclude_none=True)
    _telemetry(request).ingest_update(device_id, payload)
    return _sync(request).update_response(device_id)


@router.post("/get-fw")
def get_fw(
    request: Request,
    body: GetFwRequest,
    device_id: DeviceId = None,
) -> dict[str, Any]:
    _registry(request).require(device_id)
    _telemetry(request).record_event(
        device_id or body.deviceId, "get-fw", body.model_dump(mode="json")
    )
    return _sync(request).get_fw_response()


@router.post("/get-bottle")
def get_bottle(
    request: Request,
    device_id: DeviceId = None,
) -> dict[str, Any]:
    # Unclaimed, retired, provisioning or identity-flagged: the bottle lock, never authorization (FR-5, FR-13).
    if device_id:
        with _repo(request).db.connection() as conn:
            if device_policy.withholds_bottle(conn, device_id):
                return JSONResponse(device_policy.BOTTLE_LOCK_BODY, status_code=device_policy.BOTTLE_LOCK_STATUS)
    _registry(request).require(device_id)
    assert device_id is not None
    status, body = _sync(request).bottle_response(device_id)
    return JSONResponse(body, status_code=status)


@router.post("/get-schedule")
def get_schedule(
    request: Request,
    device_id: DeviceId = None,
) -> dict[str, Any]:
    _registry(request).require(device_id)
    assert device_id is not None
    return _sync(request).schedule_response(device_id)


@router.post("/healthcheck")
def healthcheck(
    request: Request,
    body: HealthcheckRequest,
    device_id: DeviceId = None,
) -> dict[str, Any]:
    _registry(request).healthcheck(device_id or body.deviceId, _client(request))
    _telemetry(request).record_event(
        device_id or body.deviceId, "healthcheck", body.model_dump(mode="json")
    )
    return {}


@router.post("/send-events")
def send_events(
    request: Request,
    payload: Any = Body(...),
    device_id: DeviceId = None,
) -> dict[str, Any]:
    _registry(request).require(device_id)
    assert device_id is not None
    _telemetry(request).record_event(device_id, "send-events", payload)
    # The firmware ignores the success body and only checks HTTP 200.
    return {}


@router.post("/create-qc-report")
def create_qc_report(
    request: Request,
    body: QcReportRequest,
    device_id: DeviceId = None,
) -> dict[str, Any]:
    _registry(request).require(device_id)
    assert device_id is not None
    _telemetry(request).record_qc_report(device_id, body.model_dump(mode="json"))
    return {}

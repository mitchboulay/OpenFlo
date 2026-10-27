"""Device registry: the device-API policy table, read from ``devices.status`` (AD-3, AD-4).

Device IDs are public identifiers, so nothing here is authentication; ``register`` is bound to a provisioning
session's one-time token (``services.provisioning``). Every rejection is ``{code, message}`` without ``fields``,
which the firmware ignores.
"""
from __future__ import annotations

from ..errors import ApiError
from ..models import DEVICE_ID_RE
from ..persistence.repository import Repository
from ..repositories import devices
from ..repositories.devices import Device
from . import provisioning

# Statuses served by the device API; unclaimed and retired rows are answered as unregistered.
SERVED_STATUSES = frozenset({"provisioning", "active"})


def _not_registered() -> ApiError:
    return ApiError("DEVICE_NOT_REGISTERED", "device is not registered with this backend")


class RegistryService:
    def __init__(self, repo: Repository):
        self.repo = repo

    def register(self, device_id: str, ott: str | None, remote_addr: str | None) -> None:
        """Session-token registration (AD-4): 200 on a token match, else 422 NOT_FOUND."""
        if DEVICE_ID_RE.fullmatch(device_id) is None:
            raise ApiError("MALFORMED_DEVICE_ID", "deviceId must be 1-64 characters of [A-Za-z0-9:_.-]")
        refused: ApiError | None = None
        with self.repo.db.connection() as conn:
            try:
                provisioning.register(conn, device_id, ott, remote_addr or "")
            except ApiError as exc:
                refused = exc  # committed: the session keeps the refusal event
        if refused is not None:
            raise refused

    def healthcheck(self, device_id: str, remote_addr: str | None) -> None:
        """200 for served devices, and for unknown IDs while a session awaits a join (recording a sighting).

        Pairing (Pairing_task) loops on healthcheck until HTTP 200 and only then calls register.
        """
        with self.repo.db.connection() as conn:
            device = devices.get(conn, device_id)
            served = device is not None and device.status in SERVED_STATUSES
            pairable = served or (device is None and DEVICE_ID_RE.fullmatch(device_id) is not None)
            joinable = pairable and provisioning.observe_healthcheck(conn, device, device_id, remote_addr)
        if not (served or joinable):
            raise _not_registered()

    def require(self, device_id: str | None) -> Device:
        """The served device for a sync endpoint; unknown, unclaimed and retired IDs get DEVICE_NOT_REGISTERED."""
        if not device_id:
            raise ApiError("MISSING_DEVICE_ID", "x-device-id header is required")
        with self.repo.db.connection() as conn:
            device = devices.get(conn, device_id)
        if device is None or device.status not in SERVED_STATUSES:
            raise _not_registered()
        return device

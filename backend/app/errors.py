from __future__ import annotations

from typing import Any

# Codes the 3.0.64 firmware answers with a factory reset (wipes registration,
# backend host and Wi-Fi, then restarts): INVALID_DEVICE_ID from update-device
# (FUN_40094c80 -> FUN_40097e50), NOT_UNIQUE from register. It reads error bodies
# regardless of HTTP status, so these must never reach a device.
FIRMWARE_RESET_CODES = frozenset({"INVALID_DEVICE_ID", "NOT_UNIQUE"})


class ApiError(Exception):
    """An error with a stable ``code``, for the device API and ``/api/v1`` alike.

    Serialized as ``{"code", "message"}`` (plus ``detail`` on ``/api/v1`` when given), never with
    ``fields``, which the 3.0.64 firmware treats as an ignorable body.
    """

    def __init__(
        self,
        code: str,
        message: str,
        status: int = 422,
        detail: dict[str, Any] | None = None,
    ):
        if code in FIRMWARE_RESET_CODES:
            raise ValueError(f"{code} factory-resets the device; use another code")
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.detail = detail

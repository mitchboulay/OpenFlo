from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

# Device IDs accepted on the device path (the Espressif-derived ID is 16 hex; the lab tools use longer ones).
DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9:_.-]{1,64}$")


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    deviceId: StrictStr = Field(min_length=1, max_length=64)


class UpdateDeviceRequest(BaseModel):
    """Telemetry body sent by the device to /update-device.

    Field names and types are derived from FUN_40094c80. Unknown inbound
    fields are preserved for diagnostics.
    """

    model_config = ConfigDict(extra="allow")

    batteryLevel: StrictInt | None = None
    firmwareVersion: StrictStr | None = None
    connectionLevel: StrictInt | None = None
    localIpAddress: StrictStr | None = None
    bottleSensorStatus: StrictStr | None = None
    networkName: StrictStr | None = None
    extPowerState: StrictBool | None = None
    isProVersion: StrictBool | None = None
    ramUsed: StrictInt | None = None
    ramTotal: StrictInt | None = None
    ramUsedPercent: StrictInt | None = None
    HeapFailureCount: StrictInt | None = None
    deviceType: StrictInt | None = None
    pingQuality: StrictInt | None = None
    pingLatency: StrictInt | None = None
    pingFailureCount: StrictInt | None = None
    dnsFailureCount: StrictInt | None = None
    noAppMode: StrictInt | StrictBool | None = None


class GetFwRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    firmwareVersion: StrictStr
    deviceId: StrictStr


class HealthcheckRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    deviceId: StrictStr


class QcReportData(BaseModel):
    model_config = ConfigDict(extra="allow")
    bottleSwitchPassed: StrictStr | None = None
    userDispenses: StrictStr | None = None
    firmwareVersion: StrictStr | None = None
    floatTestPassed: StrictStr | None = None
    proVersion: StrictBool | None = None
    deviceType: StrictInt | None = None


class QcReportRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    deviceId: StrictStr
    sessionId: StrictInt
    data: QcReportData


class ScheduleItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp: StrictInt = Field(gt=0)
    doseCount: StrictInt = Field(ge=1, le=2)
    cmd: StrictInt = Field(ge=0, le=1)


class EventPayload(BaseModel):
    """Event uploads have no recovered schema; accept any JSON value."""

    model_config = ConfigDict(extra="allow")
    raw: Any

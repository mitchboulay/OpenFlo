"""Request and response models for ``/api/v1`` (API Specification schemas).

Every model forbids unknown fields. Response fields that may be unknown are required and nullable, so they
serialize as ``null`` and are never omitted. PATCH bodies declare non-nullable fields as ``T = Field(None)``:
omitted means "unchanged", while an explicit ``null`` fails validation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Timestamp = str  # ISO-8601 UTC
DeviceStatus = Literal["provisioning", "active", "unclaimed", "retired"]
Guidance = Literal["ok", "refill_soon", "refill_now", "unknown"]
WakePreset = Literal["battery_saver", "balanced", "responsive", "testing"]
FlagKind = Literal["ip_conflict", "telemetry_implausible"]
PendingKind = Literal["controls", "dose", "dispense", "schedule", "retire"]
HardwareType = Literal["valve", "motor"]

# Constraint 4 bounds; the firmware substitutes 48 h for intervals <= 2 x shift-time.
MIN_SYNC_INTERVAL = 900
MAX_SYNC_INTERVAL = 172_800
MIN_SHIFT_TIME = 30
MAX_SHIFT_TIME = 3600


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorBody(Model):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    message: str
    detail: dict[str, object] | None = None


# -- homes ---------------------------------------------------------------------------------------------------

class HomeCreate(Model):
    name: str = Field(min_length=1, max_length=60)
    timezone: str | None = Field(None, description="IANA zone; defaults to the server's TZ, else UTC")


class HomeUpdate(Model):
    name: str = Field(None, min_length=1, max_length=60)
    timezone: str = Field(None, description="IANA zone")


class Home(Model):
    id: int
    name: str
    timezone: str
    created_at: Timestamp


class HomeSummary(Home):
    device_count: int
    attention_count: int
    summary: Literal["ok", "attention", "empty"]


# -- device parts ----------------------------------------------------------------------------------------------

class Controls(Model):
    dispensing_enabled: bool
    wake_preset: WakePreset | None = Field(description="null = Custom (raw seconds)")
    schedules_enabled: bool
    sync_interval_seconds: int | None
    shift_time_seconds: int | None
    updated_at: Timestamp | None


class ControlsUpdate(Model):
    dispensing_enabled: bool = Field(None)
    wake_preset: WakePreset | None = Field(None, description="A preset sets both intervals; null = Custom")
    schedules_enabled: bool = Field(None)
    sync_interval_seconds: int | None = Field(None, ge=MIN_SYNC_INTERVAL, le=MAX_SYNC_INTERVAL)
    shift_time_seconds: int | None = Field(None, ge=MIN_SHIFT_TIME, le=MAX_SHIFT_TIME)


class Profile(Model):
    id: int
    home_id: int | None
    slug: str
    name: str
    system: bool
    flow_full_ml_s: float
    capacity_ml: float
    default_dose_ml: float
    calibrated: bool


class ProfileCreate(Model):
    name: str = Field(min_length=1, max_length=40)
    capacity_ml: float = Field(gt=0, le=100_000)
    flow_full_ml_s: float = Field(gt=0, le=1000)
    default_dose_ml: float = Field(gt=0, le=100_000)


class ProfileUpdate(Model):
    name: str = Field(None, min_length=1, max_length=40)
    capacity_ml: float = Field(None, gt=0, le=100_000)
    flow_full_ml_s: float = Field(None, gt=0, le=1000)
    default_dose_ml: float = Field(None, gt=0, le=100_000)


class DosePresets(Model):
    """Light · Standard · Strong doses for the liquid, whole mL; Standard is the liquid's default dose."""

    light_ml: int
    standard_ml: int
    strong_ml: int


class Dosing(Model):
    profile: Profile
    dose_ml: float | None
    fixed_seconds: float | None
    computed_seconds: float
    compensation_enabled: bool
    flow_scale: float
    capped_ml_when_low: float | None
    warning: Literal["CAPPED_WHEN_LOW"] | None
    min_ml: int = Field(description="Smallest whole-mL dose accepted at a full bottle")
    max_ml: int = Field(description="Largest whole-mL dose accepted at a full bottle")
    flow_ml_s: float = Field(description="Calibrated flow at a full bottle, mL/s")
    calibrated: bool = Field(description="The liquid's flow is measured (system profile or a device calibration)")
    presets: DosePresets


class DosingUpdate(Model):
    profile_id: int
    dose_ml: float | None = Field(None, gt=0)
    fixed_seconds: float | None = Field(None, ge=1.0, le=30.0)
    compensation_enabled: bool = Field(None)

    @model_validator(mode="after")
    def _one_amount(self) -> DosingUpdate:
        if (self.dose_ml is None) == (self.fixed_seconds is None):
            raise ValueError("set exactly one of dose_ml and fixed_seconds")
        return self


class CalibrationRequest(Model):
    measured_ml: float = Field(gt=0)


class Bottle(Model):
    id: int
    capacity_ml: float
    initial_fill_ml: float | None
    started_at: Timestamp
    est_remaining_ml: float | None
    est_doses_left: int | None
    est_days_left: float | None
    guidance: Guidance


class BottleCreate(Model):
    fill: Literal["full", "set"]
    fill_ml: float | None = Field(None, ge=0, description="With fill=set; omitted = level unknown")


class FillAdjust(Model):
    fill_ml: float = Field(ge=0)


class DispenseRequest(Model):
    id: int
    requested_at: Timestamp
    delivered_at: Timestamp | None
    cancelled_at: Timestamp | None
    confirmed_at: Timestamp | None


class RemoteDispense(Model):
    pending: DispenseRequest | None
    last_delivered: DispenseRequest | None


class FlagChange(Model):
    field: str
    old: str | None
    new: str | None


class FlagDetail(Model):
    source_ips: list[str] | None
    field: str | None
    old: str | None
    new: str | None
    changes: list[FlagChange] = Field(description="Every changed telemetry field (field/old/new = the first)")


class Flag(Model):
    id: int
    kind: FlagKind
    detail: FlagDetail
    raised_at: Timestamp
    acked_at: Timestamp | None
    acked_by: str | None


class PendingChange(Model):
    kind: PendingKind
    since: Timestamp


# -- devices -------------------------------------------------------------------------------------------------

class UnclaimedDevice(Model):
    device_id: str
    last_ip: str | None
    first_seen: Timestamp
    last_seen: Timestamp


class DeviceUpdate(Model):
    name: str = Field(None, min_length=1, max_length=40)
    location: str | None = Field(None, max_length=60)
    installed_at: datetime = Field(None)
    home_id: int = Field(None)


class RetireRequest(Model):
    force: bool = False


class DeviceSummary(Model):
    device_id: str
    name: str | None
    location: str | None
    status: DeviceStatus
    battery_level: int | None = Field(ge=0, le=100)
    bottle_guidance: Guidance
    last_seen: Timestamp | None
    next_expected_sync: Timestamp | None
    next_dose_at: Timestamp | None
    pending_count: int
    flagged: bool


class DeviceDetail(Model):
    device_id: str
    home_id: int | None
    name: str | None
    location: str | None
    status: DeviceStatus
    retire_requested_at: Timestamp | None
    installed_at: Timestamp | None
    mac: str | None
    last_ip: str | None
    hardware_type: HardwareType | None
    pcb_version: str | None
    firmware_version: str | None
    network_name: str | None
    signal: int | None
    battery_level: int | None
    ext_power: bool | None
    first_seen: Timestamp
    last_seen: Timestamp
    last_sync: Timestamp | None
    next_expected_sync: Timestamp | None
    next_dose_at: Timestamp | None
    pending: list[PendingChange]
    flags: list[Flag]
    controls: Controls
    dosing: Dosing
    bottle: Bottle | None
    remote_dispense: RemoteDispense


# -- battery and history ---------------------------------------------------------------------------------------

class BatteryPoint(Model):
    at: Timestamp
    level: int


class Battery(Model):
    points: list[BatteryPoint]
    projection_days_to_20: float | None
    basis_days: float | None


class DispenseItem(Model):
    id: int
    code: int
    device_timestamp: int | None
    received_at: Timestamp
    est_volume_ml: float | None
    dose_count: int


class EventItem(Model):
    id: int
    received_at: Timestamp
    kind: str
    payload: object


class SyncItem(Model):
    id: int
    started_at: Timestamp
    ended_at: Timestamp
    request_count: int
    source_ip: str


class History(Model):
    kind: Literal["dispenses", "events", "syncs"]
    items: list[DispenseItem] | list[EventItem] | list[SyncItem]
    next_before_id: int | None

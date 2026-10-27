"""Map service read models onto the ``/api/v1`` response schemas (no logic beyond field shaping)."""
from __future__ import annotations

from typing import Any, cast

from .. import schemas
from ...repositories.devices import Device
from ...repositories.flags import IdentityFlag
from ...repositories.homes import Home
from ...repositories.profiles import LiquidProfile
from ...services.device_views import DeviceSnapshot, DispenseRequestView, HomeSnapshot
from ...services.dosing_service import BottleView, DosingView


def home(row: Home) -> schemas.Home:
    return schemas.Home(id=row.id, name=row.name, timezone=row.timezone, created_at=row.created_at)


def home_summary(snap: HomeSnapshot) -> schemas.HomeSummary:
    return schemas.HomeSummary(
        **home(snap.home).model_dump(), device_count=snap.device_count,
        attention_count=snap.attention_count, summary=snap.summary,
    )


def profile(row: LiquidProfile) -> schemas.Profile:
    return schemas.Profile(
        id=row.id, home_id=row.home_id, slug=row.slug, name=row.name, system=row.system,
        flow_full_ml_s=row.flow_full_ml_s, capacity_ml=row.capacity_ml, default_dose_ml=row.default_dose_ml,
        calibrated=row.calibrated,
    )


def dosing(view: DosingView) -> schemas.Dosing:
    return schemas.Dosing(
        profile=profile(view.profile), dose_ml=view.dose_ml, fixed_seconds=view.fixed_seconds,
        computed_seconds=view.computed_seconds, compensation_enabled=view.compensation_enabled,
        flow_scale=view.flow_scale, capped_ml_when_low=view.capped_ml_when_low, warning=view.warning,
        min_ml=view.min_ml, max_ml=view.max_ml, flow_ml_s=view.flow_ml_s, calibrated=view.calibrated,
        presets=schemas.DosePresets(light_ml=view.presets_ml[0], standard_ml=view.presets_ml[1],
                                    strong_ml=view.presets_ml[2]),
    )


def bottle(view: BottleView) -> schemas.Bottle:
    return schemas.Bottle(
        id=view.id, capacity_ml=view.capacity_ml, initial_fill_ml=view.initial_fill_ml,
        started_at=view.started_at, est_remaining_ml=view.est_remaining_ml, est_doses_left=view.est_doses_left,
        est_days_left=view.est_days_left, guidance=view.guidance,
    )


def controls(row: dict[str, Any]) -> schemas.Controls:
    return schemas.Controls(
        dispensing_enabled=row["dispensing_enabled"], wake_preset=row["wake_preset"],
        schedules_enabled=row["schedules_enabled"], sync_interval_seconds=row["sync_interval_seconds"],
        shift_time_seconds=row["shift_time_seconds"], updated_at=row["updated_at"],
    )


def dispense_request(view: DispenseRequestView) -> schemas.DispenseRequest:
    request = view.request
    return schemas.DispenseRequest(
        id=request.id, requested_at=request.requested_at, delivered_at=request.delivered_at,
        cancelled_at=request.cancelled_at, confirmed_at=view.confirmed_at,
    )


def _text(value: Any) -> str | None:
    return None if value is None else str(value)


def flag(row: IdentityFlag) -> schemas.Flag:
    detail = row.detail
    source_ips = None
    if row.kind == "ip_conflict":
        source_ips = sorted({*detail.get("other_ips", []), detail.get("source_ip")} - {None})
    changes = [
        schemas.FlagChange(field=key, old=_text(change.get("stored")), new=_text(change.get("reported")))
        for key, change in sorted(detail.get("changed", {}).items())
    ]
    first = changes[0] if changes else None
    return schemas.Flag(
        id=row.id, kind=cast(schemas.FlagKind, row.kind), raised_at=row.raised_at, acked_at=row.acked_at,
        acked_by=row.acked_by,
        detail=schemas.FlagDetail(
            source_ips=source_ips, field=first.field if first else None, old=first.old if first else None,
            new=first.new if first else None, changes=changes,
        ),
    )


def unclaimed(row: Device) -> schemas.UnclaimedDevice:
    return schemas.UnclaimedDevice(
        device_id=row.device_id, last_ip=row.last_ip, first_seen=row.first_seen, last_seen=row.last_seen
    )


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def device_summary(snap: DeviceSnapshot) -> schemas.DeviceSummary:
    device, report = snap.device, snap.telemetry.payload if snap.telemetry else {}
    return schemas.DeviceSummary(
        device_id=device.device_id, name=device.name, location=device.location,
        status=cast(schemas.DeviceStatus, device.status), battery_level=_int_or_none(report.get("batteryLevel")),
        bottle_guidance=cast(schemas.Guidance, snap.guidance), last_seen=device.last_seen,
        next_expected_sync=snap.sync.next_expected_sync, next_dose_at=snap.sync.next_dose_at,
        pending_count=len(snap.sync.pending), flagged=bool(snap.open_flags),
    )


def device_detail(snap: DeviceSnapshot) -> schemas.DeviceDetail:
    device, report = snap.device, snap.telemetry.payload if snap.telemetry else {}
    ext_power = report.get("extPowerState")
    return schemas.DeviceDetail(
        device_id=device.device_id, home_id=device.home_id, name=device.name, location=device.location,
        status=cast(schemas.DeviceStatus, device.status), retire_requested_at=device.retire_requested_at,
        installed_at=device.installed_at, mac=device.mac, last_ip=device.last_ip,
        hardware_type=cast(schemas.HardwareType | None, device.hardware_type), pcb_version=device.pcb_version,
        firmware_version=device.firmware_version, network_name=_text(report.get("networkName")),
        signal=_int_or_none(report.get("connectionLevel")), battery_level=_int_or_none(report.get("batteryLevel")),
        ext_power=ext_power if isinstance(ext_power, bool) else None,
        first_seen=device.first_seen, last_seen=device.last_seen,
        last_sync=snap.sync.last_sync.started_at if snap.sync.last_sync else None,
        next_expected_sync=snap.sync.next_expected_sync, next_dose_at=snap.sync.next_dose_at,
        pending=[schemas.PendingChange(kind=p.kind, since=p.since) for p in snap.sync.pending],
        flags=[flag(f) for f in snap.open_flags],
        controls=controls(snap.controls), dosing=dosing(snap.dosing),
        bottle=bottle(snap.dosing.bottle) if snap.dosing.bottle else None,
        remote_dispense=schemas.RemoteDispense(
            pending=dispense_request(snap.pending_dispense) if snap.pending_dispense else None,
            last_delivered=(dispense_request(snap.last_delivered_dispense)
                            if snap.last_delivered_dispense else None),
        ),
    )

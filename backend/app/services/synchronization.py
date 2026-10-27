from __future__ import annotations

from ..config import Settings
from ..persistence.repository import Repository
from . import device_lifecycle, device_policy, dosing_service, scheduling

# The firmware's valve timing table has 6 slots (FUN_4008e0ec).
DISPENSE_TIMING_SLOTS = 6
# Volume is tracked server-side (AD-5); the device's own counter is kept full so it never self-locks.
DOSE_COUNTER_CEILING = 100


class SynchronizationService:
    """Build only evidence-supported responses.

    remoteDispense is emitted only for an operator-queued request; never OTA URLs, external power commands,
    WiFi changes or settings resets. Schedules are served only while the operator has turned on both
    dispensing and schedules for the device (Constraint 6).
    """

    def __init__(self, repo: Repository, settings: Settings):
        self.repo = repo
        self.settings = settings

    def update_response(self, device_id: str) -> dict:
        data: dict = {"isUpToDate": True}

        # AD-6: false while the schedule the device should hold differs from the one last served; the
        # device then calls get-schedule in this sync.
        with self.repo.db.connection() as conn:
            data["isScheduleSynced"] = scheduling.sync_on_update(conn, device_id)

        # data.config is written to the device config store (FUN_400984d4). Only the
        # no-schedule RTC wake interval is ever sent; the firmware substitutes its
        # 172,800 s default for values <= 2 x shift-time.
        controls = self.repo.get_controls(device_id)
        config = {}
        # shift-time first: fast-sync-time is rejected when <= 2 x shift-time, and
        # FUN_400984d4 applies keys in document order.
        if controls["shift_time_seconds"]:
            config["shift-time"] = controls["shift_time_seconds"]
        if controls["sync_interval_seconds"]:
            config["fast-sync-time"] = controls["sync_interval_seconds"]
        if config:
            data["config"] = config

        # Operator "dispense now": FUN_40094c80 dispenses when remoteDispense.isActive
        # is present (any value) and the nonce differs from the last one it saw
        # (FUN_4008e388 -> FUN_4008e25c(4)). nonce is dereferenced unchecked, so it is
        # always sent. Taken atomically: sent in exactly one response, never retried.
        # Withheld (left queued) for an inactive or identity-flagged device (FR-13).
        if self.repo.get_controls(device_id)["dispensing_enabled"] and self._may_receive_commands(device_id):
            request = self.repo.take_pending_dispense(device_id)
            if request:
                data["remoteDispense"] = {"isActive": True, "nonce": request["nonce"]}

        # Deliberately absent:
        #   url, extPowerState, isSettingsSynced, isWifiUpdated
        return {"data": data}

    def _may_receive_commands(self, device_id: str) -> bool:
        with self.repo.db.connection() as conn:
            return device_policy.may_receive_commands(conn, device_id)

    def get_fw_response(self) -> dict:
        # No url/redirectLocation: the firmware must not enter the OTA path.
        return {"actualFirmwareVersion": self.settings.firmware_version}

    def schedule_response(self, device_id: str) -> dict:
        # Paused, retiring or flagged devices are served [] (AD-6). Its hash is recorded, so lifting the pause
        # changes the desired hash and the device refetches at its next sync.
        with self.repo.db.connection() as conn:
            items = scheduling.serve(conn, device_id)
            # Phase 2 of a two-phase retire (FR-2): completes once the empty schedule is served.
            device_lifecycle.complete_if_requested(conn, device_id)
        return {"data": items}

    def bottle_response(self, device_id: str) -> tuple[int, dict]:
        """(status, body). The bottle is the firmware's dispense interlock."""
        if not self.repo.get_controls(device_id)["dispensing_enabled"]:
            # Locked. FUN_400949bc: 422 -> FUN_40094750 reads fields.code; for
            # BOTTLE_INSTALLED_NOT_AUTHORIZED with the bottle in state OK it calls
            # FUN_40091644(3) (UNCO, bttl-vald=0); in any other state it is logged.
            # Then FUN_40091d6c clears the bottle-sync flag. This is the one device
            # response that carries "fields" on purpose.
            return device_policy.BOTTLE_LOCK_STATUS, dict(device_policy.BOTTLE_LOCK_BODY)
        # Volume is tracked server-side (AD-5), so the counter is topped up on every
        # get-bottle and the device never locks itself out as "empty".
        number = left = DOSE_COUNTER_CEILING
        # FUN_40094750 (get-bottle 200): data.dispenseLeft / dispenseNumber set the
        # dose counters; dispenseLeft != 0 calls FUN_4009183c, which authorizes the
        # bottle. Top-level "config" goes to FUN_4008e0ec, which rewrites the valve
        # timing slots AND always persists "disp-timings" from a buffer that is only
        # initialized by the entries given. So the full table is always sent, in slot order.
        # FUN_4008db0c runs dose N for config[used] tenths of a second (100 ms loop).
        # The counter is topped up every get-bottle, so "used" restarts at 0; the open
        # time for the current fill level fills every slot so the slot index never matters.
        with self.repo.db.connection() as conn:
            tenths = dosing_service.serve_dose(conn, device_id).tenths
        # Root-level "config": the cloud path (FUN_40094750(body, 0)) reads it there.
        return 200, {
            "data": {
                "dispenseLeft": left,
                "dispenseNumber": number,
                "dispenseTime": 0,
                "bottleId": "openflo",
            },
            "config": [{"index": i, "dispenseTime": tenths} for i in range(DISPENSE_TIMING_SLOTS)],
        }

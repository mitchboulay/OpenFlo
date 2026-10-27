"""Request and response models for the provisioning wizard and claims (FR-4, FR-5, AD-4)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .schemas import Model, Timestamp

SessionKind = Literal["new", "reset"]
SessionStatus = Literal["awaiting_reset", "awaiting_softap", "awaiting_join", "completed", "expired", "failed",
                        "cancelled"]


class ProvisioningCreate(Model):
    home_id: int
    kind: SessionKind
    target_device_id: str | None = Field(None, max_length=64, description="required for kind 'reset'")
    device_name: str = Field(min_length=1, max_length=40)
    location: str | None = Field(None, max_length=60)


class Session(Model):
    id: int
    home_id: int
    kind: SessionKind
    target_device_id: str | None
    device_name: str
    location: str | None
    status: SessionStatus
    bound_device_id: str | None
    reset_mode: Literal["lan", "manual"] | None = Field(
        description="reset kind: 'lan' while the server can send the reset, else 'manual' (hold the button)")
    reset_result: str | None = Field(description="the LAN reset outcome: 'ok: …' or 'failed: …'")
    created_at: Timestamp
    expires_at: Timestamp
    completed_at: Timestamp | None


class ProvisioningCreated(Model):
    session: Session
    token: str = Field(description="24-hex one-time token; returned only here, stored as SHA-256")
    pairing_url: str = Field(description="opened on the phone while it is on the device's hotspot")
    wifi_qr: str = Field(description="Wi-Fi QR payload for the 'iFLO device' hotspot")


class ProvisioningStep(Model):
    step: str
    at: Timestamp
    detail: dict[str, Any]


class ProvisioningStatus(Model):
    session: Session
    steps: list[ProvisioningStep] = Field(description="oldest first")
    next_expected_sync: Timestamp | None = Field(description="reset kind: when the target device next checks in")


class ClaimRequest(Model):
    home_id: int
    name: str = Field(min_length=1, max_length=40)
    location: str | None = Field(None, max_length=60)

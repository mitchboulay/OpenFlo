"""Request and response models for first-run setup and the server address (FR-16, AD-9)."""
from __future__ import annotations

from pydantic import Field

from ..services.address_check import CheckName, CheckStatus
from ..services.setup import CheckStep, SetupState, StepState
from .schemas import Model, Timestamp


class SetupSteps(Model):
    auth: StepState = Field(description="basic: an admin exists; oidc: discovery answers")
    server_address: StepState = Field(description="saved, or seeded from OPENFLO_PUBLIC_URL")
    address_check: CheckStep = Field(
        description="the last check of the current address; pending = not run since the address was set")


class SetupStatus(Model):
    setup_state: SetupState
    steps: SetupSteps


class SetupComplete(Model):
    setup_state: SetupState


class AdminCreate(Model):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=1024, description="at least 12 characters (422 WEAK_PASSWORD)")


class ServerAddress(Model):
    server_address: str = Field(min_length=1, max_length=2048, description="scheme://host[:port]")


class AddressCheckItem(Model):
    check: CheckName
    status: CheckStatus
    detail: str = Field(description="what was found and, when not ok, how to fix it")


class AddressCheckResult(Model):
    address: str = Field(description="the address that was checked")
    at: Timestamp
    checks: list[AddressCheckItem]

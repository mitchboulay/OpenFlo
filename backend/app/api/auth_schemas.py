"""Request and response models for authentication, tokens and server info (FR-15, FR-17, AD-10)."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .schemas import Model, Timestamp

AuthModeName = Literal["none", "basic", "oidc", "proxy"]
TokenKindName = Literal["personal", "oidc", "bootstrap"]


class LoginRequest(Model):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=1024)


class OidcExchangeRequest(Model):
    id_token: str = Field(min_length=1, max_length=16384)


class OidcExchangeResult(Model):
    token: str = Field(description="OpenFLO API token; shown once")
    expires_at: Timestamp


class Me(Model):
    actor: str
    auth_mode: AuthModeName
    method: Literal["token", "session", "proxy", "none"] = Field(description="How this request authenticated")


class TokenCreate(Model):
    name: str = Field(min_length=1, max_length=60)
    expires_in_days: int | None = Field(None, ge=1, le=3650, description="null = never expires")


class Token(Model):
    id: int
    name: str
    kind: TokenKindName
    created_at: Timestamp
    expires_at: Timestamp | None
    last_used_at: Timestamp | None
    fingerprint: str = Field(pattern=r"^[0-9a-f]{8}$")


class TokenCreated(Token):
    token: str = Field(description="The plaintext token; shown only in this response")


class ServerAuth(Model):
    mode: AuthModeName
    methods: list[str]
    oidc_issuer: str | None
    oidc_client_id: str | None


class ServerInfo(Model):
    name: str
    version: str
    api_version: str
    instance_id: str
    setup_state: Literal["setup_required", "ready"]
    auth: ServerAuth
    server_address: str | None

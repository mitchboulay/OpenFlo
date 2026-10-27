from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

AuthMode = Literal["none", "basic", "oidc", "proxy"]
AUTH_MODES: frozenset[str] = frozenset({"none", "basic", "oidc", "proxy"})


_DEFAULT_UI_DIST = str(Path(__file__).resolve().parents[2] / "ui" / "dist")


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _auth_mode(value: str) -> AuthMode:
    mode = value.strip().lower()
    if mode not in AUTH_MODES:
        raise ValueError(f"OPENFLO_AUTH_MODE must be one of {sorted(AUTH_MODES)}, got {value!r}")
    return cast(AuthMode, mode)


def _env_list(name: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.environ.get(name, "").split(",") if item.strip())


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


class StartupRefused(RuntimeError):
    """The configuration is unsafe or incomplete (Security NFR); the server must not start."""


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the device-facing emulator.

    Safe defaults: dispensing and schedules are off per device until an operator
    turns them on, OTA is always suppressed, and remote dispense is sent only for
    an operator-queued request.
    """

    db_path: str = field(
        default_factory=lambda: os.environ.get(
            "OPENFLO_BACKEND_DB", "openflo-backend.db"
        )
    )
    firmware_version: str = field(
        default_factory=lambda: os.environ.get(
            "OPENFLO_FIRMWARE_VERSION", "3.0.64"
        )
    )
    emulator_version: str = "0.1.0"
    # none | basic | oidc | proxy (AD-8). API tokens are accepted in every mode.
    auth_mode: AuthMode = field(default_factory=lambda: _auth_mode(os.environ.get("OPENFLO_AUTH_MODE", "basic")))
    # Reachable from the internet: refuses to start in ``none`` mode. compose.yaml defaults it to true.
    public: bool = field(default_factory=lambda: _env_bool("OPENFLO_PUBLIC", False))
    # basic: an admin from env (argon2 PHC hash) takes precedence over one created in first-run setup.
    admin_user: str = field(default_factory=lambda: _env("OPENFLO_ADMIN_USER"))
    admin_password_hash: str = field(default_factory=lambda: _env("OPENFLO_ADMIN_PASSWORD_HASH"))
    oidc_issuer: str = field(default_factory=lambda: _env("OPENFLO_OIDC_ISSUER").rstrip("/"))
    oidc_client_id: str = field(default_factory=lambda: _env("OPENFLO_OIDC_CLIENT_ID"))
    oidc_client_secret: str = field(default_factory=lambda: _env("OPENFLO_OIDC_CLIENT_SECRET"))
    # Empty = any user the IdP (or auth proxy) authenticates.
    oidc_allowed_groups: tuple[str, ...] = field(default_factory=lambda: _env_list("OPENFLO_OIDC_ALLOWED_GROUPS"))
    # proxy: comma-separated CIDRs whose Remote-User/X-authentik-* headers are trusted.
    trusted_proxy_cidr: str = field(default_factory=lambda: _env("OPENFLO_TRUSTED_PROXY_CIDR"))
    # Pre-fills the server address in setup; also the OIDC redirect base until the address is saved.
    public_url: str = field(default_factory=lambda: _env("OPENFLO_PUBLIC_URL").rstrip("/"))
    # Optional bootstrap API token (plaintext, from env); its SHA-256 is seeded into api_tokens at startup.
    api_token: str = field(default_factory=lambda: os.environ.get("OPENFLO_API_TOKEN", ""))
    # Default timezone for new homes (FR-1).
    default_timezone: str = field(default_factory=lambda: os.environ.get("TZ", "") or "UTC")
    # Most `unclaimed` device rows that first contact from unknown IDs may create (FR-5).
    unclaimed_cap: int = field(
        default_factory=lambda: int(os.environ.get("OPENFLO_UNCLAIMED_CAP", "10"))
    )
    # The server may reach devices on its LAN (FR-4): a reset-kind wizard sends the factory reset itself.
    local_device_access: bool = field(default_factory=lambda: _env_bool("OPENFLO_LOCAL_DEVICE_ACCESS", False))
    log_payloads: bool = field(
        default_factory=lambda: _env_bool("OPENFLO_BACKEND_LOG_PAYLOADS", True)
    )
    # Built SPA (ui/dist). Served at / when the directory exists; skipped otherwise.
    ui_dist: str = field(
        default_factory=lambda: os.environ.get("OPENFLO_UI_DIST", _DEFAULT_UI_DIST)
    )
    max_body_bytes: int = field(
        default_factory=lambda: int(
            os.environ.get("OPENFLO_BACKEND_MAX_BODY_BYTES", str(64 * 1024))
        )
    )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()

    @property
    def data_dir(self) -> Path:
        """Where persistent state lives (``/data`` in the image): the database's directory."""
        return Path(self.db_path).resolve().parent

    @property
    def trusted_proxy_networks(self) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
        return tuple(
            ipaddress.ip_network(cidr.strip(), strict=False)
            for cidr in self.trusted_proxy_cidr.split(",")
            if cidr.strip()
        )


def check_startup(settings: Settings) -> None:
    """Raise :class:`StartupRefused` for the configurations the Security NFR forbids."""
    mode = settings.auth_mode
    if mode == "none" and settings.public:
        raise StartupRefused(
            "OPENFLO_AUTH_MODE=none with OPENFLO_PUBLIC=true would let anyone on the internet control your "
            "devices; choose basic, oidc or proxy"
        )
    if mode == "proxy":
        try:
            networks = settings.trusted_proxy_networks
        except ValueError as exc:
            raise StartupRefused(f"OPENFLO_TRUSTED_PROXY_CIDR is invalid: {exc}") from exc
        if not networks:
            raise StartupRefused("OPENFLO_AUTH_MODE=proxy requires OPENFLO_TRUSTED_PROXY_CIDR")
    if mode == "oidc" and not (settings.oidc_issuer and settings.oidc_client_id):
        raise StartupRefused("OPENFLO_AUTH_MODE=oidc requires OPENFLO_OIDC_ISSUER and OPENFLO_OIDC_CLIENT_ID")

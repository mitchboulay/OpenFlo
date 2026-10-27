"""The server address devices are provisioned with (FR-16, AD-9, Critical Constraint 8).

``settings.server_address`` is the only source of ``apiUrl`` and the pairing link. Until it is saved,
``OPENFLO_PUBLIC_URL`` seeds it; once saved, the DB value wins. It is NEVER derived from a request's
``Host`` or ``X-Forwarded-Host``: a device persists it, and a wrong value needs a factory reset.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from urllib.parse import urlsplit

from ..config import Settings
from ..errors import ApiError
from ..repositories import settings as settings_repo

SERVER_ADDRESS = "server_address"
SCHEMES = ("https", "http")
MAX_ADDRESS_LENGTH = 2048


@dataclass(frozen=True, slots=True)
class Address:
    """A parsed ``scheme://host[:port]``."""

    scheme: str
    host: str
    port: int

    @property
    def url(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        default_port = 443 if self.scheme == "https" else 80
        return f"{self.scheme}://{host}" + ("" if self.port == default_port else f":{self.port}")


def parse(raw: str) -> Address:
    """``scheme://host[:port]`` with nothing else (no path, query, fragment or credentials).

    Raises 422 ``ADDRESS_INVALID``.
    """
    try:
        parts = urlsplit(raw.strip())
        port = parts.port
    except ValueError as exc:
        raise _invalid(str(exc)) from exc
    if len(raw) > MAX_ADDRESS_LENGTH or parts.scheme not in SCHEMES or not parts.hostname:
        raise _invalid("use scheme://host[:port], for example https://openflo.example.com")
    if parts.username or parts.password or parts.path not in ("", "/") or parts.query or parts.fragment:
        raise _invalid("the address has no path, query or credentials: scheme://host[:port] only")
    default_port = 443 if parts.scheme == "https" else 80
    return Address(parts.scheme, parts.hostname.lower(), port if port is not None else default_port)


def _invalid(reason: str) -> ApiError:
    return ApiError("ADDRESS_INVALID", f"invalid server address: {reason}", 422)


def saved(conn: sqlite3.Connection) -> str | None:
    value = settings_repo.get_value(conn, SERVER_ADDRESS)
    return value if isinstance(value, str) and value else None


def effective(conn: sqlite3.Connection, settings: Settings) -> str | None:
    """The saved address, else the ``OPENFLO_PUBLIC_URL`` seed (ignored when it is not a valid address)."""
    stored = saved(conn)
    if stored is not None or not settings.public_url:
        return stored
    try:
        return parse(settings.public_url).url
    except ApiError:
        return None


def save(conn: sqlite3.Connection, raw: str, actor: str) -> str:
    """Normalize and store the address; returns the stored ``scheme://host[:port]``."""
    url = parse(raw).url
    settings_repo.put(conn, SERVER_ADDRESS, url, actor)
    return url

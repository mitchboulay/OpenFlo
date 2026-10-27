"""Pure authentication policy (FR-15, AD-8): login rate limit, group allow-lists, proxy trust and CSRF."""
from __future__ import annotations

import ipaddress
import re
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from ..config import Settings
from ..errors import ApiError

ActorMethod = Literal["token", "session", "proxy", "none"]

LOGIN_ATTEMPTS_PER_MINUTE = 5
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_GROUP_SEPARATORS = re.compile(r"[,|]")  # Remote-Groups uses commas, X-authentik-groups uses pipes


@dataclass
class SlidingWindowLimiter:
    """At most ``limit`` attempts per key within any ``window_seconds``; in memory, per process.

    ponytail: one process per instance (see device_gate); move to a DB table if OpenFLO ever runs several.
    """

    limit: int = LOGIN_ATTEMPTS_PER_MINUTE
    window_seconds: float = 60.0
    _hits: dict[str, deque[float]] = field(default_factory=dict)

    def allow(self, key: str, now: float) -> bool:
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window_seconds:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def retry_after(self, key: str, now: float) -> float:
        hits = self._hits.get(key)
        return max(0.0, hits[0] + self.window_seconds - now) if hits else 0.0

    def prune(self, now: float) -> None:
        for key in [k for k, hits in self._hits.items() if not hits or hits[-1] <= now - self.window_seconds]:
            del self._hits[key]


def parse_groups(raw: str | Sequence[str] | None) -> list[str]:
    """Groups from a claim (list) or a proxy header (comma- or pipe-separated string)."""
    if raw is None:
        return []
    items: Iterable[str] = _GROUP_SEPARATORS.split(raw) if isinstance(raw, str) else (str(g) for g in raw)
    return [group.strip() for group in items if group.strip()]


def groups_allowed(allowed: Sequence[str], groups: Sequence[str]) -> bool:
    """An empty allow-list admits everyone; otherwise the user needs at least one listed group."""
    return not allowed or bool(set(allowed) & set(groups))


def proxy_trusted(
    networks: Sequence[ipaddress.IPv4Network | ipaddress.IPv6Network], client_ip: str | None
) -> bool:
    """True when the request's peer (after uvicorn's own ``--proxy-headers``) is inside a trusted CIDR."""
    if not client_ip:
        return False
    try:
        address = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    return any(address in network for network in networks)


def csrf_ok(http_method: str, actor_method: ActorMethod, sec_fetch_site: str | None) -> bool:
    """FR-15: cookie-authenticated (session, proxy) mutations need ``Sec-Fetch-Site: same-origin``.

    Bearer requests skip CSRF (a browser never attaches them cross-site). In ``none`` mode a browser's
    cross-site request is refused too, while header-less clients (curl, scripts) still work.
    """
    if http_method.upper() in SAFE_METHODS or actor_method == "token":
        return True
    if actor_method == "none":
        return sec_fetch_site in (None, "same-origin", "none")
    return sec_fetch_site == "same-origin"


def require_auth_mode(settings: Settings, mode: str) -> None:
    """409 ``WRONG_AUTH_MODE`` unless the server runs in ``mode``."""
    if settings.auth_mode != mode:
        raise ApiError("WRONG_AUTH_MODE", f"this server signs in with {settings.auth_mode!r}, not {mode!r}", 409)


DEFAULT_NEXT = "/"
MAX_NEXT_LENGTH = 2048


def safe_next(raw: object) -> str:
    """A same-origin path to land on after sign-in, else ``/`` (open-redirect guard).

    Only a path starting with a single ``/``: no ``//host`` or ``/\\host`` (browsers read both as another
    origin), no backslashes or control characters anywhere, and so no scheme.
    """
    if not isinstance(raw, str) or not raw.startswith("/") or raw.startswith("//") or len(raw) > MAX_NEXT_LENGTH:
        return DEFAULT_NEXT
    if "\\" in raw or any(ord(char) < 0x20 or ord(char) == 0x7F for char in raw):
        return DEFAULT_NEXT
    return raw

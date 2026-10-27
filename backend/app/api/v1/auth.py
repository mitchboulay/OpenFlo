"""``current_actor`` (AD-8): who is making an ``/api/v1`` request, and whether it passes CSRF (FR-15).

Resolvers run in AD-8 order and the first that returns an actor wins:
1. ``Bearer`` API token; 2. session cookie (basic/oidc); 3. proxy headers from a trusted CIDR (proxy);
4. ``operator:local`` (none). Cookie-authenticated mutations then need ``Sec-Fetch-Site: same-origin``.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request

from ...config import Settings
from ...db import Database
from ...errors import ApiError
from ...services import api_tokens
from ...services.auth_policy import ActorMethod, csrf_ok, groups_allowed, parse_groups, proxy_trusted

LOCAL_ACTOR = "operator:local"
SESSION_ACTOR = "actor"
SESSION_MODE = "mode"
# Remote-* (Authelia, oauth2-proxy, generic) first, then Authentik's outpost names.
PROXY_USER_HEADERS = ("remote-user", "x-authentik-username")
PROXY_EMAIL_HEADERS = ("remote-email", "x-authentik-email")
PROXY_GROUPS_HEADERS = ("remote-groups", "x-authentik-groups")


@dataclass(frozen=True, slots=True)
class Actor:
    name: str
    method: ActorMethod
    token_id: int | None = None


Resolver = Callable[[Request], "Actor | None"]


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _bearer(request: Request) -> Actor | None:
    """A ``Bearer`` API token. A bearer that does not resolve is rejected, never downgraded to another method."""
    scheme, _, value = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer":
        return None
    db: Database = request.app.state.db
    with db.connection() as conn:
        token = api_tokens.authenticate(conn, value.strip()) if value.strip() else None
    if token is None:
        raise ApiError("INVALID_TOKEN", "the API token is invalid, revoked or expired", 401)
    return Actor(token.actor, "token", token.id)


def _session(request: Request) -> Actor | None:
    """A signed session cookie from ``/auth/login`` or the OIDC callback, valid only in the mode that issued it."""
    mode = _settings(request).auth_mode
    session: dict[str, Any] = request.scope.get("session") or {}
    name = session.get(SESSION_ACTOR)
    if mode not in ("basic", "oidc") or session.get(SESSION_MODE) != mode or not isinstance(name, str):
        return None
    return Actor(name, "session")


def _first_header(request: Request, names: tuple[str, ...]) -> str | None:
    return next((request.headers[n].strip() for n in names if request.headers.get(n, "").strip()), None)


def _proxy(request: Request) -> Actor | None:
    """Auth-proxy headers, honored only from ``OPENFLO_TRUSTED_PROXY_CIDR``; from anywhere else they are ignored."""
    settings = _settings(request)
    client_ip = request.client.host if request.client else None
    if settings.auth_mode != "proxy" or not proxy_trusted(settings.trusted_proxy_networks, client_ip):
        return None
    user = _first_header(request, PROXY_USER_HEADERS) or _first_header(request, PROXY_EMAIL_HEADERS)
    if user is None:
        return None
    if not groups_allowed(settings.oidc_allowed_groups, parse_groups(_first_header(request, PROXY_GROUPS_HEADERS))):
        raise ApiError("GROUP_DENIED", "your account is not in a group allowed to use OpenFLO", 403)
    return Actor(f"proxy:{user}", "proxy")


def _local(request: Request) -> Actor | None:
    """``OPENFLO_AUTH_MODE=none``: every request acts as the local operator."""
    return Actor(LOCAL_ACTOR, "none") if _settings(request).auth_mode == "none" else None


RESOLVERS: tuple[Resolver, ...] = (_bearer, _session, _proxy, _local)


def current_actor(request: Request) -> Actor:
    actor = next((a for a in (resolve(request) for resolve in RESOLVERS) if a is not None), None)
    if actor is None:
        raise ApiError("AUTH_REQUIRED", "sign in or send an API token", 401)
    require_csrf(request, actor.method)
    return actor


def require_csrf(request: Request, method: ActorMethod) -> None:
    if not csrf_ok(request.method, method, request.headers.get("sec-fetch-site")):
        raise ApiError("CSRF_REJECTED", "cross-site request refused; use the OpenFLO page or an API token", 403)


def start_session(request: Request, actor_name: str) -> None:
    """Replace the session with a signed-in one (the cookie is re-signed on every response: 12 h idle expiry)."""
    request.session.clear()
    request.session.update({SESSION_ACTOR: actor_name, SESSION_MODE: _settings(request).auth_mode})


ActorDep = Annotated[Actor, Depends(current_actor)]

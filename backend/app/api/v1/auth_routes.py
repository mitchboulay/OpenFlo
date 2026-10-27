"""Unauthenticated ``/api/v1`` routes (FR-15, FR-17): sign-in, sign-out, OIDC, token exchange, server info."""
from __future__ import annotations

import logging
import time
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse

from ...errors import ApiError
from ...services import api_tokens, basic_auth, server_address, server_info
from ...services.auth_policy import SlidingWindowLimiter, require_auth_mode, safe_next
from ...services.oidc import OidcClient
from .. import auth_schemas
from .auth import start_session
from .common import RepoDep, SettingsDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])
OIDC_CALLBACK_PATH = "/api/v1/auth/oidc/callback"
OIDC_NEXT = "oidc_next"
SIGN_IN_PATH = "/sign-in"
SERVER_INFO_CACHE = "public, max-age=60"


def _oidc(request: Request) -> OidcClient:
    client: OidcClient = request.app.state.oidc
    return client


@router.post("/auth/login", status_code=204, response_class=Response)
def login(body: auth_schemas.LoginRequest, request: Request, repo: RepoDep, settings: SettingsDep) -> Response:
    """Basic mode: check the admin password and set the session cookie. 5 attempts per minute per IP."""
    require_auth_mode(settings, "basic")
    limiter: SlidingWindowLimiter = request.app.state.login_limiter
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    limiter.prune(now)
    if not limiter.allow(client_ip, now):
        logger.warning("login rate limit hit from %s", client_ip)
        retry_after = round(limiter.retry_after(client_ip, now))
        raise ApiError("RATE_LIMITED", "too many sign-in attempts; wait a minute", 429,
                       {"retry_after_seconds": retry_after})
    with repo.db.connection() as conn:
        actor = basic_auth.verify_login(conn, settings, body.username, body.password)
    if actor is None:
        logger.info("failed login for %r from %s", body.username, client_ip)
        raise ApiError("INVALID_CREDENTIALS", "wrong username or password", 401)
    start_session(request, actor)
    logger.info("login %s from %s", actor, client_ip)
    return Response(status_code=204)


@router.post("/auth/logout", status_code=204, response_class=Response)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=204)


@router.get("/auth/oidc/login", response_class=RedirectResponse, status_code=302)
async def oidc_login(
    request: Request, repo: RepoDep, settings: SettingsDep,
    next_path: Annotated[str | None, Query(alias="next", description="App path to return to; else `/`")] = None,
) -> RedirectResponse:
    """Redirect to the identity provider (Authorization Code + PKCE). ``next`` rides in the signed session."""
    require_auth_mode(settings, "oidc")
    with repo.db.connection() as conn:
        base = server_address.effective(conn, settings) or str(request.base_url).rstrip("/")
    request.session[OIDC_NEXT] = safe_next(next_path)
    return await _oidc(request).login_redirect(request, base + OIDC_CALLBACK_PATH)


@router.get("/auth/oidc/callback", response_class=RedirectResponse, status_code=302)
async def oidc_callback(request: Request, settings: SettingsDep) -> RedirectResponse:
    """The IdP's redirect back: redeem the code, check groups, set the session cookie, go to ``next``.

    Browser-only: every failure is a 302 to ``/sign-in?error=<code>`` (``OIDC_GROUP_DENIED``, ``OIDC_INVALID``,
    ``IDP_UNAVAILABLE``, ``WRONG_AUTH_MODE``), never JSON."""
    next_path = safe_next(request.session.pop(OIDC_NEXT, None))
    try:
        require_auth_mode(settings, "oidc")
        actor = await _oidc(request).complete_login(request)
    except ApiError as exc:
        logger.info("OIDC callback refused: %s", exc.code)
        return RedirectResponse(f"{SIGN_IN_PATH}?{urlencode({'error': exc.code})}", status_code=302)
    start_session(request, actor)
    logger.info("OIDC login %s", actor)
    return RedirectResponse(next_path, status_code=302)


@router.post("/auth/oidc/exchange", response_model=auth_schemas.OidcExchangeResult)
async def oidc_exchange(
    body: auth_schemas.OidcExchangeRequest, request: Request, repo: RepoDep, settings: SettingsDep
) -> auth_schemas.OidcExchangeResult:
    """Non-browser clients (AD-10): trade an IdP ``id_token`` from their own PKCE flow for an API token."""
    require_auth_mode(settings, "oidc")
    actor = await _oidc(request).exchange(body.id_token)
    with repo.db.connection() as conn:
        issued = api_tokens.issue(conn, "OIDC sign-in", actor, "oidc", api_tokens.OIDC_TOKEN_DAYS)
    assert issued.token.expires_at is not None
    return auth_schemas.OidcExchangeResult(token=issued.plaintext, expires_at=issued.token.expires_at)


@router.get("/server-info", response_model=auth_schemas.ServerInfo)
def get_server_info(response: Response, repo: RepoDep, settings: SettingsDep) -> auth_schemas.ServerInfo:
    """Name, version, setup state and sign-in methods, for clients connecting by address. Cacheable 60 s."""
    response.headers["Cache-Control"] = SERVER_INFO_CACHE
    with repo.db.connection() as conn:
        return auth_schemas.ServerInfo.model_validate(server_info.server_info(conn, settings))

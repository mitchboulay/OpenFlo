"""OIDC sign-in (FR-15, AD-8): Authorization Code + PKCE via ``authlib``, plus the client token exchange (AD-10).

Failure Modes: every IdP call has a 5 s timeout. Discovery and JWKS fetches are retried once after 1 s; the
authorization-code redemption is not (a code is single use). An unreachable IdP is 503 ``IDP_UNAVAILABLE``;
sessions and API tokens keep working. ``id_token``s are never logged.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypeVar

import httpx
from authlib.common.errors import AuthlibBaseError
from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App
from authlib.oidc.core import CodeIDToken
from joserfc.errors import JoseError
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ..config import Settings
from ..errors import ApiError
from .auth_policy import groups_allowed, parse_groups

logger = logging.getLogger(__name__)

IDP_TIMEOUT_S = 5.0
IDP_RETRY_DELAY_S = 1.0
SCOPES = "openid email profile"
DISCOVERY_PATH = "/.well-known/openid-configuration"

T = TypeVar("T")


def _idp_unavailable() -> ApiError:
    return ApiError("IDP_UNAVAILABLE", "the sign-in provider is not responding; try again or use an API token", 503)


def _invalid(reason: str) -> ApiError:
    return ApiError("OIDC_INVALID", f"sign-in with the identity provider failed: {reason}", 401)


class OidcClient:
    """The configured IdP. One instance per app; authlib caches discovery and JWKS after the first success."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: StarletteOAuth2App = OAuth().register(
            "openflo",
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret or None,
            server_metadata_url=settings.oidc_issuer + DISCOVERY_PATH,
            client_kwargs={"scope": SCOPES, "code_challenge_method": "S256", "timeout": IDP_TIMEOUT_S},
        )

    async def discovered(self) -> bool:
        """Whether the IdP's discovery document loads (first-run setup, FR-16 step 1)."""
        try:
            await self._with_retry(self.client.load_server_metadata)
        except ApiError:
            return False
        return True

    async def login_redirect(self, request: Request, redirect_uri: str) -> RedirectResponse:
        """Redirect the browser to the IdP; state, nonce and the PKCE verifier live in the signed session."""
        await self._with_retry(self.client.load_server_metadata)
        response: RedirectResponse = await self.client.authorize_redirect(request, redirect_uri)
        return response

    async def complete_login(self, request: Request) -> str:
        """Redeem the callback's code and return the actor; raises OIDC_INVALID / OIDC_GROUP_DENIED / 503."""
        await self._with_retry(self.client.load_server_metadata)
        await self._with_retry(self.client.fetch_jwk_set)
        token = await self._once(lambda: self.client.authorize_access_token(request))
        claims = token.get("userinfo")
        if not isinstance(claims, Mapping):
            raise _invalid("the provider returned no id_token")
        return self._actor(claims)

    async def exchange(self, id_token: str) -> str:
        """Validate a client-obtained ``id_token`` (signature, issuer, audience, expiry) and return the actor."""
        metadata = await self._with_retry(self.client.load_server_metadata)
        await self._with_retry(self.client.fetch_jwk_set)
        options = {"iss": {"essential": True, "values": [metadata.get("issuer", self.settings.oidc_issuer)]},
                   "aud": {"essential": True, "values": [self.settings.oidc_client_id]}}
        claims = await self._once(
            lambda: self.client.parse_id_token({"id_token": id_token}, nonce=None, claims_options=options,
                                               claims_cls=CodeIDToken)
        )
        return self._actor(claims)

    def _actor(self, claims: Mapping[str, Any]) -> str:
        groups = parse_groups(claims.get("groups"))
        name = claims.get("preferred_username") or claims.get("email") or claims.get("sub")
        if not name:
            raise _invalid("the id_token has no subject")
        if not groups_allowed(self.settings.oidc_allowed_groups, groups):
            logger.warning("OIDC sign-in refused for %s: not in an allowed group", name)
            raise ApiError("OIDC_GROUP_DENIED", "your account is not in a group allowed to use OpenFLO", 403)
        return f"oidc:{name}"

    async def _with_retry(self, call: Callable[[], Awaitable[T]]) -> T:
        try:
            return await call()
        except httpx.HTTPError as exc:
            logger.warning("identity provider call failed (%s); retrying in %.0f s", type(exc).__name__,
                           IDP_RETRY_DELAY_S)
        await asyncio.sleep(IDP_RETRY_DELAY_S)
        return await self._once(call)

    async def _once(self, call: Callable[[], Awaitable[T]]) -> T:
        try:
            return await call()
        except httpx.HTTPError as exc:
            logger.warning("identity provider unavailable: %s", type(exc).__name__)
            raise _idp_unavailable() from exc
        except (AuthlibBaseError, JoseError) as exc:
            logger.info("OIDC validation failed: %s", type(exc).__name__)
            raise _invalid(type(exc).__name__) from exc

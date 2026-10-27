"""API token resolution and the env bootstrap token (AD-8, AD-10). Only SHA-256 digests are stored."""
from __future__ import annotations

import hashlib
import logging
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..errors import ApiError
from ..repositories import tokens
from ..repositories.tokens import ApiToken, TokenKind

logger = logging.getLogger(__name__)

BOOTSTRAP_NAME = "bootstrap (OPENFLO_API_TOKEN)"
BOOTSTRAP_ACTOR = "bootstrap"
TOKEN_PREFIX = "ofl_"
OIDC_TOKEN_DAYS = 90


@dataclass(frozen=True, slots=True)
class IssuedToken:
    """A freshly created token; ``plaintext`` is returned to the caller once and never stored or logged."""

    token: ApiToken
    plaintext: str


def digest(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def seed_bootstrap(conn: sqlite3.Connection, plaintext: str) -> ApiToken | None:
    """Make ``OPENFLO_API_TOKEN`` the only active bootstrap token; unset revokes any previous one."""
    wanted = digest(plaintext) if plaintext else None
    revoked = tokens.revoke_kind_except(conn, "bootstrap", wanted)
    if revoked:
        logger.info("revoked %d stale bootstrap token(s)", revoked)
    if wanted is None:
        return None
    current = tokens.get_active_by_hash(conn, wanted)
    if current is not None:
        return current
    token = tokens.create(conn, wanted, BOOTSTRAP_NAME, BOOTSTRAP_ACTOR, "bootstrap")
    logger.info("seeded bootstrap API token fingerprint=%s", token.fingerprint)
    return token


def authenticate(conn: sqlite3.Connection, plaintext: str) -> ApiToken | None:
    """The active token for a bearer value, with ``last_used_at`` stamped; None when unknown/revoked/expired."""
    token = tokens.get_active_by_hash(conn, digest(plaintext))
    if token is not None:
        tokens.touch(conn, token.id)
    return token


def issue(
    conn: sqlite3.Connection, name: str, actor: str, kind: TokenKind, expires_in_days: int | None = None
) -> IssuedToken:
    """Create a random token (personal, or ``oidc`` from the exchange); only its SHA-256 is stored."""
    plaintext = TOKEN_PREFIX + secrets.token_urlsafe(32)
    expires_at = (
        (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat()
        if expires_in_days is not None
        else None
    )
    token = tokens.create(conn, digest(plaintext), name, actor, kind, expires_at)
    logger.info("issued %s API token id=%d fingerprint=%s for %s", kind, token.id, token.fingerprint, actor)
    return IssuedToken(token, plaintext)


def revoke(conn: sqlite3.Connection, token_id: int, actor: str) -> None:
    """Revoke a token; 404 ``TOKEN_NOT_FOUND`` when it does not exist or is already revoked."""
    if not tokens.revoke(conn, token_id):
        raise ApiError("TOKEN_NOT_FOUND", f"no active API token {token_id}", 404)
    logger.info("API token id=%d revoked by %s", token_id, actor)

"""Personal API tokens (FR-15, AD-10) and ``/me``. The plaintext is returned once; only SHA-256 is stored."""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Response

from ...repositories import tokens as tokens_repo
from ...repositories.tokens import ApiToken
from ...services import api_tokens
from .. import auth_schemas
from .auth import ActorDep
from .common import DEFAULT_LIMIT, Limit, RepoDep, SettingsDep

router = APIRouter(tags=["auth"])


def _token(token: ApiToken) -> auth_schemas.Token:
    return auth_schemas.Token(
        id=token.id, name=token.name, kind=cast(auth_schemas.TokenKindName, token.kind),
        created_at=token.created_at, expires_at=token.expires_at, last_used_at=token.last_used_at,
        fingerprint=token.fingerprint,
    )


@router.get("/me", response_model=auth_schemas.Me)
def me(actor: ActorDep, settings: SettingsDep) -> auth_schemas.Me:
    return auth_schemas.Me(actor=actor.name, auth_mode=settings.auth_mode, method=actor.method)


@router.get("/tokens", response_model=list[auth_schemas.Token])
def list_tokens(repo: RepoDep, limit: Limit = DEFAULT_LIMIT, before_id: int | None = None) -> list[auth_schemas.Token]:
    """Unrevoked tokens (personal, OIDC and bootstrap), newest first."""
    with repo.db.connection() as conn:
        return [_token(t) for t in tokens_repo.list_unrevoked(conn, limit=limit, before_id=before_id)]


@router.post("/tokens", response_model=auth_schemas.TokenCreated, status_code=201)
def create_token(body: auth_schemas.TokenCreate, repo: RepoDep, actor: ActorDep) -> auth_schemas.TokenCreated:
    with repo.db.connection() as conn:
        issued = api_tokens.issue(conn, body.name, actor.name, "personal", body.expires_in_days)
    return auth_schemas.TokenCreated(**_token(issued.token).model_dump(), token=issued.plaintext)


@router.delete("/tokens/{token_id}", status_code=204, response_class=Response)
def revoke_token(token_id: int, repo: RepoDep, actor: ActorDep) -> Response:
    with repo.db.connection() as conn:
        api_tokens.revoke(conn, token_id, actor.name)
    return Response(status_code=204)

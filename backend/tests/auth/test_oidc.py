"""OIDC mode (FR-15, AD-10) against a stub issuer served by respx: discovery, PKCE callback, groups, exchange."""
from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from joserfc import jwt
from joserfc.jwk import RSAKey

from app.services import oidc

from .conftest import API, SAME_ORIGIN, auth_client

ISSUER = "https://idp.test/application/o/openflo"
CLIENT_ID = "openflo-client"
KID = "test-key"


@dataclass
class StubIssuer:
    """The IdP: discovery, JWKS and a token endpoint that mints an id_token for the last authorize request."""

    router: respx.MockRouter
    key: RSAKey = field(default_factory=lambda: RSAKey.generate_key(2048, parameters={"kid": KID}))
    groups: list[str] = field(default_factory=lambda: ["openflo-admins"])
    nonce: str | None = None
    token_requests: list[dict[str, list[str]]] = field(default_factory=list)

    def id_token(self, **overrides: Any) -> str:
        now = int(time.time())
        claims = {"iss": ISSUER, "sub": "u-1", "aud": CLIENT_ID, "iat": now, "exp": now + 300,
                  "preferred_username": "alice", "groups": self.groups}
        if self.nonce:
            claims["nonce"] = self.nonce
        claims.update(overrides)
        return jwt.encode({"alg": "RS256", "kid": KID}, claims, self.key)

    def install(self) -> None:
        self.router.get(f"{ISSUER}/.well-known/openid-configuration").respond(json={
            "issuer": ISSUER, "authorization_endpoint": f"{ISSUER}/authorize", "token_endpoint": f"{ISSUER}/token",
            "jwks_uri": f"{ISSUER}/jwks", "id_token_signing_alg_values_supported": ["RS256"],
        })
        self.router.get(f"{ISSUER}/jwks").respond(json={"keys": [self.key.as_dict(private=False)]})
        self.router.post(f"{ISSUER}/token").mock(side_effect=self._token)

    def _token(self, request: httpx.Request) -> httpx.Response:
        self.token_requests.append(parse_qs(request.content.decode()))
        return httpx.Response(200, json={"access_token": "at", "token_type": "Bearer", "id_token": self.id_token()})


@pytest.fixture
def idp(monkeypatch: pytest.MonkeyPatch) -> Iterator[StubIssuer]:
    monkeypatch.setattr(oidc, "IDP_RETRY_DELAY_S", 0.0)
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        stub = StubIssuer(router)
        stub.install()
        yield stub


def oidc_settings(**overrides: Any) -> dict[str, Any]:
    return {"auth_mode": "oidc", "oidc_issuer": ISSUER, "oidc_client_id": CLIENT_ID,
            "oidc_client_secret": "client-secret", "public_url": "https://openflo.test", **overrides}


def _sign_in(client: Any, idp: StubIssuer, next_path: str | None = None) -> Any:
    params = {"next": next_path} if next_path is not None else None
    redirect = client.get(f"{API}/auth/oidc/login", params=params, follow_redirects=False)
    assert redirect.status_code == 302
    query = {k: v[0] for k, v in parse_qs(urlsplit(redirect.headers["location"]).query).items()}
    idp.nonce = query["nonce"]
    return query, client.get(f"{API}/auth/oidc/callback", params={"code": "c0de", "state": query["state"]},
                             follow_redirects=False)


def test_discovery_pkce_and_callback(tmp_path: Any, idp: StubIssuer) -> None:
    with auth_client(tmp_path, **oidc_settings()) as (client, _):
        query, callback = _sign_in(client, idp)
        assert query["redirect_uri"] == "https://openflo.test/api/v1/auth/oidc/callback"
        assert query["code_challenge_method"] == "S256" and query["code_challenge"]
        assert query["client_id"] == CLIENT_ID and "openid" in query["scope"]
        assert callback.status_code == 302 and callback.headers["location"] == "/"
        assert idp.token_requests[0]["code_verifier"][0]  # PKCE verifier redeemed with the code
        assert client.get(f"{API}/me").json() == {"actor": "oidc:alice", "auth_mode": "oidc", "method": "session"}
        assert client.post(f"{API}/homes", json={"name": "Cabin"}, headers=SAME_ORIGIN).status_code == 201


def test_callback_rejects_a_forged_state(tmp_path: Any, idp: StubIssuer) -> None:
    with auth_client(tmp_path, **oidc_settings()) as (client, _):
        client.get(f"{API}/auth/oidc/login", follow_redirects=False)
        response = client.get(f"{API}/auth/oidc/callback", params={"code": "c0de", "state": "forged"},
                              follow_redirects=False)
        assert response.status_code == 302 and response.headers["location"] == "/sign-in?error=OIDC_INVALID"
        assert client.get(f"{API}/me").status_code == 401


def test_callback_redirects_an_idp_error_to_sign_in(tmp_path: Any, idp: StubIssuer) -> None:
    with auth_client(tmp_path, **oidc_settings()) as (client, _):
        client.get(f"{API}/auth/oidc/login", params={"next": "/settings"}, follow_redirects=False)
        response = client.get(f"{API}/auth/oidc/callback", params={"error": "access_denied"}, follow_redirects=False)
        assert response.status_code == 302 and response.headers["location"] == "/sign-in?error=OIDC_INVALID"


def test_callback_returns_to_next(tmp_path: Any, idp: StubIssuer) -> None:
    with auth_client(tmp_path, **oidc_settings()) as (client, _):
        _, callback = _sign_in(client, idp, "/devices/7?tab=history")
        assert callback.status_code == 302 and callback.headers["location"] == "/devices/7?tab=history"
        assert client.get(f"{API}/me").json()["actor"] == "oidc:alice"


@pytest.mark.parametrize("unsafe", [
    "//evil.test/", "/\\evil.test", "https://evil.test/", "javascript:alert(1)", "evil.test", "/a\\b",
    "/x\r\nSet-Cookie: a=b", "",
])
def test_callback_ignores_an_unsafe_next(tmp_path: Any, idp: StubIssuer, unsafe: str) -> None:
    with auth_client(tmp_path, **oidc_settings()) as (client, _):
        _, callback = _sign_in(client, idp, unsafe)
        assert callback.status_code == 302 and callback.headers["location"] == "/"


def test_allowed_groups(tmp_path: Any, idp: StubIssuer) -> None:
    with auth_client(tmp_path, **oidc_settings(oidc_allowed_groups=("openflo-admins",))) as (client, _):
        idp.groups = ["staff"]
        _, denied = _sign_in(client, idp)
        assert denied.status_code == 302 and denied.headers["location"] == "/sign-in?error=OIDC_GROUP_DENIED"
        assert client.get(f"{API}/me").status_code == 401
        idp.groups = ["staff", "openflo-admins"]
        _, allowed = _sign_in(client, idp)
        assert allowed.status_code == 302 and client.get(f"{API}/me").status_code == 200


def test_exchange_issues_an_api_token(tmp_path: Any, idp: StubIssuer) -> None:
    with auth_client(tmp_path, **oidc_settings()) as (client, _):
        response = client.post(f"{API}/auth/oidc/exchange", json={"id_token": idp.id_token()})
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"token", "expires_at"} and body["token"].startswith("ofl_")
        me = client.get(f"{API}/me", headers={"Authorization": f"Bearer {body['token']}"}).json()
        assert me == {"actor": "oidc:alice", "auth_mode": "oidc", "method": "token"}
        kinds = [t["kind"] for t in client.get(f"{API}/tokens", headers={"Authorization": f"Bearer {body['token']}"}).json()]
        assert kinds == ["oidc"]


@pytest.mark.parametrize("claims", [
    {"aud": "another-client"},
    {"iss": "https://evil.test"},
    {"exp": 1_000_000_000, "iat": 999_999_000},
])
def test_exchange_rejects_invalid_id_tokens(tmp_path: Any, idp: StubIssuer, claims: dict[str, Any]) -> None:
    with auth_client(tmp_path, **oidc_settings()) as (client, _):
        response = client.post(f"{API}/auth/oidc/exchange", json={"id_token": idp.id_token(**claims)})
        assert response.status_code == 401 and response.json()["code"] == "OIDC_INVALID"


def test_exchange_rejects_garbage_and_foreign_signatures(tmp_path: Any, idp: StubIssuer) -> None:
    foreign = StubIssuer(idp.router).id_token()  # same kid, different key
    with auth_client(tmp_path, **oidc_settings()) as (client, _):
        for token in ("not-a-jwt", foreign):
            response = client.post(f"{API}/auth/oidc/exchange", json={"id_token": token})
            assert response.status_code == 401 and response.json()["code"] == "OIDC_INVALID"


def test_exchange_enforces_groups(tmp_path: Any, idp: StubIssuer) -> None:
    with auth_client(tmp_path, **oidc_settings(oidc_allowed_groups=("ops",))) as (client, _):
        response = client.post(f"{API}/auth/oidc/exchange", json={"id_token": idp.id_token()})
        assert response.status_code == 403 and response.json()["code"] == "OIDC_GROUP_DENIED"


def test_unreachable_issuer_is_503_after_one_retry(tmp_path: Any, idp: StubIssuer) -> None:
    discovery = idp.router.get(f"{ISSUER}/.well-known/openid-configuration").mock(
        side_effect=httpx.ConnectTimeout("timed out"))
    with auth_client(tmp_path, **oidc_settings()) as (client, _):
        response = client.get(f"{API}/auth/oidc/login", follow_redirects=False)
        assert response.status_code == 503 and response.json()["code"] == "IDP_UNAVAILABLE"
        assert discovery.call_count == 2


def test_server_info_advertises_the_issuer(tmp_path: Any, idp: StubIssuer) -> None:
    with auth_client(tmp_path, **oidc_settings()) as (client, _):
        auth = client.get(f"{API}/server-info").json()["auth"]
        assert auth == {"mode": "oidc", "methods": ["oidc", "token"], "oidc_issuer": ISSUER,
                        "oidc_client_id": CLIENT_ID}


def test_id_tokens_and_api_tokens_never_reach_the_logs(
    tmp_path: Any, idp: StubIssuer, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    with auth_client(tmp_path, **oidc_settings()) as (client, _):
        _sign_in(client, idp)
        id_token = idp.id_token()
        issued = client.post(f"{API}/auth/oidc/exchange", json={"id_token": id_token}).json()["token"]
        client.get(f"{API}/me", headers={"Authorization": f"Bearer {issued}"})
    logged = caplog.text
    assert caplog.records  # the flow did log
    for secret in (id_token, id_token.split(".")[1], issued, "client-secret"):
        assert secret not in logged
    # The test client logs its own request URLs; OpenFLO must not log the authorization code.
    assert not any("c0de" in record.getMessage() for record in caplog.records if record.name.startswith("app"))

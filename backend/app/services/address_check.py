"""The server-address check (AD-9): can an iFLO 3.0.64 device reach this instance at the saved address?

The browser cannot reproduce the device's TLS view, so the server checks its own address the way the
firmware connects: no SNI, TLS 1.2 only, an RSA leaf, and a chain to a root in the firmware's CA bundle.
Six independent checks run concurrently, each with its own 5 s timeout; a slow or failing check never
blocks the others. The last result is stored in ``settings.address_check``.

The address always comes from ``server_address.effective`` (Critical Constraint 8), never a request Host.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import socket
import sqlite3
import ssl
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import cache
from pathlib import Path
from typing import Any, Literal

import httpx
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa

from ..config import Settings
from ..db import Database
from ..device_gate import INSTANCE_HEADER
from ..repositories import settings as settings_repo
from . import server_address
from .server_address import Address

logger = logging.getLogger(__name__)

CheckName = Literal["dns", "tls_no_sni", "chain_firmware_bundle", "leaf_rsa", "healthcheck_reachable",
                    "port_non_443"]
CheckStatus = Literal["ok", "warn", "fail"]
IpNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network

ADDRESS_CHECK = "address_check"
CHECK_TIMEOUT_S = 5.0
MIN_RSA_BITS = 2048
HEALTHCHECK_PATH = "/device-api/v2/healthcheck"
APP_DIR = Path(__file__).resolve().parents[1]
FIRMWARE_CA_BUNDLE = APP_DIR / "firmware_ca_bundle.pem"
CLOUDFLARE_RANGES = APP_DIR / "cloudflare_ranges.json"


@dataclass(frozen=True, slots=True)
class CheckResult:
    check: CheckName
    status: CheckStatus
    detail: str


@dataclass(frozen=True, slots=True)
class AddressCheck:
    address: str
    at: str
    checks: list[CheckResult]

    @property
    def failed(self) -> bool:
        return any(result.status == "fail" for result in self.checks)


@dataclass(frozen=True)
class CheckTarget:
    """What to check and against what. Tests inject their own bundle and ranges."""

    address: Address
    instance_id: str
    ca_bundle: Path = FIRMWARE_CA_BUNDLE
    cloudflare: Sequence[IpNetwork] = field(default_factory=lambda: cloudflare_networks())
    timeout: float = CHECK_TIMEOUT_S


@cache
def cloudflare_networks(path: Path = CLOUDFLARE_RANGES) -> tuple[IpNetwork, ...]:
    ranges = json.loads(path.read_text())
    return tuple(ipaddress.ip_network(cidr) for cidr in ranges["ipv4"] + ranges["ipv6"])


def _ok(check: CheckName, detail: str) -> CheckResult:
    return CheckResult(check, "ok", detail)


def _warn(check: CheckName, detail: str) -> CheckResult:
    return CheckResult(check, "warn", detail)


def _fail(check: CheckName, detail: str) -> CheckResult:
    return CheckResult(check, "fail", detail)


async def check_dns(target: CheckTarget) -> CheckResult:
    host = target.address.host
    unresolved = _fail("dns", f"{host} does not resolve; create a DNS record pointing at this server")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, target.address.port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return unresolved
    ips = sorted({ipaddress.ip_address(str(info[4][0]).split("%")[0]) for info in infos}, key=str)
    if not ips:
        return unresolved
    if any(ip in net for ip in ips for net in target.cloudflare):
        return _warn("dns", f"{host} resolves to Cloudflare ({', '.join(map(str, ips))}): devices cannot connect "
                            "through Cloudflare's proxy. Set the record to 'DNS only' (grey cloud)")
    return _ok("dns", f"{host} resolves to {', '.join(map(str, ips))}")


def _device_context(ca_bundle: Path | None) -> ssl.SSLContext:
    """A client that connects the way the firmware does: TLS 1.2 only, and (by the caller) without SNI."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = False  # no SNI means no hostname to verify here; checked separately below
    if ca_bundle is None:
        context.verify_mode = ssl.CERT_NONE
    else:
        context.load_verify_locations(cafile=str(ca_bundle))
    return context


@dataclass(frozen=True, slots=True)
class Handshake:
    leaf_der: bytes
    peer: dict[str, Any]  # getpeercert(): populated only when the chain was verified


async def _handshake(target: CheckTarget, context: ssl.SSLContext) -> Handshake:
    # server_hostname="" disables SNI (asyncio passes None to OpenSSL), like the firmware's ClientHello.
    _, writer = await asyncio.open_connection(target.address.host, target.address.port, ssl=context,
                                              server_hostname="")
    try:
        ssl_object: ssl.SSLObject = writer.get_extra_info("ssl_object")
        return Handshake(ssl_object.getpeercert(binary_form=True) or b"", ssl_object.getpeercert() or {})
    finally:
        writer.close()


# A server that refuses the handshake either sends a TLS alert or resets the connection.
HANDSHAKE_ERRORS = (ssl.SSLError, ConnectionResetError)


def _reason(exc: OSError) -> str:
    return getattr(exc, "reason", None) or type(exc).__name__


def _https_only(check: CheckName, target: CheckTarget) -> CheckResult | None:
    if target.address.scheme == "https":
        return None
    return _fail(check, "the address uses http://; devices need https:// with a certificate")


async def check_tls_no_sni(target: CheckTarget) -> CheckResult:
    if (refused := _https_only("tls_no_sni", target)) is not None:
        return refused
    try:
        await _handshake(target, _device_context(None))
    except HANDSHAKE_ERRORS as exc:
        return _fail("tls_no_sni", f"a TLS 1.2 handshake without SNI failed ({_reason(exc)}). Serve a default "
                                   "certificate for SNI-less clients (Caddy: default_sni) and allow TLS 1.2")
    return _ok("tls_no_sni", "TLS 1.2 without SNI succeeds")


async def check_chain_firmware_bundle(target: CheckTarget) -> CheckResult:
    if (refused := _https_only("chain_firmware_bundle", target)) is not None:
        return refused
    try:
        handshake = await _handshake(target, _device_context(target.ca_bundle))
    except ssl.SSLCertVerificationError as exc:
        return _fail("chain_firmware_bundle", f"the certificate chain does not end at a root the device trusts "
                                              f"({exc.verify_message}). Use Let's Encrypt with the ISRG Root X1 chain")
    except HANDSHAKE_ERRORS as exc:
        return _fail("chain_firmware_bundle", f"TLS handshake failed ({_reason(exc)})")
    if not hostname_matches(handshake.peer, target.address.host):
        return _fail("chain_firmware_bundle", f"the certificate served without SNI is not valid for "
                                              f"{target.address.host}; make it the default certificate")
    return _ok("chain_firmware_bundle", "the chain ends at a root in the device's CA bundle")


def hostname_matches(peer: dict[str, Any], host: str) -> bool:
    """RFC 6125 matching on subjectAltName (DNS, IP); a wildcard covers exactly one leftmost label."""
    host = host.lower().rstrip(".")
    for kind, value in peer.get("subjectAltName", ()):
        name = str(value).lower().rstrip(".")
        if kind == "IP Address" and _same_ip(name, host):
            return True
        if kind == "DNS" and (name == host or (name.startswith("*.") and host.count(".") == name.count(".")
                                               and host.split(".", 1)[1] == name[2:])):
            return True
    return False


def _same_ip(a: str, b: str) -> bool:
    try:
        return ipaddress.ip_address(a) == ipaddress.ip_address(b)
    except ValueError:
        return False


async def check_leaf_rsa(target: CheckTarget) -> CheckResult:
    if (refused := _https_only("leaf_rsa", target)) is not None:
        return refused
    try:
        handshake = await _handshake(target, _device_context(None))
    except HANDSHAKE_ERRORS as exc:
        return _fail("leaf_rsa", f"TLS handshake failed ({_reason(exc)})")
    key = x509.load_der_x509_certificate(handshake.leaf_der).public_key()
    if not isinstance(key, rsa.RSAPublicKey):
        return _fail("leaf_rsa", f"the certificate key is {type(key).__name__.removesuffix('PublicKey')}; the "
                                 "device needs RSA (Caddy: key_type rsa2048)")
    if key.key_size < MIN_RSA_BITS:
        return _fail("leaf_rsa", f"the RSA key is {key.key_size} bits; use at least {MIN_RSA_BITS}")
    return _ok("leaf_rsa", f"RSA-{key.key_size} certificate")


async def check_healthcheck_reachable(target: CheckTarget) -> CheckResult:
    url = target.address.url + HEALTHCHECK_PATH
    # verify=False: this check is about routing and identity; the TLS checks above judge the certificate.
    async with httpx.AsyncClient(verify=False, timeout=target.timeout, follow_redirects=False) as client:
        response = await client.post(url, json={})
    instance = response.headers.get(INSTANCE_HEADER)
    if instance != target.instance_id:
        seen = "no OpenFLO instance header" if instance is None else "a different OpenFLO instance"
        return _fail("healthcheck_reachable", f"{url} answered HTTP {response.status_code} with {seen}; point the "
                                              "address (DNS, port forward, proxy) at this server")
    if "cf-ray" in response.headers:
        return _warn("healthcheck_reachable", "reached through Cloudflare's proxy; devices cannot use that path. "
                                              "Set the DNS record to 'DNS only' and use no Cloudflare Tunnel")
    return _ok("healthcheck_reachable", "this OpenFLO instance answers the device healthcheck")


async def check_port_non_443(target: CheckTarget) -> CheckResult:
    if target.address.port == 443:
        return _ok("port_non_443", "standard port 443")
    # ponytail: warning until T0.1 verifies a non-443 device port on real hardware; then return ok.
    return _warn("port_non_443", f"port {target.address.port} is not yet verified with the device; 443 is")


CHECKS: tuple[tuple[CheckName, Callable[[CheckTarget], Awaitable[CheckResult]]], ...] = (
    ("dns", check_dns),
    ("tls_no_sni", check_tls_no_sni),
    ("chain_firmware_bundle", check_chain_firmware_bundle),
    ("leaf_rsa", check_leaf_rsa),
    ("healthcheck_reachable", check_healthcheck_reachable),
    ("port_non_443", check_port_non_443),
)


async def _guarded(name: CheckName, check: Callable[[CheckTarget], Awaitable[CheckResult]],
                   target: CheckTarget) -> CheckResult:
    """Run one check under its own timeout. Network errors become that check's ``fail``, never the run's."""
    try:
        return await asyncio.wait_for(check(target), target.timeout)
    except asyncio.TimeoutError:  # the builtin TimeoutError only from Python 3.11
        return _fail(name, "timeout")
    except (OSError, httpx.HTTPError, ValueError) as exc:
        logger.info("address check %s failed: %s", name, type(exc).__name__)
        return _fail(name, f"could not connect: {exc}")


async def run(target: CheckTarget) -> AddressCheck:
    results = await asyncio.gather(*(_guarded(name, check, target) for name, check in CHECKS))
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return AddressCheck(target.address.url, at, list(results))


async def check_and_store(db: Database, settings: Settings, actor: str) -> AddressCheck | None:
    """Check the effective server address and store the result; None when no address is set."""
    with db.connection() as conn:
        address = server_address.effective(conn, settings)
        instance_id = settings_repo.instance_id(conn)
    if address is None:
        return None
    result = await run(CheckTarget(server_address.parse(address), instance_id))
    with db.connection() as conn:
        settings_repo.put(conn, ADDRESS_CHECK, asdict(result), actor, at=result.at)
    logger.info("address check of %s by %s: %s", result.address, actor,
                ", ".join(f"{c.check}={c.status}" for c in result.checks))
    return result


def last(conn: sqlite3.Connection) -> AddressCheck | None:
    value = settings_repo.get_value(conn, ADDRESS_CHECK)
    if not isinstance(value, dict):
        return None
    return AddressCheck(value["address"], value["at"], [CheckResult(**c) for c in value["checks"]])

"""The six address checks (AD-9) against local TLS servers that play the operator's reverse proxy."""
from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
import ssl
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID

from app.services import address_check, nightly
from app.services.address_check import AddressCheck, CheckTarget
from app.services.server_address import parse

INSTANCE = "11111111-2222-3333-4444-555555555555"
REPO = Path(__file__).resolve().parents[2]
NO_CLOUDFLARE: tuple[ipaddress.IPv4Network, ...] = ()

PrivateKey = rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _cert(subject: str, key: PrivateKey, issuer: str, issuer_key: PrivateKey, ca: bool) -> x509.Certificate:
    now = datetime.now(timezone.utc)
    builder = (
        x509.CertificateBuilder().subject_name(_name(subject)).issuer_name(_name(issuer))
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
    )
    if not ca:
        san = x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))])
        builder = builder.add_extension(san, critical=False)
    return builder.sign(issuer_key, hashes.SHA256())


@dataclass(frozen=True)
class Pki:
    bundle: Path  # the test root, injected as the "firmware bundle"
    rsa_chain: tuple[Path, Path]  # (cert chain, key)
    ecdsa_chain: tuple[Path, Path]


def _write_chain(tmp: Path, name: str, leaf: x509.Certificate, key: PrivateKey) -> tuple[Path, Path]:
    cert_path, key_path = tmp / f"{name}.pem", tmp / f"{name}.key"
    cert_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    return cert_path, key_path


@pytest.fixture(scope="module")
def pki(tmp_path_factory: pytest.TempPathFactory) -> Pki:
    tmp = tmp_path_factory.mktemp("pki")
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root = _cert("Test Root", root_key, "Test Root", root_key, ca=True)
    (tmp / "root.pem").write_bytes(root.public_bytes(serialization.Encoding.PEM))
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ec_key = ec.generate_private_key(ec.SECP256R1())
    return Pki(
        bundle=tmp / "root.pem",
        rsa_chain=_write_chain(tmp, "rsa", _cert("127.0.0.1", rsa_key, "Test Root", root_key, False), rsa_key),
        ecdsa_chain=_write_chain(tmp, "ecdsa", _cert("127.0.0.1", ec_key, "Test Root", root_key, False), ec_key),
    )


def _server_context(chain: tuple[Path, Path], sni_required: bool) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(*map(str, chain))
    if sni_required:  # a proxy with no default certificate: refuses ClientHellos without SNI
        context.sni_callback = lambda _obj, name, _ctx: None if name else ssl.ALERT_DESCRIPTION_UNRECOGNIZED_NAME
    return context


@asynccontextmanager
async def tls_server(chain: tuple[Path, Path], headers: dict[str, str] | None = None,
                     sni_required: bool = False) -> AsyncIterator[int]:
    """An HTTPS server on 127.0.0.1 answering every request with ``headers``; yields its port."""
    reply_headers = {address_check.INSTANCE_HEADER: INSTANCE, **(headers or {})}
    reply = "HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n" + "".join(
        f"{k}: {v}\r\n" for k, v in reply_headers.items()) + "\r\n{}"

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await reader.readuntil(b"\r\n\r\n")
            writer.write(reply.encode())
            await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError, ssl.SSLError):
            pass  # handshake-only clients hang up without a request
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0, ssl=_server_context(chain, sni_required))
    async with server:
        yield server.sockets[0].getsockname()[1]


def _target(port: int, bundle: Path, cloudflare: Any = NO_CLOUDFLARE, timeout: float = 5.0) -> CheckTarget:
    return CheckTarget(parse(f"https://127.0.0.1:{port}"), INSTANCE, bundle, cloudflare, timeout)


def check_against(chain: tuple[Path, Path], bundle: Path, headers: dict[str, str] | None = None,
                  sni_required: bool = False, cloudflare: Any = NO_CLOUDFLARE) -> dict[str, tuple[str, str]]:
    async def go() -> AddressCheck:
        async with tls_server(chain, headers, sni_required) as port:
            return await address_check.run(_target(port, bundle, cloudflare))

    return {c.check: (c.status, c.detail) for c in asyncio.run(go()).checks}


def statuses(results: dict[str, tuple[str, str]]) -> dict[str, str]:
    return {name: status for name, (status, _) in results.items()}


def test_rsa_leaf_chaining_to_the_bundle_is_ok(pki: Pki) -> None:
    assert statuses(check_against(pki.rsa_chain, pki.bundle)) == {
        "dns": "ok", "tls_no_sni": "ok", "chain_firmware_bundle": "ok", "leaf_rsa": "ok",
        "healthcheck_reachable": "ok", "port_non_443": "warn",  # until T0.1 verifies non-443 ports
    }


def test_ecdsa_leaf_fails_leaf_rsa(pki: Pki) -> None:
    results = check_against(pki.ecdsa_chain, pki.bundle)
    assert results["leaf_rsa"][0] == "fail" and "RSA" in results["leaf_rsa"][1]
    assert results["chain_firmware_bundle"][0] == "ok"


def test_sni_required_server_fails_tls_no_sni(pki: Pki) -> None:
    results = check_against(pki.rsa_chain, pki.bundle, sni_required=True)
    assert results["tls_no_sni"][0] == "fail" and "SNI" in results["tls_no_sni"][1]


def test_root_outside_the_firmware_bundle_fails_the_chain(pki: Pki) -> None:
    results = check_against(pki.rsa_chain, address_check.FIRMWARE_CA_BUNDLE)
    assert results["chain_firmware_bundle"][0] == "fail"
    assert results["tls_no_sni"][0] == "ok"


def test_cf_ray_header_warns(pki: Pki) -> None:
    results = check_against(pki.rsa_chain, pki.bundle, headers={"cf-ray": "8f00000000000000-SJC"})
    assert results["healthcheck_reachable"][0] == "warn" and "Cloudflare" in results["healthcheck_reachable"][1]


def test_wrong_instance_fails(pki: Pki) -> None:
    results = check_against(pki.rsa_chain, pki.bundle, headers={address_check.INSTANCE_HEADER: "someone-else"})
    assert results["healthcheck_reachable"][0] == "fail"
    assert "different OpenFLO instance" in results["healthcheck_reachable"][1]


def test_dns_resolving_to_cloudflare_warns(pki: Pki) -> None:
    results = check_against(pki.rsa_chain, pki.bundle, cloudflare=[ipaddress.ip_network("127.0.0.0/8")])
    assert results["dns"][0] == "warn" and "DNS only" in results["dns"][1]


def test_unresolvable_name_fails_dns_as_does_not_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_such_name(self: object, host: str, *args: object, **kwargs: object) -> list[object]:
        raise socket.gaierror(socket.EAI_NONAME, "nodename nor servname provided, or not known")

    monkeypatch.setattr(asyncio.BaseEventLoop, "getaddrinfo", no_such_name)
    target = CheckTarget(parse("https://openflo.example.invalid"), INSTANCE, Path("unused"), NO_CLOUDFLARE, 1.0)
    result = asyncio.run(address_check.check_dns(target))
    assert result.status == "fail"
    assert result.detail.startswith("openflo.example.invalid does not resolve")


def test_a_stalled_server_times_out_each_check_independently(pki: Pki) -> None:
    async def go() -> AddressCheck:
        async def stall(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await asyncio.sleep(1.0)  # accepts TCP, never answers the ClientHello (checks time out at 0.3 s)
            writer.close()

        server = await asyncio.start_server(stall, "127.0.0.1", 0)
        async with server:
            port = server.sockets[0].getsockname()[1]
            return await address_check.run(_target(port, pki.bundle, timeout=0.3))

    results = {c.check: (c.status, c.detail) for c in asyncio.run(go()).checks}
    for name in ("tls_no_sni", "chain_firmware_bundle", "leaf_rsa", "healthcheck_reachable"):
        assert results[name][0] == "fail", name
    assert results["tls_no_sni"][1] == "timeout"
    assert results["dns"][0] == "ok"


def test_http_address_fails_the_tls_checks(pki: Pki) -> None:
    target = CheckTarget(parse("http://127.0.0.1:9"), INSTANCE, pki.bundle, NO_CLOUDFLARE, 1.0)
    results = {c.check: c for c in asyncio.run(address_check.run(target)).checks}
    for name in ("tls_no_sni", "chain_firmware_bundle", "leaf_rsa"):
        assert results[name].status == "fail" and "https" in results[name].detail


@pytest.mark.parametrize("san, host, expected", [
    ([("DNS", "flo.example.com")], "flo.example.com", True),
    ([("DNS", "*.example.com")], "flo.example.com", True),
    ([("DNS", "*.example.com")], "a.flo.example.com", False),
    ([("DNS", "other.example.com")], "flo.example.com", False),
    ([("IP Address", "127.0.0.1")], "127.0.0.1", True),
])
def test_hostname_matches(san: list[tuple[str, str]], host: str, expected: bool) -> None:
    assert address_check.hostname_matches({"subjectAltName": tuple(san)}, host) is expected


def test_nightly_runs_at_three_local_time() -> None:
    tz = ZoneInfo("America/New_York")
    assert nightly.seconds_until(nightly.NIGHTLY_AT, datetime(2026, 10, 26, 2, 0, tzinfo=tz)) == 3600
    assert nightly.seconds_until(nightly.NIGHTLY_AT, datetime(2026, 10, 26, 3, 0, tzinfo=tz)) == 86400
    # DST ends 2026-11-01 at 02:00 EDT: 01:00 EDT -> 03:00 EST is three real hours.
    assert nightly.seconds_until(nightly.NIGHTLY_AT, datetime(2026, 11, 1, 1, 0, tzinfo=tz)) == 3 * 3600


# -- the vendored firmware CA bundle ---------------------------------------------------------------------------

def _bundle_header() -> dict[str, list[str]]:
    header: dict[str, list[str]] = {}
    for line in address_check.FIRMWARE_CA_BUNDLE.read_text().splitlines():
        if line.startswith("# ") and ": " in line:
            key, value = line[2:].split(": ", 1)
            header.setdefault(key, []).append(value)
    return header


def _vendored() -> list[x509.Certificate]:
    return x509.load_pem_x509_certificates(address_check.FIRMWARE_CA_BUNDLE.read_bytes())


def test_vendored_bundle_has_provenance_and_isrg_root_x1() -> None:
    header = _bundle_header()
    assert header["firmware_version"] == ["20251201_3.0.64"]
    assert len(header["firmware_sha256"][0]) == len(header["bundle_sha256"][0]) == 64
    assert int(header["vendored"][0]) == len(_vendored())
    assert int(header["vendored"][0]) + int(header["unmatched"][0]) == int(header["entries"][0])
    subjects = {cert.subject.rfc4514_string() for cert in _vendored()}
    assert "CN=ISRG Root X1,O=Internet Security Research Group,C=US" in subjects
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile=str(address_check.FIRMWARE_CA_BUNDLE))
    assert context.cert_store_stats()["x509_ca"] == len(_vendored())


FIRMWARE = Path(os.environ.get("OPENFLO_FIRMWARE_IMAGE", REPO / "artifacts" / "firmware" / "iflo-3.0.64.bin"))


@pytest.mark.skipif(not FIRMWARE.exists(), reason="vendor firmware is never committed (local-only check)")
def test_vendored_bundle_matches_the_firmware() -> None:
    sys.path.insert(0, str(REPO / "tools"))
    import dump_crt_bundle

    header = _bundle_header()
    assert header["firmware_sha256"] == [dump_crt_bundle._sha256(str(FIRMWARE))]
    entries = dump_crt_bundle.load_bundle(str(FIRMWARE))
    assert int(header["entries"][0]) == len(entries)
    assert [dump_crt_bundle.anchor_key(cert) for cert in _vendored()] == [
        e for e in entries if dump_crt_bundle._subject(e[0]) not in header.get("unmatched_subject", [])]

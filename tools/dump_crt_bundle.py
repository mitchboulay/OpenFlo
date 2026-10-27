"""Inspect the esp_crt_bundle in the iFLO 3.0.64 app image.

  list   <image>                         print every trust anchor in the bundle
  verify <image> <chain.pem>             replay the firmware's bundle check against a served chain
  pem    <image> <out.pem> <roots.pem>...  write the anchors as PEM (backend/app/firmware_ca_bundle.pem)

esp_crt_bundle trusts a chain when the topmost certificate the server sends is
signed by a bundle key whose subject DER equals that certificate's issuer DER.

The bundle stores only each root's subject DER and public key, not the certificate.
`pem` therefore matches every entry, on exact subject DER and SubjectPublicKeyInfo DER,
against the root stores given (Mozilla's, e.g. certifi releases) and writes the full
certificates it finds. Entries no store holds are listed in the header, never invented.
The vendored 3.0.64 file matched all 148 entries with certifi 2024.2.2's cacert.pem, then
2021.5.30's (for roots Mozilla has since removed), passed in that order.
"""
import hashlib
import re
import struct
import sys

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec, padding
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_der_public_key

BUNDLE_VA = 0x3F039E20
BUNDLE_LEN = 0x108DE


def va_to_offset(image: bytes, va: int) -> int:
    off = 24  # ESP32-S2 image header incl. extended header
    for _ in range(image[1]):
        load, length = struct.unpack_from("<II", image, off)
        off += 8
        if load <= va < load + length:
            return off + (va - load)
        off += length
    raise ValueError(f"VA {va:#x} not in any segment")


def bundle_bytes(image_path: str) -> bytes:
    image = open(image_path, "rb").read()
    assert image[0] == 0xE9, "not an ESP app image"
    start = va_to_offset(image, BUNDLE_VA)
    return image[start:start + BUNDLE_LEN]


def app_version(image_path: str) -> str:
    """esp_app_desc_t.version, at the start of the first segment (after the 24-byte header and 8-byte segment header)."""
    image = open(image_path, "rb").read()
    magic, = struct.unpack_from("<I", image, 32)
    assert magic == 0xABCD5432, "no esp_app_desc_t"
    return image[48:80].split(b"\0")[0].decode()


def load_bundle(image_path: str) -> list[tuple[bytes, bytes]]:
    bundle = bundle_bytes(image_path)
    (count,) = struct.unpack_from(">H", bundle, 0)
    off, entries = 2, []
    for _ in range(count):
        name_len, key_len = struct.unpack_from(">HH", bundle, off)
        off += 4
        entries.append((bundle[off:off + name_len], bundle[off + name_len:off + name_len + key_len]))
        off += name_len + key_len
    assert off <= len(bundle), "bundle overrun"
    return entries


def verify_signature(public_key, cert: x509.Certificate) -> None:
    if isinstance(public_key, ec.EllipticCurvePublicKey):
        public_key.verify(cert.signature, cert.tbs_certificate_bytes, ec.ECDSA(cert.signature_hash_algorithm))
    else:
        public_key.verify(cert.signature, cert.tbs_certificate_bytes, padding.PKCS1v15(), cert.signature_hash_algorithm)


def cmd_list(image_path: str) -> None:
    entries = load_bundle(image_path)
    print(f"entries={len(entries)}")
    for name_der, key_der in entries:
        key = load_der_public_key(key_der)
        size = getattr(key, "key_size", None) or key.curve.name
        labels = [s.decode("latin1") for s in re.findall(rb"[\x20-\x7e]{4,}", name_der)]
        print(f"{type(key).__name__}:{size} | {' / '.join(labels)}")


def cmd_verify(image_path: str, chain_path: str) -> int:
    chain = x509.load_pem_x509_certificates(open(chain_path, "rb").read())
    for child, parent in zip(chain, chain[1:]):
        verify_signature(parent.public_key(), child)
        print(f"link ok: {child.subject.rfc4514_string()} <- {parent.subject.rfc4514_string()}")
    top = chain[-1]
    issuer_der = top.issuer.public_bytes()
    for name_der, key_der in load_bundle(image_path):
        if name_der == issuer_der:
            verify_signature(load_der_public_key(key_der), top)
            print(f"TRUSTED: top cert signed by bundle anchor {top.issuer.rfc4514_string()}")
            return 0
    print(f"UNTRUSTED: no bundle anchor for issuer {top.issuer.rfc4514_string()}")
    return 1


def anchor_key(cert: x509.Certificate) -> tuple[bytes, bytes]:
    """(subject DER, SubjectPublicKeyInfo DER): what a bundle entry stores."""
    return cert.subject.public_bytes(), cert.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)


def _sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def cmd_pem(image_path: str, out_path: str, store_paths: list[str]) -> int:
    known: dict[tuple[bytes, bytes], x509.Certificate] = {}
    for store in store_paths:  # earlier stores win
        for cert in x509.load_pem_x509_certificates(open(store, "rb").read()):
            known.setdefault(anchor_key(cert), cert)
    entries = load_bundle(image_path)
    found = [known[e] for e in entries if e in known]
    missing = [e for e in entries if e not in known]
    header = [
        "# iFLO firmware CA bundle (esp_crt_bundle trust anchors). Generated by tools/dump_crt_bundle.py pem; do not edit.",
        f"# firmware_version: {app_version(image_path)}",
        f"# firmware_sha256: {_sha256(image_path)}",
        f"# bundle_sha256: {hashlib.sha256(bundle_bytes(image_path)).hexdigest()}",
        f"# entries: {len(entries)}",
        f"# vendored: {len(found)}",
        f"# unmatched: {len(missing)}",
        *(f"# root_store_sha256: {_sha256(store)}" for store in store_paths),
        *(f"# unmatched_subject: {_subject(name_der)}" for name_der, _ in missing),
    ]
    blocks = [f"# {cert.subject.rfc4514_string()}\n{cert.public_bytes(Encoding.PEM).decode()}" for cert in found]
    open(out_path, "w").write("\n".join(header) + "\n\n" + "\n".join(blocks))
    print(f"entries={len(entries)} vendored={len(found)} unmatched={len(missing)}")
    return 0


def _subject(name_der: bytes) -> str:
    return " / ".join(s.decode("latin1") for s in re.findall(rb"[\x20-\x7e]{4,}", name_der))


if __name__ == "__main__":
    if sys.argv[1] == "list":
        cmd_list(sys.argv[2])
    elif sys.argv[1] == "verify":
        sys.exit(cmd_verify(sys.argv[2], sys.argv[3]))
    elif sys.argv[1] == "pem":
        sys.exit(cmd_pem(sys.argv[2], sys.argv[3], sys.argv[4:]))
    else:
        sys.exit(__doc__)

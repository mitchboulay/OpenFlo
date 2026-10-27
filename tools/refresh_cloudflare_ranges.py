"""Refresh backend/app/cloudflare_ranges.json from Cloudflare's published IP lists.

Usage: python tools/refresh_cloudflare_ranges.py  (exit 0; the file is rewritten only when the ranges change,
so `git diff --exit-code` afterwards detects drift). Stdlib only.
"""
import hashlib
import ipaddress
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCES = {"ipv4": "https://www.cloudflare.com/ips-v4", "ipv6": "https://www.cloudflare.com/ips-v6"}
OUT = Path(__file__).resolve().parents[1] / "backend" / "app" / "cloudflare_ranges.json"
TIMEOUT_S = 10


def fetch(url: str) -> bytes:
    # Cloudflare answers urllib's default User-Agent with 403.
    request = urllib.request.Request(url, headers={"User-Agent": "openflo-ranges-refresh/1"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310 (fixed https URLs)
        return response.read()


def main() -> int:
    current = json.loads(OUT.read_text()) if OUT.exists() else {}
    fresh: dict[str, object] = {"sources": {}}
    for family, url in SOURCES.items():
        body = fetch(url)
        cidrs = sorted(str(ipaddress.ip_network(line.strip())) for line in body.decode().splitlines() if line.strip())
        if not cidrs:
            sys.exit(f"{url} returned no ranges")
        fresh[family] = cidrs
        fresh["sources"][family] = {"url": url, "sha256": hashlib.sha256(body).hexdigest()}  # type: ignore[index]
    if all(current.get(k) == fresh[k] for k in ("ipv4", "ipv6", "sources")):
        print("cloudflare_ranges.json is current")
        return 0
    fresh["fetched_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    OUT.write_text(json.dumps(fresh, indent=2, sort_keys=True) + "\n")
    print(f"updated {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

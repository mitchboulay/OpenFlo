# syntax=docker/dockerfile:1
# Caddy with the Cloudflare DNS provider, for ACME DNS-01 (compose.dns01.yaml).
FROM caddy:2-builder AS builder
RUN xcaddy build --with github.com/caddy-dns/cloudflare

FROM caddy:2
COPY --from=builder /usr/bin/caddy /usr/bin/caddy

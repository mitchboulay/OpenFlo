# syntax=docker/dockerfile:1

# --- UI build ---------------------------------------------------------------
# Built once on the build machine's own platform: the output is static JS/CSS, the same for every target, and
# building it under arm64 emulation (QEMU) stalls npm/Vite for an hour.
FROM --platform=$BUILDPLATFORM node:22-alpine AS ui
WORKDIR /src/ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
# gen:api reads ../backend/openapi.json. The drift check skips itself here (no .git); CI runs it.
COPY backend/openapi.json /src/backend/openapi.json
RUN npm run build

# --- Runtime ----------------------------------------------------------------
# `openflo backup|restore|check-address` (app/cli.py) is on PATH.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OPENFLO_BACKEND_DB=/data/openflo.db \
    OPENFLO_UI_DIST=/opt/openflo/ui/dist \
    FORWARDED_ALLOW_IPS=127.0.0.1

WORKDIR /opt/openflo/backend
COPY backend/requirements.txt ./
# pytest and respx are test-only dependencies; keep them out of the runtime image.
RUN grep -v -E '^(pytest|respx)' requirements.txt > /tmp/runtime-requirements.txt \
    && pip install -r /tmp/runtime-requirements.txt \
    && rm /tmp/runtime-requirements.txt \
    && groupadd --system --gid 10001 openflo \
    && useradd --system --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin openflo \
    && install -d -o 10001 -g 10001 -m 0750 /data \
    && printf '#!/bin/sh\nexec env PYTHONPATH=/opt/openflo/backend python -m app.cli "$@"\n' > /usr/local/bin/openflo \
    && chmod 0755 /usr/local/bin/openflo

COPY backend/app ./app
COPY --from=ui /src/ui/dist /opt/openflo/ui/dist

USER 10001:10001
VOLUME /data
EXPOSE 8099

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8099/healthz', timeout=4).status == 200 else 1)"]

# --proxy-headers trusts X-Forwarded-For only from FORWARDED_ALLOW_IPS (uvicorn reads it from the env).
# The image default trusts loopback only; compose.yaml sets it to the Caddy container's fixed IP.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8099", "--proxy-headers"]

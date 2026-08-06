# syntax=docker/dockerfile:1
#
# Forge-OH BFF container.
#
# Build context: repo root (see docker-compose.yml `build.context: .`).
# The context MUST be repo root, not `./bff`, because bff imports from the
# top-level sibling package `openhands_tools_ext` at runtime.
#
# Kept intentionally small via .dockerignore at the repo root.

FROM python:3.13-slim

WORKDIR /app

# Non-root user
RUN groupadd --system --gid 1001 bff && \
    useradd  --system --uid 1001 --gid bff bff

# System deps needed by the Python wheels: nothing beyond stdlib+wheels today.
# (tree-sitter grabs its own prebuilt wheels; neo4j-driver is pure Python;
# qdrant-client is pure Python.)

# Install Python dependencies. Copy requirements first for layer caching.
COPY bff/requirements.txt /app/bff/requirements.txt
RUN pip install --no-cache-dir -r /app/bff/requirements.txt

# Copy source trees. bff.main imports openhands_tools_ext.*, so both
# packages must sit at /app so `python -c 'import bff, openhands_tools_ext'`
# works from WORKDIR.
COPY bff/                  /app/bff/
COPY openhands_tools_ext/  /app/openhands_tools_ext/

# Copy top-level project markers that Settings / config resolution may
# consult at import time (pyproject.toml is read by pydantic-settings for
# some feature flags; harmless if absent).
COPY pyproject.toml        /app/pyproject.toml

RUN chown -R bff:bff /app
USER bff

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8081/health')"

LABEL org.opencontainers.image.source="https://github.com/rmholston420/Forge-OH"
LABEL org.opencontainers.image.description="Forge-OH BFF (Backend For Frontend)"
LABEL org.opencontainers.image.licenses="MIT"

# CRITICAL — two constraints that must never be changed without a migration plan:
#
# 1. Entry point is bff.main:app_with_sio (the Socket.IO ASGI wrapper), NOT bff.main:app.
#    Starting with bff.main:app silently bypasses Socket.IO; all WebSocket connections fail.
#
# 2. --workers 1 is intentional. In-memory router state (secrets, mcp servers, plugins, etc.)
#    is process-local. Do not scale workers until state is externalised.
CMD ["uvicorn", "bff.main:app_with_sio", \
     "--host", "0.0.0.0", \
     "--port", "8081", \
     "--workers", "1", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]

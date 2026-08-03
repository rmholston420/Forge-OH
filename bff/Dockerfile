# syntax=docker/dockerfile:1
FROM python:3.13-slim

WORKDIR /app

# Non-root user
RUN groupadd --system --gid 1001 bff && \
    useradd  --system --uid 1001 --gid bff bff

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

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

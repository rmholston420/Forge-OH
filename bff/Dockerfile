# syntax=docker/dockerfile:1
FROM python:3.12-slim

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

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

LABEL org.opencontainers.image.source="https://github.com/rmholston420/Forge-OH"
LABEL org.opencontainers.image.description="Forge-OH BFF (Backend For Frontend)"
LABEL org.opencontainers.image.licenses="MIT"

CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]

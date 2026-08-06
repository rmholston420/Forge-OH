"""Shared health-probe helpers for adapters.

The two probe shapes used across adapters:

- **openai_v1_models**: GET ``{base}/v1/models``. Success is HTTP 200 +
  non-empty ``data``. Used by vLLM, llama.cpp server, SGLang, and
  Ollama's OpenAI-compat surface.
- **ollama_tags**: GET ``{base}/api/tags``. Success is HTTP 200 +
  non-empty ``models``. Used by native Ollama.

Both helpers are ``asyncio.wait_for``-bounded with a short default
timeout so a hung backend never blocks the ``/api/inference-backends``
endpoint.
"""

from __future__ import annotations

import time
from typing import Callable

import httpx

from .types import BackendHealth

DEFAULT_PROBE_TIMEOUT_S = 1.5


async def probe_openai_v1_models(
    base_url: str,
    timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
) -> BackendHealth:
    """Probe an OpenAI-compat ``/v1/models`` endpoint."""

    return await _probe(
        f"{base_url.rstrip('/')}/v1/models",
        timeout_s,
        lambda body: len((body or {}).get("data", []) or []),
    )


async def probe_ollama_tags(
    base_url: str,
    timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
) -> BackendHealth:
    """Probe Ollama's native ``/api/tags`` endpoint."""

    return await _probe(
        f"{base_url.rstrip('/')}/api/tags",
        timeout_s,
        lambda body: len((body or {}).get("models", []) or []),
    )


async def _probe(
    url: str,
    timeout_s: float,
    count_models: Callable[[dict], int],
) -> BackendHealth:
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(url)
    except Exception as exc:  # network error, timeout, DNS failure
        return BackendHealth(
            state="unhealthy",
            latency_ms=None,
            model_count=None,
            error=f"{exc.__class__.__name__}: {exc}",
        )

    latency_ms = int((time.monotonic() - start) * 1000)

    if resp.status_code >= 400:
        return BackendHealth(
            state="unhealthy",
            latency_ms=latency_ms,
            model_count=None,
            error=f"HTTP {resp.status_code}",
        )

    try:
        body = resp.json()
    except Exception as exc:
        return BackendHealth(
            state="degraded",
            latency_ms=latency_ms,
            model_count=None,
            error=f"non-JSON body: {exc.__class__.__name__}",
        )

    count = count_models(body)
    if count <= 0:
        return BackendHealth(
            state="degraded",
            latency_ms=latency_ms,
            model_count=0,
            error="server up but no model loaded",
        )

    return BackendHealth(
        state="healthy",
        latency_ms=latency_ms,
        model_count=count,
        error=None,
    )

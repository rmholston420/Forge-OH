"""
bff/openhands_client.py

HTTP client wrapper for the OpenHands SDK REST API.
Base URL is read from Settings (default: http://localhost:8090).
Never hardcode port numbers here — use settings.openhands_base_url.
"""
from __future__ import annotations

import httpx
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from .settings import get_settings

_client: httpx.AsyncClient | None = None


async def startup() -> None:
    global _client
    settings = get_settings()
    _client = httpx.AsyncClient(
        base_url=settings.openhands_base_url,
        timeout=httpx.Timeout(60.0),
        headers={
            "Content-Type": "application/json",
            **({
                "Authorization": f"Bearer {settings.openhands_api_key}"
            } if settings.openhands_api_key else {}),
        },
    )


async def shutdown() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


@asynccontextmanager
async def lifespan(_app) -> AsyncGenerator[None, None]:  # type: ignore[type-arg]
    await startup()
    try:
        yield
    finally:
        await shutdown()


def get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError(
            "OpenHands client not initialised. "
            "Ensure the FastAPI lifespan context manager is wired up in main.py."
        )
    return _client

import os
from typing import Any, Dict, Optional

import httpx

OPENHANDS_AGENT_SERVER_BASE_URL = os.getenv(
    "OPENHANDS_AGENT_SERVER_BASE_URL", "http://localhost:8090"
).rstrip("/")


class OpenHandsClient:
    """
    Thin HTTP client for the external OpenHands Agent Server.

    The BFF uses this client; the frontend never talks directly to OpenHands.
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or OPENHANDS_AGENT_SERVER_BASE_URL).rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def create_run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = await self._client.post("/api/runs", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_run(self, run_id: str) -> Dict[str, Any]:
        resp = await self._client.get(f"/api/runs/{run_id}")
        resp.raise_for_status()
        return resp.json()

    async def list_events(self, run_id: str) -> Dict[str, Any]:
        resp = await self._client.get(f"/api/runs/{run_id}/events")
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()

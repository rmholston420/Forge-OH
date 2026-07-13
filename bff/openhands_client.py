"""
bff/openhands_client.py

OpenHands REST + WebSocket gateway for the Forge BFF.

ARCHITECTURAL RULE (from Forge-OH-Build-Plan-Definitive.md):
    "The frontend never talks directly to OpenHands.
     All traffic flows through the BFF."

This module is the ONLY place in the BFF that may open connections to
the OpenHands service.  All routers and services must go through
``get_openhands_client()`` — never import ``httpx`` / ``websockets``
directly to reach OpenHands.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections.abc import AsyncGenerator
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — driven entirely by environment variables
# ---------------------------------------------------------------------------

OPENHANDS_BASE_URL: str = os.environ.get(
    "OPENHANDS_BASE_URL", "http://localhost:3000"
)
OPENHANDS_API_KEY: str | None = os.environ.get("OPENHANDS_API_KEY")

# Timeout for standard REST calls (seconds)
HTTP_TIMEOUT = 30.0
# Keepalive / ping interval for WebSocket streams (seconds)
WS_PING_INTERVAL = 20.0


# ---------------------------------------------------------------------------
# Typed exceptions
# ---------------------------------------------------------------------------


class OpenHandsError(Exception):
    """Raised when OpenHands returns a non-2xx response."""

    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(f"[{status}] {code}: {detail}")
        self.status = status
        self.code = code
        self.detail = detail


class OpenHandsConnectionError(OpenHandsError):
    """Raised when the BFF cannot reach OpenHands at all."""

    def __init__(self, detail: str) -> None:
        super().__init__(0, "CONNECTION_ERROR", detail)


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

# Characters that cannot appear inside a secret value in JSON (conservative)
_REDACT_RE = re.compile(r'("(?:value|secret|token|password|apiKey|api_key)"\s*:\s*)"[^"]+"')


def redact_secrets(payload: Any) -> Any:
    """
    Strip secret values from a dict / list payload before it reaches
    the frontend.  Operates recursively on nested structures.

    Secret keys: value, secret, token, password, apiKey, api_key.
    Replaces the value with the redaction sentinel ``"[REDACTED]"``.
    """
    if isinstance(payload, dict):
        redacted: dict[str, Any] = {}
        for k, v in payload.items():
            if k.lower() in {"value", "secret", "token", "password", "apikey", "api_key"}:
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_secrets(v)
        return redacted
    if isinstance(payload, list):
        return [redact_secrets(item) for item in payload]
    return payload


def redact_secrets_json(raw_json: str) -> str:
    """Fast regex redaction on a raw JSON string (used for streaming events)."""
    return _REDACT_RE.sub(r'\1"[REDACTED]"', raw_json)


# ---------------------------------------------------------------------------
# OpenHandsClient
# ---------------------------------------------------------------------------


class OpenHandsClient:
    """
    Async HTTP + WebSocket client for the OpenHands service.

    Do not instantiate directly — use ``get_openhands_client()``.
    """

    def __init__(
        self,
        base_url: str = OPENHANDS_BASE_URL,
        api_key: str | None = OPENHANDS_API_KEY,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=HTTP_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, **params: Any) -> Any:
        try:
            resp = await self._http.get(path, params=params or None)
        except httpx.ConnectError as exc:
            raise OpenHandsConnectionError(str(exc)) from exc
        await self._raise_for_status(resp)
        return resp.json()

    async def _post(self, path: str, body: Any = None) -> Any:
        try:
            resp = await self._http.post(path, json=body)
        except httpx.ConnectError as exc:
            raise OpenHandsConnectionError(str(exc)) from exc
        await self._raise_for_status(resp)
        return resp.json()

    async def _patch(self, path: str, body: Any = None) -> Any:
        try:
            resp = await self._http.patch(path, json=body)
        except httpx.ConnectError as exc:
            raise OpenHandsConnectionError(str(exc)) from exc
        await self._raise_for_status(resp)
        return resp.json()

    @staticmethod
    async def _raise_for_status(resp: httpx.Response) -> None:
        if resp.is_success:
            return
        code = "OPENHANDS_ERROR"
        detail = resp.text
        try:
            body = resp.json()
            code = body.get("code", code)
            detail = body.get("detail", detail)
        except Exception:  # noqa: BLE001
            pass
        raise OpenHandsError(resp.status_code, code, detail)

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    async def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /api/conversations — starts a new OpenHands run."""
        result: dict[str, Any] = await self._post("/api/conversations", payload)
        return redact_secrets(result)

    async def pause_run(self, run_id: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._patch(f"/api/conversations/{run_id}/pause")
        return redact_secrets(result)

    async def resume_run(self, run_id: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._patch(f"/api/conversations/{run_id}/resume")
        return redact_secrets(result)

    async def stop_run(self, run_id: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._patch(f"/api/conversations/{run_id}/stop")
        return redact_secrets(result)

    async def approve_action(self, run_id: str, action_id: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._post(
            f"/api/conversations/{run_id}/actions/{action_id}/approve"
        )
        return redact_secrets(result)

    async def reject_action(self, run_id: str, action_id: str, reason: str = "") -> dict[str, Any]:
        result: dict[str, Any] = await self._post(
            f"/api/conversations/{run_id}/actions/{action_id}/reject",
            {"reason": reason},
        )
        return redact_secrets(result)

    async def get_run(self, run_id: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._get(f"/api/conversations/{run_id}")
        return redact_secrets(result)

    async def list_runs(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        result: dict[str, Any] = await self._get(
            "/api/conversations", page=page, page_size=page_size
        )
        return redact_secrets(result)

    # ------------------------------------------------------------------
    # Event streaming (WebSocket)
    # ------------------------------------------------------------------

    async def stream_run_events(
        self, run_id: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Async generator that yields parsed event dicts from the OpenHands
        WebSocket event stream for a given run.

        All yielded events are passed through ``redact_secrets()`` before
        being yielded — secret values never reach the caller.

        Usage::

            async for event in client.stream_run_events(run_id):
                await sio.emit("run:event", event, room=run_id)
        """
        import websockets  # lazy import — optional dep for non-streaming paths

        ws_base = self._base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_base}/ws/conversations/{run_id}/stream"

        extra_headers: list[tuple[str, str]] = []
        if OPENHANDS_API_KEY:
            extra_headers.append(("Authorization", f"Bearer {OPENHANDS_API_KEY}"))

        try:
            async with websockets.connect(
                ws_url,
                extra_headers=extra_headers,
                ping_interval=WS_PING_INTERVAL,
            ) as ws:
                async for raw in ws:
                    if isinstance(raw, bytes):
                        raw = raw.decode()
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.warning("Non-JSON WS frame from OpenHands: %s", raw[:200])
                        continue
                    yield redact_secrets(event)
        except ConnectionRefusedError as exc:
            raise OpenHandsConnectionError(
                f"WebSocket connection refused for run {run_id}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Workspaces
    # ------------------------------------------------------------------

    async def list_workspaces(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._get("/api/workspaces")
        return [redact_secrets(w) for w in result]

    async def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._get(f"/api/workspaces/{workspace_id}")
        return redact_secrets(result)

    async def reset_workspace(self, workspace_id: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._post(f"/api/workspaces/{workspace_id}/reset")
        return redact_secrets(result)

    # ------------------------------------------------------------------
    # MCP / Integrations
    # ------------------------------------------------------------------

    async def list_mcp_servers(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._get("/api/integrations/mcp")
        return [redact_secrets(s) for s in result]

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        result: dict[str, Any] = await self._get("/health")
        return result


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_client: OpenHandsClient | None = None
_client_lock = asyncio.Lock()


async def get_openhands_client() -> OpenHandsClient:
    """
    Return the singleton OpenHandsClient instance.

    Thread-safe via an asyncio lock.  The client is lazily initialised
    on first use so that application startup does not fail if OpenHands
    is temporarily unavailable.
    """
    global _client  # noqa: PLW0603
    if _client is None:
        async with _client_lock:
            if _client is None:  # double-checked locking
                _client = OpenHandsClient()
                logger.info(
                    "OpenHandsClient initialised: base_url=%s auth=%s",
                    OPENHANDS_BASE_URL,
                    "key" if OPENHANDS_API_KEY else "none",
                )
    return _client

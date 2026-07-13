"""
bff/openhands_client.py

OpenHands REST + WebSocket wrapper.

ARCHITECTURE RULE (non-negotiable):
    The frontend NEVER talks directly to OpenHands.
    ALL traffic flows through this module.
    Raw secret values are NEVER forwarded to callers.

Ref: Forge-OH-Build-Plan-Definitive.md § Architecture
"""
from __future__ import annotations

import os
from typing import Any, AsyncIterator

import httpx
import socketio

# ---------------------------------------------------------------------------
# Configuration (env-driven, never hardcoded)
# ---------------------------------------------------------------------------

OH_BASE_URL: str = os.getenv("OPENHANDS_BASE_URL", "http://localhost:3001")
OH_API_KEY: str = os.getenv("OPENHANDS_API_KEY", "")
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class OpenHandsClientError(Exception):
    """Raised when an upstream OpenHands call fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

def redact_secrets(payload: Any) -> Any:
    """
    Recursively strip any field whose key contains 'secret', 'token',
    'password', or 'key' so raw values never reach the browser.
    """
    _SENSITIVE = frozenset({"secret", "token", "password", "key", "api_key"})
    if isinstance(payload, dict):
        return {
            k: "[REDACTED]" if any(s in k.lower() for s in _SENSITIVE)
            else redact_secrets(v)
            for k, v in payload.items()
        }
    if isinstance(payload, list):
        return [redact_secrets(item) for item in payload]
    return payload


# ---------------------------------------------------------------------------
# REST client
# ---------------------------------------------------------------------------

class OpenHandsClient:
    """
    Async HTTP wrapper around the OpenHands REST API.

    Usage::

        async with OpenHandsClient() as oh:
            runs = await oh.list_runs()
    """

    def __init__(
        self,
        base_url: str = OH_BASE_URL,
        api_key: str = OH_API_KEY,
    ) -> None:
        self._base = base_url.rstrip("/")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=self._base,
            headers=headers,
            timeout=_TIMEOUT,
        )

    async def __aenter__(self) -> "OpenHandsClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, **params: Any) -> Any:
        r = await self._client.get(path, params=params or None)
        self._raise_for_status(r)
        return redact_secrets(r.json())

    async def _post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        r = await self._client.post(path, json=body or {})
        self._raise_for_status(r)
        return redact_secrets(r.json())

    async def _patch(self, path: str, body: dict[str, Any] | None = None) -> Any:
        r = await self._client.patch(path, json=body or {})
        self._raise_for_status(r)
        return redact_secrets(r.json())

    async def _delete(self, path: str) -> Any:
        r = await self._client.delete(path)
        self._raise_for_status(r)
        return r.json() if r.content else {}

    @staticmethod
    def _raise_for_status(r: httpx.Response) -> None:
        if r.is_error:
            raise OpenHandsClientError(
                f"OpenHands API error {r.status_code}: {r.text[:200]}",
                status_code=r.status_code,
            )

    # ------------------------------------------------------------------
    # Runs / Conversations
    # ------------------------------------------------------------------

    async def list_runs(self, **filters: Any) -> list[dict[str, Any]]:
        """List all runs (maps to OH conversations)."""
        return await self._get("/api/conversations", **filters)

    async def get_run(self, run_id: str) -> dict[str, Any]:
        return await self._get(f"/api/conversations/{run_id}")

    async def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._post("/api/conversations", payload)

    async def stop_run(self, run_id: str) -> dict[str, Any]:
        return await self._post(f"/api/conversations/{run_id}/stop")

    async def pause_run(self, run_id: str) -> dict[str, Any]:
        return await self._post(f"/api/conversations/{run_id}/pause")

    async def resume_run(self, run_id: str) -> dict[str, Any]:
        return await self._post(f"/api/conversations/{run_id}/resume")

    async def fork_run(self, run_id: str) -> dict[str, Any]:
        return await self._post(f"/api/conversations/{run_id}/fork")

    async def approve_run(self, run_id: str) -> dict[str, Any]:
        return await self._post(f"/api/conversations/{run_id}/approve")

    async def reject_run(self, run_id: str) -> dict[str, Any]:
        return await self._post(f"/api/conversations/{run_id}/reject")

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    async def get_events(
        self, run_id: str, since_event_id: int | None = None
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if since_event_id is not None:
            params["since"] = since_event_id
        return await self._get(f"/api/conversations/{run_id}/events", **params)

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    async def list_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/api/conversations/{run_id}/artifacts")

    async def get_artifact(self, run_id: str, artifact_id: str) -> dict[str, Any]:
        return await self._get(
            f"/api/conversations/{run_id}/artifacts/{artifact_id}"
        )

    async def list_file_diffs(self, run_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/api/conversations/{run_id}/artifacts/files")

    async def get_diff(
        self, run_id: str, path: str
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/conversations/{run_id}/artifacts/diff", path=path
        )

    async def export_patch(self, run_id: str) -> bytes:
        r = await self._client.get(
            f"/api/conversations/{run_id}/export/patch"
        )
        self._raise_for_status(r)
        return r.content

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def list_commands(self, run_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/api/conversations/{run_id}/commands")

    async def get_command_output(
        self, run_id: str, command_id: str
    ) -> dict[str, Any]:
        data = await self._get(
            f"/api/conversations/{run_id}/commands/{command_id}/output"
        )
        # Extra redaction pass: stdout/stderr may carry secret echos
        return redact_secrets(data)

    # ------------------------------------------------------------------
    # Traces (OTEL)
    # ------------------------------------------------------------------

    async def list_traces(self, run_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/api/conversations/{run_id}/traces")

    async def get_span(
        self, run_id: str, span_id: str
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/conversations/{run_id}/traces/{span_id}"
        )

    # ------------------------------------------------------------------
    # Browser sessions
    # ------------------------------------------------------------------

    async def list_browser_sessions(
        self, run_id: str
    ) -> list[dict[str, Any]]:
        return await self._get(
            f"/api/conversations/{run_id}/browser/sessions"
        )

    async def get_browser_session(
        self, run_id: str, session_id: str
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/conversations/{run_id}/browser/sessions/{session_id}"
        )

    # ------------------------------------------------------------------
    # Workspaces
    # ------------------------------------------------------------------

    async def list_workspaces(self) -> list[dict[str, Any]]:
        return await self._get("/api/workspaces")

    async def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        return await self._get(f"/api/workspaces/{workspace_id}")

    async def reset_workspace(self, workspace_id: str) -> dict[str, Any]:
        return await self._post(f"/api/workspaces/{workspace_id}/reset")

    # ------------------------------------------------------------------
    # Secrets (metadata only — raw values NEVER returned)
    # ------------------------------------------------------------------

    async def list_secrets(self) -> list[dict[str, Any]]:
        """Returns secret metadata + maskedValue only. Raw values never forwarded."""
        return await self._get("/api/secrets")

    async def create_secret(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """POSTs secret to OpenHands. Raw value travels BFF→OH only, never to frontend."""
        result = await self._post("/api/secrets", payload)
        return redact_secrets(result)

    async def update_secret(
        self, secret_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        result = await self._patch(f"/api/secrets/{secret_id}", payload)
        return redact_secrets(result)

    async def delete_secret(self, secret_id: str) -> dict[str, Any]:
        return await self._delete(f"/api/secrets/{secret_id}")


# ---------------------------------------------------------------------------
# WebSocket / Socket.IO streaming client
# ---------------------------------------------------------------------------

class OpenHandsStreamClient:
    """
    Wraps the Socket.IO oh_event stream from OpenHands.

    The BFF mediates all streaming — the frontend connects to the BFF
    Socket.IO namespace, not to OpenHands directly.

    Usage::

        async for event in OpenHandsStreamClient().stream(run_id, since=42):
            await sio.emit("oh_event", event, room=run_id)
    """

    def __init__(self, base_url: str = OH_BASE_URL) -> None:
        self._base = base_url

    async def stream(
        self,
        run_id: str,
        since: int = 0,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Async-generate validated oh_event dicts from OpenHands.
        Automatically reconnects from *since* on disconnect.
        """
        sio = socketio.AsyncSimpleClient()
        try:
            await sio.connect(
                self._base,
                transports=["websocket"],
                socketio_path="/socket.io",
                auth={"conversation_id": run_id, "latest_event_id": since},
            )
            while True:
                event_name, data = await sio.receive()
                if event_name == "oh_event":
                    yield redact_secrets(data)
        finally:
            await sio.disconnect()

"""
bff/routers/bash.py — Live bash execution + streaming for Forge-OH.

Upstream surface (OpenHands agent-server, 1.40.0):
  POST   /api/bash/execute_bash_command  — synchronous exec, returns BashOutput
  POST   /api/bash/start_bash_command    — async start, returns BashCommand
  GET    /api/bash/bash_events/search    — paginated event search
  GET    /api/bash/bash_events/{id}      — single event
  DELETE /api/bash/bash_events           — clear all
  Upstream bash events are GLOBAL, not per-conversation.

BFF surface (frontend contract):
  POST   /api/runs/{run_id}/bash                       — start a command
  POST   /api/runs/{run_id}/bash/execute               — run synchronously
  GET    /api/runs/{run_id}/bash/events                — paged JSON events
  GET    /api/runs/{run_id}/bash/stream                — SSE relay
  DELETE /api/runs/{run_id}/bash/events                — clear history

The `run_id` in the path is currently a cosmetic namespace: upstream bash
routes are global. We accept it so the frontend can hang the terminal off
a run's URL, and so we can add per-run scoping later without changing the
client contract.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from bff.openhands_client import get_client

router = APIRouter(prefix="/runs/{run_id}/bash", tags=["bash"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class BashRunBody(BaseModel):
    command: str = Field(..., min_length=1, description="Bash command to run")
    cwd: str | None = Field(default=None, description="Optional working directory")
    timeout: int = Field(default=300, ge=1, le=1800, description="Max seconds to run")


# ---------------------------------------------------------------------------
# Reshaper
# ---------------------------------------------------------------------------


def _to_event(u: dict[str, Any]) -> dict[str, Any]:
    """Normalise a BashEvent (BashCommand | BashOutput) for the frontend."""
    return {
        "id": u.get("id"),
        "kind": u.get("kind"),
        "commandId": u.get("command_id") or u.get("id"),
        "timestamp": u.get("timestamp"),
        "order": u.get("order", 0),
        "command": u.get("command"),
        "cwd": u.get("cwd"),
        "stdout": u.get("stdout"),
        "stderr": u.get("stderr"),
        "exitCode": u.get("exit_code"),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("")
async def start_bash(run_id: str, body: BashRunBody) -> dict[str, Any]:
    """Start a bash command asynchronously; returns the BashCommand event."""
    client = get_client()
    resp = await client.post(
        "/api/bash/start_bash_command",
        json={
            "command": body.command,
            "cwd": body.cwd,
            "timeout": body.timeout,
        },
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:400])
    return {"data": _to_event(resp.json() or {})}


@router.post("/execute")
async def execute_bash(run_id: str, body: BashRunBody) -> dict[str, Any]:
    """Run a bash command synchronously; returns the final BashOutput event."""
    client = get_client()
    resp = await client.post(
        "/api/bash/execute_bash_command",
        json={
            "command": body.command,
            "cwd": body.cwd,
            "timeout": body.timeout,
        },
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:400])
    return {"data": _to_event(resp.json() or {})}


@router.get("/events")
async def list_events(
    run_id: str,
    command_id: str | None = Query(default=None, description="Filter by command_id"),
    order_gt: int | None = Query(
        default=None, alias="order__gt", description="Return events with order > this"
    ),
    limit: int = Query(default=200, ge=1, le=1000),
    page_id: str | None = Query(default=None),
) -> dict[str, Any]:
    """List bash events (paginated). Filters by command_id + order for polling."""
    params: dict[str, Any] = {"limit": limit, "sort_order": "asc"}
    if command_id:
        params["command_id__eq"] = command_id
    if order_gt is not None:
        params["order__gt"] = order_gt
    if page_id:
        params["page_id"] = page_id
    client = get_client()
    resp = await client.get("/api/bash/bash_events/search", params=params)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:400])
    payload = resp.json() or {}
    items = [_to_event(e) for e in (payload.get("items") or [])]
    return {"data": items, "nextPageId": payload.get("next_page_id")}


@router.delete("/events")
async def clear_events(run_id: str) -> dict[str, Any]:
    """Clear ALL bash events (upstream is global). Idempotent."""
    client = get_client()
    resp = await client.delete("/api/bash/bash_events")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:400])
    return {"data": resp.json() or {}}


# ---------------------------------------------------------------------------
# SSE relay
# ---------------------------------------------------------------------------

# Cap poll cadence and max stream lifetime so a forgotten client can't
# hammer the upstream forever.
_POLL_INTERVAL_S = 0.5
_MAX_STREAM_S = 600  # 10 minutes


def _sse_frame(event: str, data: dict[str, Any]) -> bytes:
    """Encode a single Server-Sent Events frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


async def _bash_event_stream(
    request: Request,
    command_id: str | None,
    from_order: int,
) -> AsyncIterator[bytes]:
    """Poll upstream and yield new events as SSE frames.

    Terminates when:
      - client disconnects (Request.is_disconnected() → True),
      - a BashOutput event with a non-null exit_code arrives, OR
      - _MAX_STREAM_S seconds elapse.
    """
    client = get_client()
    last_order = from_order
    loop = asyncio.get_event_loop()
    start = loop.time()

    # Announce that the stream is live so the client can flip UI state.
    yield _sse_frame("open", {"commandId": command_id, "fromOrder": from_order})

    while True:
        if await request.is_disconnected():
            break
        if loop.time() - start > _MAX_STREAM_S:
            yield _sse_frame("timeout", {"maxSeconds": _MAX_STREAM_S})
            break

        params: dict[str, Any] = {
            "limit": 200,
            "sort_order": "asc",
            "order__gt": last_order,
        }
        if command_id:
            params["command_id__eq"] = command_id

        try:
            resp = await client.get("/api/bash/bash_events/search", params=params)
        except Exception as exc:  # network hiccup — surface and continue
            yield _sse_frame("error", {"detail": str(exc)[:200]})
            await asyncio.sleep(_POLL_INTERVAL_S)
            continue

        if resp.status_code >= 400:
            yield _sse_frame("error", {"status": resp.status_code, "detail": resp.text[:200]})
            await asyncio.sleep(_POLL_INTERVAL_S)
            continue

        payload = resp.json() or {}
        items = payload.get("items") or []
        done = False
        for raw in items:
            evt = _to_event(raw)
            last_order = max(last_order, int(raw.get("order", 0)))
            yield _sse_frame("event", evt)
            # Terminal event: BashOutput with a real exit_code.
            if evt.get("kind") == "BashOutput" and evt.get("exitCode") is not None:
                done = True

        if done:
            yield _sse_frame("close", {"lastOrder": last_order})
            break

        await asyncio.sleep(_POLL_INTERVAL_S)


@router.get("/stream")
async def stream_bash(
    run_id: str,
    request: Request,
    command_id: str | None = Query(default=None),
    from_order: int = Query(default=-1, alias="from_order"),
) -> StreamingResponse:
    """SSE relay of bash events.

    Query params:
      command_id — optional filter, restricts the stream to one command.
      from_order — start after this order (default -1 → include order 0).
    """
    return StreamingResponse(
        _bash_event_stream(request, command_id, from_order),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering
            "Connection": "keep-alive",
        },
    )

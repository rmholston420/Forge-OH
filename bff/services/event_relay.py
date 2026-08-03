"""
bff/services/event_relay.py

Background polling task that pulls events + status from the OpenHands
agent-server for a given conversation and forwards them over Socket.IO to
any connected browser clients subscribed to that conversation's room.

Wire protocol on the browser side (see src/lib/streaming/useRunStream.ts):
  Socket.IO namespace: /
  Room / query param:  conversationId
  Event name:          oh-event    (each ActionEvent/MessageEvent/etc)
                       oh-status   (execution_status transitions)

Poll cadence:
  running / waiting_for_confirmation -> 500 ms
  idle / paused                      -> 2 s
  finished / error / stuck / deleting -> stop task

The relay is entirely single-process, single-user local. No external state.
Cursor (next_page_id) is held per-conversation in-memory.

Task lifecycle:
  start_relay(cid) is idempotent; if a task is already running for cid it
  is a no-op. stop_relay(cid) cancels the task.  When a conversation
  reaches a terminal execution_status the relay self-stops.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from bff.openhands_client import get_client

log = logging.getLogger(__name__)

# Poll intervals in seconds per execution_status.
_FAST_INTERVAL = 0.5
_SLOW_INTERVAL = 2.0
_TERMINAL_STATUSES = {"finished", "error", "stuck", "deleting"}
_ACTIVE_STATUSES = {"running", "waiting_for_confirmation"}

# Set from bff.main after sio is created (avoids circular import).
_sio: Any = None
# One asyncio.Task per active conversation.
_tasks: dict[str, asyncio.Task[None]] = {}


def set_sio(sio: Any) -> None:
    """Wire the Socket.IO server into the relay. Called once at BFF startup."""
    global _sio
    _sio = sio


def _pick_interval(status: str) -> float:
    return _FAST_INTERVAL if status in _ACTIVE_STATUSES else _SLOW_INTERVAL


async def _fetch_status(cid: str) -> str | None:
    """Return the current execution_status for a conversation, or None on 404."""
    try:
        resp = await get_client().get(f"/api/conversations/{cid}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("execution_status")
    except Exception as exc:  # noqa: BLE001 — never crash the relay
        log.warning("relay[%s]: status fetch failed: %s", cid, exc)
        return None


async def _fetch_page(cid: str, page_id: str | None) -> tuple[list[dict], str | None]:
    """Fetch one page of events. Returns (events, next_page_id)."""
    params: dict[str, Any] = {"limit": 100, "sort_order": "TIMESTAMP"}
    if page_id is not None:
        params["page_id"] = page_id
    try:
        resp = await get_client().get(
            f"/api/conversations/{cid}/events/search",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        # Response shape is undocumented (schema is {}). Accept two common
        # FastAPI paginator shapes: {"items": [...], "next_page_id": "..."}
        # or a bare list.
        if isinstance(data, list):
            return data, None
        items = data.get("items") or data.get("data") or data.get("events") or []
        next_page = data.get("next_page_id") or data.get("nextPageId")
        return items, next_page
    except Exception as exc:  # noqa: BLE001
        log.warning("relay[%s]: events fetch failed: %s", cid, exc)
        return [], page_id


async def _emit(room: str, event_name: str, payload: dict) -> None:
    if _sio is None:
        return
    await _sio.emit(event_name, payload, room=room)


async def _run_loop(cid: str) -> None:
    """Poll agent-server and relay events + status until terminal."""
    room = f"conversationId={cid}"
    last_status: str | None = None
    page_id: str | None = None
    log.info("relay[%s]: starting", cid)
    try:
        while True:
            status = await _fetch_status(cid)
            if status is None:
                # Conversation disappeared. Give up.
                log.info("relay[%s]: conversation not found — stopping", cid)
                return

            if status != last_status:
                await _emit(room, "oh-status", {
                    "conversationId": cid,
                    "executionStatus": status,
                    "prev": last_status,
                })
                last_status = status

            events, next_page = await _fetch_page(cid, page_id)
            for ev in events:
                await _emit(room, "oh-event", ev)
            if next_page:
                page_id = next_page

            if status in _TERMINAL_STATUSES:
                log.info("relay[%s]: terminal status '%s' — stopping", cid, status)
                return

            await asyncio.sleep(_pick_interval(status))
    except asyncio.CancelledError:
        log.info("relay[%s]: cancelled", cid)
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("relay[%s]: crashed: %s", cid, exc)
    finally:
        _tasks.pop(cid, None)


def start_relay(cid: str) -> None:
    """Start (or no-op if already running) the event relay for a conversation."""
    if cid in _tasks and not _tasks[cid].done():
        return
    _tasks[cid] = asyncio.create_task(_run_loop(cid), name=f"relay-{cid}")


def stop_relay(cid: str) -> None:
    task = _tasks.get(cid)
    if task is not None and not task.done():
        task.cancel()


async def shutdown_all() -> None:
    for task in list(_tasks.values()):
        task.cancel()
    for task in list(_tasks.values()):
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
    _tasks.clear()

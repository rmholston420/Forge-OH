"""
Post-Stage-3 hygiene tripwire (2026-08-05).

Ensures WebSocket-delivered events go through the same ``normalize_event``
projection used by the HTTP bootstrap path (``bff/routers/runs.py::list_events``).

Prior to this fix, the relay emitted the raw agent-server payload while
the bootstrap emitted the projected ToolEvent shape. Any new field added
to the BFF projection would fail to reach live socket clients.

The test asserts:
  1. ``event_relay._run_loop`` calls ``normalize_event`` on every fetched
     dict-shaped event before ``_emit``.
  2. The wire payload delivered to ``sio.emit`` has the projected keys
     ({id, eventId, type, timestamp, summary, raw}) and NOT the raw
     agent-server keys ({kind}).
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def relay_module():
    from bff.services import event_relay

    return event_relay


@pytest.mark.asyncio
async def test_relay_emits_normalized_wire_shape(relay_module: Any) -> None:
    """Every event forwarded over Socket.IO must be the projected ToolEvent shape."""
    cid = "conv-normalize-tripwire"
    raw_action = {
        "id": "ev-1",
        "kind": "ActionEvent",
        "timestamp": "2026-08-05T23:00:00Z",
        "source": "agent",
        "action": {"tool": "shell", "arguments": {"command": "ls"}},
        "security_risk": "LOW",
    }
    # Second event: also a dict but a MessageEvent (exercises another branch).
    raw_message = {
        "id": "ev-2",
        "kind": "MessageEvent",
        "timestamp": "2026-08-05T23:00:01Z",
        "source": "user",
        "content": [{"type": "text", "text": "hi"}],
    }
    events_page: list[dict[str, Any]] = [raw_action, raw_message]

    # Mock the sio server so we can inspect emissions.
    sio_mock = MagicMock()
    sio_mock.emit = AsyncMock()
    relay_module.set_sio(sio_mock)

    # Patch the internal helpers so _run_loop reaches the emit block on the
    # first iteration, then hits a terminal status and returns.
    #
    # _run_loop control flow per iteration (see bff/services/event_relay.py):
    #   1. status = _fetch_status(cid)
    #   2. if status changed: emit 'status' (and maybe 'approval_required')
    #   3. events, next_page = _fetch_page(cid, page_id)
    #   4. for ev in events: emit 'event'  <-- our tripwire target
    #   5. if status in _TERMINAL_STATUSES: return
    #
    # The terminal check is AFTER the event emissions, so we need
    # _fetch_page to return the raw events on the first call and an
    # empty page on the second — otherwise the same events emit twice.
    call_counter = {"status": 0, "page": 0}

    async def fake_fetch_conversation(_cid: str) -> dict[str, Any]:
        return {"execution_status": "running", "workspace": {}}

    async def fake_fetch_status(_cid: str) -> str:
        call_counter["status"] += 1
        # Iteration 1: still running so we enter the events loop.
        # Iteration 2: terminal so _run_loop returns cleanly.
        return "running" if call_counter["status"] == 1 else "finished"

    async def fake_fetch_page(
        _cid: str, _page_id: str | None
    ) -> tuple[list[dict[str, Any]], str | None]:
        call_counter["page"] += 1
        # Only the first fetch returns real events. Second fetch is
        # empty so the terminal-status check on iteration 2 can return
        # without re-emitting the same page.
        if call_counter["page"] == 1:
            return events_page, None
        return [], None

    with (
        patch.object(relay_module, "_fetch_conversation", fake_fetch_conversation),
        patch.object(relay_module, "_fetch_status", fake_fetch_status),
        patch.object(relay_module, "_fetch_page", fake_fetch_page),
        patch.object(relay_module.sidecar_producers, "reset_accumulator", MagicMock()),
    ):
        await asyncio.wait_for(relay_module._run_loop(cid), timeout=2.0)

    # Filter to just the 'event' emissions (skip 'status'/'approval_required').
    event_emissions = [
        call for call in sio_mock.emit.call_args_list if call.args[0] == "event"
    ]
    assert len(event_emissions) == 2, (
        f"expected 2 'event' emissions, got {len(event_emissions)}: "
        f"{[c.args for c in event_emissions]}"
    )

    for call in event_emissions:
        _name, payload = call.args
        assert isinstance(payload, dict)
        # Projected ToolEvent keys must be present.
        assert "type" in payload, f"missing 'type' in wire payload: {payload}"
        assert "summary" in payload, f"missing 'summary' in wire payload: {payload}"
        assert "raw" in payload, f"missing 'raw' in wire payload: {payload}"
        assert "eventId" in payload, f"missing 'eventId' in wire payload: {payload}"
        # Raw agent-server key must NOT be at the top level (only inside .raw).
        assert "kind" not in payload, (
            f"raw 'kind' key leaked into wire payload — normalization skipped: {payload}"
        )
        # The original raw event must be preserved for debugging.
        assert isinstance(payload["raw"], dict)
        assert payload["raw"].get("kind") in {"ActionEvent", "MessageEvent"}

    # Sanity: the ActionEvent projection must expose the ToolEvent type.
    action_payload = next(
        c.args[1]
        for c in event_emissions
        if c.args[1]["raw"].get("kind") == "ActionEvent"
    )
    assert action_payload["type"] == "action"
    # Stage 3.1 risk projection must survive the wire.
    assert action_payload.get("securityRisk") == "LOW"

"""bff/services/search_events.py — WebSearchEvent producer (Stage 6.1).

Sibling of ``bff/services/memory_events.py``. Authors the *raw* event dict
that ``event_normalize.normalize_event`` turns into a wire event of type
``"web_search"``. Two entry points:

- :func:`build_web_search_event` — pure factory. Returns a dict shaped
  identically to what agent-server would emit for a native event kind:
  ``id``, ``kind``, ``timestamp``, ``source``, plus the semantic fields
  ``query`` / ``result_count`` / ``provenance`` / ``latency_ms``.

- :func:`emit_web_search` — side-effecting wrapper that builds the raw
  event, normalizes it via ``event_normalize.normalize_event``, and
  pushes it onto the Socket.IO room for the given conversation via
  ``event_relay._emit``. Returns the normalized wire event so callers
  can also persist / assert.

Called by ``bff/routers/search.py :: emit_search`` when the ``search_web``
tool posts to the bridge endpoint from agent-server.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from bff.services.event_normalize import normalize_event

__all__ = [
    "WEB_SEARCH_KIND",
    "build_web_search_event",
    "emit_web_search",
]


WEB_SEARCH_KIND = "WebSearchEvent"
"""Raw event ``kind`` string. Matches _KIND_TO_TYPE mapping in event_normalize."""


def build_web_search_event(
    *,
    conversation_id: str,
    query: str,
    result_count: int,
    provenance: str,
    latency_ms: int,
    event_id: str | None = None,
    timestamp: datetime | None = None,
    source: str = "search",
) -> dict[str, Any]:
    """Build the raw event dict for a web-search consultation.

    Parameters
    ----------
    conversation_id
        Run / conversation UUID. Set as ``runId`` on the raw event so the
        frontend can tag it without parsing the socket room name.
    query
        The verbatim search query string.
    result_count
        Number of hits returned by the underlying SearchPort call.
    provenance
        Adapter provenance string (e.g. ``"searxng:http://127.0.0.1:18888"``).
        Forwarded verbatim on the wire.
    latency_ms
        Wall-clock adapter latency, integer milliseconds.
    event_id
        Optional caller-supplied UUID. When ``None`` a random one is generated.
    timestamp
        Optional caller-supplied timestamp. Defaults to ``datetime.now`` UTC.
    source
        Origin tag; defaults to ``"search"``.
    """
    if not isinstance(conversation_id, str) or not conversation_id:
        raise ValueError(
            "build_web_search_event: conversation_id must be a non-empty string"
        )
    if not isinstance(query, str):
        raise ValueError("build_web_search_event: query must be a string")
    if not isinstance(result_count, int) or isinstance(result_count, bool):
        raise ValueError(
            "build_web_search_event: result_count must be an int "
            f"(got {type(result_count).__name__})"
        )
    if result_count < 0:
        raise ValueError(
            f"build_web_search_event: result_count must be >= 0, got {result_count}"
        )
    if not isinstance(provenance, str):
        raise ValueError("build_web_search_event: provenance must be a string")
    if not isinstance(latency_ms, int) or isinstance(latency_ms, bool):
        raise ValueError(
            "build_web_search_event: latency_ms must be an int "
            f"(got {type(latency_ms).__name__})"
        )
    if latency_ms < 0:
        raise ValueError(
            f"build_web_search_event: latency_ms must be >= 0, got {latency_ms}"
        )

    ts = timestamp or datetime.now(timezone.utc)
    return {
        "id": event_id or str(uuid.uuid4()),
        "kind": WEB_SEARCH_KIND,
        "timestamp": ts.isoformat(),
        "source": source,
        "runId": conversation_id,
        "query": query,
        "result_count": int(result_count),
        "provenance": provenance,
        "latency_ms": int(latency_ms),
    }


async def emit_web_search(
    *,
    conversation_id: str,
    query: str,
    result_count: int,
    provenance: str,
    latency_ms: int,
    event_id: str | None = None,
    timestamp: datetime | None = None,
    source: str = "search",
) -> dict[str, Any]:
    """Build, normalize, and push a WebSearchEvent to the client.

    Uses the same wire pathway as ``emit_memory_consultation``:
    ``normalize_event(raw)`` -> ``_sio.emit("event", wire, room=...)``.

    Best-effort — if Socket.IO isn't wired up (unit tests, CLI usage),
    the normalization still runs and the wire event is returned but no
    remote emission occurs. Never raises on emit failure.
    """
    from bff.services import event_relay  # lazy import to avoid cycle at boot

    raw = build_web_search_event(
        conversation_id=conversation_id,
        query=query,
        result_count=result_count,
        provenance=provenance,
        latency_ms=latency_ms,
        event_id=event_id,
        timestamp=timestamp,
        source=source,
    )
    wire = normalize_event(raw)
    room = f"conversationId={conversation_id}"
    try:
        await event_relay._emit(room, "event", wire)
    except Exception:  # pragma: no cover - defensive
        pass
    return wire

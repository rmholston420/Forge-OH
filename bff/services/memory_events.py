"""bff/services/memory_events.py — MemoryConsultationEvent producer.

Stage 5.6a (ADR-024). This module authors the *raw* event dict that the
existing ``event_normalize.normalize_event`` projector turns into a wire
event of type ``"memory_consultation"``. Two entry points:

- :func:`build_memory_consultation_event` — pure factory. Returns a dict
  shaped identically to what agent-server would emit for a native event
  kind: ``id``, ``kind``, ``timestamp``, ``source``, plus the semantic
  fields ``tier`` / ``query`` / ``result_count``. Deterministic and
  easily testable.

- :func:`emit_memory_consultation` — side-effecting wrapper that builds
  the raw event, normalizes it via ``event_normalize.normalize_event``,
  and pushes it onto the Socket.IO room for the given conversation via
  ``event_relay._emit``. Returns the normalized wire event so callers
  can also persist / assert.

Not yet wired to any caller (ADR-023 D7: curated_write is library-only
until a higher-stack tool exists). Ready to be called from the future
``consult_memory`` tool in Stage 5.6b or from any Kosmos-side caller.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from bff.services.event_normalize import normalize_event

__all__ = [
    "MEMORY_CONSULTATION_KIND",
    "build_memory_consultation_event",
    "emit_memory_consultation",
]


MEMORY_CONSULTATION_KIND = "MemoryConsultationEvent"
"""Raw event ``kind`` string. Matches _KIND_TO_TYPE mapping in event_normalize."""


def build_memory_consultation_event(
    *,
    conversation_id: str,
    tier: str,
    query: str,
    result_count: int,
    event_id: str | None = None,
    timestamp: datetime | None = None,
    source: str = "memory",
) -> dict[str, Any]:
    """Build the raw event dict for a memory consultation.

    Parameters
    ----------
    conversation_id
        Run / conversation UUID. Set as ``runId`` on the raw event so the
        frontend can tag it without parsing the socket room name.
    tier
        Memory tier label. Free-form but expected to be one of
        ``"semantic"``, ``"temporal"``, ``"episodic"``.
    query
        The search query string (verbatim; caller decides whether to
        truncate for privacy).
    result_count
        Number of hits returned by the underlying MemoryPort call.
    event_id
        Optional caller-supplied UUID. When ``None`` a random one is
        generated. Same UUID space as agent-server events.
    timestamp
        Optional caller-supplied timestamp. Defaults to ``datetime.now``
        in UTC.
    source
        Origin tag; defaults to ``"memory"``. Not the same field as
        ``ActionEvent.source``.
    """
    if not isinstance(conversation_id, str) or not conversation_id:
        raise ValueError(
            "build_memory_consultation_event: conversation_id must be a "
            "non-empty string"
        )
    if not isinstance(tier, str) or not tier:
        raise ValueError(
            "build_memory_consultation_event: tier must be a non-empty string"
        )
    if not isinstance(query, str):
        raise ValueError(
            "build_memory_consultation_event: query must be a string"
        )
    if not isinstance(result_count, int) or isinstance(result_count, bool):
        raise ValueError(
            "build_memory_consultation_event: result_count must be an int "
            f"(got {type(result_count).__name__})"
        )
    if result_count < 0:
        raise ValueError(
            f"build_memory_consultation_event: result_count must be >= 0, "
            f"got {result_count}"
        )

    ts = timestamp or datetime.now(timezone.utc)
    return {
        "id": event_id or str(uuid.uuid4()),
        "kind": MEMORY_CONSULTATION_KIND,
        "timestamp": ts.isoformat(),
        "source": source,
        "runId": conversation_id,
        "tier": tier,
        "query": query,
        "result_count": int(result_count),
    }


async def emit_memory_consultation(
    *,
    conversation_id: str,
    tier: str,
    query: str,
    result_count: int,
    event_id: str | None = None,
    timestamp: datetime | None = None,
    source: str = "memory",
) -> dict[str, Any]:
    """Build, normalize, and push a MemoryConsultationEvent to the client.

    Uses the same wire pathway as the event relay:
    ``normalize_event(raw)`` -> ``_sio.emit("event", wire, room=...)``.

    Best-effort — if Socket.IO isn't wired up (unit tests, CLI usage),
    the normalization still runs and the wire event is returned but no
    remote emission occurs. Never raises on emit failure.
    """
    from bff.services import event_relay  # lazy import to avoid cycle at boot

    raw = build_memory_consultation_event(
        conversation_id=conversation_id,
        tier=tier,
        query=query,
        result_count=result_count,
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

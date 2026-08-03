"""Trajectory sidecar producers (Slice F.15).

The trajectory STOP hook reads
``$WORKSPACE/.forge-oh/trajectory-sidecar.json`` at run completion to
build the ``TrajectoryRecord``. F.12 seeded ``task_description`` at
conversation-create time. F.15 keeps the other sidecar fields
(``plan``, ``symptom``, ``diffs``, ``repograph_symbols``) up to date
by tapping the event stream that already flows through
:mod:`bff.services.event_relay`.

Design
------

* **Additive, best-effort.** Every producer wraps its own I/O in a
  broad ``except`` — a badly-shaped event must never break the relay
  loop or crash the run.
* **Idempotent per-field.** Each producer computes the latest value
  for its field and writes the whole thing back. ``update_sidecar``
  atomically read-modify-writes under ``fcntl.LOCK_EX`` so concurrent
  writers can't corrupt the file.
* **Off the hot path.** Sidecar writes happen after the relay has
  already emitted the event to socket.io, so producer latency doesn't
  delay the frontend. All producers are synchronous (they hit local
  disk, not the network) and bounded to a few ms per call.
* **Per-conversation event accumulator.** Some producers
  (``diffs``, ``plan``) need the full event history for a
  conversation to compute their state, but event_relay hands us
  events one page at a time. We keep a small in-memory
  accumulator keyed by conversation id so we can re-run the
  reconstruction incrementally without re-fetching the full page
  every time.

Public API
----------

``update_from_event(cid, workspace, event)`` — call once per event
    forwarded by the relay. Runs every producer.
``reset_accumulator(cid)`` — clear the in-memory buffer for a
    conversation, e.g. when its relay terminates.
"""

from __future__ import annotations

import logging
from typing import Any

from bff.services import action_reconstruction, file_diff_reconstruction
from bff.services.sidecar import update_sidecar

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-conversation event accumulator
# ---------------------------------------------------------------------------

# We keep only the smallest possible slice of events per conversation:
# just the ones the producers actually consume. This bounds memory in
# very long-running sessions.

_events_by_cid: dict[str, list[dict[str, Any]]] = {}

# Hard cap: if a conversation streams more than this many events,
# drop older ones to bound memory. 5000 is generous — a typical run
# emits 50-200 events; a pathological loop could emit thousands.
_MAX_EVENTS_PER_CID = 5000


def _append(cid: str, event: dict[str, Any]) -> list[dict[str, Any]]:
    """Append ``event`` to the accumulator and return the full list."""
    buf = _events_by_cid.setdefault(cid, [])
    buf.append(event)
    if len(buf) > _MAX_EVENTS_PER_CID:
        # Drop the oldest 10% at once rather than per-append so the
        # amortized cost stays O(1).
        drop = _MAX_EVENTS_PER_CID // 10
        del buf[:drop]
        log.warning(
            "sidecar_producers[%s]: event buffer capped, dropped %d oldest events",
            cid,
            drop,
        )
    return buf


def reset_accumulator(cid: str) -> None:
    """Discard the in-memory event buffer for a conversation.

    Called by event_relay when the conversation reaches a terminal
    status, or by tests that need clean isolation.
    """
    _events_by_cid.pop(cid, None)


# ---------------------------------------------------------------------------
# Individual producers
# ---------------------------------------------------------------------------


def _produce_plan(events: list[dict[str, Any]], cid: str) -> str | None:
    """Extract a plan-text snapshot from accumulated events.

    We use :func:`action_reconstruction.build_plan` which is the same
    code path the ``/api/runs/{id}/plan`` endpoint uses, so the
    trajectory-side plan can't diverge from the frontend-side plan.

    Returns the plan rendered as newline-separated ``title (status)``
    lines, or ``None`` if no plan events were observed. Empty string
    is deliberately NOT returned — it would clear a previously
    populated field.
    """
    try:
        steps = action_reconstruction.build_plan(events, cid)
    except Exception:
        log.debug("sidecar_producers[%s]: build_plan raised", cid, exc_info=True)
        return None
    if not steps:
        return None
    lines: list[str] = []
    for step in steps:
        title = str(step.get("title") or step.get("content") or "").strip()
        status = str(step.get("status") or "").strip()
        if not title:
            continue
        lines.append(f"{title} ({status})" if status else title)
    return "\n".join(lines) if lines else None


def _produce_diffs(events: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Extract file-diff summaries from accumulated events.

    Uses :func:`file_diff_reconstruction.build_summaries` — same code
    path the ``/api/runs/{id}/summaries`` endpoint uses. Each entry
    is coerced into the ``TrajectoryDiff`` shape (``path``,
    ``lines_added``, ``lines_removed``, ``summary``) so the STOP hook
    can consume it without further transformation.
    """
    try:
        summaries = file_diff_reconstruction.build_summaries(events)
    except Exception:
        log.debug("sidecar_producers: build_summaries raised", exc_info=True)
        return None
    if not summaries:
        return None
    out: list[dict[str, Any]] = []
    for s in summaries:
        path = s.get("path")
        if not isinstance(path, str) or not path:
            continue
        added = s.get("linesAdded") or s.get("lines_added") or 0
        removed = s.get("linesRemoved") or s.get("lines_removed") or 0
        try:
            added_int = max(0, int(added))
            removed_int = max(0, int(removed))
        except (TypeError, ValueError):
            added_int, removed_int = 0, 0
        summary = str(s.get("summary") or "")
        out.append(
            {
                "path": path,
                "lines_added": added_int,
                "lines_removed": removed_int,
                "summary": summary,
            }
        )
    return out or None


# Verify-observation events emit a symptom via a well-known content
# shape. We match on both the raw agent-server envelope and the
# normalized shape defensively.
_SYMPTOM_KEYS = ("symptom", "verify_symptom", "failure_reason")


def _extract_symptom_from_event(event: dict[str, Any]) -> str | None:
    """Best-effort: pull a symptom string out of a verify observation."""
    # 1. Direct top-level key.
    for key in _SYMPTOM_KEYS:
        val = event.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    # 2. Nested under ``observation`` or ``content``.
    for container_key in ("observation", "content", "extras", "data"):
        container = event.get(container_key)
        if isinstance(container, dict):
            for key in _SYMPTOM_KEYS:
                val = container.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
    return None


def _produce_symptom(events: list[dict[str, Any]]) -> str | None:
    """Return the most recent symptom emitted by any event.

    Walks the accumulator in reverse so the freshest symptom wins.
    Returns ``None`` if no event carried one, so the sidecar's
    existing value is preserved by ``update_sidecar``'s merge
    semantics.
    """
    for event in reversed(events):
        if not isinstance(event, dict):
            continue
        sym = _extract_symptom_from_event(event)
        if sym:
            return sym
    return None


# RepoGraph-lookup actions announce which symbols they queried via
# well-known keys on the action envelope. We accumulate the union of
# symbols across all such actions in a single run.
_REPOGRAPH_ACTION_KINDS = frozenset(
    {"repograph.search", "repograph.symbol_lookup", "repograph_query"}
)
_SYMBOL_KEYS = ("symbols", "symbol_ids", "query_symbols")


def _extract_symbols_from_event(event: dict[str, Any]) -> list[str]:
    """Pull symbol ids from a RepoGraph-related event, if any."""
    kind = event.get("action") or event.get("actionKind") or event.get("kind")
    if isinstance(kind, str) and kind.lower() not in _REPOGRAPH_ACTION_KINDS:
        # Only care about RepoGraph actions; skip other events cheaply.
        # We still fall through if ``kind`` is missing entirely so a
        # bare payload with symbol keys is not silently ignored.
        return []
    collected: list[str] = []
    for container in (event, event.get("args"), event.get("params")):
        if not isinstance(container, dict):
            continue
        for key in _SYMBOL_KEYS:
            val = container.get(key)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and item.strip():
                        collected.append(item.strip())
    return collected


def _produce_repograph_symbols(events: list[dict[str, Any]]) -> list[str] | None:
    """Union of all RepoGraph symbols queried during the run.

    Order-preserving deduplication so the first-observed symbol
    always appears first in the trajectory record.
    """
    seen: dict[str, None] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        for sym in _extract_symbols_from_event(event):
            seen.setdefault(sym, None)
    return list(seen.keys()) or None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def update_from_event(
    *,
    cid: str,
    workspace: str,
    session_id: str,
    event: dict[str, Any],
) -> None:
    """Update the sidecar based on a single relay event.

    ``cid`` is the conversation id (used as the accumulator key AND
    the ``run_id`` context for ``build_plan``); ``session_id`` is the
    sidecar key (matches OPENHANDS_SESSION_ID, i.e. also the
    conversation id in Forge-OH).

    Any exception in a producer is caught and logged at DEBUG; the
    event relay must never fail because a sidecar write failed.
    """
    if not workspace or not session_id or not isinstance(event, dict):
        return
    events = _append(cid, event)

    fields: dict[str, Any] = {}

    # Symptom + symbols are cheap per-event; compute on every call.
    try:
        symptom = _produce_symptom(events)
        if symptom is not None:
            fields["symptom"] = symptom
    except Exception:
        log.debug("sidecar_producers[%s]: symptom producer raised", cid, exc_info=True)

    try:
        symbols = _produce_repograph_symbols(events)
        if symbols is not None:
            fields["repograph_symbols"] = symbols
    except Exception:
        log.debug("sidecar_producers[%s]: symbols producer raised", cid, exc_info=True)

    # Plan + diffs are O(len(events)); still fine at 5000-event cap
    # (worst case a few ms per call). Compute on every event so the
    # sidecar always reflects the freshest state — the STOP hook may
    # read at any moment.
    try:
        plan_text = _produce_plan(events, cid)
        if plan_text is not None:
            fields["plan"] = plan_text
    except Exception:
        log.debug("sidecar_producers[%s]: plan producer raised", cid, exc_info=True)

    try:
        diffs = _produce_diffs(events)
        if diffs is not None:
            fields["diffs"] = diffs
    except Exception:
        log.debug("sidecar_producers[%s]: diffs producer raised", cid, exc_info=True)

    if not fields:
        return

    try:
        update_sidecar(
            workspace=workspace,
            session_id=session_id,
            fields=fields,
        )
    except Exception:
        log.debug(
            "sidecar_producers[%s]: update_sidecar raised", cid, exc_info=True
        )


__all__ = (
    "reset_accumulator",
    "update_from_event",
)

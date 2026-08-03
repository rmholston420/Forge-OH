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
        # ``file_diff_reconstruction.build_summaries`` uses the
        # frontend-facing key names (``additions``/``deletions``); the
        # older ``linesAdded``/``lines_added`` fallbacks are kept in
        # case an upstream refactor changes the shape.
        added = (
            s.get("additions")
            or s.get("linesAdded")
            or s.get("lines_added")
            or 0
        )
        removed = (
            s.get("deletions")
            or s.get("linesRemoved")
            or s.get("lines_removed")
            or 0
        )
        try:
            added_int = max(0, int(added))
            removed_int = max(0, int(removed))
        except (TypeError, ValueError):
            added_int, removed_int = 0, 0
        status = str(s.get("status") or "")
        summary = str(s.get("summary") or status)
        out.append(
            {
                "path": path,
                "lines_added": added_int,
                "lines_removed": removed_int,
                "summary": summary,
            }
        )
    return out or None


# The real agent-server event schema (verified F.15 fixup) has NO
# top-level ``symptom`` key. Failures surface as:
#   * ObservationEvent with observation.is_error == True (any tool)
#   * ObservationEvent w/ TerminalObservation + exit_code != 0
#   * HookExecutionEvent with success == False, or verify verdict of
#     ``failed``/``error`` inside its stdout JSON payload.
#
# We ALSO honor the legacy top-level ``symptom``/``verify_symptom``/
# ``failure_reason`` keys so a future refactor that adds them can't
# regress silently.

_SYMPTOM_KEYS = ("symptom", "verify_symptom", "failure_reason")
_VERIFY_FAILING_VERDICTS = frozenset({"failed", "error", "fail"})
_MAX_SYMPTOM_LEN = 500


def _flatten_content_text(container: Any) -> str:
    """Collapse a ``content`` list-of-dicts into a single string.

    Both ``ObservationEvent.observation.content`` and
    ``ActionEvent.action.content`` follow the OpenHands wire format:
    a list of ``{"type": "text", "text": "..."}`` chunks.
    """
    if isinstance(container, str):
        return container.strip()
    if isinstance(container, list):
        parts: list[str] = []
        for item in container:
            if isinstance(item, dict):
                txt = item.get("text")
                if isinstance(txt, str) and txt.strip():
                    parts.append(txt.strip())
            elif isinstance(item, str) and item.strip():
                parts.append(item.strip())
        return " ".join(parts).strip()
    return ""


def _truncate(text: str) -> str:
    text = text.strip()
    if len(text) <= _MAX_SYMPTOM_LEN:
        return text
    return text[: _MAX_SYMPTOM_LEN - 1].rstrip() + "…"


def _extract_symptom_from_event(event: dict[str, Any]) -> str | None:
    """Best-effort: derive a symptom string from a single event.

    Order of precedence:

    1. Legacy top-level key (future-proofing).
    2. HookExecutionEvent that reports failure.
    3. ObservationEvent with an error signal (is_error / exit_code).
    4. Nested legacy keys.
    """
    # 1. Legacy top-level.
    for key in _SYMPTOM_KEYS:
        val = event.get(key)
        if isinstance(val, str) and val.strip():
            return _truncate(val)

    kind = event.get("kind")

    # 2. HookExecutionEvent — verify hook fires here.
    if kind == "HookExecutionEvent":
        success = event.get("success")
        # Try the parsed JSON in stdout first — it names the verdict.
        stdout = event.get("stdout")
        parsed: dict[str, Any] | None = None
        if isinstance(stdout, str) and stdout.strip():
            import json as _json

            try:
                candidate = _json.loads(stdout)
            except Exception:
                candidate = None
            if isinstance(candidate, dict):
                parsed = candidate
        if parsed is not None:
            ctx = parsed.get("additionalContext") if isinstance(
                parsed.get("additionalContext"), dict
            ) else {}
            verdict = ctx.get("verdict") or parsed.get("verdict")
            if isinstance(verdict, str) and verdict.lower() in _VERIFY_FAILING_VERDICTS:
                reason = parsed.get("reason") or ctx.get("stderr_tail")
                if isinstance(reason, str) and reason.strip():
                    return _truncate(f"verify {verdict}: {reason}")
                return _truncate(f"verify {verdict}")
        if success is False:
            # Fall back to the hook's ``reason`` or stderr.
            reason = event.get("reason") or event.get("stderr")
            if isinstance(reason, str) and reason.strip():
                return _truncate(f"hook failed: {reason}")
            return "hook failed"

    # 3. ObservationEvent — any tool that errored.
    if kind == "ObservationEvent":
        obs = event.get("observation")
        if isinstance(obs, dict):
            is_error = bool(obs.get("is_error"))
            exit_code = obs.get("exit_code")
            terminal_failed = (
                obs.get("kind") == "TerminalObservation"
                and isinstance(exit_code, int)
                and exit_code != 0
            )
            if is_error or terminal_failed:
                text = _flatten_content_text(obs.get("content"))
                obs_kind = obs.get("kind") or "tool"
                if text:
                    if terminal_failed:
                        return _truncate(f"{obs_kind} exit={exit_code}: {text}")
                    return _truncate(f"{obs_kind} error: {text}")
                if terminal_failed:
                    return _truncate(f"{obs_kind} exit={exit_code}")
                return _truncate(f"{obs_kind} error")

    # 4. Nested legacy keys (kept for defensive matching).
    for container_key in ("observation", "content", "extras", "data"):
        container = event.get(container_key)
        if isinstance(container, dict):
            for key in _SYMPTOM_KEYS:
                val = container.get(key)
                if isinstance(val, str) and val.strip():
                    return _truncate(val)
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


# RepoGraph-lookup actions announce which symbols they queried. In
# the real agent-server schema an action's payload lives under
# ``event.action`` (a dict with its own ``kind``). We match by
# either the outer ``event.kind`` (rare RepoGraph tool events) or
# the inner ``event.action.kind`` (normal case).
_REPOGRAPH_ACTION_KINDS = frozenset(
    {
        "repograph.search",
        "repograph.symbol_lookup",
        "repograph_query",
        # Camel/PascalCase variants we may see if RepoGraph is
        # wired in later as a first-class OpenHands tool.
        "repographsearchaction",
        "repographlookupaction",
        "repographqueryaction",
    }
)
_SYMBOL_KEYS = ("symbols", "symbol_ids", "query_symbols")


def _iter_action_kinds(event: dict[str, Any]) -> list[str]:
    """Return every candidate ``kind`` string for RepoGraph matching."""
    kinds: list[str] = []
    for k in (event.get("kind"), event.get("actionKind")):
        if isinstance(k, str):
            kinds.append(k.lower())
    inner = event.get("action")
    if isinstance(inner, dict):
        k2 = inner.get("kind")
        if isinstance(k2, str):
            kinds.append(k2.lower())
    elif isinstance(inner, str):
        # Older shape: ``action`` was the kind string itself.
        kinds.append(inner.lower())
    return kinds


def _extract_symbols_from_event(event: dict[str, Any]) -> list[str]:
    """Pull symbol ids from a RepoGraph-related event, if any."""
    kinds = _iter_action_kinds(event)
    if kinds and not any(k in _REPOGRAPH_ACTION_KINDS for k in kinds):
        # No RepoGraph kind matched; skip cheaply.
        return []
    collected: list[str] = []
    # Search both the outer envelope and the nested ``action`` /
    # ``args`` / ``params`` payloads for symbol lists.
    action_payload = event.get("action") if isinstance(event.get("action"), dict) else {}
    for container in (
        event,
        action_payload,
        event.get("args"),
        event.get("params"),
        action_payload.get("args") if isinstance(action_payload.get("args"), dict) else None,
    ):
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

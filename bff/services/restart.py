"""Restart-from-here composition (ADR-026, Stage 6.4c).

Given a source ``run_id`` and an ``anchor_event_id``, mint a NEW run whose
worktree is checked out at the commit sha captured for that event, seeded
with the anchor's user-message text as the initial prompt.

Composition (order matters — rollback is defined by it):

    1. Fetch source conversation from agent-server (must exist).
    2. Bulk-lookup ``anchor_event_id`` in ``event_commit_ledger`` (must resolve).
    3. Fetch source events search page containing the anchor id (must be
       a ``MessageEvent`` with ``source == "user"``).
    4. Resolve source repo from the source conversation's ``working_dir``.
    5. Mint a fresh ``run_id`` and provision a worktree at the anchor sha.
    6. POST /api/conversations with the fresh worktree + the source's agent
       config. Rollback the worktree on any failure here.
    7. POST /api/conversations/{new_cid}/events seeded with the anchor's
       message text. Rollback the worktree on failure here (agent-server
       leaves the conversation orphaned; log but do not attempt cleanup —
       agent-server rejects DELETE on freshly-created conversations
       inconsistently).
    8. Best-effort: capture the seeded event's own sha in the ledger so
       the seeded prompt is itself a restart anchor.
    9. Return ``RestartResult``.

Every failure raises ``RestartError`` with a discriminated ``code`` field
so the router can map cleanly to HTTP status.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from bff.openhands_client import get_client
from bff.services import event_commit_ledger
from bff.services.worktree import (
    WorktreeError,
    _resolve_source_repo_for_worktree,
    head_sha,
    provision_worktree,
    remove_worktree,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RestartError(Exception):
    """Base exception for restart_from_here failures.

    ``code`` is a stable enum-ish string the router uses to pick the HTTP
    status.  Never displayed to end-users verbatim.
    """

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


# code enum:
#   source_not_found      → 404
#   anchor_not_found      → 404 (event id not in source events)
#   no_sha_anchor         → 409 (event exists but ledger has no sha row)
#   not_user_message      → 409 (event is not a MessageEvent w/ source=user)
#   source_no_working_dir → 409 (source conv has no worktree at all)
#   worktree_failed       → 502
#   create_failed         → 502
#   seed_failed           → 502
#   upstream_error        → 502 (generic 5xx from agent-server)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class RestartResult:
    """Payload returned to the router on success."""

    restarted_run_id: str
    source_run_id: str
    from_event_id: str
    reset_to_sha: str
    worktree_path: str
    message_text: str


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def _extract_message_text(ev: dict[str, Any]) -> str:
    """Best-effort user-message-text extraction (agent-server 1.40.0 shape).

    Preferred: ``event.content[0].text`` (matches how ``create_run`` and
    ``send_run_message`` build their outbound payloads).  Falls back to
    ``event.message`` or ``event.text`` if the primary path is empty.

    Returns "" when nothing usable is found — the router surfaces this
    as ``not_user_message`` because a user message without text is
    indistinguishable from an assistant message here.
    """
    content = ev.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            txt = first.get("text")
            if isinstance(txt, str) and txt.strip():
                return txt
    for k in ("message", "text"):
        v = ev.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def _mint_run_id() -> str:
    """Same shape as create_run's ``worktree_run_id`` (``run-<hex12>``)."""
    return f"run-{_uuid.uuid4().hex[:12]}"


async def restart_from_here(
    app: FastAPI,
    *,
    source_run_id: str,
    anchor_event_id: str,
) -> RestartResult:
    """Implement ADR-026 restart-from-here.

    See module docstring for the ordered composition.  Raises
    ``RestartError`` on any failure so the router can map to HTTP.

    Ledger operations pass ``app`` positionally to match
    ``event_commit_ledger.record_sha`` / ``bulk_get_shas`` /
    ``delete_run`` signatures verified in step 1a.
    """
    client = get_client()

    # 1) Source conversation must exist.
    try:
        conv_resp = await client.get(f"/api/conversations/{source_run_id}")
    except Exception as exc:  # network / TCP
        raise RestartError("upstream_error", f"agent-server unreachable: {exc}") from exc
    if conv_resp.status_code == 404:
        raise RestartError("source_not_found", f"run {source_run_id!r} not found")
    if conv_resp.status_code >= 400:
        raise RestartError(
            "upstream_error",
            f"agent-server {conv_resp.status_code}: {conv_resp.text[:200]}",
        )
    conv = conv_resp.json() or {}
    workspace = conv.get("workspace") or {}
    source_working_dir = workspace.get("working_dir") or ""
    if not source_working_dir:
        raise RestartError(
            "source_no_working_dir",
            f"source run {source_run_id!r} has no working_dir; cannot restart",
        )

    # 2) Ledger must have a sha for (source_run_id, anchor_event_id).
    #    Passing app positionally per event_commit_ledger contract.
    sha_map: dict[str, str] = {}
    try:
        sha_map = await event_commit_ledger.bulk_get_shas(app, [anchor_event_id])
    except Exception as exc:
        raise RestartError(
            "upstream_error", f"ledger lookup failed: {exc}"
        ) from exc
    anchor_sha = sha_map.get(anchor_event_id) or ""
    if not anchor_sha:
        raise RestartError(
            "no_sha_anchor",
            f"no commit sha captured for event {anchor_event_id!r}; "
            "restart requires a user message authored while in a git worktree",
        )

    # 3) Anchor event must exist AND be a user MessageEvent.  Agent-server's
    #    /events/search endpoint doesn't take an id filter directly, but its
    #    ``event_id`` param does exact-match filtering when supported.  Fall
    #    back to fetching a bounded page and looking for the id there.
    ev = await _fetch_event(client, source_run_id, anchor_event_id)
    if ev is None:
        raise RestartError(
            "anchor_not_found",
            f"event {anchor_event_id!r} not found on run {source_run_id!r}",
        )
    ev_kind = ev.get("kind") or ev.get("type")
    ev_src = ev.get("source")
    if ev_kind != "MessageEvent" or ev_src != "user":
        raise RestartError(
            "not_user_message",
            f"event {anchor_event_id!r} is not a user MessageEvent "
            f"(kind={ev_kind!r}, source={ev_src!r})",
        )
    message_text = _extract_message_text(ev)
    if not message_text:
        # Contract: a user MessageEvent without extractable text is
        # indistinguishable from an assistant/tool event for restart
        # purposes.  Treat as not-user-message.
        raise RestartError(
            "not_user_message",
            f"event {anchor_event_id!r} carries no user-message text to seed with",
        )

    # 4) Resolve the source repo the worktree lives off.
    source_repo = _resolve_source_repo_for_worktree(Path(source_working_dir))
    if source_repo is None:
        # Non-worktree working_dir (bare path or the workspace root itself).
        # Fall back to using working_dir as the repo — provision_worktree
        # will still reject non-git dirs with WorktreeError.
        source_repo = Path(source_working_dir)

    # 5) Mint id + provision worktree at anchor sha.
    new_run_id = _mint_run_id()
    try:
        info = provision_worktree(new_run_id, source_repo, base_ref=anchor_sha)
    except WorktreeError as exc:
        raise RestartError(
            "worktree_failed",
            f"could not provision worktree at sha {anchor_sha[:12]}: {exc}",
        ) from exc

    new_working_dir = str(info.path)
    log.info(
        "restart: provisioned worktree %s at sha %s from source %s",
        new_run_id, anchor_sha, source_run_id,
    )

    # 6) POST /api/conversations reusing source agent config.
    agent_cfg = conv.get("agent") or {}
    workspace_kind = workspace.get("kind") or "LocalWorkspace"
    source_title = conv.get("title") or f"Run {source_run_id[:8]}"
    create_body: dict[str, Any] = {
        "workspace": {
            "working_dir": new_working_dir,
            "kind": workspace_kind,
        },
        "initial_message": None,  # seed via separate events POST for parity
        "agent": agent_cfg,
        "title": f"Restart of {source_title} @ {anchor_sha[:7]}",
    }
    # Preserve hook_config if the source had one (Stage F.8 verify/trajectory).
    if isinstance(conv.get("hook_config"), (dict, list)):
        create_body["hook_config"] = conv["hook_config"]

    try:
        create_resp = await client.post("/api/conversations", json=create_body)
    except Exception as exc:
        remove_worktree(new_run_id, missing_ok=True)
        raise RestartError(
            "create_failed", f"agent-server unreachable during create: {exc}"
        ) from exc
    if create_resp.status_code >= 400:
        remove_worktree(new_run_id, missing_ok=True)
        raise RestartError(
            "create_failed",
            f"agent-server rejected create ({create_resp.status_code}): "
            f"{create_resp.text[:200]}",
        )
    created = create_resp.json() or {}
    new_cid = (
        created.get("id")
        or created.get("conversation_id")
    )
    if not new_cid:
        remove_worktree(new_run_id, missing_ok=True)
        raise RestartError(
            "create_failed",
            f"agent-server create response missing id: {str(created)[:200]}",
        )

    # 7) Seed the new conversation with the anchor's user-message text.
    #    Matching send_run_message's body shape.
    try:
        events_resp = await client.post(
            f"/api/conversations/{new_cid}/events",
            json={
                "role": "user",
                "content": [{"type": "text", "text": message_text}],
                "run": True,  # kick off agent processing immediately
            },
        )
    except Exception as exc:
        remove_worktree(new_run_id, missing_ok=True)
        raise RestartError(
            "seed_failed", f"agent-server unreachable during seed: {exc}"
        ) from exc
    if events_resp.status_code >= 400:
        remove_worktree(new_run_id, missing_ok=True)
        raise RestartError(
            "seed_failed",
            f"agent-server rejected seed ({events_resp.status_code}): "
            f"{events_resp.text[:200]}",
        )

    # 8) Best-effort: stamp the seeded event's sha into the ledger so it
    #    itself is a restart anchor.  Never fails the outer operation.
    try:
        # Discover the just-created event via the same follow-up pattern
        # used by send_run_message.
        latest_resp = await client.get(
            f"/api/conversations/{new_cid}/events/search",
            params={"limit": 1, "sort_order": "CREATED_AT_DESC"},
        )
        if latest_resp.status_code < 400:
            payload = latest_resp.json() or {}
            latest = (
                payload if isinstance(payload, list)
                else (
                    payload.get("items")
                    or payload.get("data")
                    or payload.get("events")
                    or []
                )
            )
            if latest:
                seeded = latest[0] or {}
                seeded_id = seeded.get("id") or seeded.get("event_id")
                if seeded_id:
                    seeded_sha = head_sha(new_working_dir)
                    if seeded_sha:
                        await event_commit_ledger.record_sha(
                            app,
                            run_id=new_cid,
                            event_id=seeded_id,
                            commit_sha=seeded_sha,
                        )
                        log.info(
                            "restart: seeded event %s on new run %s stamped @ %s",
                            seeded_id, new_cid, seeded_sha[:12],
                        )
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("restart: seed-event sha capture failed: %s", exc)

    return RestartResult(
        restarted_run_id=new_cid,
        source_run_id=source_run_id,
        from_event_id=anchor_event_id,
        reset_to_sha=anchor_sha,
        worktree_path=new_working_dir,
        message_text=message_text,
    )


# ---------------------------------------------------------------------------
# Event lookup helper (bounded scan, agent-server has no id-filter API)
# ---------------------------------------------------------------------------


async def _fetch_event(
    client: Any, run_id: str, event_id: str, *, page_limit: int = 500
) -> dict[str, Any] | None:
    """Fetch an event by id from the source conversation.

    Uses ``GET /api/conversations/{run_id}/events/search?limit={N}`` and
    scans for a matching ``id`` field.  ``page_limit`` bounds the scan to
    prevent OOM on very long runs.

    Returns ``None`` if the id isn't in the first ``page_limit`` events.
    """
    try:
        resp = await client.get(
            f"/api/conversations/{run_id}/events/search",
            params={"limit": page_limit, "sort_order": "TIMESTAMP"},
        )
    except Exception as exc:
        raise RestartError(
            "upstream_error", f"agent-server unreachable during event fetch: {exc}"
        ) from exc
    if resp.status_code == 404:
        raise RestartError("source_not_found", f"run {run_id!r} not found")
    if resp.status_code >= 400:
        raise RestartError(
            "upstream_error",
            f"agent-server {resp.status_code}: {resp.text[:200]}",
        )
    payload = resp.json() or {}
    items = (
        payload if isinstance(payload, list)
        else (
            payload.get("items")
            or payload.get("data")
            or payload.get("events")
            or []
        )
    )
    for it in items:
        if not isinstance(it, dict):
            continue
        if (it.get("id") or it.get("event_id")) == event_id:
            return it
    return None

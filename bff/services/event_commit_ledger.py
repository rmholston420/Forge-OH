"""
bff/services/event_commit_ledger.py

Stage 6.4c (ADR-026 §Storage — option W2) — per-event commit-sha sidecar.

User-message events are authored by agent-server (see
`POST /api/conversations` `initial_message` in `bff.routers.runs.create_run`
and `POST /api/conversations/{id}/events` in `send_run_message`).  The
BFF never touches the event body, so `commit_sha_at_time_of_event` cannot
be stamped directly on the MessageEvent.

This module holds a small aiosqlite-backed mapping
`(run_id, event_id) -> commit_sha` that the BFF writes right after it
hands a user-message text to agent-server.  Event normalisation joins
against this table on the read path so the frontend sees the field
exactly as if agent-server had produced it.  Absent hits (pre-ADR-026
runs, or capture failures) downgrade gracefully: the frontend hides the
Restart button on those events.

Lifetime management follows the ``idempotency_ledger.py`` pattern:
``init_db(app)`` from the FastAPI lifespan startup handler opens a
single shared aiosqlite connection on ``app.state.event_commit_db``;
``close_db(app)`` closes it on shutdown.

Table schema:
  ``event_commit_shas``
    run_id      TEXT NOT NULL
    event_id    TEXT NOT NULL
    commit_sha  TEXT NOT NULL
    captured_at REAL NOT NULL   — unix epoch seconds
    PRIMARY KEY (run_id, event_id)

Indexes:
  ``idx_evshas_run`` on (run_id) for `delete_run` and future run-scoped
  queries.

Capture site contracts (both live in ``bff.routers.runs``):
  1. Right after ``POST /api/conversations`` succeeds in ``create_run``,
     the BFF does a follow-up ``GET /api/conversations/{id}/events?limit=1&order=asc``
     (per ADR-026 §Storage capture-point P1) to obtain the initial
     ``event_id``, runs ``git rev-parse HEAD`` in the freshly-provisioned
     worktree, and calls :func:`record_sha`.
  2. Right after ``POST /api/conversations/{id}/events`` succeeds in
     ``send_run_message``, the BFF reads the returned ``event.id``, runs
     ``git rev-parse HEAD`` in the run's worktree, and calls
     :func:`record_sha`.

Both capture sites treat write failures as non-fatal.  The user-facing
side effect on failure is that the Restart button will be hidden on
that specific event; the run itself is unaffected.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import aiosqlite
from fastapi import FastAPI

log = logging.getLogger(__name__)

DB_PATH = Path("data/event_commit_ledger.db")


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


async def init_db(app: FastAPI) -> None:
    """Open the shared DB connection and create tables. Call once at startup."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(DB_PATH))
    conn.row_factory = aiosqlite.Row
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_commit_shas (
            run_id      TEXT NOT NULL,
            event_id    TEXT NOT NULL,
            commit_sha  TEXT NOT NULL,
            captured_at REAL NOT NULL,
            PRIMARY KEY (run_id, event_id)
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_evshas_run ON event_commit_shas (run_id)"
    )
    await conn.commit()
    app.state.event_commit_db = conn


async def close_db(app: FastAPI) -> None:
    """Close the shared DB connection. Call once at shutdown."""
    conn: aiosqlite.Connection | None = getattr(app.state, "event_commit_db", None)
    if conn is not None:
        await conn.close()
        app.state.event_commit_db = None


def _get_conn(app: FastAPI) -> aiosqlite.Connection:
    conn: aiosqlite.Connection | None = getattr(app.state, "event_commit_db", None)
    if conn is None:
        raise RuntimeError(
            "event_commit_ledger: DB not initialised. "
            "Call init_db(app) from the FastAPI lifespan startup handler."
        )
    return conn


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------


async def record_sha(
    app: FastAPI,
    *,
    run_id: str,
    event_id: str,
    commit_sha: str,
) -> None:
    """Insert or replace the (run_id, event_id) -> commit_sha mapping.

    ``INSERT OR REPLACE`` is used because the primary key is
    ``(run_id, event_id)`` and a second capture for the same event
    (e.g. a retry loop) should overwrite rather than error.  This
    matches the "graceful-downgrade" contract in ADR-026 §Storage:
    absent rows hide the Restart button; a stale row is worse only in
    the pathological case of a same-event re-capture at a different
    HEAD, which never happens in practice (agent-server issues a
    fresh ``event_id`` per POST).

    All fields are required.  Empty strings for ``run_id``, ``event_id``,
    or ``commit_sha`` raise ``ValueError`` so a silent capture bug in
    the router surfaces at insert time rather than at the eventual
    read.
    """
    if not run_id:
        raise ValueError("event_commit_ledger.record_sha: run_id is required")
    if not event_id:
        raise ValueError("event_commit_ledger.record_sha: event_id is required")
    if not commit_sha:
        raise ValueError("event_commit_ledger.record_sha: commit_sha is required")
    conn = _get_conn(app)
    await conn.execute(
        "INSERT OR REPLACE INTO event_commit_shas "
        "(run_id, event_id, commit_sha, captured_at) VALUES (?, ?, ?, ?)",
        (run_id, event_id, commit_sha, time.time()),
    )
    await conn.commit()


# ---------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------


async def get_sha(app: FastAPI, event_id: str) -> str | None:
    """Return the commit sha for ``event_id``, or ``None`` if not recorded.

    ``event_id`` is unique across all runs in agent-server (UUID-shaped
    ids), so this lookup does not need ``run_id`` as a discriminator.
    The primary key remains ``(run_id, event_id)`` for cascade-delete
    ergonomics, not for lookup disambiguation.
    """
    if not event_id:
        return None
    conn = _get_conn(app)
    async with conn.execute(
        "SELECT commit_sha FROM event_commit_shas WHERE event_id = ? LIMIT 1",
        (event_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return row["commit_sha"] if row else None


async def bulk_get_shas(
    app: FastAPI, event_ids: list[str]
) -> dict[str, str]:
    """Bulk lookup — returns ``{event_id: commit_sha}`` for hits only.

    Used by the events read paths in ``bff.routers.runs`` to avoid N+1
    lookups when normalising a page of events.  Missing event_ids
    simply do not appear in the returned dict.
    """
    if not event_ids:
        return {}
    conn = _get_conn(app)
    # SQLite has a 999-parameter default limit; chunk defensively.
    out: dict[str, str] = {}
    CHUNK = 500
    for i in range(0, len(event_ids), CHUNK):
        chunk = event_ids[i : i + CHUNK]
        placeholders = ",".join("?" * len(chunk))
        query = (
            f"SELECT event_id, commit_sha FROM event_commit_shas "
            f"WHERE event_id IN ({placeholders})"
        )
        async with conn.execute(query, chunk) as cursor:
            async for row in cursor:
                out[row["event_id"]] = row["commit_sha"]
    return out


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


async def delete_run(app: FastAPI, run_id: str) -> int:
    """Delete all rows for ``run_id``.  Returns the row count deleted.

    Called from the existing ``DELETE /api/runs/{run_id}`` handler in
    ``bff.routers.runs`` so ledger rows are reaped alongside the run's
    conversation + worktree.
    """
    if not run_id:
        return 0
    conn = _get_conn(app)
    cursor = await conn.execute(
        "DELETE FROM event_commit_shas WHERE run_id = ?", (run_id,)
    )
    await conn.commit()
    return cursor.rowcount if cursor.rowcount is not None else 0

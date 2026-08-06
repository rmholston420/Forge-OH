"""
bff/services/idempotency_ledger.py

Stage 6.3 — durable exactly-once ledger for state-changing tool calls.

Lifetime management:
  Call ``init_db(app)`` from the FastAPI lifespan startup handler.
  A single shared aiosqlite connection is stored on
  ``app.state.idempotency_db`` and closed by ``close_db(app)`` on shutdown.
  Follows the ``episodic_memory.py`` pattern; do not open new connections
  per request.

Key design (see BUILD_LOG 2026-08-06 Stage 6.3 for the SDK probe):
  The OpenHands SDK does not expose ``task_id`` / ``step_index`` to a
  ``ToolExecutor``.  What is available at call time:
    * ``conversation.id`` — stable run identifier (BFF's ``runId``).
    * ``conversation.state.leaf_event_id`` — id of the last event before
      the pending tool action.  Deterministic across replay of the same
      LLM decision because the replayed action re-emerges at the same
      leaf.
    * ``tool_name`` — registered SDK tool name.
    * ``arguments`` — the pydantic ``Action`` model (dumped to JSON with
      sorted keys for hash stability).

  Idempotency key: sha256 of ``f"{conversation_id}|{leaf_event_id}|{tool_name}|{args_json}"``.
  If ``leaf_event_id`` is None (fresh conversation, no leaf yet) we use
  the sentinel string ``"root"`` — this preserves the "first tool call
  in a fresh conversation" case without letting two different fresh
  conversations collide (``conversation_id`` still differs).

  Rationale for including ``leaf_event_id`` (vs a monotonic step index):
    * SDK-native: no derived counter to keep in sync.
    * Replay-safe: the same LLM decision replayed after a crash re-emerges
      with the same leaf_event_id, so the key matches and the second
      execution is skipped.
    * Order-independent between concurrent conversations.

Table schema:
  ``completed_side_effects``
    idempotency_key TEXT PRIMARY KEY  — sha256 hex digest
    conversation_id TEXT NOT NULL
    leaf_event_id   TEXT NOT NULL     — "root" sentinel allowed
    tool_name       TEXT NOT NULL
    argument_hash   TEXT NOT NULL     — sha256 of sorted-keys JSON
    result_summary  TEXT              — first 500 chars of str(result)
    result_json     TEXT              — cached observation payload (JSON)
    completed_at    REAL NOT NULL     — unix epoch seconds

Indexes:
  ``idx_ledger_conversation`` on (conversation_id) for run-scoped queries.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import aiosqlite
from fastapi import FastAPI

DB_PATH = Path("data/idempotency_ledger.db")

LEAF_ROOT_SENTINEL = "root"


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
        CREATE TABLE IF NOT EXISTS completed_side_effects (
            idempotency_key TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            leaf_event_id   TEXT NOT NULL,
            tool_name       TEXT NOT NULL,
            argument_hash   TEXT NOT NULL,
            result_summary  TEXT,
            result_json     TEXT,
            completed_at    REAL NOT NULL
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ledger_conversation "
        "ON completed_side_effects (conversation_id)"
    )
    await conn.commit()
    app.state.idempotency_db = conn


async def close_db(app: FastAPI) -> None:
    """Close the shared DB connection. Call once at shutdown."""
    conn: aiosqlite.Connection | None = getattr(app.state, "idempotency_db", None)
    if conn is not None:
        await conn.close()
        app.state.idempotency_db = None


def _get_conn(app: FastAPI) -> aiosqlite.Connection:
    conn: aiosqlite.Connection | None = getattr(app.state, "idempotency_db", None)
    if conn is None:
        raise RuntimeError(
            "idempotency_ledger: DB not initialised. "
            "Call init_db(app) from the FastAPI lifespan startup handler."
        )
    return conn


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


def _canonical_args_json(arguments: dict) -> str:
    """Deterministic JSON serialization for hashing.

    ``sort_keys=True`` keeps dict-key order irrelevant.  ``default=str``
    lets us hash non-native types (e.g. pydantic model dumped values,
    ``Decimal``, ``datetime``) without a TypeError; the string cast is
    stable per Python's ``repr`` contract for these types.
    """
    return json.dumps(arguments, sort_keys=True, default=str, separators=(",", ":"))


def compute_argument_hash(arguments: dict) -> str:
    """Argument-only hash (sha256 hex).  Exposed for debugging + tests."""
    return hashlib.sha256(_canonical_args_json(arguments).encode()).hexdigest()


def compute_idempotency_key(
    conversation_id: str,
    leaf_event_id: str | None,
    tool_name: str,
    arguments: dict,
) -> str:
    """Compute the ledger's primary key.

    ``leaf_event_id`` is normalized to ``LEAF_ROOT_SENTINEL`` when
    ``None`` so the key is always a well-formed sha256 hex digest.
    """
    leaf = leaf_event_id if leaf_event_id else LEAF_ROOT_SENTINEL
    arg_hash = compute_argument_hash(arguments)
    material = f"{conversation_id}|{leaf}|{tool_name}|{arg_hash}"
    return hashlib.sha256(material.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Ledger operations
# ---------------------------------------------------------------------------


async def has_completed(app: FastAPI, key: str) -> bool:
    """Return True iff a side-effect keyed by ``key`` has already run."""
    conn = _get_conn(app)
    async with conn.execute(
        "SELECT 1 FROM completed_side_effects WHERE idempotency_key = ?",
        (key,),
    ) as cursor:
        row = await cursor.fetchone()
    return row is not None


async def get_cached_result(app: FastAPI, key: str) -> dict | None:
    """Return the cached observation payload for ``key``, or None.

    Returns ``{"result_summary": str, "result_json": Any | None,
    "completed_at": float}`` when the key exists.  A previously-completed
    entry with no cached ``result_json`` still returns a dict so the
    caller can distinguish "completed but no payload" from "not
    completed" (``None``).
    """
    conn = _get_conn(app)
    async with conn.execute(
        "SELECT result_summary, result_json, completed_at "
        "FROM completed_side_effects WHERE idempotency_key = ?",
        (key,),
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        return None
    result_json = row["result_json"]
    parsed: object | None = None
    if result_json is not None:
        try:
            parsed = json.loads(result_json)
        except json.JSONDecodeError:
            parsed = None
    return {
        "result_summary": row["result_summary"] or "",
        "result_json": parsed,
        "completed_at": row["completed_at"],
    }


async def mark_completed(
    app: FastAPI,
    *,
    key: str,
    conversation_id: str,
    leaf_event_id: str | None,
    tool_name: str,
    arguments: dict,
    result_summary: str = "",
    result_json: object | None = None,
) -> None:
    """Record that the side effect keyed by ``key`` has completed.

    Uses ``INSERT OR IGNORE`` so a concurrent duplicate insert is a
    no-op rather than a constraint error.  Callers should always call
    ``has_completed`` first; this is a belt-and-braces safety net.
    """
    conn = _get_conn(app)
    leaf = leaf_event_id if leaf_event_id else LEAF_ROOT_SENTINEL
    arg_hash = compute_argument_hash(arguments)
    summary = result_summary[:500]
    payload = json.dumps(result_json, default=str) if result_json is not None else None
    await conn.execute(
        """
        INSERT OR IGNORE INTO completed_side_effects (
            idempotency_key, conversation_id, leaf_event_id, tool_name,
            argument_hash, result_summary, result_json, completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            key,
            conversation_id,
            leaf,
            tool_name,
            arg_hash,
            summary,
            payload,
            time.time(),
        ),
    )
    await conn.commit()


async def clear_conversation(app: FastAPI, conversation_id: str) -> int:
    """Delete all ledger rows for a conversation.  Returns rows deleted.

    Used by explicit resume-from-scratch / test-teardown flows.  Not
    called on normal crash-and-resume (that's the whole point of the
    ledger surviving restarts).
    """
    conn = _get_conn(app)
    cursor = await conn.execute(
        "DELETE FROM completed_side_effects WHERE conversation_id = ?",
        (conversation_id,),
    )
    await conn.commit()
    return cursor.rowcount  # type: ignore[return-value]

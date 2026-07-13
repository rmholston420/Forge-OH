"""
bff/services/episodic_memory.py

Episodic memory store — lightweight SQLite-backed log of run events
for context injection into the OpenHands agent prompt.

Lifetime management:
  Call `init_db(app)` from the FastAPI lifespan startup handler.
  A single shared aiosqlite connection is stored on `app.state.memory_db`
  and closed by `close_db(app)` on shutdown.

  NEVER call `aiosqlite.connect()` per-request — that creates a new file
  handle on every call and causes SQLite locking errors under concurrency.
"""
from __future__ import annotations

import json
import time
import aiosqlite
from pathlib import Path
from fastapi import FastAPI

DB_PATH = Path("data/episodic_memory.db")


async def init_db(app: FastAPI) -> None:
    """Open the shared DB connection and create tables. Call once at startup."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(DB_PATH))
    conn.row_factory = aiosqlite.Row
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_entries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id      TEXT    NOT NULL,
            event_type  TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            metadata    TEXT    NOT NULL DEFAULT '{}',
            created_at  REAL    NOT NULL
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_run_id ON memory_entries (run_id)"
    )
    await conn.commit()
    app.state.memory_db = conn


async def close_db(app: FastAPI) -> None:
    """Close the shared DB connection. Call once at shutdown."""
    conn: aiosqlite.Connection | None = getattr(app.state, "memory_db", None)
    if conn is not None:
        await conn.close()
        app.state.memory_db = None


def _get_conn(app: FastAPI) -> aiosqlite.Connection:
    conn: aiosqlite.Connection | None = getattr(app.state, "memory_db", None)
    if conn is None:
        raise RuntimeError(
            "episodic_memory: DB not initialised. "
            "Call init_db(app) from the FastAPI lifespan startup handler."
        )
    return conn


async def record_event(
    app: FastAPI,
    run_id: str,
    event_type: str,
    content: str,
    metadata: dict | None = None,
) -> int:
    """Append a memory entry. Returns the new row id."""
    conn = _get_conn(app)
    cursor = await conn.execute(
        """
        INSERT INTO memory_entries (run_id, event_type, content, metadata, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (run_id, event_type, content, json.dumps(metadata or {}), time.time()),
    )
    await conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


async def get_recent_events(
    app: FastAPI,
    run_id: str,
    limit: int = 50,
) -> list[dict]:
    """Return the most recent `limit` entries for a run, oldest-first."""
    conn = _get_conn(app)
    async with conn.execute(
        """
        SELECT id, run_id, event_type, content, metadata, created_at
        FROM memory_entries
        WHERE run_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (run_id, limit),
    ) as cursor:
        rows = await cursor.fetchall()
    # Reverse so oldest is first (chronological order for prompt injection)
    return [
        {
            "id": row["id"],
            "run_id": row["run_id"],
            "event_type": row["event_type"],
            "content": row["content"],
            "metadata": json.loads(row["metadata"]),
            "created_at": row["created_at"],
        }
        for row in reversed(rows)
    ]


async def clear_run_memory(app: FastAPI, run_id: str) -> int:
    """Delete all memory entries for a run. Returns count of deleted rows."""
    conn = _get_conn(app)
    cursor = await conn.execute(
        "DELETE FROM memory_entries WHERE run_id = ?",
        (run_id,),
    )
    await conn.commit()
    return cursor.rowcount  # type: ignore[return-value]

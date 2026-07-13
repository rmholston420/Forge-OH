"""Episodic Memory — SQLite-backed cross-session memory store.

Persists key facts, past decisions, and failed approaches across sessions.
Queried at the start of each planning step to handle long-horizon tasks
without context fragmentation.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class EpisodicMemory:
    def __init__(self, db_path: str = ".openhands/episodic_memory.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON memories(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kind ON memories(kind)")
            conn.commit()

    def store(self, session_id: str, kind: str, content: str, metadata: dict[str, Any] | None = None) -> int:
        """Store a memory entry. kind: 'decision', 'fact', 'failure', 'outcome'."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO memories (session_id, kind, content, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, kind, content, json.dumps(metadata or {}), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]

    def recall(self, session_id: str, kind: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        """Recall memories for a session, optionally filtered by kind."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if kind:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE session_id=? AND kind=? ORDER BY created_at DESC LIMIT ?",
                    (session_id, kind, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
            return [dict(r) for r in rows]

    def build_recall_preamble(self, session_id: str) -> str:
        """Build a recall preamble to inject into agent planning step."""
        memories = self.recall(session_id, limit=5)
        if not memories:
            return ""
        lines = ["## Session Memory\n"]
        for mem in memories:
            lines.append(f"- [{mem['kind'].upper()}] {mem['content']}")
        return "\n".join(lines)

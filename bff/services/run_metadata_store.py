from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunMetadata:
    run_id: str
    title: Optional[str] = None
    task: Optional[str] = None
    created_at: str = ""


class RunMetadataStore:
    def __init__(self, db_path: str | Path = "bff/data/run_metadata.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_metadata (
                    run_id TEXT PRIMARY KEY,
                    title TEXT,
                    task TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def upsert(
        self,
        run_id: str,
        *,
        title: Optional[str] = None,
        task: Optional[str] = None,
    ) -> RunMetadata:
        existing = self.get(run_id)
        created_at = existing.created_at if existing else _utc_now_iso()
        next_title = title if title is not None else (existing.title if existing else None)
        next_task = task if task is not None else (existing.task if existing else None)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO run_metadata (run_id, title, task, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    title = excluded.title,
                    task = excluded.task
                """,
                (run_id, next_title, next_task, created_at),
            )
            conn.commit()

        return RunMetadata(
            run_id=run_id,
            title=next_title,
            task=next_task,
            created_at=created_at,
        )

    def get(self, run_id: str) -> Optional[RunMetadata]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT run_id, title, task, created_at
                FROM run_metadata
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()

        if row is None:
            return None

        return RunMetadata(
            run_id=row["run_id"],
            title=row["title"],
            task=row["task"],
            created_at=row["created_at"],
        )

    def get_title(self, run_id: str) -> Optional[str]:
        record = self.get(run_id)
        return record.title if record else None

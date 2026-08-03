"""SQLite-backed store for TrajectoryRecords (Rec #3, Slice F.2).

Local-first: the DB lives at ``~/.forge-oh/trajectories.db`` by default,
symmetric with the verify-loop's ``~/.forge-oh/verify-state.json``. No
BFF schema coupling, no cloud fields.

Schema
------
One row per trajectory. Structured columns for the fields we query on
(``final_status``, ``created_at``, ``run_id``, ``session_id``,
``repograph_repo_key``); nested collections (``diffs``,
``verify_iterations``, ``repograph_symbols``) are JSON-encoded
alongside; the embedding is a raw ``float32`` blob for compact storage
and O(1) numpy roundtrip.

Concurrency
-----------
Single-writer (the trajectory writer hook), multi-reader (the retriever
+ BFF read endpoints). WAL mode + a busy timeout gives us safe
concurrent reads without a separate service. All writes are atomic
single-statement upserts.
"""

from __future__ import annotations

import json
import os
import sqlite3
import struct
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from openhands_tools_ext.trajectory.schema import (
    TrajectoryDiff,
    TrajectoryRecord,
    TrajectoryStatus,
)
from openhands_tools_ext.verify.schema import VerificationStep


def default_db_path() -> Path:
    """Return the canonical trajectory DB path, respecting overrides.

    Resolution order:
    1. ``FORGE_OH_TRAJECTORY_DB`` env var (absolute path).
    2. ``$OPENHANDS_PROJECT_DIR/.forge-oh/trajectories.db`` if that
       env var is set (matches the verify-loop state location).
    3. ``~/.forge-oh/trajectories.db``.
    """
    override = os.environ.get("FORGE_OH_TRAJECTORY_DB")
    if override:
        return Path(override).expanduser().resolve()

    project_dir = os.environ.get("OPENHANDS_PROJECT_DIR")
    if project_dir:
        return Path(project_dir) / ".forge-oh" / "trajectories.db"

    return Path.home() / ".forge-oh" / "trajectories.db"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def encode_embedding(vector: list[float] | None) -> bytes | None:
    """Pack a float embedding vector as a little-endian float32 blob."""
    if vector is None:
        return None
    return struct.pack(f"<{len(vector)}f", *vector)


def decode_embedding(blob: bytes | None) -> list[float] | None:
    """Reverse of :func:`encode_embedding`."""
    if blob is None:
        return None
    n, remainder = divmod(len(blob), 4)
    if remainder:
        raise ValueError(f"embedding blob length {len(blob)} is not a multiple of 4 bytes")
    return list(struct.unpack(f"<{n}f", blob))


class TrajectoryStore:
    """SQLite store for :class:`TrajectoryRecord`."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # -- connection / schema ------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        # WAL for concurrent reads while the writer hook runs.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS trajectories (
                    trajectory_id       TEXT PRIMARY KEY,
                    run_id              TEXT NOT NULL,
                    session_id          TEXT NOT NULL,
                    task_description    TEXT NOT NULL,
                    plan                TEXT NOT NULL DEFAULT '',
                    diffs_json          TEXT NOT NULL DEFAULT '[]',
                    verify_iterations_json TEXT NOT NULL DEFAULT '[]',
                    final_status        TEXT NOT NULL,
                    symptom             TEXT NOT NULL DEFAULT '',
                    repograph_repo_key  TEXT NOT NULL DEFAULT '',
                    repograph_symbols_json TEXT NOT NULL DEFAULT '[]',
                    embedding           BLOB,
                    embedding_model     TEXT NOT NULL DEFAULT '',
                    created_at          TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_trajectories_status
                    ON trajectories(final_status);
                CREATE INDEX IF NOT EXISTS idx_trajectories_created_at
                    ON trajectories(created_at);
                CREATE INDEX IF NOT EXISTS idx_trajectories_run_id
                    ON trajectories(run_id);
                CREATE INDEX IF NOT EXISTS idx_trajectories_repo_key
                    ON trajectories(repograph_repo_key);
                """
            )
            conn.commit()

    # -- row <-> record mapping --------------------------------------------

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> TrajectoryRecord:
        return TrajectoryRecord(
            trajectory_id=row["trajectory_id"],
            run_id=row["run_id"],
            session_id=row["session_id"],
            task_description=row["task_description"],
            plan=row["plan"],
            diffs=[TrajectoryDiff(**d) for d in json.loads(row["diffs_json"])],
            verify_iterations=[
                VerificationStep(**v) for v in json.loads(row["verify_iterations_json"])
            ],
            final_status=TrajectoryStatus(row["final_status"]),
            symptom=row["symptom"],
            repograph_repo_key=row["repograph_repo_key"],
            repograph_symbols=json.loads(row["repograph_symbols_json"]),
            embedding=decode_embedding(row["embedding"]),
            embedding_model=row["embedding_model"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _record_to_row(record: TrajectoryRecord) -> tuple:
        return (
            record.trajectory_id,
            record.run_id,
            record.session_id,
            record.task_description,
            record.plan,
            json.dumps([d.model_dump() for d in record.diffs]),
            json.dumps([v.model_dump() for v in record.verify_iterations]),
            record.final_status
            if isinstance(record.final_status, str)
            else record.final_status.value,
            record.symptom,
            record.repograph_repo_key,
            json.dumps(record.repograph_symbols),
            encode_embedding(record.embedding),
            record.embedding_model,
            record.created_at or _utc_now_iso(),
        )

    # -- public API ---------------------------------------------------------

    def insert(self, record: TrajectoryRecord) -> TrajectoryRecord:
        """Insert a new trajectory. Raises on duplicate ``trajectory_id``.

        Backfills ``created_at`` with the current UTC ISO timestamp if the
        record was constructed without one.
        """
        if not record.created_at:
            record = record.model_copy(update={"created_at": _utc_now_iso()})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO trajectories (
                    trajectory_id, run_id, session_id, task_description, plan,
                    diffs_json, verify_iterations_json, final_status, symptom,
                    repograph_repo_key, repograph_symbols_json, embedding,
                    embedding_model, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._record_to_row(record),
            )
            conn.commit()
        return record

    def get(self, trajectory_id: str) -> TrajectoryRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM trajectories WHERE trajectory_id = ?",
                (trajectory_id,),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def get_by_run(self, run_id: str) -> TrajectoryRecord | None:
        """Fetch the (single) trajectory recorded for a run, if any."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM trajectories WHERE run_id = ? ORDER BY created_at DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def list_all(
        self,
        *,
        limit: int | None = None,
        statuses: Iterable[TrajectoryStatus] | None = None,
        repo_key: str | None = None,
    ) -> list[TrajectoryRecord]:
        """Return trajectories newest-first.

        Filters combine with AND. Passing ``statuses`` empty (rather than
        ``None``) returns no rows.
        """
        clauses: list[str] = []
        params: list[object] = []
        if statuses is not None:
            values = [s.value if isinstance(s, TrajectoryStatus) else s for s in statuses]
            if not values:
                return []
            placeholders = ",".join("?" for _ in values)
            clauses.append(f"final_status IN ({placeholders})")
            params.extend(values)
        if repo_key is not None:
            clauses.append("repograph_repo_key = ?")
            params.append(repo_key)

        sql = "SELECT * FROM trajectories"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def update_embedding(
        self,
        trajectory_id: str,
        embedding: list[float],
        embedding_model: str,
    ) -> None:
        """Attach an embedding to an existing trajectory.

        Raises :class:`KeyError` if the trajectory does not exist.
        """
        blob = encode_embedding(embedding)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE trajectories
                   SET embedding = ?, embedding_model = ?
                 WHERE trajectory_id = ?
                """,
                (blob, embedding_model, trajectory_id),
            )
            conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(trajectory_id)

    def list_unembedded(self, *, limit: int | None = None) -> list[TrajectoryRecord]:
        """Return trajectories missing an embedding, newest-first."""
        sql = "SELECT * FROM trajectories WHERE embedding IS NULL ORDER BY created_at DESC"
        params: list[object] = []
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def count(self) -> int:
        with self._connect() as conn:
            (n,) = conn.execute("SELECT COUNT(*) FROM trajectories").fetchone()
        return int(n)

    def delete(self, trajectory_id: str) -> bool:
        """Remove a trajectory. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM trajectories WHERE trajectory_id = ?",
                (trajectory_id,),
            )
            conn.commit()
        return cursor.rowcount > 0

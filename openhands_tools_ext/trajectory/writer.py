"""Trajectory writer + background indexer (Rec #3, Slice F.5).

At run completion, materialize a :class:`TrajectoryRecord` from what
the run produced and persist it via :class:`TrajectoryStore`. Records
are written with ``embedding=None``; the :class:`TrajectoryIndexer`
runs later (inline or async) to populate embeddings.

Design
------
- **Writer is pure library**: no CLI, no sidecar reads. Callers (the
  run-completion hook, tests) assemble the inputs and call
  :meth:`TrajectoryWriter.write_from_run`. Keeps the writer trivially
  testable and re-usable from anywhere.
- **Idempotent by trajectory_id**: repeated writes for the same
  ``run_id`` deterministically resolve to the same trajectory_id
  (``traj_{run_id}``); the writer replaces the record on conflict so
  the last observation wins (matches the STOP hook re-firing on
  successful verification retry loops).
- **Indexer is a background pass**: iterates
  ``store.list_unembedded()`` and calls the embedder. Batch size and
  the "how many to embed per invocation" budget are configurable so
  the same code path works for inline (embed everything) and cron
  (embed a chunk).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from openhands_tools_ext.trajectory.embedder import (
    TrajectoryEmbedder,
    get_default_embedder,
)
from openhands_tools_ext.trajectory.schema import (
    TrajectoryDiff,
    TrajectoryRecord,
    TrajectoryStatus,
    make_trajectory_id,
)
from openhands_tools_ext.trajectory.store import TrajectoryStore


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class RunSummary:
    """All fields the writer needs from a completed run.

    Callers assemble this from whatever sources they have (sidecars,
    BFF stores, environment variables). Empty defaults mean "no
    signal" and are safely dropped from the embedding text.
    """

    run_id: str
    session_id: str = ""
    task_description: str = ""
    plan: str = ""
    diffs: list[TrajectoryDiff] = field(default_factory=list)
    verify_iterations: list[dict[str, object]] = field(default_factory=list)
    symptom: str = ""
    final_status: TrajectoryStatus = TrajectoryStatus.UNKNOWN
    repograph_repo_key: str = ""
    repograph_symbols: list[str] = field(default_factory=list)


class TrajectoryWriter:
    """Materializes and persists a :class:`TrajectoryRecord`."""

    def __init__(self, store: TrajectoryStore) -> None:
        self.store = store

    def build_record(self, summary: RunSummary) -> TrajectoryRecord:
        """Build a record from a :class:`RunSummary`. No IO."""
        from openhands_tools_ext.verify.schema import VerificationStep

        # verify_iterations may arrive as plain dicts (from a JSON
        # sidecar) or already-typed VerificationSteps. Normalize.
        iterations: list[VerificationStep] = []
        for step in summary.verify_iterations:
            if isinstance(step, VerificationStep):
                iterations.append(step)
            else:
                iterations.append(VerificationStep(**step))  # type: ignore[arg-type]

        return TrajectoryRecord(
            trajectory_id=make_trajectory_id(summary.run_id),
            run_id=summary.run_id,
            session_id=summary.session_id,
            task_description=summary.task_description,
            plan=summary.plan,
            diffs=summary.diffs,
            verify_iterations=iterations,
            symptom=summary.symptom,
            final_status=summary.final_status,
            repograph_repo_key=summary.repograph_repo_key,
            repograph_symbols=summary.repograph_symbols,
            embedding=None,
            embedding_model="",
            created_at=_utc_now_iso(),
        )

    def write_from_run(self, summary: RunSummary) -> TrajectoryRecord:
        """Build the record and upsert it into the store.

        Returns the persisted record so callers can inspect the
        trajectory_id / created_at without a re-read.
        """
        record = self.build_record(summary)
        # Upsert by trajectory_id (== traj_{run_id}) — replace on conflict
        # so re-fired STOP hooks converge on the latest observation.
        existing = self.store.get(record.trajectory_id)
        if existing is not None:
            self.store.delete(record.trajectory_id)
        self.store.insert(record)
        return record


class TrajectoryIndexer:
    """Background pass that populates embeddings for pending records.

    Parameters
    ----------
    store : TrajectoryStore
        Source of pending records and target of updates.
    embedder : TrajectoryEmbedder | None, optional
        Embedder to use; falls back to the process-wide default.
    batch_size : int, optional
        Records to fetch per pass. The embedder itself processes them
        as a single batch (one model call), so this also caps the max
        batch it will see.
    """

    def __init__(
        self,
        store: TrajectoryStore,
        embedder: TrajectoryEmbedder | None = None,
        *,
        batch_size: int = 16,
    ) -> None:
        self.store = store
        self._embedder = embedder
        self.batch_size = batch_size

    @property
    def embedder(self) -> TrajectoryEmbedder:
        if self._embedder is None:
            self._embedder = get_default_embedder()
        return self._embedder

    def index_pending(self, *, max_records: int | None = None) -> int:
        """Embed and persist up to ``max_records`` pending records.

        Returns the number of records embedded.

        Semantics
        ---------
        - Records without an embedding are pulled in insertion order.
        - When ``max_records`` is ``None`` we drain the whole queue in
          batches; otherwise we stop as soon as we've hit the budget.
        - Each batch is one embedder call (one GPU forward pass) so a
          large batch amortizes model overhead.
        """
        from openhands_tools_ext.trajectory.embedder import build_record_text

        indexed = 0
        while True:
            if max_records is not None and indexed >= max_records:
                break
            budget = self.batch_size
            if max_records is not None:
                budget = min(budget, max_records - indexed)
            pending = self.store.list_unembedded(limit=budget)
            if not pending:
                break
            texts = [build_record_text(r) for r in pending]
            vectors = self.embedder.embed_batch(texts)
            for record, vec in zip(pending, vectors, strict=True):
                self.store.update_embedding(record.trajectory_id, vec, self.embedder.model_name)
                indexed += 1
        return indexed

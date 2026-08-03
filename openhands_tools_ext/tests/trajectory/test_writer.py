"""Unit tests for TrajectoryWriter + TrajectoryIndexer (Rec #3, Slice F.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from openhands_tools_ext.trajectory.embedder import TrajectoryEmbedder
from openhands_tools_ext.trajectory.schema import (
    TrajectoryDiff,
    TrajectoryStatus,
    make_trajectory_id,
)
from openhands_tools_ext.trajectory.store import TrajectoryStore
from openhands_tools_ext.trajectory.writer import (
    RunSummary,
    TrajectoryIndexer,
    TrajectoryWriter,
)
from openhands_tools_ext.verify.schema import VerificationStep, VerifyRunner, VerifyVerdict


class FakeEncoder:
    def __init__(self, dim: int = 4) -> None:
        self.dim = dim
        self.calls: list[str | list[str]] = []

    def encode(
        self,
        sentences: str | list[str],
        *,
        normalize_embeddings: bool = False,
        convert_to_numpy: bool = False,
    ) -> object:
        self.calls.append(sentences)
        if isinstance(sentences, str):
            return [1.0 / (self.dim**0.5)] * self.dim
        return [[1.0 / (self.dim**0.5)] * self.dim for _ in sentences]


@pytest.fixture
def store(tmp_path: Path) -> TrajectoryStore:
    return TrajectoryStore(tmp_path / "traj.db")


# ---------------------------------------------------------------------------
# TrajectoryWriter
# ---------------------------------------------------------------------------


class TestTrajectoryWriter:
    def test_write_minimal_summary(self, store: TrajectoryStore) -> None:
        w = TrajectoryWriter(store)
        rec = w.write_from_run(RunSummary(run_id="run1", final_status=TrajectoryStatus.SUCCESS))
        assert rec.trajectory_id == make_trajectory_id("run1")
        assert rec.embedding is None
        assert rec.embedding_model == ""
        assert rec.created_at  # non-empty ISO string
        # Round-trip through the store.
        loaded = store.get(rec.trajectory_id)
        assert loaded is not None
        assert loaded.trajectory_id == rec.trajectory_id

    def test_write_full_summary(self, store: TrajectoryStore) -> None:
        w = TrajectoryWriter(store)
        diff = TrajectoryDiff(path="a.py", lines_added=3, lines_removed=1, summary="patch")
        step = VerificationStep(
            iteration=1,
            max_iterations=3,
            runner=VerifyRunner.PYTEST,
            test_selected=["a.py"],
            command="pytest -x a.py",
            exit_code=0,
            stdout_tail="passed",
            stderr_tail="",
            duration_ms=42,
            verdict=VerifyVerdict.PASS,
        )
        rec = w.write_from_run(
            RunSummary(
                run_id="run2",
                session_id="sess",
                task_description="fix null deref",
                plan="1. reproduce\n2. patch",
                diffs=[diff],
                verify_iterations=[step],
                symptom="AttributeError",
                final_status=TrajectoryStatus.SUCCESS,
                repograph_repo_key="repo_main",
                repograph_symbols=["a.func"],
            )
        )
        loaded = store.get(rec.trajectory_id)
        assert loaded is not None
        assert loaded.task_description == "fix null deref"
        assert loaded.diffs == [diff]
        assert loaded.verify_iterations == [step]
        assert loaded.symptom == "AttributeError"
        assert loaded.repograph_symbols == ["a.func"]

    def test_verify_iterations_accepts_plain_dicts(self, store: TrajectoryStore) -> None:
        # The STOP hook may pass verify_iterations as JSON dicts.
        w = TrajectoryWriter(store)
        step_dict = {
            "iteration": 1,
            "max_iterations": 3,
            "runner": "pytest",
            "test_selected": ["b.py"],
            "command": "pytest b.py",
            "exit_code": 1,
            "stdout_tail": "",
            "stderr_tail": "boom",
            "duration_ms": 10,
            "verdict": "fail",
        }
        rec = w.write_from_run(
            RunSummary(
                run_id="run3",
                verify_iterations=[step_dict],
                final_status=TrajectoryStatus.FAILED,
            )
        )
        loaded = store.get(rec.trajectory_id)
        assert loaded is not None
        assert len(loaded.verify_iterations) == 1
        assert loaded.verify_iterations[0].exit_code == 1

    def test_rewrite_replaces_existing(self, store: TrajectoryStore) -> None:
        w = TrajectoryWriter(store)
        w.write_from_run(
            RunSummary(
                run_id="run4",
                task_description="first attempt",
                final_status=TrajectoryStatus.FAILED,
            )
        )
        w.write_from_run(
            RunSummary(
                run_id="run4",
                task_description="second attempt",
                final_status=TrajectoryStatus.SUCCESS,
            )
        )
        loaded = store.get(make_trajectory_id("run4"))
        assert loaded is not None
        assert loaded.task_description == "second attempt"
        assert loaded.final_status == TrajectoryStatus.SUCCESS
        assert store.count() == 1

    def test_default_status_is_unknown(self, store: TrajectoryStore) -> None:
        w = TrajectoryWriter(store)
        rec = w.write_from_run(RunSummary(run_id="run5"))
        assert rec.final_status == TrajectoryStatus.UNKNOWN


# ---------------------------------------------------------------------------
# TrajectoryIndexer
# ---------------------------------------------------------------------------


class TestTrajectoryIndexer:
    def _make_indexer(
        self, store: TrajectoryStore, *, batch_size: int = 16
    ) -> tuple[TrajectoryIndexer, FakeEncoder]:
        enc = FakeEncoder(dim=4)
        emb = TrajectoryEmbedder(model_name="fake-model", device="cpu", loader=lambda n, d: enc)
        indexer = TrajectoryIndexer(store, embedder=emb, batch_size=batch_size)
        return indexer, enc

    def _seed(self, store: TrajectoryStore, n: int) -> None:
        w = TrajectoryWriter(store)
        for i in range(n):
            w.write_from_run(
                RunSummary(
                    run_id=f"r{i}",
                    task_description=f"task {i}",
                    final_status=TrajectoryStatus.SUCCESS,
                )
            )

    def test_index_pending_empty_store(self, store: TrajectoryStore) -> None:
        indexer, enc = self._make_indexer(store)
        assert indexer.index_pending() == 0
        assert enc.calls == []

    def test_index_pending_drains_all(self, store: TrajectoryStore) -> None:
        self._seed(store, 3)
        indexer, _ = self._make_indexer(store)
        assert indexer.index_pending() == 3
        # All records now have embeddings and the model name is recorded.
        for i in range(3):
            rec = store.get(make_trajectory_id(f"r{i}"))
            assert rec is not None
            assert rec.embedding is not None
            assert len(rec.embedding) == 4
            assert rec.embedding_model == "fake-model"
        # A follow-up pass is a no-op.
        assert indexer.index_pending() == 0

    def test_index_pending_respects_max_records(self, store: TrajectoryStore) -> None:
        self._seed(store, 5)
        indexer, _ = self._make_indexer(store)
        assert indexer.index_pending(max_records=2) == 2
        # 3 still pending.
        assert len(store.list_unembedded()) == 3

    def test_index_pending_batches(self, store: TrajectoryStore) -> None:
        self._seed(store, 5)
        indexer, enc = self._make_indexer(store, batch_size=2)
        assert indexer.index_pending() == 5
        # 5 records with batch_size=2 → 3 batches (2, 2, 1).
        batch_call_shapes = [len(c) if isinstance(c, list) else 1 for c in enc.calls]
        assert batch_call_shapes == [2, 2, 1]

    def test_batch_max_records_combination(self, store: TrajectoryStore) -> None:
        self._seed(store, 10)
        indexer, enc = self._make_indexer(store, batch_size=3)
        # Ask for 5 with batches of 3 → batches of [3, 2].
        assert indexer.index_pending(max_records=5) == 5
        batch_call_shapes = [len(c) if isinstance(c, list) else 1 for c in enc.calls]
        assert batch_call_shapes == [3, 2]

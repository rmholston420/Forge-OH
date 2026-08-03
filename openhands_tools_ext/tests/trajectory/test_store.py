"""Unit tests for TrajectoryStore (Rec #3, Slice F.2)."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from openhands_tools_ext.trajectory.schema import (
    TrajectoryDiff,
    TrajectoryRecord,
    TrajectoryStatus,
    make_trajectory_id,
)
from openhands_tools_ext.trajectory.store import (
    TrajectoryStore,
    decode_embedding,
    default_db_path,
    encode_embedding,
)
from openhands_tools_ext.verify.schema import (
    VerificationStep,
    VerifyRunner,
    VerifyVerdict,
)


def _rec(
    run_id: str,
    status: TrajectoryStatus = TrajectoryStatus.SUCCESS,
    *,
    task: str = "task",
    embedding: list[float] | None = None,
    repo_key: str = "6bcc20c96720",
    symbols: list[str] | None = None,
    created_at: str = "2026-08-03T12:00:00Z",
) -> TrajectoryRecord:
    return TrajectoryRecord(
        trajectory_id=make_trajectory_id(run_id),
        run_id=run_id,
        session_id=f"sess_{run_id}",
        task_description=task,
        final_status=status,
        repograph_repo_key=repo_key,
        repograph_symbols=symbols or [],
        embedding=embedding,
        embedding_model="BAAI/bge-code-v1" if embedding else "",
        created_at=created_at,
    )


@pytest.fixture
def store(tmp_path: Path) -> TrajectoryStore:
    return TrajectoryStore(tmp_path / "traj.db")


class TestEncodeDecodeEmbedding:
    def test_none_roundtrip(self) -> None:
        assert encode_embedding(None) is None
        assert decode_embedding(None) is None

    def test_float_roundtrip(self) -> None:
        vec = [0.1, -0.2, 3.14, -1.5e-3]
        blob = encode_embedding(vec)
        assert isinstance(blob, bytes)
        assert len(blob) == len(vec) * 4
        out = decode_embedding(blob)
        assert out is not None
        for expected, got in zip(vec, out, strict=True):
            assert got == pytest.approx(expected, rel=1e-6)

    def test_bad_blob_length_raises(self) -> None:
        with pytest.raises(ValueError):
            decode_embedding(b"\x00\x00\x00")  # 3 bytes, not multiple of 4

    def test_1536_dim_matches_bge_code_v1(self) -> None:
        # Sanity: real embedder outputs 1536 floats -> 6144-byte blob.
        vec = [float(i) for i in range(1536)]
        blob = encode_embedding(vec)
        assert blob is not None
        assert len(blob) == 6144
        # Spot-check first + last elements.
        first = struct.unpack("<f", blob[0:4])[0]
        last = struct.unpack("<f", blob[-4:])[0]
        assert first == pytest.approx(0.0)
        assert last == pytest.approx(1535.0)


class TestDefaultDbPath:
    def test_env_override_wins(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        override = tmp_path / "override.db"
        monkeypatch.setenv("FORGE_OH_TRAJECTORY_DB", str(override))
        assert default_db_path() == override.resolve()

    def test_project_dir_used(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("FORGE_OH_TRAJECTORY_DB", raising=False)
        monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
        assert default_db_path() == tmp_path / ".forge-oh" / "trajectories.db"

    def test_home_fallback(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("FORGE_OH_TRAJECTORY_DB", raising=False)
        monkeypatch.delenv("OPENHANDS_PROJECT_DIR", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        assert default_db_path() == tmp_path / ".forge-oh" / "trajectories.db"


class TestTrajectoryStore:
    def test_init_creates_db_and_parent_dir(self, tmp_path: Path) -> None:
        db = tmp_path / "nested" / "traj.db"
        assert not db.exists()
        TrajectoryStore(db)
        assert db.exists()

    def test_insert_and_get_roundtrip(self, store: TrajectoryStore) -> None:
        rec = _rec("run1")
        store.insert(rec)
        loaded = store.get(rec.trajectory_id)
        assert loaded == rec

    def test_insert_backfills_created_at(self, store: TrajectoryStore) -> None:
        rec = _rec("run1").model_copy(update={"created_at": ""})
        inserted = store.insert(rec)
        assert inserted.created_at != ""
        loaded = store.get(rec.trajectory_id)
        assert loaded is not None
        assert loaded.created_at == inserted.created_at

    def test_full_payload_roundtrip(self, store: TrajectoryStore) -> None:
        step = VerificationStep(
            iteration=1,
            max_iterations=3,
            runner=VerifyRunner.PYTEST,
            duration_ms=10,
            verdict=VerifyVerdict.PASS,
        )
        diff = TrajectoryDiff(
            path="a.py",
            lines_added=5,
            lines_removed=2,
            summary="patch",
        )
        rec = _rec("run1", embedding=[0.1, 0.2, 0.3, 0.4]).model_copy(
            update={
                "plan": "step1\nstep2",
                "diffs": [diff],
                "verify_iterations": [step],
                "symptom": "boom",
                "repograph_symbols": ["mod.func", "mod.Class.method"],
            }
        )
        store.insert(rec)
        loaded = store.get(rec.trajectory_id)
        assert loaded is not None
        # Non-embedding fields must roundtrip exactly.
        for f in TrajectoryRecord.model_fields:
            if f == "embedding":
                continue
            assert getattr(loaded, f) == getattr(rec, f), f"{f} mismatch"
        # Embedding is float32-packed, so allow rel tolerance.
        assert loaded.embedding is not None
        assert rec.embedding is not None
        for expected, got in zip(rec.embedding, loaded.embedding, strict=True):
            assert got == pytest.approx(expected, rel=1e-6)

    def test_get_missing_returns_none(self, store: TrajectoryStore) -> None:
        assert store.get("does_not_exist") is None

    def test_duplicate_insert_raises(self, store: TrajectoryStore) -> None:
        import sqlite3

        rec = _rec("run1")
        store.insert(rec)
        with pytest.raises(sqlite3.IntegrityError):
            store.insert(rec)

    def test_get_by_run(self, store: TrajectoryStore) -> None:
        rec = _rec("run1")
        store.insert(rec)
        assert store.get_by_run("run1") == rec
        assert store.get_by_run("run_missing") is None

    def test_list_all_newest_first(self, store: TrajectoryStore) -> None:
        older = _rec("run1", created_at="2026-08-01T00:00:00Z")
        newer = _rec("run2", created_at="2026-08-02T00:00:00Z")
        store.insert(older)
        store.insert(newer)
        rows = store.list_all()
        assert [r.run_id for r in rows] == ["run2", "run1"]

    def test_list_all_filter_by_status(self, store: TrajectoryStore) -> None:
        s1 = _rec("run1", TrajectoryStatus.SUCCESS)
        s2 = _rec("run2", TrajectoryStatus.FAILED)
        s3 = _rec("run3", TrajectoryStatus.VERIFIED_FAILURE)
        for r in (s1, s2, s3):
            store.insert(r)
        successes = store.list_all(statuses=[TrajectoryStatus.SUCCESS])
        assert [r.run_id for r in successes] == ["run1"]
        failed = store.list_all(
            statuses=[TrajectoryStatus.FAILED, TrajectoryStatus.VERIFIED_FAILURE]
        )
        assert {r.run_id for r in failed} == {"run2", "run3"}

    def test_list_all_empty_statuses_returns_empty(self, store: TrajectoryStore) -> None:
        store.insert(_rec("run1"))
        assert store.list_all(statuses=[]) == []

    def test_list_all_filter_by_repo_key(self, store: TrajectoryStore) -> None:
        a = _rec("run1", repo_key="repo_a")
        b = _rec("run2", repo_key="repo_b")
        store.insert(a)
        store.insert(b)
        assert [r.run_id for r in store.list_all(repo_key="repo_a")] == ["run1"]

    def test_list_all_limit(self, store: TrajectoryStore) -> None:
        for i in range(5):
            store.insert(_rec(f"run{i}", created_at=f"2026-08-0{i + 1}T00:00:00Z"))
        rows = store.list_all(limit=2)
        assert len(rows) == 2

    def test_update_embedding(self, store: TrajectoryStore) -> None:
        rec = _rec("run1")
        store.insert(rec)
        vec = [0.5, -0.5, 1.0]
        store.update_embedding(rec.trajectory_id, vec, "test-model")
        loaded = store.get(rec.trajectory_id)
        assert loaded is not None
        assert loaded.embedding is not None
        for expected, got in zip(vec, loaded.embedding, strict=True):
            assert got == pytest.approx(expected, rel=1e-6)
        assert loaded.embedding_model == "test-model"

    def test_update_embedding_missing_raises_key_error(self, store: TrajectoryStore) -> None:
        with pytest.raises(KeyError):
            store.update_embedding("does_not_exist", [0.1], "model")

    def test_list_unembedded(self, store: TrajectoryStore) -> None:
        with_emb = _rec("run1", embedding=[0.1, 0.2])
        without_emb = _rec("run2", created_at="2026-08-04T00:00:00Z")
        store.insert(with_emb)
        store.insert(without_emb)
        pending = store.list_unembedded()
        assert [r.run_id for r in pending] == ["run2"]

    def test_count(self, store: TrajectoryStore) -> None:
        assert store.count() == 0
        store.insert(_rec("run1"))
        store.insert(_rec("run2"))
        assert store.count() == 2

    def test_delete(self, store: TrajectoryStore) -> None:
        store.insert(_rec("run1"))
        assert store.delete("traj_run1") is True
        assert store.get("traj_run1") is None
        assert store.delete("traj_run1") is False

    def test_wal_mode_enabled(self, store: TrajectoryStore) -> None:
        with store._connect() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"

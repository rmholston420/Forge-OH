"""Tests for the Trajectory Memory router (Slice F.6, Rec #3).

The retriever's semantic component is deterministic against a
``FakeEncoder`` so search results can be asserted exactly.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bff.deps.trajectory_store import get_trajectory_store, reset_trajectory_store
from bff.main import app
from openhands_tools_ext.trajectory.embedder import reset_default_embedder
from openhands_tools_ext.trajectory.schema import (
    TrajectoryRecord,
    TrajectoryStatus,
    make_trajectory_id,
)
from openhands_tools_ext.trajectory.store import TrajectoryStore


class FakeEncoder:
    """Deterministic encoder: known text → known vector."""

    def __init__(self, mapping: dict[str, list[float]], dim: int = 4) -> None:
        self.mapping = mapping
        self.dim = dim

    def encode(
        self,
        sentences: str | list[str],
        *,
        normalize_embeddings: bool = False,
        convert_to_numpy: bool = False,
    ) -> object:
        if isinstance(sentences, str):
            return self.mapping.get(sentences, [0.0] * self.dim)
        return [self.mapping.get(s, [0.0] * self.dim) for s in sentences]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[TrajectoryStore]:
    s = TrajectoryStore(tmp_path / "traj.db")
    app.dependency_overrides[get_trajectory_store] = lambda: s
    try:
        yield s
    finally:
        app.dependency_overrides.pop(get_trajectory_store, None)
        reset_trajectory_store()


@pytest.fixture(autouse=True)
def _reset_embedder() -> Iterator[None]:
    reset_default_embedder()
    yield
    reset_default_embedder()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _rec(
    run_id: str,
    *,
    status: TrajectoryStatus = TrajectoryStatus.SUCCESS,
    task: str = "task",
    embedding: list[float] | None = None,
    repo_key: str = "repo_main",
    symbols: list[str] | None = None,
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
        embedding_model="fake" if embedding else "",
        created_at="2026-08-03T12:00:00Z",
    )


def _install_fake_embedder(mapping: dict[str, list[float]], dim: int = 4) -> None:
    """Swap the process-wide default embedder for a deterministic one."""
    from openhands_tools_ext.trajectory import embedder as embedder_mod

    fake = embedder_mod.TrajectoryEmbedder(
        model_name="fake",
        device="cpu",
        loader=lambda n, d: FakeEncoder(mapping, dim=dim),
    )
    embedder_mod._DEFAULT_EMBEDDER = fake  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# GET /trajectories
# ---------------------------------------------------------------------------


class TestListTrajectories:
    def test_empty(self, client: TestClient, store: TrajectoryStore) -> None:
        r = client.get("/api/trajectories")
        assert r.status_code == 200
        body = r.json()
        assert body == {"total": 0, "records": []}

    def test_list_returns_all(self, client: TestClient, store: TrajectoryStore) -> None:
        store.insert(_rec("run1"))
        store.insert(_rec("run2"))
        r = client.get("/api/trajectories")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        assert {rec["run_id"] for rec in body["records"]} == {"run1", "run2"}

    def test_list_respects_limit(self, client: TestClient, store: TrajectoryStore) -> None:
        for i in range(5):
            store.insert(_rec(f"r{i}"))
        r = client.get("/api/trajectories?limit=2")
        assert r.status_code == 200
        assert len(r.json()["records"]) == 2

    def test_list_filters_by_status(self, client: TestClient, store: TrajectoryStore) -> None:
        store.insert(_rec("ok", status=TrajectoryStatus.SUCCESS))
        store.insert(_rec("bad", status=TrajectoryStatus.FAILED))
        r = client.get("/api/trajectories?status=success")
        assert r.status_code == 200
        run_ids = {rec["run_id"] for rec in r.json()["records"]}
        assert run_ids == {"ok"}

    def test_list_filters_by_repo(self, client: TestClient, store: TrajectoryStore) -> None:
        store.insert(_rec("a", repo_key="repo_a"))
        store.insert(_rec("b", repo_key="repo_b"))
        r = client.get("/api/trajectories?repo_key=repo_a")
        assert r.status_code == 200
        assert [rec["run_id"] for rec in r.json()["records"]] == ["a"]

    def test_invalid_limit_rejected(self, client: TestClient, store: TrajectoryStore) -> None:
        r = client.get("/api/trajectories?limit=0")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /trajectories/{trajectory_id}
# ---------------------------------------------------------------------------


class TestGetTrajectory:
    def test_missing_returns_404(self, client: TestClient, store: TrajectoryStore) -> None:
        r = client.get("/api/trajectories/traj_missing")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"]

    def test_returns_record(self, client: TestClient, store: TrajectoryStore) -> None:
        store.insert(_rec("run1"))
        r = client.get(f"/api/trajectories/{make_trajectory_id('run1')}")
        assert r.status_code == 200
        assert r.json()["run_id"] == "run1"


# ---------------------------------------------------------------------------
# POST /trajectories/search
# ---------------------------------------------------------------------------


class TestSearchTrajectories:
    def test_empty_store_returns_zero_hits(
        self, client: TestClient, store: TrajectoryStore
    ) -> None:
        _install_fake_embedder({"fix bug": [1.0, 0.0, 0.0, 0.0]})
        r = client.post(
            "/api/trajectories/search",
            json={"task_description": "fix bug"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body == {"query": "fix bug", "k": 3, "hits": []}

    def test_ranks_by_semantic(self, client: TestClient, store: TrajectoryStore) -> None:
        store.insert(_rec("far", embedding=[0.0, 1.0, 0.0, 0.0]))
        store.insert(_rec("near", embedding=[1.0, 0.0, 0.0, 0.0]))
        _install_fake_embedder({"fix bug": [1.0, 0.0, 0.0, 0.0]})
        r = client.post(
            "/api/trajectories/search",
            json={"task_description": "fix bug", "k": 2},
        )
        assert r.status_code == 200
        hits = r.json()["hits"]
        assert [h["record"]["run_id"] for h in hits] == ["near", "far"]
        assert hits[0]["semantic_score"] > hits[1]["semantic_score"]

    def test_symbol_overlap_boosts(self, client: TestClient, store: TrajectoryStore) -> None:
        store.insert(_rec("plain", embedding=[1.0, 0.0, 0.0, 0.0], symbols=["x.y"]))
        store.insert(_rec("overlap", embedding=[1.0, 0.0, 0.0, 0.0], symbols=["a.b"]))
        _install_fake_embedder({"fix bug": [1.0, 0.0, 0.0, 0.0]})
        r = client.post(
            "/api/trajectories/search",
            json={
                "task_description": "fix bug",
                "current_symbols": ["a.b"],
            },
        )
        assert r.status_code == 200
        run_ids = [h["record"]["run_id"] for h in r.json()["hits"]]
        assert run_ids == ["overlap", "plain"]

    def test_verified_only_default_hides_failures(
        self, client: TestClient, store: TrajectoryStore
    ) -> None:
        store.insert(_rec("ok", status=TrajectoryStatus.SUCCESS, embedding=[1.0, 0.0, 0.0, 0.0]))
        store.insert(_rec("bad", status=TrajectoryStatus.FAILED, embedding=[1.0, 0.0, 0.0, 0.0]))
        _install_fake_embedder({"fix bug": [1.0, 0.0, 0.0, 0.0]})
        r = client.post(
            "/api/trajectories/search",
            json={"task_description": "fix bug"},
        )
        assert r.status_code == 200
        run_ids = [h["record"]["run_id"] for h in r.json()["hits"]]
        assert run_ids == ["ok"]

    def test_verified_only_false_includes_failures(
        self, client: TestClient, store: TrajectoryStore
    ) -> None:
        store.insert(_rec("ok", status=TrajectoryStatus.SUCCESS, embedding=[1.0, 0.0, 0.0, 0.0]))
        store.insert(_rec("bad", status=TrajectoryStatus.FAILED, embedding=[1.0, 0.0, 0.0, 0.0]))
        _install_fake_embedder({"fix bug": [1.0, 0.0, 0.0, 0.0]})
        r = client.post(
            "/api/trajectories/search",
            json={"task_description": "fix bug", "verified_only": False},
        )
        assert r.status_code == 200
        run_ids = {h["record"]["run_id"] for h in r.json()["hits"]}
        assert run_ids == {"ok", "bad"}

    def test_repo_key_filter(self, client: TestClient, store: TrajectoryStore) -> None:
        store.insert(_rec("a", repo_key="repo_a", embedding=[1.0, 0.0, 0.0, 0.0]))
        store.insert(_rec("b", repo_key="repo_b", embedding=[1.0, 0.0, 0.0, 0.0]))
        _install_fake_embedder({"fix bug": [1.0, 0.0, 0.0, 0.0]})
        r = client.post(
            "/api/trajectories/search",
            json={"task_description": "fix bug", "repo_key": "repo_a"},
        )
        assert r.status_code == 200
        run_ids = [h["record"]["run_id"] for h in r.json()["hits"]]
        assert run_ids == ["a"]

    def test_exclude_run_ids(self, client: TestClient, store: TrajectoryStore) -> None:
        store.insert(_rec("keep", embedding=[1.0, 0.0, 0.0, 0.0]))
        store.insert(_rec("drop", embedding=[1.0, 0.0, 0.0, 0.0]))
        _install_fake_embedder({"fix bug": [1.0, 0.0, 0.0, 0.0]})
        r = client.post(
            "/api/trajectories/search",
            json={"task_description": "fix bug", "exclude_run_ids": ["drop"]},
        )
        assert r.status_code == 200
        run_ids = [h["record"]["run_id"] for h in r.json()["hits"]]
        assert run_ids == ["keep"]

    def test_k_clamped_by_pydantic(self, client: TestClient, store: TrajectoryStore) -> None:
        r = client.post(
            "/api/trajectories/search",
            json={"task_description": "x", "k": 100},
        )
        assert r.status_code == 422

    def test_empty_task_rejected(self, client: TestClient, store: TrajectoryStore) -> None:
        r = client.post(
            "/api/trajectories/search",
            json={"task_description": ""},
        )
        assert r.status_code == 422

    def test_symptom_used_in_query(self, client: TestClient, store: TrajectoryStore) -> None:
        store.insert(_rec("run1", embedding=[1.0, 0.0, 0.0, 0.0]))
        _install_fake_embedder(
            {
                "fix bug\nsymptom: boom": [1.0, 0.0, 0.0, 0.0],
                "fix bug": [0.0, 1.0, 0.0, 0.0],  # unused if wiring correct
            }
        )
        r = client.post(
            "/api/trajectories/search",
            json={"task_description": "fix bug", "symptom": "boom"},
        )
        assert r.status_code == 200
        hits = r.json()["hits"]
        # The combined query was used → semantic_score is ~1.0.
        assert hits[0]["semantic_score"] == pytest.approx(1.0)

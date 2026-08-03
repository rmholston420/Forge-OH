"""Unit tests for TrajectoryRetriever (Rec #3, Slice F.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from openhands_tools_ext.trajectory.embedder import TrajectoryEmbedder
from openhands_tools_ext.trajectory.retriever import (
    RetrievalHit,
    TrajectoryRetriever,
    combine,
    cosine,
    jaccard,
)
from openhands_tools_ext.trajectory.schema import (
    SEMANTIC_WEIGHT,
    SYMBOL_WEIGHT,
    TrajectoryRecord,
    TrajectoryStatus,
    make_trajectory_id,
)
from openhands_tools_ext.trajectory.store import TrajectoryStore


class ProgrammableEncoder:
    """FakeEncoder that returns caller-specified vectors for known inputs."""

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


def _rec(
    run_id: str,
    *,
    status: TrajectoryStatus = TrajectoryStatus.SUCCESS,
    task: str = "task",
    symptom: str = "",
    embedding: list[float] | None = None,
    repo_key: str = "repo_main",
    symbols: list[str] | None = None,
    created_at: str = "2026-08-03T12:00:00Z",
) -> TrajectoryRecord:
    return TrajectoryRecord(
        trajectory_id=make_trajectory_id(run_id),
        run_id=run_id,
        session_id=f"sess_{run_id}",
        task_description=task,
        symptom=symptom,
        final_status=status,
        repograph_repo_key=repo_key,
        repograph_symbols=symbols or [],
        embedding=embedding,
        embedding_model="fake" if embedding else "",
        created_at=created_at,
    )


@pytest.fixture
def store(tmp_path: Path) -> TrajectoryStore:
    return TrajectoryStore(tmp_path / "traj.db")


# ---------------------------------------------------------------------------
# scoring helpers
# ---------------------------------------------------------------------------


class TestCosine:
    def test_identical_vectors(self) -> None:
        assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors(self) -> None:
        assert cosine([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_empty_vector_returns_zero(self) -> None:
        assert cosine([], [1.0]) == 0.0
        assert cosine([1.0], []) == 0.0

    def test_zero_vector_returns_zero(self) -> None:
        assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError):
            cosine([1.0, 0.0], [1.0, 0.0, 0.0])


class TestJaccard:
    def test_identical_sets(self) -> None:
        assert jaccard(["a", "b"], ["a", "b"]) == pytest.approx(1.0)

    def test_disjoint(self) -> None:
        assert jaccard(["a"], ["b"]) == 0.0

    def test_partial(self) -> None:
        # {a, b, c} vs {b, c, d}: inter=2, union=4
        assert jaccard(["a", "b", "c"], ["b", "c", "d"]) == pytest.approx(0.5)

    def test_empty_returns_zero(self) -> None:
        assert jaccard([], ["a"]) == 0.0
        assert jaccard(["a"], []) == 0.0
        assert jaccard([], []) == 0.0

    def test_dedup_within_input(self) -> None:
        assert jaccard(["a", "a", "b"], ["a", "b"]) == pytest.approx(1.0)


class TestCombine:
    def test_pure_semantic(self) -> None:
        assert combine(1.0, 0.0) == pytest.approx(SEMANTIC_WEIGHT)

    def test_pure_symbol(self) -> None:
        assert combine(0.0, 1.0) == pytest.approx(SYMBOL_WEIGHT)

    def test_both_max_is_one(self) -> None:
        assert combine(1.0, 1.0) == pytest.approx(1.0)

    def test_both_zero(self) -> None:
        assert combine(0.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# retriever
# ---------------------------------------------------------------------------


class TestTrajectoryRetriever:
    def _make_retriever(
        self,
        store: TrajectoryStore,
        mapping: dict[str, list[float]],
        dim: int = 4,
    ) -> TrajectoryRetriever:
        emb = TrajectoryEmbedder(
            device="cpu",
            loader=lambda n, d: ProgrammableEncoder(mapping, dim=dim),
        )
        return TrajectoryRetriever(store, embedder=emb)

    def test_empty_store_returns_empty(self, store: TrajectoryStore) -> None:
        r = self._make_retriever(store, {"q": [1.0, 0.0, 0.0, 0.0]})
        assert r.retrieve("q") == []

    def test_k_zero_returns_empty(self, store: TrajectoryStore) -> None:
        store.insert(_rec("run1", embedding=[1.0, 0.0, 0.0, 0.0]))
        r = self._make_retriever(store, {"q": [1.0, 0.0, 0.0, 0.0]})
        assert r.retrieve("q", k=0) == []

    def test_ranks_by_cosine_desc(self, store: TrajectoryStore) -> None:
        # Query vector aligned with e1.
        store.insert(_rec("far", embedding=[0.0, 1.0, 0.0, 0.0]))
        store.insert(_rec("mid", embedding=[0.5, 0.5, 0.0, 0.0]))
        store.insert(_rec("near", embedding=[1.0, 0.0, 0.0, 0.0]))
        r = self._make_retriever(store, {"q": [1.0, 0.0, 0.0, 0.0]})
        hits = r.retrieve("q", k=3)
        assert [h.record.run_id for h in hits] == ["near", "mid", "far"]

    def test_top_k_truncation(self, store: TrajectoryStore) -> None:
        for i in range(5):
            store.insert(
                _rec(
                    f"run{i}",
                    embedding=[float(i) / 5.0, 1.0 - float(i) / 5.0, 0.0, 0.0],
                )
            )
        r = self._make_retriever(store, {"q": [0.0, 1.0, 0.0, 0.0]})
        hits = r.retrieve("q", k=2)
        assert len(hits) == 2

    def test_skips_records_without_embedding(self, store: TrajectoryStore) -> None:
        store.insert(_rec("with", embedding=[1.0, 0.0, 0.0, 0.0]))
        store.insert(_rec("without", embedding=None))
        r = self._make_retriever(store, {"q": [1.0, 0.0, 0.0, 0.0]})
        hits = r.retrieve("q")
        assert [h.record.run_id for h in hits] == ["with"]

    def test_verified_only_filters_failures(self, store: TrajectoryStore) -> None:
        store.insert(_rec("ok", status=TrajectoryStatus.SUCCESS, embedding=[1.0, 0.0, 0.0, 0.0]))
        store.insert(_rec("bad", status=TrajectoryStatus.FAILED, embedding=[1.0, 0.0, 0.0, 0.0]))
        r = self._make_retriever(store, {"q": [1.0, 0.0, 0.0, 0.0]})
        hits = r.retrieve("q")
        assert [h.record.run_id for h in hits] == ["ok"]

    def test_verified_only_false_includes_all(self, store: TrajectoryStore) -> None:
        store.insert(_rec("ok", status=TrajectoryStatus.SUCCESS, embedding=[1.0, 0.0, 0.0, 0.0]))
        store.insert(_rec("bad", status=TrajectoryStatus.FAILED, embedding=[1.0, 0.0, 0.0, 0.0]))
        r = self._make_retriever(store, {"q": [1.0, 0.0, 0.0, 0.0]})
        hits = r.retrieve("q", verified_only=False)
        assert {h.record.run_id for h in hits} == {"ok", "bad"}

    def test_repo_key_filter(self, store: TrajectoryStore) -> None:
        store.insert(_rec("a", repo_key="repo_a", embedding=[1.0, 0.0, 0.0, 0.0]))
        store.insert(_rec("b", repo_key="repo_b", embedding=[1.0, 0.0, 0.0, 0.0]))
        r = self._make_retriever(store, {"q": [1.0, 0.0, 0.0, 0.0]})
        hits = r.retrieve("q", repo_key="repo_a")
        assert [h.record.run_id for h in hits] == ["a"]

    def test_symbol_overlap_boosts_score(self, store: TrajectoryStore) -> None:
        # Two records with identical semantic score; overlap should be the tiebreaker.
        store.insert(_rec("no_overlap", embedding=[1.0, 0.0, 0.0, 0.0], symbols=["x.y"]))
        store.insert(_rec("full_overlap", embedding=[1.0, 0.0, 0.0, 0.0], symbols=["a.b"]))
        r = self._make_retriever(store, {"q": [1.0, 0.0, 0.0, 0.0]})
        hits = r.retrieve("q", current_symbols=["a.b"])
        assert [h.record.run_id for h in hits[:2]] == ["full_overlap", "no_overlap"]
        assert hits[0].symbol_overlap == pytest.approx(1.0)
        assert hits[1].symbol_overlap == 0.0

    def test_no_current_symbols_disables_overlap(self, store: TrajectoryStore) -> None:
        store.insert(_rec("run1", embedding=[1.0, 0.0, 0.0, 0.0], symbols=["a.b"]))
        r = self._make_retriever(store, {"q": [1.0, 0.0, 0.0, 0.0]})
        hits = r.retrieve("q", current_symbols=None)
        assert hits[0].symbol_overlap == 0.0

    def test_score_is_convex_combination(self, store: TrajectoryStore) -> None:
        store.insert(_rec("run1", embedding=[1.0, 0.0, 0.0, 0.0], symbols=["a.b"]))
        r = self._make_retriever(store, {"q": [1.0, 0.0, 0.0, 0.0]})
        (hit,) = r.retrieve("q", current_symbols=["a.b"])
        # perfect cosine + perfect overlap → score = SEM_W + SYM_W = 1.
        assert hit.semantic_score == pytest.approx(1.0)
        assert hit.symbol_overlap == pytest.approx(1.0)
        assert hit.score == pytest.approx(SEMANTIC_WEIGHT + SYMBOL_WEIGHT)

    def test_exclude_run_ids(self, store: TrajectoryStore) -> None:
        store.insert(_rec("keep", embedding=[1.0, 0.0, 0.0, 0.0]))
        store.insert(_rec("drop", embedding=[1.0, 0.0, 0.0, 0.0]))
        r = self._make_retriever(store, {"q": [1.0, 0.0, 0.0, 0.0]})
        hits = r.retrieve("q", exclude_run_ids=["drop"])
        assert [h.record.run_id for h in hits] == ["keep"]

    def test_query_includes_symptom_when_provided(self, store: TrajectoryStore) -> None:
        store.insert(_rec("run1", embedding=[1.0, 0.0, 0.0, 0.0]))
        # Programmable encoder maps each exact query string to its vector.
        combined_query = "fix bug\nsymptom: boom"
        r = self._make_retriever(
            store,
            {
                combined_query: [1.0, 0.0, 0.0, 0.0],
                "fix bug": [0.0, 1.0, 0.0, 0.0],  # unused
            },
        )
        hits = r.retrieve("fix bug", symptom="boom")
        assert hits[0].semantic_score == pytest.approx(1.0)

    def test_returns_retrieval_hit_dataclass(self, store: TrajectoryStore) -> None:
        store.insert(_rec("run1", embedding=[1.0, 0.0, 0.0, 0.0]))
        r = self._make_retriever(store, {"q": [1.0, 0.0, 0.0, 0.0]})
        (hit,) = r.retrieve("q")
        assert isinstance(hit, RetrievalHit)
        assert hit.record.run_id == "run1"

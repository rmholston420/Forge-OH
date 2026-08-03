"""Retriever for TrajectoryRecords (Rec #3, Slice F.4).

Given a natural-language query (task description + optional symptom)
and the current run's touched RepoGraph symbols, return the top-k
prior trajectories ranked by::

    score = SEMANTIC_WEIGHT * cosine(query_emb, record_emb)
          + SYMBOL_WEIGHT   * jaccard(current_symbols, record_symbols)

Both terms are normalized to ``[0, 1]``. Weights come from
``schema.SEMANTIC_WEIGHT`` / ``SYMBOL_WEIGHT`` (locked at 0.7 / 0.3).

Design notes
------------
- **Retrieval scope**: only records with an embedding are considered.
  Records without an embedding (writer-emitted, indexer-pending) are
  silently skipped by :meth:`retrieve`.
- **``verified_only=True`` default**: retrieval defaults to
  successfully-verified cases so poorly-fixed prior runs don't
  propagate bad patterns (see research doc Rec #3 §F risks).
- **Repo scoping**: when ``repo_key`` is passed, only trajectories
  touching the same repo participate. Symbol overlap across different
  repos is meaningless.
- **In-memory scan**: MVP scale is thousands of records max; a plain
  Python loop with dot-product is fast enough. If it becomes hot,
  swap to a numpy matmul path without changing the public API.
"""

from __future__ import annotations

from dataclasses import dataclass

from openhands_tools_ext.trajectory.embedder import (
    TrajectoryEmbedder,
    build_query_text,
    get_default_embedder,
)
from openhands_tools_ext.trajectory.schema import (
    DEFAULT_RETRIEVAL_K,
    SEMANTIC_WEIGHT,
    SYMBOL_WEIGHT,
    TrajectoryRecord,
    TrajectoryStatus,
)
from openhands_tools_ext.trajectory.store import TrajectoryStore


@dataclass(frozen=True)
class RetrievalHit:
    """One record returned by the retriever with its component scores.

    Attributes
    ----------
    record : TrajectoryRecord
        The retrieved case.
    score : float
        The combined ``SEMANTIC_WEIGHT * semantic + SYMBOL_WEIGHT * overlap``
        used for ranking.
    semantic_score : float
        Cosine similarity in ``[-1, 1]`` (typically ``[0, 1]`` for
        normalized embeddings from a decent encoder).
    symbol_overlap : float
        Jaccard similarity in ``[0, 1]`` between the current-run
        symbols and this record's symbols. ``0.0`` when either side is
        empty.
    """

    record: TrajectoryRecord
    score: float
    semantic_score: float
    symbol_overlap: float


# ---------------------------------------------------------------------------
# scoring helpers
# ---------------------------------------------------------------------------


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors.

    We do NOT assume unit-normalized vectors here so this helper is
    reusable outside the embedder. The embedder produces normalized
    vectors, so in the hot path this reduces to a dot product.
    """
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        raise ValueError(f"vector length mismatch: {len(a)} vs {len(b)}")
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / ((na**0.5) * (nb**0.5))


def jaccard(a: list[str] | set[str], b: list[str] | set[str]) -> float:
    """Jaccard similarity between two symbol sets.

    Returns ``0.0`` when either side is empty (rather than raising or
    returning ``1.0`` on double-empty) so an unindexed run doesn't
    spuriously match every empty-symbol record.
    """
    sa = set(a)
    sb = set(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union


def combine(semantic_score: float, symbol_overlap: float) -> float:
    """Convex combination of the two normalized score components."""
    return SEMANTIC_WEIGHT * semantic_score + SYMBOL_WEIGHT * symbol_overlap


# ---------------------------------------------------------------------------
# retriever
# ---------------------------------------------------------------------------


class TrajectoryRetriever:
    """Semantic + symbol-overlap retriever over :class:`TrajectoryStore`."""

    def __init__(
        self,
        store: TrajectoryStore,
        embedder: TrajectoryEmbedder | None = None,
    ) -> None:
        self.store = store
        self._embedder = embedder  # lazy-resolved

    @property
    def embedder(self) -> TrajectoryEmbedder:
        if self._embedder is None:
            self._embedder = get_default_embedder()
        return self._embedder

    # -- public API ---------------------------------------------------------

    def retrieve(
        self,
        task_description: str,
        *,
        symptom: str = "",
        k: int = DEFAULT_RETRIEVAL_K,
        verified_only: bool = True,
        repo_key: str | None = None,
        current_symbols: list[str] | None = None,
        exclude_run_ids: list[str] | None = None,
    ) -> list[RetrievalHit]:
        """Return the top-``k`` prior trajectories similar to the query.

        Parameters
        ----------
        task_description : str
            The natural-language task about to be started.
        symptom : str, optional
            Observed error / behavior text; combined with the task via
            :func:`build_query_text`.
        k : int, optional
            Retrieval budget.
        verified_only : bool, optional
            When ``True`` (default), only records with
            ``final_status="success"`` participate. Set ``False`` to
            include failures as negative examples.
        repo_key : str | None, optional
            Restrict to trajectories touching this RepoGraph
            ``repo_key``. Required for meaningful symbol overlap; when
            omitted, symbol overlap still runs but is unlikely to hit.
        current_symbols : list[str] | None, optional
            RepoGraph symbol ids the current task is expected to
            touch. Empty / ``None`` disables symbol overlap
            (contribution = 0).
        exclude_run_ids : list[str] | None, optional
            Skip records whose ``run_id`` matches. Useful to hide the
            current in-flight run from itself.
        """
        if k <= 0:
            return []
        statuses = [TrajectoryStatus.SUCCESS] if verified_only else None
        candidates = self.store.list_all(statuses=statuses, repo_key=repo_key)

        excluded = set(exclude_run_ids or [])
        candidates = [c for c in candidates if c.run_id not in excluded]

        # Only records with an embedding participate in semantic ranking.
        embedded = [c for c in candidates if c.embedding is not None]
        if not embedded:
            return []

        query_text = build_query_text(task_description, symptom)
        query_vec = self.embedder.embed(query_text)

        current_syms = list(current_symbols) if current_symbols else []
        hits: list[RetrievalHit] = []
        for rec in embedded:
            assert rec.embedding is not None  # narrowed above
            sem = cosine(query_vec, rec.embedding)
            # Clamp cosine to [0, 1] for the combined score. Normalized
            # embeddings rarely go negative, but clamp defensively so the
            # convex combination stays in [0, 1].
            sem_clamped = max(0.0, min(1.0, sem))
            overlap = jaccard(current_syms, rec.repograph_symbols) if current_syms else 0.0
            hits.append(
                RetrievalHit(
                    record=rec,
                    score=combine(sem_clamped, overlap),
                    semantic_score=sem,
                    symbol_overlap=overlap,
                )
            )

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

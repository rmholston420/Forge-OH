"""Trajectory Memory HTTP surface (Slice F.6, Recommendation #3).

Endpoints:

* ``GET  /api/trajectories/{trajectory_id}`` — return one record.
* ``POST /api/trajectories/search``          — top-k semantic + symbol
  overlap retrieval.
* ``GET  /api/trajectories``                 — list / filter records
  (Overview widget uses this for its proactive display before diving
  into search).

The router lazily constructs a :class:`TrajectoryRetriever` per
request, sharing the process-wide store (from ``bff.deps``) and the
default embedder. Tests override the store dependency for isolation.

Errors follow the same convention as ``bff/routers/repograph.py``:
FastAPI ``HTTPException`` with ``status_code`` from ``starlette.status``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from bff.deps.trajectory_store import get_trajectory_store
from openhands_tools_ext.trajectory.retriever import (
    RetrievalHit,
    TrajectoryRetriever,
)
from openhands_tools_ext.trajectory.schema import (
    DEFAULT_RETRIEVAL_K,
    TrajectoryRecord,
    TrajectoryStatus,
)
from openhands_tools_ext.trajectory.store import TrajectoryStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trajectories", tags=["trajectories"])

# Module-level singletons to satisfy ruff B008 (no function call in defaults).
_LIMIT_QUERY = Query(default=50, ge=1, le=500)
_STATUS_QUERY = Query(default=None, alias="status")
_REPO_KEY_QUERY = Query(default=None)
_STORE_DEP = Depends(get_trajectory_store)


# ---------------------------------------------------------------------------
# request / response models
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    """Body for ``POST /api/trajectories/search``."""

    task_description: str = Field(..., min_length=1)
    symptom: str = ""
    k: int = Field(default=DEFAULT_RETRIEVAL_K, ge=1, le=25)
    verified_only: bool = True
    repo_key: str | None = None
    current_symbols: list[str] = Field(default_factory=list)
    exclude_run_ids: list[str] = Field(default_factory=list)


class SearchHit(BaseModel):
    """One retrieval hit — record + component scores."""

    record: TrajectoryRecord
    score: float
    semantic_score: float
    symbol_overlap: float


class SearchResponse(BaseModel):
    query: str
    k: int
    hits: list[SearchHit]


class ListResponse(BaseModel):
    total: int
    records: list[TrajectoryRecord]


def _hit_to_response(hit: RetrievalHit) -> SearchHit:
    return SearchHit(
        record=hit.record,
        score=hit.score,
        semantic_score=hit.semantic_score,
        symbol_overlap=hit.symbol_overlap,
    )


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=ListResponse)
def list_trajectories(
    limit: int = _LIMIT_QUERY,
    status_filter: list[TrajectoryStatus] | None = _STATUS_QUERY,
    repo_key: str | None = _REPO_KEY_QUERY,
    store: TrajectoryStore = _STORE_DEP,
) -> ListResponse:
    """List recent trajectories, optionally filtered by status / repo."""
    records = store.list_all(limit=limit, statuses=status_filter, repo_key=repo_key)
    return ListResponse(total=store.count(), records=records)


@router.get("/{trajectory_id}", response_model=TrajectoryRecord)
def get_trajectory(
    trajectory_id: str,
    store: TrajectoryStore = _STORE_DEP,
) -> TrajectoryRecord:
    """Return one record by ``trajectory_id``."""
    rec = store.get(trajectory_id)
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"trajectory {trajectory_id!r} not found",
        )
    return rec


@router.post("/search", response_model=SearchResponse)
def search_trajectories(
    body: SearchRequest,
    store: TrajectoryStore = _STORE_DEP,
) -> SearchResponse:
    """Retrieve up to ``k`` prior trajectories similar to the query."""
    retriever = TrajectoryRetriever(store)
    try:
        hits = retriever.retrieve(
            body.task_description,
            symptom=body.symptom,
            k=body.k,
            verified_only=body.verified_only,
            repo_key=body.repo_key,
            current_symbols=body.current_symbols or None,
            exclude_run_ids=body.exclude_run_ids or None,
        )
    except Exception as exc:  # pragma: no cover - defensive shim
        logger.exception("trajectory search failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"trajectory search failed: {exc}",
        ) from exc
    return SearchResponse(
        query=body.task_description,
        k=body.k,
        hits=[_hit_to_response(h) for h in hits],
    )


__all__: tuple[str, ...] = (
    "ListResponse",
    "SearchHit",
    "SearchRequest",
    "SearchResponse",
    "router",
)


def __getattr__(name: str) -> Any:  # pragma: no cover - re-export shim
    raise AttributeError(name)

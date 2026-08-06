"""QdrantVectorAdapter — VectorPort backed by Qdrant.

ADR-026 (Ratified v25) — primary adapter for
:class:`ports.vector.VectorPort`.

Design
------

The adapter itself is a thin coordinator that:

* enforces the §7 zero-trust rule on every write via
  :func:`ports.vector.validate_zero_trust_payload`;
* accepts an injected :class:`QdrantBackend` Protocol so contract tests
  use :class:`InMemoryQdrantBackend` without ever importing
  ``qdrant-client``;
* normalizes point IDs to stable UUIDv5 strings so free-form callable
  ids like ``claim-01`` survive resume-after-crash (donor Rigpa
  :class:`QdrantClaimUpserter` pattern);
* creates a collection lazily on first write, using the dimension of
  the first vector inserted;
* returns typed :class:`ports.vector.VectorHit` values from
  :meth:`search` and a typed :class:`ports.vector.SnapshotHandle` from
  :meth:`snapshot`.

``qdrant-client`` is imported lazily inside the future
:class:`RealQdrantBackend` (not shipped in Stage 1.7 — added when the
Docker Compose Qdrant service lands). The ``pyproject.toml`` runtime
dep is declared at commit time per DEBUG_LOG 2026-07-29 21:42 EDT.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from openhands_tools_ext.memory.ports.vector import (
    SnapshotHandle,
    VectorHit,
    VectorPort,
    validate_zero_trust_payload,
)

__all__ = [
    "InMemoryQdrantBackend",
    "QdrantBackend",
    "QdrantVectorAdapter",
]


#: UUIDv5 namespace for hashing free-form point ids to Qdrant-valid UUIDs.
#: Fixed URL so the mapping is reproducible across processes and hosts —
#: donor Rigpa uses the same construction (rigpa_gnosis.qdrant_upserter).
POINT_ID_NAMESPACE: uuid.UUID = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://kosmos.local/vector/points"
)


def _to_point_id(raw: str) -> str:
    """Return a Qdrant-safe point id.

    Qdrant accepts numeric ids and UUID strings. Any free-form string
    (e.g. ``claim-01``) is hashed to a stable UUIDv5 under
    :data:`POINT_ID_NAMESPACE`.
    """
    try:
        # Already a valid UUID — return canonical string.
        return str(uuid.UUID(raw))
    except (ValueError, TypeError):
        return str(uuid.uuid5(POINT_ID_NAMESPACE, raw))


# ---------------------------------------------------------------------------
# Backend seam — mirrors OtelBackend / AgeBackend / StreamClient
# ---------------------------------------------------------------------------


@runtime_checkable
class QdrantBackend(Protocol):
    """Injectable backend for :class:`QdrantVectorAdapter`.

    Lets the adapter be tested without installing ``qdrant-client``.
    Real code passes :class:`RealQdrantBackend` (imported lazily on
    demand; not shipped in Stage 1.7); tests pass
    :class:`InMemoryQdrantBackend`.
    """

    async def ensure_collection(self, name: str, *, dim: int) -> None:
        """Idempotent create-if-absent for ``name`` at dimension ``dim``."""

    async def upsert_point(
        self,
        collection: str,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None: ...

    async def search_points(
        self,
        collection: str,
        query_vector: list[float],
        limit: int,
        filter: dict[str, Any] | None,
    ) -> list[VectorHit]: ...

    async def delete_point(self, collection: str, point_id: str) -> None: ...

    async def create_snapshot(self, collection: str) -> SnapshotHandle: ...

    def is_healthy(self) -> bool: ...

    async def close(self) -> None: ...


# ---------------------------------------------------------------------------
# InMemoryQdrantBackend — in-process backend for contract tests
# ---------------------------------------------------------------------------


@dataclass
class _StoredPoint:
    vector: list[float]
    payload: dict[str, Any]


@dataclass
class _StoredCollection:
    dim: int
    points: dict[str, _StoredPoint] = field(default_factory=dict)


class InMemoryQdrantBackend:
    """In-memory Qdrant-like backend for tests.

    Implements cosine similarity in Python. Not intended for production.
    Zero third-party imports.
    """

    def __init__(self, *, healthy: bool = True) -> None:
        self.healthy = healthy
        self._collections: dict[str, _StoredCollection] = {}
        self._closed = False
        self.snapshot_calls: list[str] = []

    # ---- Collection lifecycle -----------------------------------------

    async def ensure_collection(self, name: str, *, dim: int) -> None:
        existing = self._collections.get(name)
        if existing is None:
            self._collections[name] = _StoredCollection(dim=dim)
            return
        if existing.dim != dim:
            raise ValueError(
                f"collection {name!r} already exists at dim={existing.dim}; "
                f"refusing dim={dim} write"
            )

    # ---- Point operations ---------------------------------------------

    async def upsert_point(
        self,
        collection: str,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        col = self._collections[collection]  # ensure_collection ran first
        col.points[point_id] = _StoredPoint(
            vector=list(vector), payload=dict(payload)
        )

    async def search_points(
        self,
        collection: str,
        query_vector: list[float],
        limit: int,
        filter: dict[str, Any] | None,  # noqa: A002 - matches Qdrant API
    ) -> list[VectorHit]:
        col = self._collections.get(collection)
        if col is None:
            return []
        hits: list[VectorHit] = []
        for pid, point in col.points.items():
            if filter is not None and not _matches_filter(point.payload, filter):
                continue
            score = _cosine(query_vector, point.vector)
            hits.append(VectorHit(id=pid, score=score, payload=dict(point.payload)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]

    async def delete_point(self, collection: str, point_id: str) -> None:
        col = self._collections.get(collection)
        if col is None:
            return
        col.points.pop(point_id, None)

    # ---- Snapshot -----------------------------------------------------

    async def create_snapshot(self, collection: str) -> SnapshotHandle:
        self.snapshot_calls.append(collection)
        col = self._collections.get(collection)
        if col is None:
            raise KeyError(f"unknown collection: {collection!r}")
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        name = f"{collection}-{ts}"
        return SnapshotHandle(
            collection=collection,
            name=name,
            path=f"/tmp/inmem-qdrant/{name}.snapshot",
            created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )

    # ---- Lifecycle ----------------------------------------------------

    def is_healthy(self) -> bool:
        return self.healthy and not self._closed

    async def close(self) -> None:
        self._closed = True


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _matches_filter(payload: dict[str, Any], filter: dict[str, Any]) -> bool:  # noqa: A002
    for k, v in filter.items():
        if payload.get(k) != v:
            return False
    return True


# ---------------------------------------------------------------------------
# QdrantVectorAdapter — the actual VectorPort adapter
# ---------------------------------------------------------------------------


class QdrantVectorAdapter:
    """Primary VectorPort adapter (ADR-026).

    Enforces zero-trust payload at the port layer (ADR-026 Q1). Delegates
    all backend I/O to an injected :class:`QdrantBackend`.

    Parameters
    ----------
    backend:
        In production, ``RealQdrantBackend`` wrapping ``AsyncQdrantClient``
        (not shipped in Stage 1.7 — added when Compose lands). In tests,
        :class:`InMemoryQdrantBackend`.
    """

    def __init__(self, *, backend: QdrantBackend) -> None:
        self._backend = backend
        self._lock = asyncio.Lock()
        self._closed = False

    # ---- Writes -------------------------------------------------------

    async def upsert(
        self,
        collection: str,
        id: str,  # noqa: A002 - matches Qdrant point-id argument
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        # §7 zero-trust guard — non-bypassable.
        validate_zero_trust_payload(payload)

        if not isinstance(vector, (list, tuple)) or len(vector) == 0:
            raise ValueError("vector must be a non-empty list of floats")
        if any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in vector):
            raise ValueError("vector must contain only floats")

        vec = [float(v) for v in vector]
        point_id = _to_point_id(id)

        async with self._lock:
            await self._backend.ensure_collection(collection, dim=len(vec))
            await self._backend.upsert_point(collection, point_id, vec, dict(payload))

    async def delete(
        self,
        collection: str,
        id: str,  # noqa: A002 - matches Qdrant point-id argument
    ) -> None:
        await self._backend.delete_point(collection, _to_point_id(id))

    # ---- Reads --------------------------------------------------------

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        *,
        limit: int = 10,
        filter: dict[str, Any] | None = None,  # noqa: A002 - Qdrant API
    ) -> list[VectorHit]:
        if limit <= 0:
            raise ValueError(f"limit must be positive; got {limit}")
        # ADR-056 §D3 (STATUS AMENDMENT 2026-08-01): empty query_vector is a
        # spec-legal no-op that returns an empty result set. Zetesis Stage 6.3
        # (proper) wiring calls search(collection=..., query_vector=[], limit=1)
        # as a no-op binding proof and ignores the result. Real retrieval
        # activates at Stage 6.4 via ADR-073 (EmbeddingsPort).
        if not isinstance(query_vector, (list, tuple)):
            raise ValueError("query_vector must be a list of floats")
        if len(query_vector) == 0:
            return []
        qv = [float(v) for v in query_vector]
        return await self._backend.search_points(collection, qv, limit, filter)

    async def snapshot(self, collection: str) -> SnapshotHandle:
        return await self._backend.create_snapshot(collection)

    # ---- Lifecycle ----------------------------------------------------

    def is_healthy(self) -> bool:
        # Non-throwing per ADR-023 rule 5.
        try:
            return bool(self._backend.is_healthy())
        except Exception:
            return False

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._backend.close()
        except Exception:
            # Never raise on shutdown.
            pass


# Static Protocol conformance check — mirrors Stage 1.4 / 1.5 / 1.6 pattern.
_PORT_CHECK: VectorPort = QdrantVectorAdapter(  # type: ignore[assignment]
    backend=InMemoryQdrantBackend(),
)
del _PORT_CHECK

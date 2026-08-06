"""VectorPort — formal port for approximate-nearest-neighbour vector storage.

Locked in by ADR-026 (Ratified v25). One primary adapter for Stage 1.7:
``QdrantVectorAdapter`` (qdrant-client async). A future pgvector adapter
is deferred (see ADR-026).

Design invariants
-----------------

1. Every method that touches the backend is **async**. Rationale in
   ADR-026 Q2: Qdrant is inherently network I/O and donor Rigpa uses
   ``AsyncQdrantClient`` throughout. Sync signatures would force
   plugins to wrap in ``asyncio.run`` and break composition inside
   kernel async loops. ``is_healthy`` is the exception (sync,
   non-throwing) so it can be called in hot paths.

2. ``upsert()`` **enforces §7 zero-trust at the port layer** (ADR-026
   Q1): raises ``ValueError`` if ``payload`` lacks ``provenance`` or if
   ``confidence`` is missing / not a float in ``[0.0, 1.0]``. The whole
   point of the port abstraction is to make this rule non-bypassable
   for any plugin that reaches VectorPort directly.

3. ``search()`` returns typed :class:`VectorHit` values, not raw dicts.
   Donor Rigpa returned dicts; typed dataclasses match the pattern set
   by ``SearchPort`` (ADR-021) and ``SecretValue`` (ADR-024).

4. ``snapshot()`` returns a typed :class:`SnapshotHandle` carrying the
   backend-local path so the four-store DR-drill (spec §11) can verify
   the artifact without a second round-trip.

5. ``is_healthy()`` is **non-throwing** (ADR-023 rule 5 reused).

6. ``close()`` is **idempotent** — flushes and releases the client
   once; subsequent calls no-op.

7. Nothing here imports ``qdrant_client``. The adapter package does
   that lazily via a ``QdrantBackend`` Protocol seam.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "REQUIRED_PAYLOAD_KEYS",
    "SnapshotHandle",
    "VectorHit",
    "VectorPort",
    "validate_zero_trust_payload",
]


# ---------------------------------------------------------------------------
# Typed value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VectorHit:
    """One search result: id, score, and full payload."""

    id: str
    score: float
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SnapshotHandle:
    """Handle to a Qdrant native snapshot artifact.

    ``path`` is the backend-local filesystem path (Qdrant returns this
    in the snapshot-create response). Used by the four-store DR-drill
    to verify the artifact without a second round-trip.
    """

    collection: str
    name: str
    path: str
    created_at: str  # ISO-8601


# ---------------------------------------------------------------------------
# Zero-trust payload guard (ADR-026 Q1 — enforced at port layer)
# ---------------------------------------------------------------------------


#: Payload keys required on every VectorPort write. Matches spec §7
#: zero-trust rule. Any additional keys are allowed.
REQUIRED_PAYLOAD_KEYS: frozenset[str] = frozenset({"provenance", "confidence"})


def validate_zero_trust_payload(payload: dict[str, Any]) -> None:
    """Raise ``ValueError`` if ``payload`` violates §7 zero-trust rule.

    - ``provenance`` must be present and truthy (any type — a URL,
      an event id, a plugin name).
    - ``confidence`` must be present and be a ``float`` (or ``int``) in
      ``[0.0, 1.0]``.

    This is a pure function so callers (kernel init, tests, or plugin
    code that wants to fail fast before hitting the port) can reuse it.
    """
    if not isinstance(payload, dict):
        raise ValueError(
            f"payload must be a dict; got {type(payload).__name__}"
        )
    missing = REQUIRED_PAYLOAD_KEYS - payload.keys()
    if missing:
        raise ValueError(
            f"payload missing required zero-trust keys: {sorted(missing)}"
        )
    if not payload["provenance"]:
        raise ValueError("payload['provenance'] must be truthy")
    conf = payload["confidence"]
    if not isinstance(conf, (int, float)) or isinstance(conf, bool):
        raise ValueError(
            f"payload['confidence'] must be a float; got {type(conf).__name__}"
        )
    conf_f = float(conf)
    if not (0.0 <= conf_f <= 1.0):
        raise ValueError(
            f"payload['confidence'] must be in [0.0, 1.0]; got {conf_f}"
        )


# ---------------------------------------------------------------------------
# The port
# ---------------------------------------------------------------------------


@runtime_checkable
class VectorPort(Protocol):
    """Approximate-nearest-neighbour vector storage contract.

    Adapters (Stage 1.7 ships :class:`QdrantVectorAdapter`) implement
    this Protocol. The kernel and every plugin depend on the Protocol,
    never on the vendor.
    """

    async def upsert(
        self,
        collection: str,
        id: str,  # noqa: A002 - matches Qdrant point-id argument
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        """Insert or replace one ``(id, vector, payload)`` point.

        ``collection`` is a logical namespace and is created lazily by
        the adapter on first write. ``payload`` MUST include the two
        zero-trust keys ``provenance`` and ``confidence`` per spec §7 —
        implementations raise ``ValueError`` otherwise.
        """

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        *,
        limit: int = 10,
        filter: dict[str, Any] | None = None,  # noqa: A002 - Qdrant API
    ) -> list[VectorHit]:
        """Approximate-nearest-neighbour search.

        Returns up to ``limit`` typed :class:`VectorHit` values. The
        ``filter`` argument is a key/value equality dict; the adapter
        translates it to the backend's native filter grammar.
        """

    async def delete(
        self,
        collection: str,
        id: str,  # noqa: A002 - matches Qdrant point-id argument
    ) -> None:
        """Remove one point by id. No-op if the id does not exist."""

    async def snapshot(self, collection: str) -> SnapshotHandle:
        """Take a native snapshot of ``collection``.

        Used by the four-store DR-drill (spec §11). Returns a typed
        :class:`SnapshotHandle` including the backend-local path so the
        drill script can verify the artifact directly.
        """

    def is_healthy(self) -> bool:
        """Return ``True`` iff the backend is reachable.

        Non-throwing per ADR-023 rule 5. Callers do not need to guard
        this call in hot paths.
        """

    async def close(self) -> None:
        """Release backend resources. Idempotent."""

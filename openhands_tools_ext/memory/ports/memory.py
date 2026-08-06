"""ports.memory — MemoryPort Protocol (ADR-027, extends ADR-008).

Locked in Stage 1.8. Backed by DozerDB (community Neo4j fork with enterprise
features backported permissively, per ADR-008) + Graphiti temporal index +
Agent Memory Guard v0.2.2 write-time policy filter.

Zero-trust guarantee (spec §7): every write MUST supply `provenance` and
`confidence`. Enforcement is at the port layer (this module) — non-bypassable
by any adapter or plugin. AMG runs as an additional defense-in-depth policy
layer atop the port guard, never as a replacement for it.

Canonical pattern (matches ADR-022/023/024/025/026):
- Backend-touching methods are async.
- `is_healthy()` is sync + non-throwing (ADR-023 rule 5).
- `close()` is async + idempotent.
- Typed value objects returned from reads (no raw dicts).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from numbers import Real
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "MemoryEventId",
    "MemoryEventRecord",
    "MemoryHit",
    "MemoryPort",
    "MemoryWriteBlocked",
    "MEMORY_REQUIRED_FIELDS",
    "validate_zero_trust_write",
]


MEMORY_REQUIRED_FIELDS = frozenset({"provenance", "confidence"})
"""Fields that every MemoryPort write MUST carry (spec §7 zero-trust)."""


@dataclass(frozen=True, slots=True)
class MemoryEventId:
    """Handle returned from every write. Immutable."""

    id: str
    written_at: datetime


@dataclass(frozen=True, slots=True)
class MemoryHit:
    """One row of a query_temporal / search_semantic / query result. Immutable.

    ``score`` is optional: temporal queries populate it with a naive
    substring-match indicator (``1.0`` on match), semantic queries populate
    it with the vector-similarity score returned by the underlying
    ``VectorPort`` adapter, and callers that don't care about score set it
    to ``None``.
    """

    id: str
    payload: dict[str, Any]
    score: float | None = None
    as_of: datetime | None = None


@dataclass(frozen=True, slots=True)
class MemoryEventRecord:
    """One recent-writes row returned by ``MemoryPort.list_recent_writes``.

    Immutable projection of a persisted ``:MemoryEvent`` node, shaped for the
    memory-inspector UI (Stage 5.6a / ADR-024). Read-only surface — does not
    expose the underlying graph handle.

    Fields mirror the payload written by ``write_event``:
        - ``id``              — the UUID assigned at write time (same value as
          ``MemoryEventId.id``).
        - ``subject`` / ``predicate`` / ``object`` — the ADR-021 triple.
        - ``provenance``      — required by spec §7 zero-trust.
        - ``confidence``      — required by spec §7 zero-trust, ``[0.0, 1.0]``.
        - ``pii_tier``        — policy tier tag (default ``"Public"``).
        - ``source_citation`` — optional caller-provided citation string.
        - ``written_at``      — UTC timestamp assigned at write time.
    """

    id: str
    subject: str
    predicate: str
    object: str
    provenance: str
    confidence: float
    pii_tier: str
    source_citation: str | None
    written_at: datetime


class MemoryWriteBlocked(RuntimeError):
    """Raised by an adapter when Agent Memory Guard returns `block`.

    Port-level guard failures raise `ValueError` (constructor-time invariant).
    AMG `block` failures raise this (runtime policy invariant) so callers can
    distinguish "you passed bad args" from "policy says no".
    """


def validate_zero_trust_write(
    *,
    provenance: Any,
    confidence: Any,
) -> None:
    """Enforce spec §7 zero-trust guarantee at the port layer.

    Raises ValueError on:
    - falsy / empty / non-string provenance
    - missing confidence
    - confidence that is not a real number
    - confidence outside [0.0, 1.0]
    - confidence that is a bool (mirrors ADR-026 rule; bool is a subclass of
      int in Python and would otherwise pass a numeric check silently)

    This is a pure function. Adapters MUST call it before any backend I/O.
    Non-bypassable.
    """
    if not isinstance(provenance, str) or not provenance:
        raise ValueError(
            "MemoryPort write requires non-empty string 'provenance' "
            "(spec §7 zero-trust; ADR-027)."
        )
    if isinstance(confidence, bool):
        raise ValueError(
            "MemoryPort 'confidence' must be a real number in [0.0, 1.0], "
            "not bool (spec §7 zero-trust; ADR-027)."
        )
    if not isinstance(confidence, Real):
        raise ValueError(
            "MemoryPort 'confidence' must be a real number in [0.0, 1.0] "
            "(spec §7 zero-trust; ADR-027)."
        )
    conf = float(confidence)
    if conf < 0.0 or conf > 1.0:
        raise ValueError(
            f"MemoryPort 'confidence' must be in [0.0, 1.0], got {conf} "
            "(spec §7 zero-trust; ADR-027)."
        )


@runtime_checkable
class MemoryPort(Protocol):
    """Kosmos MemoryPort — the sole plugin-visible memory interface.

    Backed by a graph store (DozerDB, ADR-008), a temporal index (Graphiti),
    and a write-time policy filter (Agent Memory Guard v0.2.2). Plugins MUST
    NOT import any of those directly; all coupling flows through this port.
    """

    async def write_event(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        provenance: str,
        confidence: float,
        source_citation: str | None = None,
        pii_tier: str = "Public",
        attributes: dict[str, Any] | None = None,
    ) -> MemoryEventId:
        """Persist a typed claim-triple (subject, predicate, object).

        Raises:
            ValueError: port-level zero-trust guard failed (missing/invalid
                provenance or confidence).
            MemoryWriteBlocked: Agent Memory Guard returned `block`.
        """
        ...

    async def query_temporal(
        self,
        cypher_or_query: str,
        *,
        as_of: datetime | None = None,
        limit: int = 20,
    ) -> list[MemoryHit]:
        """Query the temporal graph.

        If `as_of` is provided, results reflect graph state at that moment.
        `cypher_or_query` may be a Cypher fragment (adapter-interpreted) or
        a natural-language query if the temporal index supports it (Graphiti
        does; other backends may not).
        """
        ...

    async def link_entities(
        self,
        source_id: str,
        target_id: str,
        relationship: str,
        *,
        provenance: str,
        confidence: float,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Create a directed typed edge between two existing memory nodes.

        Raises:
            ValueError: port-level zero-trust guard failed.
            MemoryWriteBlocked: AMG returned `block`.
        """
        ...

    async def quarantine_write(
        self,
        payload: dict[str, Any],
        *,
        reason: str,
        provenance: str,
        confidence: float,
    ) -> MemoryEventId:
        """Route an untrusted write to the quarantine lane (spec §115).

        Payloads land in a Gnosis sub-table (semantically a graph subgraph
        tagged `:Quarantined`), pending Tier-1/Tier-2 review before promotion
        to durable semantic memory.

        Raises:
            ValueError: port-level zero-trust guard failed.
        """
        ...

    async def list_recent_writes(
        self,
        *,
        limit: int = 50,
    ) -> list["MemoryEventRecord"]:
        """Return the ``limit`` most recent ``:MemoryEvent`` writes, newest first.

        Read-only inspection surface used by the memory-inspector UI
        (Stage 5.6a / ADR-024). Sort key is the ``written_at`` timestamp set
        by ``write_event``. Adapters MUST NOT block on this; if the backend
        is closed or unreachable, they MAY return an empty list rather than
        raise (the inspector renders an empty state).
        """
        ...

    async def search_semantic(
        self,
        query: str,
        *,
        corpus: str | None = None,
        limit: int = 20,
        min_score: float = 0.0,
    ) -> list[MemoryHit]:
        """Semantic nearest-neighbour retrieval (ADR-074).

        Embeds ``query`` via ``EmbeddingsPort`` and searches the DozerDB
        memory-vector namespace via ``VectorPort``, then re-hydrates each
        vector hit into a ``MemoryHit`` carrying the full stored payload
        (including provenance + confidence) and the raw similarity score.

        ``corpus`` selects the logical vector collection
        (``kosmos-memory-{corpus or "default"}``). ``min_score`` filters
        out hits below the given cosine similarity; ``0.0`` keeps every
        hit the vector store returns.

        Adapters MAY degrade to an empty list when the composed
        ``EmbeddingsPort`` or ``VectorPort`` is not booted; they MUST
        NOT swallow port-level guard failures (``ValueError`` is
        re-raised so callers see the bug immediately).
        """
        ...

    def is_healthy(self) -> bool:
        """Sync, non-throwing readiness probe (ADR-023 rule 5).

        MUST NOT raise. On error, return False and log.
        """
        ...

    async def close(self) -> None:
        """Idempotent teardown. Safe to call multiple times."""
        ...

"""openhands_tools_ext.memory.adapters.dozerdb.adapter — DozerDB MemoryPort adapter.

Ported from Kosmos `adapters.memory.dozerdb.adapter` @ SHA c455165 per
Forge-OH ADR-021 (Stage 5.3b). See PORTING_LEDGER.md for provenance.

Architecture (three injectable Protocol seams):

    DozerDbMemoryAdapter                          (implements MemoryPort)
      ├── GraphBackend         (Cypher I/O — DozerDB in prod, in-mem in tests)
      ├── AmgPolicy            (NoOpAmgPolicy in Forge-OH; see ADR-021 D5)
      └── TemporalIndex        (DozerDbTemporalIndex in prod, in-mem in tests)

Plugins MUST depend on `openhands_tools_ext.memory.ports.memory.MemoryPort`
only — never on `DozerDbMemoryAdapter` or `neo4j` directly (ADR-007).

Write path (enforced order):
    1. `ports.memory.validate_zero_trust_write` — non-bypassable floor.
    2. `AmgPolicy.evaluate(...)` — allow / redact / quarantine / block
       (NoOp in Forge-OH; policy layer preserved for future re-wiring).
    3. `GraphBackend` transaction — CIDOC-CRM reified-event shape
       (:Entity)+(:MemoryEvent)+(:Entity) with [:SUBJECT_OF]/[:OBJECT_OF]
       edges (ADR-021 D1).
    4. `TemporalIndex.record_event(...)` — DozerDbTemporalIndex fulltext
       registration (ADR-021 D2).

Read path:
    1. `TemporalIndex.query_temporal(...)` — DozerDbTemporalIndex Lucene
       fulltext in prod; in-memory scan for tests.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol, runtime_checkable

from openhands_tools_ext.memory.ports.embeddings import EmbeddingsPort
from openhands_tools_ext.memory.ports.memory import (
    MemoryEventId,
    MemoryEventRecord,
    MemoryHit,
    MemoryPort,
    MemoryWriteBlocked,
    validate_zero_trust_write,
)
from openhands_tools_ext.memory.ports.vector import VectorPort

from .semantic_memory_path import SemanticMemoryPath

__all__ = [
    "AlwaysBlockAmgPolicy",
    "AlwaysQuarantineAmgPolicy",
    "AmgPolicy",
    "AmgVerdict",
    "DozerDbMemoryAdapter",
    "GraphBackend",
    "InMemoryGraphBackend",
    "InMemoryTemporalIndex",
    "NoOpAmgPolicy",
    "TemporalIndex",
]


log = logging.getLogger(__name__)


# ── AmgPolicy Protocol + verdict + test doubles ─────────────────────────────


@dataclass(frozen=True, slots=True)
class AmgVerdict:
    """Result of an Agent Memory Guard policy evaluation."""

    decision: Literal["allow", "redact", "quarantine", "block"]
    reason: str = ""
    redacted_payload: dict[str, Any] | None = None


@runtime_checkable
class AmgPolicy(Protocol):
    """Agent Memory Guard policy interface (write-time filter).

    Forge-OH wires `NoOpAmgPolicy` at the composition root (ADR-021 D5).
    The `AmgGuardPolicy` implementation from Kosmos is intentionally not
    ported — the AMG PyPI dep stays out of Forge-OH. In-memory
    `AlwaysBlock` / `AlwaysQuarantine` implementations below are used for
    contract tests.
    """

    def evaluate(self, payload: dict[str, Any]) -> AmgVerdict: ...


class NoOpAmgPolicy:
    """AmgPolicy test double that always returns `allow`."""

    def evaluate(self, payload: dict[str, Any]) -> AmgVerdict:
        return AmgVerdict(decision="allow")


class AlwaysBlockAmgPolicy:
    """AmgPolicy test double that always returns `block`."""

    def __init__(self, reason: str = "test-block") -> None:
        self._reason = reason

    def evaluate(self, payload: dict[str, Any]) -> AmgVerdict:
        return AmgVerdict(decision="block", reason=self._reason)


class AlwaysQuarantineAmgPolicy:
    """AmgPolicy test double that always returns `quarantine`."""

    def __init__(self, reason: str = "test-quarantine") -> None:
        self._reason = reason

    def evaluate(self, payload: dict[str, Any]) -> AmgVerdict:
        return AmgVerdict(decision="quarantine", reason=self._reason)


# ── GraphBackend Protocol + in-memory test backend ──────────────────────────


@runtime_checkable
class GraphBackend(Protocol):
    """Cypher-shaped graph store abstraction.

    Real backend: `DozerDbGraphBackend` (Bolt to DozerDB via `neo4j` driver).
    Test backend: `InMemoryGraphBackend` (pure-Python dicts).

    All methods are async. `is_healthy` is sync + non-throwing (ADR-023
    rule 5). `close` is async + idempotent.
    """

    async def add_node(self, label: str, props: dict[str, Any]) -> str: ...
    async def add_edge(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        props: dict[str, Any] | None,
    ) -> None: ...
    async def query_cypher(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...
    async def delete_node(self, node_id: str) -> None: ...
    def is_healthy(self) -> bool: ...
    async def close(self) -> None: ...


class InMemoryGraphBackend:
    """Pure-Python `GraphBackend` for contract tests. Zero third-party deps.

    Supports the small subset of Cypher used by the adapter: substring match
    against node label or props via a simple parametric interpreter. Not a
    general-purpose Cypher engine.
    """

    def __init__(self, *, fail_healthy: bool = False) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[dict[str, Any]] = []
        self._closed = False
        self._fail_healthy = fail_healthy

    async def add_node(self, label: str, props: dict[str, Any]) -> str:
        node_id = props.get("id") or str(uuid.uuid4())
        self._nodes[node_id] = {"id": node_id, "label": label, **props}
        return node_id

    async def add_edge(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        props: dict[str, Any] | None,
    ) -> None:
        self._edges.append(
            {
                "from": from_id,
                "to": to_id,
                "rel_type": rel_type,
                "props": dict(props or {}),
            }
        )

    async def query_cypher(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Minimal query: `label:<Label>` returns all nodes with that label;
        `contains:<substr>` returns nodes whose payload dumps to `substr`.
        Anything else returns all nodes. Test-only semantics.
        """
        needle = (cypher or "").strip()
        if needle.startswith("label:"):
            label = needle.split(":", 1)[1].strip()
            return [n for n in self._nodes.values() if n.get("label") == label]
        if needle.startswith("contains:"):
            frag = needle.split(":", 1)[1].strip().lower()
            return [n for n in self._nodes.values() if frag in str(n).lower()]
        return list(self._nodes.values())

    async def delete_node(self, node_id: str) -> None:
        self._nodes.pop(node_id, None)
        self._edges = [
            e for e in self._edges if e["from"] != node_id and e["to"] != node_id
        ]

    def is_healthy(self) -> bool:
        if self._fail_healthy:
            return False
        return not self._closed

    async def close(self) -> None:
        self._closed = True


# ── TemporalIndex Protocol + in-memory test backend ─────────────────────────


@runtime_checkable
class TemporalIndex(Protocol):
    """Temporal knowledge-graph indexer.

    Real backend: `DozerDbTemporalIndex` (plain Cypher over Neo4j fulltext
    + range indexes; see ADR-021 D2/D3).
    Test backend: `InMemoryTemporalIndex`.
    """

    async def record_event(
        self,
        event_id: str,
        payload: dict[str, Any],
        *,
        as_of: datetime,
    ) -> None: ...
    async def query_temporal(
        self,
        query: str,
        *,
        as_of: datetime | None = None,
        limit: int = 20,
    ) -> list[MemoryHit]: ...
    async def close(self) -> None: ...


@dataclass
class _Episode:
    id: str
    payload: dict[str, Any]
    as_of: datetime


class InMemoryTemporalIndex:
    """Pure-Python `TemporalIndex` for contract tests."""

    def __init__(self) -> None:
        self._episodes: list[_Episode] = []

    async def record_event(
        self,
        event_id: str,
        payload: dict[str, Any],
        *,
        as_of: datetime,
    ) -> None:
        self._episodes.append(_Episode(id=event_id, payload=dict(payload), as_of=as_of))

    async def query_temporal(
        self,
        query: str,
        *,
        as_of: datetime | None = None,
        limit: int = 20,
    ) -> list[MemoryHit]:
        hits: list[MemoryHit] = []
        needle = (query or "").lower()
        for ep in self._episodes:
            if as_of is not None and ep.as_of > as_of:
                continue
            payload_dump = str(ep.payload).lower()
            score = 1.0 if not needle or needle in payload_dump else 0.0
            if score == 0.0 and needle:
                continue
            hits.append(
                MemoryHit(id=ep.id, payload=dict(ep.payload), score=score, as_of=ep.as_of)
            )
            if len(hits) >= limit:
                break
        return hits

    async def close(self) -> None:
        return None


# ── Stage 5.6a helpers (ADR-024): recent-writes projection ───────────────

# Cypher forms per backend. The in-memory backend honours ``label:<Label>``
# as a special-case shortcut (see ``InMemoryGraphBackend.query_cypher``);
# the Bolt-backed backend forwards its argument verbatim to
# ``session.run`` so needs full Cypher. Both must yield rows whose
# properties include the fields written by ``write_event``: ``id``,
# ``subject``, ``predicate``, ``object``, ``provenance``, ``confidence``,
# ``pii_tier``, ``source_citation``, ``written_at``.
_RECENT_WRITES_CYPHER: dict[str, str] = {
    "InMemoryGraphBackend": "label:MemoryEvent",
    "__default__": (
        "MATCH (e:MemoryEvent) "
        "RETURN e.id AS id, e.subject AS subject, e.predicate AS predicate, "
        "       e.object AS object, e.provenance AS provenance, "
        "       e.confidence AS confidence, e.pii_tier AS pii_tier, "
        "       e.source_citation AS source_citation, "
        "       e.written_at AS written_at "
        "ORDER BY e.written_at DESC "
        "LIMIT $limit"
    ),
}


def _record_from_props(props: dict[str, Any]) -> MemoryEventRecord | None:
    """Project a MemoryEvent props dict into a ``MemoryEventRecord``.

    Returns ``None`` for rows that don't carry the mandatory triple + zero-trust
    fields — defensive against schema drift or partial writes surfaced by an
    older backend. Never raises.
    """
    try:
        event_id = props.get("id")
        subject = props.get("subject")
        predicate = props.get("predicate")
        obj = props.get("object")
        provenance = props.get("provenance")
        confidence = props.get("confidence")
        written_at = props.get("written_at")
        if not all(
            isinstance(v, str) and v
            for v in (event_id, subject, predicate, obj, provenance)
        ):
            return None
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            return None
        # written_at is stored as ISO-8601 string; accept datetime pass-through too.
        if isinstance(written_at, str):
            try:
                written_at_dt = datetime.fromisoformat(written_at)
            except ValueError:
                return None
        elif isinstance(written_at, datetime):
            written_at_dt = written_at
        else:
            return None
        source_citation = props.get("source_citation")
        if source_citation is not None and not isinstance(source_citation, str):
            source_citation = None
        pii_tier = props.get("pii_tier") or "Public"
        if not isinstance(pii_tier, str):
            pii_tier = "Public"
        return MemoryEventRecord(
            id=event_id,
            subject=subject,
            predicate=predicate,
            object=obj,
            provenance=provenance,
            confidence=float(confidence),
            pii_tier=pii_tier,
            source_citation=source_citation,
            written_at=written_at_dt,
        )
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("_record_from_props swallowed error: %s", exc)
        return None


# ── DozerDbMemoryAdapter ────────────────────────────────────────────────────


@dataclass
class _AdapterOptions:
    """Constructor options captured for is_healthy / close bookkeeping."""

    closed: bool = False
    close_errors_swallowed: list[str] = field(default_factory=list)


class DozerDbMemoryAdapter:
    """MemoryPort adapter backed by DozerDB (Neo4j-compatible).

    Wiring is via injected `GraphBackend`, `AmgPolicy`, `TemporalIndex`
    Protocol implementations. Contract tests use in-memory backends
    declared above; Forge-OH production wiring (see
    ``openhands_tools_ext.memory.composition``) uses `DozerDbGraphBackend`
    (`neo4j` Bolt driver), `NoOpAmgPolicy` (ADR-021 D5), and
    `DozerDbTemporalIndex` (plain Cypher fulltext, ADR-021 D2).

    Zero-trust guarantee: every write path calls
    ``openhands_tools_ext.memory.ports.memory.validate_zero_trust_write``
    before any backend I/O.
    """

    def __init__(
        self,
        *,
        graph: GraphBackend,
        amg: AmgPolicy,
        temporal: TemporalIndex,
        embeddings: EmbeddingsPort | None = None,
        vector: VectorPort | None = None,
        default_corpus: str | None = None,
    ) -> None:
        self._graph = graph
        self._amg = amg
        self._temporal = temporal
        # ADR-074 D3: optional semantic memory lane. Constructed only
        # when BOTH ports are wired. When absent, ``search_semantic``
        # degrades to an empty list and ``write_event`` skips the
        # embed+upsert side effect.
        self._semantic: SemanticMemoryPath | None = None
        if embeddings is not None and vector is not None:
            self._semantic = SemanticMemoryPath(
                embeddings=embeddings,
                vector=vector,
            )
        self._default_corpus = default_corpus
        self._state = _AdapterOptions()

    # ── writes ──────────────────────────────────────────────────────────

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
        # 1. Non-bypassable port-level guard (spec §7).
        validate_zero_trust_write(provenance=provenance, confidence=confidence)

        payload: dict[str, Any] = {
            "subject": subject,
            "predicate": predicate,
            "object": object,
            "provenance": provenance,
            "confidence": float(confidence),
            "pii_tier": pii_tier,
            "source_citation": source_citation,
            "attributes": dict(attributes or {}),
        }

        # 2. Agent Memory Guard policy layer.
        verdict = self._amg.evaluate(payload)
        if verdict.decision == "block":
            raise MemoryWriteBlocked(verdict.reason or "AMG blocked write")
        if verdict.decision == "redact" and verdict.redacted_payload is not None:
            payload = dict(verdict.redacted_payload)
        if verdict.decision == "quarantine":
            # Route via quarantine lane with the same provenance/confidence.
            return await self.quarantine_write(
                payload,
                reason=verdict.reason or "AMG quarantine",
                provenance=provenance,
                confidence=float(confidence),
            )

        # 3. Graph write. CIDOC-CRM reified-event shape (ADR-021 D1):
        #    (:Entity {role:'subject'}) + (:MemoryEvent) + (:Entity {role:'object'})
        #    with (:MemoryEvent)-[:SUBJECT_OF]->(:Entity) and
        #         (:MemoryEvent)-[:OBJECT_OF ]->(:Entity).
        #    The event is a first-class addressable node; there is no direct
        #    (:Entity)-[:PREDICATE]->(:Entity) edge — traversal goes through
        #    the event so multiple provenanced/timed events between the same
        #    subject/object are all representable.
        written_at = datetime.now(timezone.utc)
        event_id = str(uuid.uuid4())

        subject_id = await self._graph.add_node(
            "Entity", {"value": subject, "role": "subject"}
        )
        object_id = await self._graph.add_node(
            "Entity", {"value": object, "role": "object"}
        )
        event_props = {
            "id": event_id,
            "predicate": predicate,
            "written_at": written_at.isoformat(),
            **payload,
        }
        await self._graph.add_node("MemoryEvent", event_props)
        await self._graph.add_edge(
            event_id, subject_id, "SUBJECT_OF", {"role": "subject"}
        )
        await self._graph.add_edge(
            event_id, object_id, "OBJECT_OF", {"role": "object"}
        )

        # 4. Temporal index registration.
        await self._temporal.record_event(event_id, payload, as_of=written_at)

        # 5. Semantic memory lane (ADR-074 D3). Optional side effect;
        #    failures are logged but do not affect the primary write.
        #    Corpus resolution: attributes["corpus_name"] > default_corpus.
        if self._semantic is not None:
            corpus = (
                (attributes or {}).get("corpus_name")
                or self._default_corpus
            )
            await self._semantic.embed_and_upsert(
                event_id,
                payload,
                corpus=corpus,
                as_of=written_at,
            )

        return MemoryEventId(id=event_id, written_at=written_at)

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
        validate_zero_trust_write(provenance=provenance, confidence=confidence)
        payload = {
            "source_id": source_id,
            "target_id": target_id,
            "relationship": relationship,
            "provenance": provenance,
            "confidence": float(confidence),
            "attributes": dict(attributes or {}),
        }
        verdict = self._amg.evaluate(payload)
        if verdict.decision == "block":
            raise MemoryWriteBlocked(verdict.reason or "AMG blocked link")
        if verdict.decision == "quarantine":
            await self.quarantine_write(
                payload,
                reason=verdict.reason or "AMG quarantine",
                provenance=provenance,
                confidence=float(confidence),
            )
            return
        # allow / redact both proceed to the graph.
        edge_props = payload
        if verdict.decision == "redact" and verdict.redacted_payload is not None:
            edge_props = dict(verdict.redacted_payload)
        await self._graph.add_edge(source_id, target_id, relationship, edge_props)

    async def quarantine_write(
        self,
        payload: dict[str, Any],
        *,
        reason: str,
        provenance: str,
        confidence: float,
    ) -> MemoryEventId:
        validate_zero_trust_write(provenance=provenance, confidence=confidence)
        written_at = datetime.now(timezone.utc)
        event_id = str(uuid.uuid4())
        node_props = {
            "id": event_id,
            "reason": reason,
            "provenance": provenance,
            "confidence": float(confidence),
            "written_at": written_at.isoformat(),
            "quarantined_payload": dict(payload),
        }
        await self._graph.add_node("Quarantined", node_props)
        # Quarantined writes are NOT indexed in the temporal index — they are
        # not semantic memory until reviewed and promoted.
        return MemoryEventId(id=event_id, written_at=written_at)

    # ── reads ───────────────────────────────────────────────────────────

    async def query_temporal(
        self,
        cypher_or_query: str,
        *,
        as_of: datetime | None = None,
        limit: int = 20,
    ) -> list[MemoryHit]:
        return await self._temporal.query_temporal(
            cypher_or_query, as_of=as_of, limit=limit
        )

    async def list_recent_writes(
        self,
        *,
        limit: int = 50,
    ) -> list[MemoryEventRecord]:
        """Return the ``limit`` most recent ``:MemoryEvent`` writes, newest first.

        Stage 5.6a / ADR-024. Read-only inspection surface for the
        memory-inspector UI. Sort key is the ``written_at`` ISO-8601 string
        set by ``write_event``; strings compare correctly because every write
        stamps ``datetime.now(timezone.utc).isoformat()`` (fixed 26-char UTC).

        Executes a bounded Cypher query against the graph backend. Adapters
        MUST NOT swallow programmer errors (bad ``limit``) but MAY return an
        empty list when the backend is closed or the query returns nothing.
        """
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError(
                f"list_recent_writes: limit must be a positive int, got {limit!r}"
            )
        if self._state.closed:
            return []

        rows = await self._graph.query_cypher(
            # `label:MemoryEvent` is honoured by both the real Bolt backend
            # (see DozerDbGraphBackend._run: this string is executed as-is
            # against a live DozerDB session; we use a normal Cypher form for
            # production) and by the in-memory backend (special-case shortcut).
            #
            # For the in-memory backend the `label:MemoryEvent` prefix returns
            # all `:MemoryEvent` nodes; for the Bolt backend we need real
            # Cypher. We branch on backend type via duck-typed detection:
            # if the backend supports the shortcut form we use it; otherwise
            # we send full Cypher. The bolt backend's query_cypher passes
            # the string straight to `session.run`, so a Cypher string works.
            _RECENT_WRITES_CYPHER.get(
                type(self._graph).__name__,
                _RECENT_WRITES_CYPHER["__default__"],
            ),
            {"limit": int(limit)},
        )
        out: list[MemoryEventRecord] = []
        for row in rows:
            # The Bolt backend returns Cypher projections keyed by the
            # RETURN aliases (`id`, `subject`, ...). The in-memory backend
            # returns raw node dicts (`{"id": ..., "label": "MemoryEvent",
            # ...payload}`); we accept either shape.
            props: dict[str, Any] = dict(row)
            if props.get("label") == "MemoryEvent":
                # in-memory backend row — already a payload dict
                pass
            record = _record_from_props(props)
            if record is not None:
                out.append(record)
        # In-memory backend has no ORDER BY — sort newest-first here so both
        # backends satisfy the contract.
        out.sort(key=lambda r: r.written_at, reverse=True)
        return out[:limit]

    async def search_semantic(
        self,
        query: str,
        *,
        corpus: str | None = None,
        limit: int = 20,
        min_score: float = 0.0,
    ) -> list[MemoryHit]:
        """Semantic retrieval via EmbeddingsPort + VectorPort (ADR-074 D1).

        Degrades to an empty list when the semantic lane is unwired
        (either dependency ``None`` at construction time).
        """
        if self._semantic is None:
            return []
        resolved_corpus = corpus or self._default_corpus
        return await self._semantic.semantic_lookup(
            query,
            corpus=resolved_corpus,
            limit=limit,
            min_score=min_score,
        )

    # ── lifecycle ───────────────────────────────────────────────────────

    def is_healthy(self) -> bool:
        """Sync, non-throwing (ADR-023 rule 5)."""
        try:
            if self._state.closed:
                return False
            return bool(self._graph.is_healthy())
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("memory.is_healthy raised: %s", exc)
            return False

    async def close(self) -> None:
        """Idempotent — safe to call multiple times."""
        if self._state.closed:
            return
        self._state.closed = True
        for name, obj in (("graph", self._graph), ("temporal", self._temporal)):
            try:
                await obj.close()
            except Exception as exc:  # noqa: BLE001 - swallow per ADR-023 rule 5
                self._state.close_errors_swallowed.append(f"{name}: {exc}")
                log.warning("memory.close swallowed %s.close error: %s", name, exc)

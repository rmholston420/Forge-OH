"""openhands_tools_ext.memory.adapters.dozerdb.dozerdb_temporal_index — Cypher fulltext temporal index.

New Forge-OH code (Stage 5.3b, ADR-021 D2/D3). Replaces Kosmos's deleted
``GraphitiTemporalIndex`` with a plain-Cypher implementation over the same
``:MemoryEvent`` nodes that ``DozerDbMemoryAdapter.write_event`` already
writes via ``GraphBackend.add_node``.

Design (ADR-021 D2/D3):
- Storage is co-located with the graph: ``:MemoryEvent`` nodes carry all
  searchable fields (``subject``/``predicate``/``object``/
  ``source_citation``/``written_at``/...). ``record_event`` is a no-op for
  persistence — the graph write already happened. Its only side effect is
  lazy, idempotent index creation on first call.
- Indexes: one Lucene FULLTEXT INDEX over subject/predicate/object/
  source_citation, one RANGE INDEX over ``written_at``, one UNIQUENESS
  CONSTRAINT on ``id``.
- ``query_temporal`` executes ``db.index.fulltext.queryNodes`` against the
  fulltext index, filters ``written_at <= as_of`` via the range index, and
  returns typed ``MemoryHit`` objects.

Zero-trust: no user input is interpolated into Cypher. Only ``$query`` (as
a Lucene query string), ``$as_of_iso`` (ISO-8601 string), and ``$limit``
(int) cross the driver boundary as parameters.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from openhands_tools_ext.memory.ports.memory import MemoryHit

log = logging.getLogger(__name__)

# All (label, index name, DDL) triples for idempotent boot-time creation.
_INDEX_DDL: tuple[tuple[str, str], ...] = (
    (
        "memory_event_text",
        "CREATE FULLTEXT INDEX memory_event_text IF NOT EXISTS "
        "FOR (n:MemoryEvent) ON EACH "
        "[n.subject, n.predicate, n.object, n.source_citation]",
    ),
    (
        "memory_event_written_at",
        "CREATE RANGE INDEX memory_event_written_at IF NOT EXISTS "
        "FOR (n:MemoryEvent) ON (n.written_at)",
    ),
    (
        "memory_event_id_unique",
        "CREATE CONSTRAINT memory_event_id_unique IF NOT EXISTS "
        "FOR (n:MemoryEvent) REQUIRE n.id IS UNIQUE",
    ),
)


# Lucene reserved characters: + - && || ! ( ) { } [ ] ^ " ~ * ? : \ /
# See https://lucene.apache.org/core/9_0_0/queryparser/org/apache/lucene/queryparser/classic/package-summary.html
_LUCENE_ESCAPE_CHARS = r'+-&|!(){}[]^"~*?:\/'


def _escape_lucene(query: str) -> str:
    """Escape Lucene syntax so callers can pass arbitrary user text.

    Users of ``query_temporal`` pass plain natural-language strings; treat
    them as literal terms and escape any Lucene metacharacters. Callers
    that DO want Lucene syntax (e.g. field-scoped queries) can bypass this
    by calling ``query_cypher`` on the graph backend directly.
    """
    out: list[str] = []
    for ch in query:
        if ch in _LUCENE_ESCAPE_CHARS:
            out.append("\\")
        out.append(ch)
    return "".join(out)


class DozerDbTemporalIndex:
    """Plain-Cypher TemporalIndex over ``:MemoryEvent`` nodes (ADR-021).

    Requires a ``DozerDbGraphBackend`` (or any Protocol-compatible backend
    that supports ``query_cypher``). Does NOT own the connection lifecycle —
    the graph backend is closed by ``DozerDbMemoryAdapter.close``.

    Read the module docstring for the storage-colocation design.
    """

    def __init__(self, graph: Any) -> None:
        """Wire the temporal index against a graph backend.

        ``graph`` must satisfy the ``GraphBackend`` Protocol
        (``query_cypher``, ``close``). Typing is ``Any`` to avoid a
        circular import with ``adapter.py``.
        """
        self._graph = graph
        self._indexes_ready = False
        self._closed = False

    # ── TemporalIndex Protocol ─────────────────────────────────────────

    async def record_event(
        self,
        event_id: str,
        payload: dict[str, Any],
        *,
        as_of: datetime,
    ) -> None:
        """No-op for storage; ensures indexes exist on first call.

        The graph backend has already written the ``:MemoryEvent`` node
        with all searchable fields (see ``DozerDbMemoryAdapter.write_event``
        step 3, ADR-021 D1). This method exists to satisfy the
        ``TemporalIndex`` Protocol and to lazy-create the fulltext/range
        indexes idempotently.
        """
        if self._closed:
            raise RuntimeError("DozerDbTemporalIndex is closed")
        if not self._indexes_ready:
            await self._ensure_indexes()
        # event_id / payload / as_of are unused: the graph write already
        # captured them. Kept for Protocol conformance.
        _ = event_id, payload, as_of

    async def query_temporal(
        self,
        query: str,
        *,
        as_of: datetime | None = None,
        limit: int = 20,
    ) -> list[MemoryHit]:
        """Lucene fulltext search over ``:MemoryEvent`` with optional as-of filter.

        Empty query → returns the ``limit`` most recent events (matches
        the InMemoryTemporalIndex semantic of returning all events when
        needle is empty). Non-empty query → Lucene fulltext search over
        subject/predicate/object/source_citation.

        ``as_of`` filters to events with ``written_at <= as_of`` (string
        comparison on ISO-8601 timestamps; correctness guaranteed by the
        lex order of ISO-8601). Results are ordered by score DESC then
        ``written_at`` DESC.
        """
        if self._closed:
            raise RuntimeError("DozerDbTemporalIndex is closed")
        if not self._indexes_ready:
            await self._ensure_indexes()

        limit = max(1, min(int(limit), 1000))
        as_of_iso = as_of.isoformat() if as_of is not None else None

        if not query:
            # No text query — just return most recent events (with as_of
            # filter if provided). Uses the range index on written_at.
            cypher = (
                "MATCH (n:MemoryEvent) "
                "WHERE $as_of_iso IS NULL OR n.written_at <= $as_of_iso "
                "RETURN n AS node, 1.0 AS score "
                "ORDER BY n.written_at DESC "
                "LIMIT $limit"
            )
            params = {"as_of_iso": as_of_iso, "limit": limit}
        else:
            lucene_query = _escape_lucene(query)
            cypher = (
                "CALL db.index.fulltext.queryNodes('memory_event_text', $q) "
                "YIELD node, score "
                "WHERE $as_of_iso IS NULL OR node.written_at <= $as_of_iso "
                "RETURN node, score "
                "ORDER BY score DESC, node.written_at DESC "
                "LIMIT $limit"
            )
            params = {"q": lucene_query, "as_of_iso": as_of_iso, "limit": limit}

        rows = await self._graph.query_cypher(cypher, params)
        return [self._row_to_hit(r) for r in rows]

    async def close(self) -> None:
        """Idempotent close. Does not close the graph backend (it is owned by the adapter)."""
        self._closed = True

    # ── internals ─────────────────────────────────────────────────────

    async def _ensure_indexes(self) -> None:
        """Create the fulltext + range + uniqueness structures if absent.

        Each DDL uses ``IF NOT EXISTS`` so this is idempotent. Errors are
        logged and re-raised — a temporal index without its indexes is
        broken by construction and must fail loudly.
        """
        for name, ddl in _INDEX_DDL:
            try:
                await self._graph.query_cypher(ddl, {})
            except Exception as exc:
                log.error(
                    "DozerDbTemporalIndex._ensure_indexes failed for %s: %s",
                    name,
                    exc,
                )
                raise
        self._indexes_ready = True

    @staticmethod
    def _row_to_hit(row: dict[str, Any]) -> MemoryHit:
        """Adapt a Cypher row (``{node: <Node|dict>, score: <float>}``) to ``MemoryHit``.

        ``neo4j`` returns nodes as ``Node`` objects that behave like dicts
        under indexing but are not dicts. We dereference by known keys.
        """
        node = row["node"]
        # Both Node and dict support subscript access to props.
        payload: dict[str, Any] = {
            "subject": node.get("subject") if hasattr(node, "get") else node["subject"],
            "predicate": node.get("predicate") if hasattr(node, "get") else node["predicate"],
            "object": node.get("object") if hasattr(node, "get") else node["object"],
            "provenance": node.get("provenance") if hasattr(node, "get") else node["provenance"],
            "confidence": node.get("confidence") if hasattr(node, "get") else node["confidence"],
            "pii_tier": node.get("pii_tier") if hasattr(node, "get") else node["pii_tier"],
            "source_citation": (
                node.get("source_citation") if hasattr(node, "get") else node["source_citation"]
            ),
        }
        # Attributes are JSON-encoded by _sanitize_props before graph write.
        raw_attrs = (
            node.get("attributes") if hasattr(node, "get") else node.get("attributes")
        )
        if isinstance(raw_attrs, str):
            try:
                payload["attributes"] = json.loads(raw_attrs)
            except json.JSONDecodeError:
                payload["attributes"] = {}
        else:
            payload["attributes"] = dict(raw_attrs or {})

        # Parse written_at (ISO-8601 str) back to datetime for MemoryHit.as_of.
        written_at_raw = (
            node.get("written_at") if hasattr(node, "get") else node["written_at"]
        )
        as_of_dt = datetime.fromisoformat(written_at_raw)

        event_id = node.get("id") if hasattr(node, "get") else node["id"]
        score = float(row.get("score", 0.0) or 0.0)

        return MemoryHit(id=event_id, payload=payload, score=score, as_of=as_of_dt)

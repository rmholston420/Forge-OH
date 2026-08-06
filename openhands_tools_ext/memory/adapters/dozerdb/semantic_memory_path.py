"""adapters.memory.dozerdb.semantic_memory_path — ADR-074 D3.

Composes ``EmbeddingsPort`` + ``VectorPort`` into a semantic write/read
lane that lives *inside* the DozerDB memory adapter. Plugins never see
this class directly — they see the ``MemoryPort.search_semantic()``
surface added in ADR-074 D1.

Design invariants (per ADR-074):

1. **Zero-trust guard preserved.** Vector upserts go through
   ``VectorPort.upsert(...)`` which enforces provenance + confidence at
   its own port layer (``ports/vector.py::validate_zero_trust_payload``).
   This class NEVER attempts to bypass that guard.

2. **Graceful degradation.** If either the embeddings port or the
   vector port is ``None`` (not booted), read paths return an empty
   list and write paths log-and-return. This matches the existing
   Gnosis-route degradation pattern (see ``kernel/app.py::gnosis_graph_nodes``).

3. **Collection layout.** ``kosmos-memory-{corpus or "default"}``. One
   Qdrant collection per corpus so per-corpus retrieval doesn't have to
   post-filter.

4. **Vector id = memory event id.** The vector-store point id is the
   same UUID returned by ``MemoryPort.write_event(...)`` so the two
   stores stay linked by primary key without a join table.

5. **Payload shape mirrors the graph write.** subject / predicate /
   object / provenance / confidence / pii_tier / as_of are all
   persisted in the vector-store payload so ``search_semantic`` can
   re-hydrate a full ``MemoryHit`` without a second graph lookup.

References:
    - ADR-074 §D3 (this file's authority)
    - ADR-026 (VectorPort — downstream port)
    - ADR-073 (EmbeddingsPort — upstream port)
    - ADR-008 / ADR-027 (MemoryPort — the surface this helper serves)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from openhands_tools_ext.memory.ports.embeddings import EmbeddingsPort
from openhands_tools_ext.memory.ports.memory import MemoryHit
from openhands_tools_ext.memory.ports.vector import VectorPort

__all__ = ["SemanticMemoryPath", "memory_collection_for"]


log = logging.getLogger(__name__)


def memory_collection_for(corpus: str | None) -> str:
    """Return the Qdrant collection name for a given memory corpus.

    Pure function so callers can compute the name without a live path
    instance (e.g. from test fixtures or migration scripts).
    """
    return f"kosmos-memory-{corpus or 'default'}"


class SemanticMemoryPath:
    """Compose EmbeddingsPort + VectorPort into a semantic memory lane.

    Constructed inside the DozerDB memory adapter when both dependencies
    are wired. When either dependency is missing, the adapter simply
    doesn't attempt to construct this class and the ``search_semantic``
    surface degrades to an empty list.
    """

    def __init__(
        self,
        *,
        embeddings: EmbeddingsPort,
        vector: VectorPort,
    ) -> None:
        self._embeddings = embeddings
        self._vector = vector

    # ── write path ─────────────────────────────────────────────────────

    async def embed_and_upsert(
        self,
        event_id: str,
        payload: dict[str, Any],
        *,
        corpus: str | None,
        as_of: datetime,
    ) -> None:
        """Embed the memory-event payload and upsert it into VectorPort.

        Called from ``DozerDbMemoryAdapter.write_event`` after the graph
        + temporal writes have succeeded. ``payload`` already carries
        the zero-trust ``provenance`` + ``confidence`` fields validated
        at the MemoryPort layer, so the VectorPort guard is a
        defense-in-depth check rather than the primary enforcement.

        Failure is logged but does NOT raise: the memory event has
        already been persisted to the graph + temporal index. Callers
        will still see it via ``query_temporal``; only the semantic
        lane is affected.
        """
        text = _payload_to_embed_text(payload)
        try:
            vectors = await self._embeddings.embed(texts=[text])
        except Exception as exc:  # noqa: BLE001 — non-fatal by contract
            log.warning(
                "SemanticMemoryPath.embed_and_upsert: embed failed for "
                "event_id=%s corpus=%s: %s",
                event_id,
                corpus,
                exc,
            )
            return
        if not vectors or not vectors[0]:
            log.warning(
                "SemanticMemoryPath.embed_and_upsert: empty vector for "
                "event_id=%s corpus=%s",
                event_id,
                corpus,
            )
            return
        vector_payload = dict(payload)
        vector_payload["event_id"] = event_id
        vector_payload["corpus"] = corpus or "default"
        vector_payload["as_of"] = as_of.isoformat()
        try:
            await self._vector.upsert(
                collection=memory_collection_for(corpus),
                id=event_id,
                vector=vectors[0],
                payload=vector_payload,
            )
        except ValueError:
            # Zero-trust guard tripped in VectorPort. This is a bug in
            # the MemoryPort caller — re-raise so it surfaces loudly.
            raise
        except Exception as exc:  # noqa: BLE001 — non-fatal by contract
            log.warning(
                "SemanticMemoryPath.embed_and_upsert: vector upsert "
                "failed for event_id=%s corpus=%s: %s",
                event_id,
                corpus,
                exc,
            )

    # ── read path ──────────────────────────────────────────────────────

    async def semantic_lookup(
        self,
        query: str,
        *,
        corpus: str | None,
        limit: int,
        min_score: float,
    ) -> list[MemoryHit]:
        """Embed ``query`` and return matching memory events.

        Returns an empty list on any degradation path (embed failure,
        vector search failure, dependency unset). Never raises for
        infrastructure failures — the semantic lane is opt-in and must
        not brick the rest of the MemoryPort surface.
        """
        if not query:
            return []
        try:
            vectors = await self._embeddings.embed(texts=[query])
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "SemanticMemoryPath.semantic_lookup: embed failed: %s",
                exc,
            )
            return []
        if not vectors or not vectors[0]:
            return []
        try:
            hits = await self._vector.search(
                memory_collection_for(corpus),
                vectors[0],
                limit=limit,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "SemanticMemoryPath.semantic_lookup: vector search "
                "failed for corpus=%s: %s",
                corpus,
                exc,
            )
            return []

        out: list[MemoryHit] = []
        for h in hits:
            if h.score is not None and h.score < min_score:
                continue
            as_of = _parse_as_of(h.payload.get("as_of"))
            # Restore the original MemoryEventId string from the
            # stored payload; the raw ``h.id`` is the UUIDv5 hash the
            # Qdrant adapter uses internally (see ``_to_point_id``).
            event_id = h.payload.get("event_id") or h.id
            out.append(
                MemoryHit(
                    id=event_id,
                    payload=dict(h.payload),
                    score=h.score,
                    as_of=as_of,
                )
            )
        return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _payload_to_embed_text(payload: dict[str, Any]) -> str:
    """Flatten the memory-event payload into a single embedding string.

    The graph writer decomposes each fact into (subject, predicate,
    object). The embed text mirrors that decomposition so the
    representation stays stable across corpora and doesn't depend on
    payload-key ordering.
    """
    subject = payload.get("subject", "")
    predicate = payload.get("predicate", "")
    obj = payload.get("object", "")
    citation = payload.get("source_citation") or ""
    attrs = payload.get("attributes") or {}
    attr_str = " ".join(f"{k}={v}" for k, v in sorted(attrs.items()))
    parts = [
        f"{subject} {predicate} {obj}".strip(),
        citation,
        attr_str,
    ]
    return " | ".join(p for p in parts if p)


def _parse_as_of(raw: Any) -> datetime | None:
    """Parse an ISO-8601 as_of string back to a ``datetime``.

    Tolerates ``None`` (returns ``None``) and malformed values (returns
    ``None`` + logs). Never raises.
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        log.debug("SemanticMemoryPath: unparseable as_of=%r", raw)
        return None

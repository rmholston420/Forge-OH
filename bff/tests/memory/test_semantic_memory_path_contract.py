"""Contract tests for SemanticMemoryPath (ADR-074 D3).

Runs against in-memory fakes: no live Ollama, no live Qdrant. Verifies
the write path embeds + upserts, the read path embeds + searches, the
graceful degradation paths return empty on any failure, and the
zero-trust guard is preserved via ``VectorPort.upsert``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pytest

from openhands_tools_ext.memory.adapters.dozerdb.semantic_memory_path import (
    SemanticMemoryPath,
    memory_collection_for,
)
from openhands_tools_ext.memory.adapters.vector.qdrant.adapter import (
    InMemoryQdrantBackend,
    QdrantVectorAdapter,
)
from openhands_tools_ext.memory.ports.embeddings import EmbeddingsPort
from openhands_tools_ext.memory.ports.memory import MemoryHit


# ---------------------------------------------------------------------------
# In-memory doubles
# ---------------------------------------------------------------------------


@dataclass
class _FakeEmbeddings:
    """Deterministic 4-dim EmbeddingsPort double.

    Returns a vector whose components hash the input text so equal
    inputs get equal vectors and different inputs get different ones,
    without needing Ollama running.
    """

    calls: list[list[str]] = field(default_factory=list)
    fail: bool = False

    async def embed(self, *, texts: list[str], model: str | None = None) -> list[list[float]]:
        self.calls.append(list(texts))
        if self.fail:
            raise RuntimeError("embed backend down")
        out: list[list[float]] = []
        for t in texts:
            # 4-dim vector with a stable spread across [0, 1].
            h = abs(hash(t))
            out.append([
                ((h >> 0) & 0xFFFF) / 65535.0,
                ((h >> 16) & 0xFFFF) / 65535.0,
                ((h >> 32) & 0xFFFF) / 65535.0,
                ((h >> 48) & 0xFFFF) / 65535.0,
            ])
        return out

    def dimensions(self, model: str | None = None) -> int:
        return 4

    def is_healthy(self) -> bool:
        return not self.fail

    async def close(self) -> None:
        return None


def _payload(**extra: Any) -> dict[str, Any]:
    return {
        "subject": "Colossus",
        "predicate": "hasComponent",
        "object": "RTX 5090",
        "provenance": "kernel-test",
        "confidence": 0.9,
        "pii_tier": "Public",
        "source_citation": None,
        "attributes": {},
        **extra,
    }


def _adapter() -> QdrantVectorAdapter:
    return QdrantVectorAdapter(backend=InMemoryQdrantBackend())


# ---------------------------------------------------------------------------
# Protocol shape
# ---------------------------------------------------------------------------


def test_fake_embeddings_conforms_to_embeddings_port() -> None:
    assert isinstance(_FakeEmbeddings(), EmbeddingsPort)


def test_memory_collection_for_default_and_named() -> None:
    assert memory_collection_for(None) == "kosmos-memory-default"
    assert memory_collection_for("gnosis") == "kosmos-memory-gnosis"


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------


def test_embed_and_upsert_writes_vector_for_default_corpus() -> None:
    emb = _FakeEmbeddings()
    vec = _adapter()
    path = SemanticMemoryPath(embeddings=emb, vector=vec)
    as_of = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    asyncio.run(
        path.embed_and_upsert(
            "event-1",
            _payload(),
            corpus=None,
            as_of=as_of,
        )
    )
    # Round-trip: search with the same text should return that event.
    hits = asyncio.run(
        path.semantic_lookup(
            "Colossus hasComponent RTX 5090",
            corpus=None,
            limit=5,
            min_score=0.0,
        )
    )
    assert len(hits) == 1
    assert hits[0].id == "event-1"
    assert hits[0].payload["provenance"] == "kernel-test"
    assert hits[0].payload["corpus"] == "default"


def test_embed_and_upsert_isolates_by_corpus() -> None:
    emb = _FakeEmbeddings()
    vec = _adapter()
    path = SemanticMemoryPath(embeddings=emb, vector=vec)
    as_of = datetime.now(timezone.utc)
    asyncio.run(path.embed_and_upsert("ev-g", _payload(), corpus="gnosis", as_of=as_of))
    asyncio.run(path.embed_and_upsert("ev-k", _payload(subject="Kosmos"), corpus="kosmos", as_of=as_of))
    gnosis_hits = asyncio.run(
        path.semantic_lookup("Colossus hasComponent RTX 5090", corpus="gnosis", limit=5, min_score=0.0)
    )
    kosmos_hits = asyncio.run(
        path.semantic_lookup("Kosmos hasComponent RTX 5090", corpus="kosmos", limit=5, min_score=0.0)
    )
    assert {h.id for h in gnosis_hits} == {"ev-g"}
    assert {h.id for h in kosmos_hits} == {"ev-k"}


def test_embed_and_upsert_survives_embed_backend_failure() -> None:
    emb = _FakeEmbeddings(fail=True)
    vec = _adapter()
    path = SemanticMemoryPath(embeddings=emb, vector=vec)
    # No exception — just a silent skip + warning log.
    asyncio.run(
        path.embed_and_upsert(
            "event-x",
            _payload(),
            corpus=None,
            as_of=datetime.now(timezone.utc),
        )
    )
    hits = asyncio.run(
        path.semantic_lookup("Colossus", corpus=None, limit=5, min_score=0.0)
    )
    assert hits == []


def test_embed_and_upsert_zero_trust_violation_reraises() -> None:
    emb = _FakeEmbeddings()
    vec = _adapter()
    path = SemanticMemoryPath(embeddings=emb, vector=vec)
    bad = _payload()
    del bad["provenance"]
    with pytest.raises(ValueError):
        asyncio.run(
            path.embed_and_upsert(
                "event-bad",
                bad,
                corpus=None,
                as_of=datetime.now(timezone.utc),
            )
        )


# ---------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------


def test_semantic_lookup_empty_query_returns_empty() -> None:
    emb = _FakeEmbeddings()
    vec = _adapter()
    path = SemanticMemoryPath(embeddings=emb, vector=vec)
    hits = asyncio.run(path.semantic_lookup("", corpus=None, limit=5, min_score=0.0))
    assert hits == []


def test_semantic_lookup_min_score_filters_below_threshold() -> None:
    emb = _FakeEmbeddings()
    vec = _adapter()
    path = SemanticMemoryPath(embeddings=emb, vector=vec)
    asyncio.run(
        path.embed_and_upsert(
            "event-1",
            _payload(),
            corpus=None,
            as_of=datetime.now(timezone.utc),
        )
    )
    # A totally different query gets a lower cosine score. Force a
    # threshold above the achievable score to prove filtering works.
    hits = asyncio.run(
        path.semantic_lookup(
            "totally unrelated string that shares no hash",
            corpus=None,
            limit=5,
            min_score=0.999,
        )
    )
    # There's at most one point in the collection, so the min_score
    # either includes or excludes it deterministically.
    assert all((h.score is None) or (h.score >= 0.999) for h in hits)


def test_semantic_lookup_reconstructs_as_of_from_payload() -> None:
    emb = _FakeEmbeddings()
    vec = _adapter()
    path = SemanticMemoryPath(embeddings=emb, vector=vec)
    as_of = datetime(2026, 8, 1, 10, 30, tzinfo=timezone.utc)
    asyncio.run(
        path.embed_and_upsert("event-1", _payload(), corpus=None, as_of=as_of)
    )
    hits = asyncio.run(
        path.semantic_lookup(
            "Colossus hasComponent RTX 5090", corpus=None, limit=5, min_score=0.0
        )
    )
    assert len(hits) == 1
    assert hits[0].as_of == as_of


def test_semantic_lookup_survives_missing_collection() -> None:
    emb = _FakeEmbeddings()
    vec = _adapter()
    path = SemanticMemoryPath(embeddings=emb, vector=vec)
    # Collection never created — InMemoryQdrantBackend returns empty.
    hits = asyncio.run(
        path.semantic_lookup("anything", corpus="nonexistent", limit=5, min_score=0.0)
    )
    assert hits == []


# ---------------------------------------------------------------------------
# MemoryHit shape (D1 — score is now optional)
# ---------------------------------------------------------------------------


def test_memory_hit_score_can_be_none() -> None:
    h = MemoryHit(id="x", payload={"a": 1})
    assert h.score is None
    assert h.as_of is None

"""Live smoke helpers for the DozerDB MemoryPort adapter.

Two entry points:

- ``search_semantic(...)``: Stage 5.3a helper — composes just the semantic
  lane (Ollama + Qdrant + SemanticMemoryPath) against live infra. No graph
  writes. Kept for regression parity with the Stage 5.3a verify.
- ``roundtrip(...)``: Stage 5.3b helper — composes the full
  ``DozerDbMemoryAdapter`` via ``composition.make_memory_adapter``,
  writes one event, then reads it back via both ``search_semantic`` and
  ``query_temporal``. This is the Definition-of-Done smoke for Stage 5.3b.

Neither entry point is a plugin surface. Plugins consume ``MemoryPort``.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from openhands_tools_ext.memory.adapters.dozerdb.semantic_memory_path import (
    SemanticMemoryPath,
)
from openhands_tools_ext.memory.adapters.embeddings.ollama.adapter import (
    OllamaEmbeddingsAdapter,
)
from openhands_tools_ext.memory.adapters.vector.qdrant.adapter import (
    QdrantVectorAdapter,
)
from openhands_tools_ext.memory.ports.memory import MemoryHit


async def search_semantic(
    query: str,
    *,
    corpus: str | None = None,
    limit: int = 10,
    min_score: float = 0.0,
) -> list[MemoryHit]:
    """Semantic-only smoke (Stage 5.3a parity)."""
    from openhands_tools_ext.memory.adapters.vector.qdrant.real_backend import (
        RealQdrantBackend,
    )

    embeddings = OllamaEmbeddingsAdapter()
    backend = RealQdrantBackend(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
    vectors = QdrantVectorAdapter(backend=backend)
    path = SemanticMemoryPath(embeddings=embeddings, vector=vectors)
    try:
        return await path.semantic_lookup(
            query, corpus=corpus, limit=limit, min_score=min_score
        )
    finally:
        await embeddings.close()
        await backend.close()


async def roundtrip(
    subject: str = "Colossus",
    predicate: str = "hasComponent",
    object_: str = "RTX 5090",
    *,
    provenance: str = "stage-5.3b-smoke",
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Stage 5.3b round-trip smoke: write → read semantic + temporal.

    Composes the full adapter via ``composition.make_memory_adapter`` and
    runs a single write followed by both retrieval paths. Returns a
    structured dict for programmatic inspection.

    Prerequisites (Colossus):
        - DozerDB on ``NEO4J_BOLT_URI`` (default ``bolt://localhost:7687``)
        - ``NEO4J_PASSWORD`` in env
        - Ollama on ``OLLAMA_URL`` (default ``http://localhost:11434``)
        - Qdrant on ``QDRANT_URL`` (default ``http://localhost:6333``)
    """
    from openhands_tools_ext.memory.composition import make_memory_adapter

    adapter = make_memory_adapter()
    try:
        event = await adapter.write_event(
            subject,
            predicate,
            object_,
            provenance=provenance,
            confidence=confidence,
        )
        semantic_hits = await adapter.search_semantic(subject, limit=5)
        temporal_hits = await adapter.query_temporal(subject, limit=5)
        return {
            "event_id": event.id,
            "written_at": event.written_at.isoformat(),
            "semantic_hits": [
                {"id": h.id, "score": h.score} for h in semantic_hits
            ],
            "temporal_hits": [
                {"id": h.id, "score": h.score} for h in temporal_hits
            ],
        }
    finally:
        await adapter.close()


if __name__ == "__main__":
    import json
    result = asyncio.run(roundtrip())
    print(json.dumps(result, indent=2))

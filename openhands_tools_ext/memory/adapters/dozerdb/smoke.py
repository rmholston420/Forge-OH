"""Stage 5.3a live smoke helper for SemanticMemoryPath.

Convenience entry point for the plan's §5.3.4 verification step. Composes
Stage 5.2's ``OllamaEmbeddingsAdapter`` + ``QdrantVectorAdapter`` (backed by
``RealQdrantBackend``) with the just-vendored ``SemanticMemoryPath`` and
runs a read-only ``semantic_lookup`` against live infrastructure.

This is NOT a plugin surface. Plugins consume ``MemoryPort.search_semantic``,
which lands with ``DozerDbMemoryAdapter`` in Stage 5.3b. Kept scoped to
``openhands_tools_ext.memory.adapters.dozerdb`` so it can be removed cleanly
when 5.3b provides the real adapter path.
"""

from __future__ import annotations

import os

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
    """Live semantic lookup against local Ollama + Qdrant.

    Env vars (matching Stage 5.2 conventions):
        OLLAMA_URL          — Ollama native root, default ``http://localhost:11434``
        OLLAMA_EMBED_MODEL  — embedder model, default per ADR-020 (0.6b)
        QDRANT_URL          — Qdrant HTTP endpoint, default ``http://localhost:6333``
    """
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

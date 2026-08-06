"""openhands_tools_ext.memory.composition — Forge-OH memory composition root (Stage 5.3b).

Wires the ``DozerDbMemoryAdapter`` from injected env vars into a fully-live
``MemoryPort`` implementation. ADR-007 dictates plugins depend ONLY on
``MemoryPort`` — never on this module, ``DozerDbMemoryAdapter``, ``neo4j``,
or the Qdrant client. This module is the single point where env → concrete
class translation happens.

Env vars (Forge-OH naming, differs from Kosmos):
    NEO4J_BOLT_URI      Bolt URL to the shared Colossus DozerDB instance.
                        Default: ``bolt://localhost:7687``
    NEO4J_USER          Bolt auth user. Default: ``neo4j``
    NEO4J_PASSWORD      Bolt auth password. Required — no default; missing
                        raises RuntimeError at composition time.
    NEO4J_DATABASE      Target database. Default: ``forgeoh``
    OLLAMA_URL          Ollama native root for embeddings (default
                        ``http://localhost:11434``). Distinct from
                        ``OLLAMA_BASE_URL`` (which is the OpenAI-compat
                        ``/v1`` prefix used by the BFF model router).
    OLLAMA_EMBED_MODEL  Embedder model tag (default per ADR-020).
    QDRANT_URL          Qdrant HTTP endpoint. Default:
                        ``http://localhost:6333``
    FORGEOH_MEMORY_CORPUS
                        Default corpus for semantic writes/reads.
                        Default: ``default``

Design choices (ADR-021):
    - AmgPolicy = ``NoOpAmgPolicy`` (D5). No ``agent-memory-guard`` PyPI
      dep is pulled.
    - TemporalIndex = ``DozerDbTemporalIndex`` over the same shared
      DozerDB session graph writes use (D1-D3).
    - Semantic lane = optional; disabled when either Ollama or Qdrant is
      unreachable at compose time. The core write/read path still works.
"""

from __future__ import annotations

import os
from typing import Any

from openhands_tools_ext.memory.adapters.dozerdb.adapter import DozerDbMemoryAdapter
from openhands_tools_ext.memory.adapters.dozerdb.dozerdb_graph_backend import (
    DozerDbGraphBackend,
)
from openhands_tools_ext.memory.adapters.dozerdb.dozerdb_temporal_index import (
    DozerDbTemporalIndex,
)
from openhands_tools_ext.memory.adapters.dozerdb.adapter import NoOpAmgPolicy


__all__ = ["make_memory_adapter"]


def _require_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(
            f"composition.make_memory_adapter: env var {key} is unset. "
            "See openhands_tools_ext.memory.composition module docstring."
        )
    return value


def _optional_semantic_pair() -> tuple[Any, Any] | None:
    """Build (embeddings, vector) if both dependencies are importable.

    Failures here are non-fatal: the adapter degrades to graph-only write
    and empty ``search_semantic`` responses (Kosmos ADR-074 D3 invariant).
    """
    try:
        from openhands_tools_ext.memory.adapters.embeddings.ollama.adapter import (
            OllamaEmbeddingsAdapter,
        )
        from openhands_tools_ext.memory.adapters.vector.qdrant.adapter import (
            QdrantVectorAdapter,
        )
        from openhands_tools_ext.memory.adapters.vector.qdrant.real_backend import (
            RealQdrantBackend,
        )
    except ImportError:
        return None

    embeddings = OllamaEmbeddingsAdapter()
    backend = RealQdrantBackend(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
    )
    vectors = QdrantVectorAdapter(backend=backend)
    return embeddings, vectors


def make_memory_adapter() -> DozerDbMemoryAdapter:
    """Compose a ``DozerDbMemoryAdapter`` wired to Colossus infra.

    Returns a live adapter with:
        - ``DozerDbGraphBackend`` pointing at ``NEO4J_BOLT_URI`` /
          ``NEO4J_DATABASE`` (default ``forgeoh``)
        - ``NoOpAmgPolicy`` (ADR-021 D5)
        - ``DozerDbTemporalIndex`` sharing the same graph backend
        - Optional semantic lane (OllamaEmbeddings + QdrantVector) if
          both are importable

    Caller owns lifecycle: ``await adapter.close()`` when done.
    """
    graph = DozerDbGraphBackend(
        uri=os.getenv("NEO4J_BOLT_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=_require_env("NEO4J_PASSWORD"),
        database=os.getenv("NEO4J_DATABASE", "forgeoh"),
    )
    temporal = DozerDbTemporalIndex(graph=graph)

    semantic = _optional_semantic_pair()
    if semantic is None:
        return DozerDbMemoryAdapter(
            graph=graph,
            amg=NoOpAmgPolicy(),
            temporal=temporal,
            default_corpus=os.getenv("FORGEOH_MEMORY_CORPUS", "default"),
        )
    embeddings, vectors = semantic
    return DozerDbMemoryAdapter(
        graph=graph,
        amg=NoOpAmgPolicy(),
        temporal=temporal,
        embeddings=embeddings,
        vector=vectors,
        default_corpus=os.getenv("FORGEOH_MEMORY_CORPUS", "default"),
    )

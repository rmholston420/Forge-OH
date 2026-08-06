"""DozerDB memory adapters (ADR-074).

Stage 5.3a: only ``SemanticMemoryPath`` is vendored — the composition helper
that wires ``EmbeddingsPort`` + ``VectorPort`` into a semantic write/read
lane. The full ``DozerDbMemoryAdapter`` (with the Bolt driver, Graphiti
temporal index, and Agent Memory Guard policy) lands in Stage 5.3b.
"""

from openhands_tools_ext.memory.adapters.dozerdb.semantic_memory_path import (
    SemanticMemoryPath,
    memory_collection_for,
)

__all__ = [
    "SemanticMemoryPath",
    "memory_collection_for",
]

"""DozerDB memory adapters (ADR-021).

Stage 5.3b: full ``DozerDbMemoryAdapter`` + ``DozerDbGraphBackend`` +
``DozerDbTemporalIndex`` ported from Kosmos @ SHA c455165 with the graph
shape decisions locked in Forge-OH ADR-021 (A2 + B2 + C1 + α + δ).

The Kosmos ``AmgGuardPolicy`` / ``AmgV02Policy`` symbols are intentionally
not re-exported — Forge-OH wires ``NoOpAmgPolicy`` at the composition root
(ADR-021 D5) and does not pull the ``agent-memory-guard`` PyPI dep.
"""

from openhands_tools_ext.memory.adapters.dozerdb.adapter import (
    AlwaysBlockAmgPolicy,
    AlwaysQuarantineAmgPolicy,
    AmgPolicy,
    AmgVerdict,
    DozerDbMemoryAdapter,
    GraphBackend,
    InMemoryGraphBackend,
    InMemoryTemporalIndex,
    NoOpAmgPolicy,
    TemporalIndex,
)
from openhands_tools_ext.memory.adapters.dozerdb.dozerdb_graph_backend import (
    DozerDbGraphBackend,
)
from openhands_tools_ext.memory.adapters.dozerdb.semantic_memory_path import (
    SemanticMemoryPath,
    memory_collection_for,
)

__all__ = [
    "AlwaysBlockAmgPolicy",
    "AlwaysQuarantineAmgPolicy",
    "AmgPolicy",
    "AmgVerdict",
    "DozerDbGraphBackend",
    "DozerDbMemoryAdapter",
    "GraphBackend",
    "InMemoryGraphBackend",
    "InMemoryTemporalIndex",
    "NoOpAmgPolicy",
    "SemanticMemoryPath",
    "TemporalIndex",
    "memory_collection_for",
]

"""Memory router — read-only inspector surface (Stage 5.6a / ADR-024).

BFF surface (frontend contract — src/features/memory-inspector/api.ts):
  GET /api/memory/recent-writes?limit=50 -> {data: MemoryWriteRecord[]}

The MemoryWriteRecord shape mirrors ``openhands_tools_ext.memory.ports.memory
.MemoryEventRecord``, projected to JSON (dataclass -> dict via a small
serializer here so we don't leak the dataclass shape into the wire type).

No write endpoints. Zero-trust writes never flow through the BFF surface;
callers of ``MemoryPort.write_event`` are agent-server-side tools.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from bff.deps.memory_port import get_memory_port

router = APIRouter(prefix="/memory", tags=["memory"])


def _record_to_wire(r) -> dict:  # MemoryEventRecord -> JSON-safe dict
    """Project a MemoryEventRecord dataclass into the wire shape.

    Field names follow the frontend contract in
    ``src/features/memory-inspector/api.ts``: triple + provenance +
    confidence + pii_tier + source_citation + writtenAt (ISO-8601 UTC).
    """
    return {
        "id": r.id,
        "subject": r.subject,
        "predicate": r.predicate,
        "object": r.object,
        "provenance": r.provenance,
        "confidence": r.confidence,
        "piiTier": r.pii_tier,
        "sourceCitation": r.source_citation,
        "writtenAt": r.written_at.isoformat(),
    }


@router.get("/recent-writes")
async def get_recent_writes(
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Return the most-recent MemoryEvent writes, newest first.

    503 when the MemoryPort is not composed (NEO4J_PASSWORD unset or
    composition failed); the frontend renders an empty-state banner.
    """
    port = get_memory_port()
    if port is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Memory service unavailable: MemoryPort not initialised "
                "(check NEO4J_PASSWORD and DozerDB connectivity)."
            ),
        )
    records = await port.list_recent_writes(limit=limit)
    return {"data": [_record_to_wire(r) for r in records]}

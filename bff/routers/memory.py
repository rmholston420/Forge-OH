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

import os

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from bff.deps.memory_port import get_memory_port
from bff.services.memory_events import emit_memory_consultation

router = APIRouter(prefix="/memory", tags=["memory"])

_EMIT_ENABLED_ENV = "FORGE_MEMORY_EMIT_ENABLED"


def _emit_enabled() -> bool:
    """Feature gate for the emit endpoint (Stage 5.6b).

    Enabled when ``FORGE_MEMORY_EMIT_ENABLED=1`` OR when a MemoryPort is
    composed (i.e. the deployment has NEO4J_PASSWORD configured, which
    implies the operator wants the memory surface active). The env-var
    override lets tests and local dev turn the endpoint on without
    booting DozerDB.
    """
    if os.environ.get(_EMIT_ENABLED_ENV, "").strip() in {"1", "true", "True"}:
        return True
    return get_memory_port() is not None


class EmitConsultationRequest(BaseModel):
    """Wire body for ``POST /api/memory/emit-consultation`` (Stage 5.6b).

    Kept intentionally small; the projector fills in ``id``, ``timestamp``,
    and ``source`` on the raw event.
    """

    runId: str = Field(..., min_length=1, description="Conversation / run id.")
    tier: str = Field(
        ...,
        min_length=1,
        description="Memory tier label (semantic|temporal|episodic).",
    )
    query: str = Field(..., description="Verbatim query string.")
    resultCount: int = Field(..., ge=0, description="Non-negative hit count.")


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


@router.post("/emit-consultation")
async def emit_consultation(body: EmitConsultationRequest) -> dict:
    """Bridge endpoint: agent-server tool -> BFF Socket.IO -> frontend.

    Stage 5.6b (ADR-024 D6). The agent-server (:8090) cannot call
    :func:`bff.services.event_relay._emit` in-process; this endpoint is
    the HTTP hop that lets ``consult_memory`` surface a
    ``MemoryConsultationEvent`` on the run-detail timeline. Best-effort:
    normalization always succeeds, Socket.IO emission is fire-and-forget.

    Gated by :func:`_emit_enabled` — 503s when neither the env override
    nor a composed MemoryPort indicates the memory surface is active.
    """
    if not _emit_enabled():
        raise HTTPException(
            status_code=503,
            detail=(
                "Memory emit disabled: set FORGE_MEMORY_EMIT_ENABLED=1 or "
                "configure NEO4J_PASSWORD so the MemoryPort composes."
            ),
        )
    wire = await emit_memory_consultation(
        conversation_id=body.runId,
        tier=body.tier,
        query=body.query,
        result_count=body.resultCount,
    )
    return {"data": wire}


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

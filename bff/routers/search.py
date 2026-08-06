"""Search router — web-search timeline bridge (Stage 6.1).

BFF surface:
  POST /api/search/emit -> {data: normalized WebSearchEvent wire}

The agent-server (:8090) cannot call ``bff.services.event_relay._emit``
in-process; this endpoint is the HTTP hop that lets ``search_web`` surface
a ``WebSearchEvent`` on the run-detail timeline (mirrors ADR-024 D6 pattern
used by ``consult_memory``).

Gated by :func:`_emit_enabled` — 503s when neither the env override nor a
detectable SearXNG base URL indicates the search surface is active. The
gate is intentionally cheap: no network I/O in the hot path (Stage 5.6b's
discipline).
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from bff.services.search_events import emit_web_search

router = APIRouter(prefix="/search", tags=["search"])

_EMIT_ENABLED_ENV = "FORGE_SEARCH_EMIT_ENABLED"
_SEARXNG_BASE_URL_ENV = "FORGE_SEARXNG_BASE_URL"


def _emit_enabled() -> bool:
    """Feature gate for the emit endpoint (Stage 6.1).

    Enabled when ``FORGE_SEARCH_EMIT_ENABLED=1`` OR when
    ``FORGE_SEARXNG_BASE_URL`` is set (implies the operator has stood up
    the local SearXNG). Env-var override lets tests turn the endpoint on
    without booting the container. Cheap sync check — no network I/O.
    """
    if os.environ.get(_EMIT_ENABLED_ENV, "").strip() in {"1", "true", "True"}:
        return True
    base = os.environ.get(_SEARXNG_BASE_URL_ENV, "").strip()
    return bool(base)


class EmitSearchRequest(BaseModel):
    """Wire body for ``POST /api/search/emit`` (Stage 6.1).

    Kept intentionally small; the projector fills in ``id``, ``timestamp``,
    and ``source`` on the raw event.
    """

    runId: str = Field(..., min_length=1, description="Conversation / run id.")
    query: str = Field(..., description="Verbatim query string.")
    resultCount: int = Field(..., ge=0, description="Non-negative hit count.")
    provenance: str = Field(
        ...,
        min_length=1,
        description="Adapter provenance string (e.g. searxng:http://127.0.0.1:18888).",
    )
    latencyMs: int = Field(..., ge=0, description="Non-negative latency in ms.")


@router.post("/emit")
async def emit_search(body: EmitSearchRequest) -> dict:
    """Bridge endpoint: search_web tool -> BFF Socket.IO -> frontend."""
    if not _emit_enabled():
        raise HTTPException(
            status_code=503,
            detail=(
                "Search emit disabled: set FORGE_SEARCH_EMIT_ENABLED=1 or "
                "FORGE_SEARXNG_BASE_URL so the search surface is active."
            ),
        )
    wire = await emit_web_search(
        conversation_id=body.runId,
        query=body.query,
        result_count=body.resultCount,
        provenance=body.provenance,
        latency_ms=body.latencyMs,
    )
    return {"data": wire}

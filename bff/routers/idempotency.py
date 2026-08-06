"""Idempotency router — Stage 6.3 exactly-once ledger HTTP surface.

BFF surface:
  POST /api/idempotency/check -> {data: {completed: bool, key: str,
                                         cached: {...} | null}}
  POST /api/idempotency/mark  -> {data: {key: str, recorded: bool}}

Tools run inside agent-server (:8090); the ledger DB lives in BFF
(:8081) alongside the other SQLite stores (episodic_memory,
run_metadata_store).  A ``ToolExecutor`` that opts into idempotency
calls these two endpoints on either side of its real side effect,
mirroring the ADR-024 D6 process-boundary bridge already used by
``search_web`` and ``consult_memory``.

Not gated by any env flag — this is a production surface (unlike
``_debug/inject-event``).  A tool that wants to bypass the ledger simply
doesn't call these endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from bff.services import idempotency_ledger

router = APIRouter(prefix="/idempotency", tags=["idempotency"])


class CheckRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1)
    leaf_event_id: str | None = Field(
        default=None,
        description=(
            "SDK ConversationState.leaf_event_id at the moment the tool "
            "call was decided.  None is allowed and coerces to the "
            "'root' sentinel inside the ledger."
        ),
    )
    tool_name: str = Field(..., min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class MarkRequest(CheckRequest):
    result_summary: str = ""
    result_json: Any | None = None


@router.post("/check")
async def check(payload: CheckRequest, request: Request) -> dict:
    """Return whether a side effect keyed by these inputs has completed."""
    key = idempotency_ledger.compute_idempotency_key(
        conversation_id=payload.conversation_id,
        leaf_event_id=payload.leaf_event_id,
        tool_name=payload.tool_name,
        arguments=payload.arguments,
    )
    cached = await idempotency_ledger.get_cached_result(request.app, key)
    return {
        "data": {
            "completed": cached is not None,
            "key": key,
            "cached": cached,
        }
    }


@router.post("/mark")
async def mark(payload: MarkRequest, request: Request) -> dict:
    """Record that a side effect keyed by these inputs has completed."""
    key = idempotency_ledger.compute_idempotency_key(
        conversation_id=payload.conversation_id,
        leaf_event_id=payload.leaf_event_id,
        tool_name=payload.tool_name,
        arguments=payload.arguments,
    )
    already = await idempotency_ledger.has_completed(request.app, key)
    await idempotency_ledger.mark_completed(
        request.app,
        key=key,
        conversation_id=payload.conversation_id,
        leaf_event_id=payload.leaf_event_id,
        tool_name=payload.tool_name,
        arguments=payload.arguments,
        result_summary=payload.result_summary,
        result_json=payload.result_json,
    )
    return {
        "data": {
            "key": key,
            "recorded": not already,
        }
    }

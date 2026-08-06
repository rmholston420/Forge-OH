"""Debug router — dev-only event injection (Stage 6.2).

BFF surface:
  POST /api/_debug/inject-event -> {data: normalized wire event}

Gated behind ``FORGE_TIMELINE_DEBUG_INJECT=1``. When the flag is
unset the endpoint returns 404 (not 503) so its very existence is
non-observable in production deployments.

Why this exists (versus per-event emit endpoints):
The BFF already ships two production emit endpoints for surfaces we
actually own — ``/api/memory/emit-consultation`` (Stage 5.6b) and
``/api/search/emit`` (Stage 6.1). Adding a third for each future
E2E-only surface (condensation in 6.2, idempotency ledger in 6.3,
skills-fired in 6.6, etc.) inflates the API for no production
purpose. This generic injector accepts a ``kind`` + arbitrary
extra fields, passes them through the same
``event_normalize.normalize_event`` -> ``event_relay._emit`` pipeline
as any real event, and returns the normalized wire event.

Consumers: ONLY the Playwright E2E specs under ``src/tests/e2e/``.
Never called by production tools.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from bff.services.event_normalize import normalize_event

router = APIRouter(prefix="/_debug", tags=["debug"])

_ENABLED_ENV = "FORGE_TIMELINE_DEBUG_INJECT"


def _enabled() -> bool:
    """Feature gate. Off by default; existence hidden as 404 when off."""
    return os.environ.get(_ENABLED_ENV, "").strip() in {"1", "true", "True"}


class InjectEventRequest(BaseModel):
    """Wire body for ``POST /api/_debug/inject-event`` (Stage 6.2).

    The projector stamps ``id`` / ``timestamp`` / ``source`` when absent
    so callers only need to supply ``runId`` + ``kind`` (+ any extra
    fields the target normalizer expects).
    """

    runId: str = Field(..., min_length=1, description="Conversation / run id.")
    kind: str = Field(
        ...,
        min_length=1,
        description="Raw event ``kind`` (matches _KIND_TO_TYPE key).",
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra fields passed through untouched onto the raw event.",
    )


@router.post("/inject-event")
async def inject_event(body: InjectEventRequest) -> dict:
    """Inject a synthetic event and push it through the normalize pipeline.

    Returns the normalized wire event under ``data`` so callers can
    assert its shape from the client side. Never raises on the
    Socket.IO emit; failures there are swallowed by design (mirrors
    ``emit_web_search`` / ``emit_memory_consultation`` behavior).
    """
    if not _enabled():
        # 404 (not 503) so the endpoint is indistinguishable from a
        # non-existent route in production. This is intentional.
        raise HTTPException(status_code=404, detail="Not Found")

    now = datetime.now(timezone.utc).isoformat()
    raw: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "kind": body.kind,
        "timestamp": now,
        "source": "environment",
        "runId": body.runId,
    }
    # extra overrides / augments any of the defaults above
    raw.update(body.extra or {})

    wire = normalize_event(raw)

    # Best-effort Socket.IO emit into the run's room. Lazy import to
    # avoid boot-cycle: event_relay imports settings which imports
    # routers.
    try:
        from bff.services import event_relay

        room = f"conversationId={body.runId}"
        await event_relay._emit(room, "event", wire)
    except Exception:  # pragma: no cover - best-effort
        pass

    return {"data": wire}

"""GET /api/inference-backends — live inventory of configured backends.

Read-only endpoint that returns the canonical registry defined in
``bff/services/inference_backends/registry.py`` with a fresh health
probe per entry. Never raises: even a fully unreachable set of
backends returns 200 with per-entry ``unhealthy`` states.
"""

from __future__ import annotations

from fastapi import APIRouter

from bff.services.inference_backends import list_backends

router = APIRouter(prefix="/inference-backends", tags=["inference-backends"])


@router.get("")
async def list_inference_backends() -> dict:
    """Return every configured backend + its current health.

    Response shape::

        {"data": [
            {
                "id": "ollama",
                "displayName": "Ollama",
                "baseUrl": "http://localhost:11434",
                "supportsStreaming": true,
                "roleHint": "any",
                "health": {
                    "state": "healthy",
                    "latencyMs": 12,
                    "modelCount": 3,
                    "error": null
                }
            },
            ...
        ]}
    """

    metas = await list_backends()
    return {"data": [m.as_dict() for m in metas]}

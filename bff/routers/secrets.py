"""Secrets router — passthrough to agent-server settings-backed secret store.

Upstream (agent-server):
  GET    /api/settings/secrets                 → {secrets: [{name, description}]}
  PUT    /api/settings/secrets                 → create (SecretCreateRequest: name, value, description)
  GET    /api/settings/secrets/{name}          → fetch value (not exposed by BFF)
  DELETE /api/settings/secrets/{name}          → delete
  POST   /api/conversations/{id}/secrets       → per-conversation secret update

BFF surface (frontend contract — src/features/secrets/api.ts):
  GET    /api/secrets                          → SecretRef[]
  POST   /api/secrets                          → SecretRef
  PUT    /api/secrets/{id}/rotate              → SecretRef      (id == secret name)
  DELETE /api/secrets/{id}                     → 204
  POST   /api/runs/{run_id}/secrets            → {ok: true}     (per-conversation)

Design notes:
- Local-first single-user: no Authorization header enforcement (dropped from
  the interim stub). Access control lives at the agent-server layer if enabled.
- Secret values NEVER leave the agent-server. The BFF only ever exposes
  metadata: {id, name, description, valueStatus}. `valueStatus='masked'`
  whenever the upstream list contains the name (upstream only lists set
  secrets); no 'unset' path today.
- Rotate is implemented as delete-then-recreate because upstream lacks a
  dedicated rotate endpoint and PUT semantics for existing names are unclear
  from the openapi (a PUT with a colliding name may 409).
"""
from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from bff.openhands_client import get_client


router = APIRouter(prefix="/secrets", tags=["secrets"])


# ---------------------------------------------------------------------------
# Reshape upstream {name, description} → frontend SecretRef
# ---------------------------------------------------------------------------

def _to_ref(item: dict[str, Any]) -> dict[str, Any]:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    name = item.get("name") or ""
    return {
        "id": name,
        "name": name,
        "description": item.get("description"),
        "createdAt": now,
        "updatedAt": now,
        "valueStatus": "masked",
    }


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class CreateSecretBody(BaseModel):
    # Frontend contract sends {name, value, description?}. Legacy stub accepted
    # {key, rawValue, scope} — support that too for backward compatibility.
    name: Optional[str] = None
    value: Optional[str] = None
    description: Optional[str] = None
    # Legacy shape
    key: Optional[str] = None
    rawValue: Optional[str] = None


class RotateSecretBody(BaseModel):
    newValue: str


class ConversationSecretsBody(BaseModel):
    # Upstream POST /api/conversations/{id}/secrets accepts an UpdateSecretsRequest.
    # We pass through 'secrets' verbatim.
    secrets: dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _upstream_list() -> list[dict[str, Any]]:
    client = get_client()
    resp = await client.get("/api/settings/secrets")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
    payload = resp.json() or {}
    return payload.get("secrets") or []


async def _upstream_create(name: str, value: str, description: Optional[str]) -> None:
    client = get_client()
    resp = await client.put(
        "/api/settings/secrets",
        json={"name": name, "value": value, "description": description},
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:400])


async def _upstream_delete(name: str) -> None:
    client = get_client()
    resp = await client.delete(f"/api/settings/secrets/{name}")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"secret not found: {name}")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_secrets(scope: Optional[str] = None) -> list[dict[str, Any]]:
    """List secrets (metadata only).

    The 'scope' query param is accepted for frontend compatibility but has no
    effect: agent-server stores a single global secrets namespace. The
    per-conversation POST is a separate write-only merge, not a listable scope.
    """
    items = await _upstream_list()
    return [_to_ref(i) for i in items]


@router.post("")
async def create_secret(body: CreateSecretBody) -> dict[str, Any]:
    name = body.name or body.key
    value = body.value if body.value is not None else body.rawValue
    if not name or value is None:
        raise HTTPException(status_code=422, detail="Missing required fields: name, value")

    await _upstream_create(name, value, body.description)

    # Refetch to return canonical metadata
    items = await _upstream_list()
    match = next((i for i in items if i.get("name") == name), {"name": name, "description": body.description})
    return _to_ref(match)


@router.put("/{secret_id}/rotate")
async def rotate_secret(secret_id: str, body: RotateSecretBody) -> dict[str, Any]:
    # Preserve description across rotate
    items = await _upstream_list()
    existing = next((i for i in items if i.get("name") == secret_id), None)
    if not existing:
        raise HTTPException(status_code=404, detail=f"secret not found: {secret_id}")
    description = existing.get("description")

    await _upstream_delete(secret_id)
    await _upstream_create(secret_id, body.newValue, description)

    items = await _upstream_list()
    match = next((i for i in items if i.get("name") == secret_id), {"name": secret_id, "description": description})
    return _to_ref(match)


@router.delete("/{secret_id}", status_code=204)
async def delete_secret(secret_id: str) -> Response:
    await _upstream_delete(secret_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Per-conversation secrets (POST /api/runs/{run_id}/secrets)
#
# Registered here (rather than in runs router) to keep secret handling
# centralized. Mounted under /runs prefix externally via a dedicated route.
# ---------------------------------------------------------------------------

conv_secrets_router = APIRouter(tags=["secrets"])


@conv_secrets_router.post("/runs/{run_id}/secrets")
async def update_conversation_secrets(run_id: str, body: ConversationSecretsBody) -> dict[str, Any]:
    client = get_client()
    resp = await client.post(
        f"/api/conversations/{run_id}/secrets",
        json={"secrets": body.secrets},
    )
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="run not found")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
    return {"ok": True, "run_id": run_id}

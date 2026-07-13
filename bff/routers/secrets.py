"""Secrets vault router — Phase 3 stub.
Values are never returned. The BFF will delegate to the system keychain
or a Vault instance in production.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class UpsertSecretRequest(BaseModel):
    name: str
    value: str
    scope: str = 'global'
    scopeId: Optional[str] = None
    description: Optional[str] = None


class RotateSecretRequest(BaseModel):
    value: str


def _stub_secret(id_: str, name: str, scope: str, description: Optional[str] = None) -> dict:
    return {
        "id": id_, "name": name, "scope": scope, "scopeId": None,
        "description": description,
        "masked": True,  # value is NEVER in the response
        "lastRotatedAt": None,
        "createdAt": "2026-07-12T00:00:00Z",
        "updatedAt": "2026-07-12T00:00:00Z",
    }


@router.get("/secrets")
async def list_secrets() -> dict:
    return {"data": [], "stub": True}


@router.post("/secrets")
async def upsert_secret(body: UpsertSecretRequest) -> dict:
    # Never echo back the value
    secret = _stub_secret("secret-new-001", body.name, body.scope, body.description)
    return {"data": secret}


@router.delete("/secrets/{secret_id}")
async def delete_secret(secret_id: str) -> dict:
    return {"ok": True, "secret_id": secret_id}


@router.post("/secrets/{secret_id}/rotate")
async def rotate_secret(secret_id: str, body: RotateSecretRequest) -> dict:
    from datetime import datetime, timezone
    secret = _stub_secret(secret_id, "stub", "global")
    secret["lastRotatedAt"] = datetime.now(timezone.utc).isoformat()
    return {"data": secret}

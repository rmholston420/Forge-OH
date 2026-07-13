from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/secrets", tags=["secrets"])


class SecretRefModel(BaseModel):
    """Returned to client — never includes raw value."""
    id: str
    name: str
    scope: Literal["global", "workspace", "run"]
    provider: Literal["env", "vault", "k8s-secret", "plaintext"]
    masked_preview: str  # Always '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022'
    created_at: str
    updated_at: str
    rotated_at: str | None = None
    used_in: list[str] = []


class CreateSecretRequest(BaseModel):
    name: str
    scope: Literal["global", "workspace", "run"]
    provider: Literal["env", "vault", "k8s-secret", "plaintext"]
    value: str  # write-only — never returned after this point


class RotateSecretRequest(BaseModel):
    value: str  # write-only


class RotateSecretResponse(BaseModel):
    secret_id: str
    status: Literal["rotated"]
    rotated_at: str


def _mask(value: str) -> str:
    return "•" * min(len(value), 8)


# In-memory store: stores hashed value, never plaintext after write
_SECRETS: dict[str, SecretRefModel] = {}
_SECRET_HASHES: dict[str, str] = {}  # id -> sha256 of value


@router.get("/", response_model=list[SecretRefModel])
async def list_secrets() -> list[SecretRefModel]:
    return list(_SECRETS.values())


@router.post("/", response_model=SecretRefModel, status_code=status.HTTP_201_CREATED)
async def create_secret(payload: CreateSecretRequest) -> SecretRefModel:
    import uuid
    new_id = f"secret-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    # Store SHA-256 hash only — never the plaintext value
    _SECRET_HASHES[new_id] = hashlib.sha256(payload.value.encode()).hexdigest()
    ref = SecretRefModel(
        id=new_id,
        name=payload.name,
        scope=payload.scope,
        provider=payload.provider,
        masked_preview=_mask(payload.value),
        created_at=now,
        updated_at=now,
    )
    _SECRETS[new_id] = ref
    return ref  # value field never included in response


@router.post("/{secret_id}/rotate", response_model=RotateSecretResponse)
async def rotate_secret(secret_id: str, payload: RotateSecretRequest) -> RotateSecretResponse:
    ref = _SECRETS.get(secret_id)
    if not ref:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found")
    now = datetime.now(timezone.utc).isoformat()
    # Re-hash new value — old value is discarded
    _SECRET_HASHES[secret_id] = hashlib.sha256(payload.value.encode()).hexdigest()
    _SECRETS[secret_id] = ref.model_copy(
        update={"masked_preview": _mask(payload.value), "rotated_at": now, "updated_at": now}
    )
    return RotateSecretResponse(secret_id=secret_id, status="rotated", rotated_at=now)


@router.delete("/{secret_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(secret_id: str) -> None:
    if secret_id not in _SECRETS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found")
    del _SECRETS[secret_id]
    _SECRET_HASHES.pop(secret_id, None)

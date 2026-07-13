"""
bff/routers/secrets.py

Secrets router — interim contract for Forge-OH vertical slice.

TODO(foh-phase2):
- Design a clean, consistent secrets API for Forge-OH
- Replace in-memory _STORE with a real secrets backend (Vault, AWS Secrets Manager, etc.)
- Decide on workspace scoping and persistence beyond in-memory
- All mutating endpoints already require auth; verify JWT strategy here.
"""
from typing import Dict, Literal, Optional, List, Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from bff.auth_state import _TOKENS

router = APIRouter(prefix="/secrets", tags=["secrets"])

Scope = Literal["global", "workspace", "run"]


class SecretRecord(BaseModel):
    id: str
    key: str
    rawValue: str
    scope: Scope
    tags: List[str] = Field(default_factory=list)


# TODO(foh-phase2): replace with non-sensitive placeholder constants once a
# real secrets backend is in place. Do NOT substitute real credentials here.
_STORE: Dict[str, SecretRecord] = {
    "sec-1": SecretRecord(id="sec-1", key="OPENAI_API_KEY", rawValue="REPLACE_ME_OPENAI", scope="global", tags=[]),
    "sec-2": SecretRecord(id="sec-2", key="GITHUB_TOKEN", rawValue="REPLACE_ME_GITHUB", scope="global", tags=[]),
    "sec-3": SecretRecord(id="sec-3", key="WORKSPACE_SECRET", rawValue="REPLACE_ME_WORKSPACE", scope="workspace", tags=[]),
}


def _mask(value: str) -> str:
    return "****" if len(value) < 4 else "****" + value[-4:]


def _parse_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid auth header")
    return parts[1]


def _require_auth(authorization: Optional[str]) -> str:
    token = _parse_token(authorization)
    if token not in _TOKENS:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


def _to_public(record: SecretRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "key": record.key,
        "scope": record.scope,
        "tags": list(record.tags),
        "maskedValue": _mask(record.rawValue),
    }


def _find_store_id_by_key(key: str) -> Optional[str]:
    for sid, rec in _STORE.items():
        if rec.key == key:
            return sid
    return None


@router.get("")
def list_secrets(
    scope: Optional[Scope] = None,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    _require_auth(authorization)
    items = [_to_public(rec) for rec in _STORE.values() if not scope or rec.scope == scope]
    return {"data": items}


@router.post("")
def create_secret(
    body: dict,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    _require_auth(authorization)

    key = body.get("key")
    scope = body.get("scope")
    tags = body.get("tags", [])
    raw_value = body.get("rawValue")
    plain_value = body.get("value")
    value = raw_value if raw_value is not None else plain_value

    if not key or not value or not scope:
        raise HTTPException(status_code=422, detail="Missing required fields")

    if _find_store_id_by_key(key):
        raise HTTPException(status_code=409, detail="Secret already exists")

    new_id = f"sec-{len(_STORE) + 1}"
    rec = SecretRecord(id=new_id, key=key, rawValue=value, scope=scope, tags=tags)
    _STORE[new_id] = rec
    return {"data": _to_public(rec)}


@router.put("/{secret_id}/rotate")
def rotate_secret(
    secret_id: str,
    body: dict,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    _require_auth(authorization)

    if secret_id not in _STORE:
        raise HTTPException(status_code=404, detail="Secret not found")

    new_value = body.get("newValue")
    if not new_value:
        raise HTTPException(status_code=422, detail="Missing newValue")

    _STORE[secret_id] = _STORE[secret_id].model_copy(update={"rawValue": new_value})
    return _to_public(_STORE[secret_id])


@router.delete("/{secret_id}")
def delete_secret(
    secret_id: str,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    _require_auth(authorization)

    store_id = secret_id if secret_id in _STORE else _find_store_id_by_key(secret_id)
    if not store_id:
        raise HTTPException(status_code=404, detail="Secret not found")

    _STORE.pop(store_id, None)
    return {"ok": True}

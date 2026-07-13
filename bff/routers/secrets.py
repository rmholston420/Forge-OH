from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal
from uuid import uuid4
from datetime import datetime, timezone

router = APIRouter(prefix='/secrets', tags=['secrets'])

ScopeT = Literal['global', 'workspace', 'run']


class SecretView(BaseModel):
    id:          str
    key:         str
    scope:       ScopeT
    workspaceId: Optional[str] = None
    maskedValue: str
    createdAt:   str
    updatedAt:   str
    createdBy:   str
    tags:        list[str] = []


class SecretStore(BaseModel):
    model_config = ConfigDict(json_schema_extra={"exclude": ["rawValue"]})

    id:          str
    key:         str
    scope:       ScopeT
    workspaceId: Optional[str] = None
    rawValue:    str
    createdAt:   str
    updatedAt:   str
    createdBy:   str
    tags:        list[str] = []


class CreateRequest(BaseModel):
    key:         str
    value:       str
    scope:       ScopeT = 'global'
    workspaceId: Optional[str] = None
    tags:        list[str] = []


class RotateRequest(BaseModel):
    newValue: str


def _now(): return datetime.now(timezone.utc).isoformat()
def _mask(v: str): return '****' + v[-4:] if len(v) >= 4 else '****'
def _view(s: SecretStore) -> SecretView:
    return SecretView(
        id=s.id, key=s.key, scope=s.scope, workspaceId=s.workspaceId,
        maskedValue=_mask(s.rawValue), createdAt=s.createdAt,
        updatedAt=s.updatedAt, createdBy=s.createdBy, tags=s.tags,
    )


_STORE: dict[str, SecretStore] = {
    'sec-1': SecretStore(
        id='sec-1', key='OPENAI_API_KEY', scope='global',
        rawValue='sk-xxxxxxxxxxxxxx1234', createdAt=_now(),
        updatedAt=_now(), createdBy='admin', tags=['llm'],
    ),
    'sec-2': SecretStore(
        id='sec-2', key='BRAVE_SEARCH_API_KEY', scope='global',
        rawValue='BSA_xxxxxxxxxxxx5678', createdAt=_now(),
        updatedAt=_now(), createdBy='admin', tags=['search'],
    ),
    'sec-3': SecretStore(
        id='sec-3', key='GITHUB_TOKEN', scope='workspace',
        workspaceId='ws-1', rawValue='ghp_xxxxxxxxxxxx9abc',
        createdAt=_now(), updatedAt=_now(), createdBy='user', tags=['git'],
    ),
}


@router.get('', response_model=list[SecretView])
def list_secrets(scope: Optional[ScopeT] = Query(None)):
    """List secrets. scope must be one of: global, workspace, run."""
    items = list(_STORE.values())
    if scope:
        items = [s for s in items if s.scope == scope]
    return [_view(s) for s in items]


@router.post('', response_model=SecretView)
def create_secret(body: CreateRequest):
    if any(s.key == body.key for s in _STORE.values()):
        raise HTTPException(409, f'Secret key {body.key!r} already exists')
    s = SecretStore(
        id=str(uuid4()), key=body.key, scope=body.scope,
        workspaceId=body.workspaceId, rawValue=body.value,
        createdAt=_now(), updatedAt=_now(), createdBy='current-user',
        tags=body.tags,
    )
    _STORE[s.id] = s
    return _view(s)


@router.put('/{secret_id}/rotate', response_model=SecretView)
def rotate_secret(secret_id: str, body: RotateRequest):
    s = _STORE.get(secret_id)
    if not s:
        raise HTTPException(404, 'Secret not found')
    updated = s.model_copy(update={'rawValue': body.newValue, 'updatedAt': _now()})
    _STORE[secret_id] = updated
    return _view(updated)


@router.delete('/{secret_id}')
def delete_secret(secret_id: str):
    if secret_id not in _STORE:
        raise HTTPException(404, 'Secret not found')
    del _STORE[secret_id]
    return {'ok': True}

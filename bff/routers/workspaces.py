from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
from uuid import uuid4
from datetime import datetime, timezone

from bff.middleware.rbac import require_role

router = APIRouter(prefix='/workspaces', tags=['workspaces'])


class EnvVar(BaseModel):
    key:    str
    value:  str
    masked: bool = True


class Workspace(BaseModel):
    id:            str
    name:          str
    description:   Optional[str] = None
    type:          Literal['local', 'docker', 'e2b', 'modal']
    status:        Literal['idle', 'active', 'error', 'provisioning']
    createdAt:     str
    updatedAt:     str
    runCount:      int
    diskUsageMb:   float
    diskLimitMb:   float = 2048
    envVars:       list[EnvVar] = []
    agentPresetId: Optional[str] = None


class CreateWorkspaceRequest(BaseModel):
    name:          str
    description:   Optional[str] = None
    type:          Literal['local', 'docker', 'e2b', 'modal'] = 'local'
    envVars:       list[EnvVar] = []
    agentPresetId: Optional[str] = None


class UpdateWorkspaceRequest(BaseModel):
    """All fields optional for true PATCH semantics."""
    name:          Optional[str] = None
    description:   Optional[str] = None
    type:          Optional[Literal['local', 'docker', 'e2b', 'modal']] = None
    envVars:       Optional[list[EnvVar]] = None
    agentPresetId: Optional[str] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# TODO(foh-phase2): _WORKSPACES is process-scoped in-memory state. With
# --workers > 1, each Uvicorn worker gets its own isolated copy. Replace
# with a persistent store (Redis, DB) before any multi-worker deployment.
_WORKSPACES: dict[str, Workspace] = {
    'ws-1': Workspace(
        id='ws-1', name='Default Local', type='local', status='idle',
        createdAt=_now(), updatedAt=_now(), runCount=12,
        diskUsageMb=340, diskLimitMb=2048,
        description='Default local workspace for quick runs',
    ),
    'ws-2': Workspace(
        id='ws-2', name='Docker Sandbox', type='docker', status='idle',
        createdAt=_now(), updatedAt=_now(), runCount=5,
        diskUsageMb=1200, diskLimitMb=2048,
        description='Isolated Docker environment',
    ),
}


@router.get('', response_model=list[Workspace])
def list_workspaces():
    return list(_WORKSPACES.values())


@router.get('/{workspace_id}', response_model=Workspace)
def get_workspace(workspace_id: str):
    ws = _WORKSPACES.get(workspace_id)
    if not ws:
        raise HTTPException(404, 'Workspace not found')
    return ws


@router.post('', response_model=Workspace)
def create_workspace(
    body: CreateWorkspaceRequest,
    _: None = Depends(require_role('write')),
):
    ws = Workspace(
        id=str(uuid4()), status='provisioning',
        createdAt=_now(), updatedAt=_now(),
        runCount=0, diskUsageMb=0,
        **body.dict(),
    )
    _WORKSPACES[ws.id] = ws
    return ws


@router.patch('/{workspace_id}', response_model=Workspace)
def update_workspace(
    workspace_id: str,
    body: UpdateWorkspaceRequest,
    _: None = Depends(require_role('write')),
):
    ws = _WORKSPACES.get(workspace_id)
    if not ws:
        raise HTTPException(404, 'Workspace not found')
    updated = ws.copy(update={**body.dict(exclude_none=True), 'updatedAt': _now()})
    _WORKSPACES[workspace_id] = updated
    return updated


@router.delete('/{workspace_id}')
def delete_workspace(
    workspace_id: str,
    _: None = Depends(require_role('delete')),
):
    if workspace_id not in _WORKSPACES:
        raise HTTPException(404, 'Workspace not found')
    del _WORKSPACES[workspace_id]
    return {'ok': True}


@router.post('/{workspace_id}/reset', response_model=Workspace)
def reset_workspace(
    workspace_id: str,
    _: None = Depends(require_role('write')),
):
    ws = _WORKSPACES.get(workspace_id)
    if not ws:
        raise HTTPException(404, 'Workspace not found')
    # Reset clears disk usage AND run count, and returns status to idle.
    reset = ws.copy(update={'diskUsageMb': 0, 'runCount': 0, 'status': 'idle', 'updatedAt': _now()})
    _WORKSPACES[workspace_id] = reset
    return reset

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, HttpUrl

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceModel(BaseModel):
    id: str
    name: str
    type: Literal["local", "docker", "remote-api"]
    health: Literal["healthy", "warning", "error", "disconnected"]
    agent_server_url: str | None = None
    isolation_mode: Literal["shared", "isolated", "strict"] = "isolated"
    run_count: int = 0
    active_run_id: str | None = None
    last_seen_at: str | None = None
    created_at: str
    updated_at: str
    meta: dict = {}


class CreateWorkspaceRequest(BaseModel):
    name: str
    type: Literal["local", "docker", "remote-api"]
    agent_server_url: str | None = None
    isolation_mode: Literal["shared", "isolated", "strict"] = "isolated"


class ResetWorkspaceResponse(BaseModel):
    workspace_id: str
    status: Literal["reset"]
    reset_at: str


class DuplicateRequest(BaseModel):
    name: str


# ---------------------------------------------------------------------------
# In-memory store (replace with OpenHands workspace adapter in production)
# ---------------------------------------------------------------------------
_WORKSPACES: dict[str, WorkspaceModel] = {
    "ws-local-001": WorkspaceModel(
        id="ws-local-001",
        name="Local Dev",
        type="local",
        health="healthy",
        isolation_mode="isolated",
        run_count=12,
        last_seen_at=datetime.now(timezone.utc).isoformat(),
        created_at="2026-06-01T00:00:00Z",
        updated_at=datetime.now(timezone.utc).isoformat(),
    ),
    "ws-docker-001": WorkspaceModel(
        id="ws-docker-001",
        name="Docker Sandbox",
        type="docker",
        health="warning",
        isolation_mode="strict",
        run_count=3,
        created_at="2026-06-15T00:00:00Z",
        updated_at=datetime.now(timezone.utc).isoformat(),
    ),
}


@router.get("/", response_model=list[WorkspaceModel])
async def list_workspaces() -> list[WorkspaceModel]:
    return list(_WORKSPACES.values())


@router.get("/{workspace_id}", response_model=WorkspaceModel)
async def get_workspace(workspace_id: str) -> WorkspaceModel:
    ws = _WORKSPACES.get(workspace_id)
    if not ws:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return ws


@router.post("/", response_model=WorkspaceModel, status_code=status.HTTP_201_CREATED)
async def create_workspace(payload: CreateWorkspaceRequest) -> WorkspaceModel:
    import uuid
    new_id = f"ws-{payload.type}-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    ws = WorkspaceModel(
        id=new_id,
        name=payload.name,
        type=payload.type,
        health="healthy",
        agent_server_url=str(payload.agent_server_url) if payload.agent_server_url else None,
        isolation_mode=payload.isolation_mode,
        created_at=now,
        updated_at=now,
    )
    _WORKSPACES[new_id] = ws
    return ws


@router.post("/{workspace_id}/reset", response_model=ResetWorkspaceResponse)
async def reset_workspace(workspace_id: str) -> ResetWorkspaceResponse:
    ws = _WORKSPACES.get(workspace_id)
    if not ws:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    now = datetime.now(timezone.utc).isoformat()
    _WORKSPACES[workspace_id] = ws.model_copy(
        update={"active_run_id": None, "health": "healthy", "updated_at": now}
    )
    return ResetWorkspaceResponse(workspace_id=workspace_id, status="reset", reset_at=now)


@router.post("/{workspace_id}/duplicate", response_model=WorkspaceModel)
async def duplicate_workspace(workspace_id: str, body: DuplicateRequest) -> WorkspaceModel:
    ws = _WORKSPACES.get(workspace_id)
    if not ws:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    import uuid
    new_id = f"ws-{ws.type}-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    dup = ws.model_copy(update={"id": new_id, "name": body.name, "run_count": 0, "created_at": now, "updated_at": now})
    _WORKSPACES[new_id] = dup
    return dup


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(workspace_id: str) -> None:
    if workspace_id not in _WORKSPACES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    del _WORKSPACES[workspace_id]

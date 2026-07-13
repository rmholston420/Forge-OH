"""Workspaces router — Phase 3 stub."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class CreateWorkspaceRequest(BaseModel):
    name: str
    type: str  # local | docker | remote_api
    description: Optional[str] = None
    baseDir: Optional[str] = None
    dockerImage: Optional[str] = None
    remoteUrl: Optional[str] = None
    envVars: dict = {}


def _stub_workspace(id_: str, name: str, type_: str) -> dict:
    return {
        "id": id_, "name": name, "type": type_,
        "status": "inactive", "description": None,
        "baseDir": None, "dockerImage": None, "remoteUrl": None,
        "envVars": {}, "createdAt": "2026-07-12T00:00:00Z",
        "updatedAt": "2026-07-12T00:00:00Z",
        "lastUsedAt": None, "activeRunCount": 0,
    }


@router.get("/workspaces")
async def list_workspaces() -> dict:
    return {"data": [], "stub": True}


@router.post("/workspaces")
async def create_workspace(body: CreateWorkspaceRequest) -> dict:
    ws = _stub_workspace("ws-new-001", body.name, body.type)
    ws["description"] = body.description
    ws["baseDir"] = body.baseDir
    ws["dockerImage"] = body.dockerImage
    ws["remoteUrl"] = body.remoteUrl
    ws["envVars"] = body.envVars
    return {"data": ws}


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str) -> dict:
    return {"data": None, "stub": True, "workspace_id": workspace_id}


@router.patch("/workspaces/{workspace_id}")
async def update_workspace(workspace_id: str, body: CreateWorkspaceRequest) -> dict:
    ws = _stub_workspace(workspace_id, body.name, body.type)
    return {"data": ws}


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str) -> dict:
    return {"ok": True, "workspace_id": workspace_id}


@router.post("/workspaces/{workspace_id}/test")
async def test_workspace_connection(workspace_id: str) -> dict:
    return {"ok": True, "latencyMs": 12, "error": None}

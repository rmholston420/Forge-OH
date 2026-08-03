"""
Workspaces router — thin passthrough over openhands agent-server 1.40.0.

Agent-server owns the canonical workspace registry:
  GET    /api/workspaces         -> {workspaces:[{id,name,path,parentPath?}], workspaceParents:[...]}
  POST   /api/workspaces         -> {workspaces:[...]}   (adds each item)
  DELETE /api/workspaces?path=X  -> {deleted: true}
  POST   /api/workspaces/parents -> registers a parent dir under which
                                    children can be created
  DELETE /api/workspaces/parents?path=X

The BFF exposes a frontend-shaped view: WorkspaceItem with a `type:'local'`
field kept for compatibility with the existing UI's typed schema (single-user
local-first stack — no other kinds are supported).

Stage 6 changes:
  - Dropped in-memory _WORKSPACES stub.
  - Dropped fake docker/e2b/modal type variants; local is the only kind.
  - Dropped envVars, diskUsage, runCount, status — none of these are
    modelled by agent-server. If the UI needs derived stats later, we can
    compute them on read.
  - test_workspace_connection() now does a real path check.
  - reset_workspace endpoint removed (destructive, unused by any spec DoD).
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from bff.openhands_client import get_client

log = logging.getLogger(__name__)
router = APIRouter(prefix="/workspaces", tags=["workspaces"])

# Root under which new workspaces are created when the caller doesn't supply
# an absolute path. Falls back to ~/dev/forge-oh/workspaces on Colossus.
_DEFAULT_ROOT = Path(
    os.getenv("FORGE_WORKSPACES_ROOT", str(Path.home() / "dev" / "forge-oh" / "workspaces"))
)


# ---------------------------------------------------------------------------
# BFF-shaped models
# ---------------------------------------------------------------------------


class Workspace(BaseModel):
    id: str
    name: str
    path: str
    parentPath: str | None = None
    type: Literal["local"] = "local"  # kept for existing UI schema
    # Legacy fields the UI may still read; safe defaults.
    status: Literal["idle", "active", "error", "provisioning"] = "idle"
    createdAt: str | None = None
    updatedAt: str | None = None
    runCount: int = 0
    diskUsageMb: float = 0.0
    diskLimitMb: float = 2048.0
    envVars: list[dict] = []
    agentPresetId: str | None = None


class CreateWorkspaceRequest(BaseModel):
    name: str
    path: str | None = None  # absolute path; if omitted, derived from name under DEFAULT_ROOT
    parentPath: str | None = None
    # Ignored (kept so existing UI POSTs don't 422 during transition):
    description: str | None = None
    type: Literal["local"] = "local"
    envVars: list[dict] = []
    agentPresetId: str | None = None


class UpdateWorkspaceRequest(BaseModel):
    name: str | None = None
    path: str | None = None
    parentPath: str | None = None


class TestConnectionResult(BaseModel):
    ok: bool
    latencyMs: float | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip()).strip("-").lower()
    return s or f"ws-{uuid4().hex[:8]}"


def _to_bff(item: dict) -> Workspace:
    """Convert an agent-server WorkspaceItem to the BFF Workspace shape."""
    return Workspace(
        id=item["id"],
        name=item["name"],
        path=item["path"],
        parentPath=item.get("parentPath"),
    )


async def _list_agent_workspaces() -> list[dict]:
    """Return raw agent-server WorkspaceItems."""
    client = get_client()
    try:
        r = await client.get("/api/workspaces")
        r.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"agent-server workspace list failed: {exc}") from exc
    data = r.json() or {}
    return list(data.get("workspaces", []))


async def _get_agent_workspace_by_id(workspace_id: str) -> dict | None:
    for w in await _list_agent_workspaces():
        if w.get("id") == workspace_id:
            return w
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=list[Workspace])
async def list_workspaces() -> list[Workspace]:
    items = await _list_agent_workspaces()
    return [_to_bff(w) for w in items]


@router.get("/{workspace_id}", response_model=Workspace)
async def get_workspace(workspace_id: str) -> Workspace:
    ws = await _get_agent_workspace_by_id(workspace_id)
    if not ws:
        raise HTTPException(404, "Workspace not found")
    return _to_bff(ws)


@router.post("", response_model=Workspace)
async def create_workspace(body: CreateWorkspaceRequest) -> Workspace:
    # Derive path if not provided.
    if body.path:
        path = body.path
    else:
        _DEFAULT_ROOT.mkdir(parents=True, exist_ok=True)
        path = str(_DEFAULT_ROOT / _slug(body.name))

    # Make sure the directory exists so agent-server can chdir into it later.
    Path(path).mkdir(parents=True, exist_ok=True)

    wid = uuid4().hex
    item = {"id": wid, "name": body.name, "path": path}
    if body.parentPath:
        item["parentPath"] = body.parentPath

    client = get_client()
    try:
        r = await client.post("/api/workspaces", json={"workspaces": [item]})
        r.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"agent-server workspace create failed: {exc}") from exc

    # Look up the freshly added item (agent-server may normalize fields).
    fresh = await _get_agent_workspace_by_id(wid)
    return _to_bff(fresh) if fresh else _to_bff(item)


@router.patch("/{workspace_id}", response_model=Workspace)
async def update_workspace(workspace_id: str, body: UpdateWorkspaceRequest) -> Workspace:
    # Agent-server has no PATCH; emulate as delete + re-add. Only 'name' can
    # meaningfully change (path change would mean a new workspace anyway).
    existing = await _get_agent_workspace_by_id(workspace_id)
    if not existing:
        raise HTTPException(404, "Workspace not found")

    new_name = body.name or existing["name"]
    new_path = body.path or existing["path"]
    new_parent = body.parentPath if body.parentPath is not None else existing.get("parentPath")

    client = get_client()
    # Delete by original path.
    try:
        dr = await client.delete("/api/workspaces", params={"path": existing["path"]})
        if dr.status_code >= 400:
            raise HTTPException(502, f"agent-server delete during update failed: {dr.text[:200]}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"agent-server delete failed: {exc}") from exc

    # Re-add with same id, new name/path.
    item = {"id": workspace_id, "name": new_name, "path": new_path}
    if new_parent:
        item["parentPath"] = new_parent
    Path(new_path).mkdir(parents=True, exist_ok=True)
    try:
        r = await client.post("/api/workspaces", json={"workspaces": [item]})
        r.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"agent-server re-add failed: {exc}") from exc

    return _to_bff(item)


@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: str) -> dict:
    ws = await _get_agent_workspace_by_id(workspace_id)
    if not ws:
        raise HTTPException(404, "Workspace not found")
    client = get_client()
    try:
        r = await client.delete("/api/workspaces", params={"path": ws["path"]})
        r.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"agent-server delete failed: {exc}") from exc
    return {"ok": True}


@router.post("/{workspace_id}/test", response_model=TestConnectionResult)
async def test_workspace_connection(workspace_id: str) -> TestConnectionResult:
    """Real health check: verify path exists and is read/writable by the BFF."""
    ws = await _get_agent_workspace_by_id(workspace_id)
    if not ws:
        raise HTTPException(404, "Workspace not found")
    p = Path(ws["path"])
    if not p.exists():
        return TestConnectionResult(ok=False, error=f"path does not exist: {p}")
    if not p.is_dir():
        return TestConnectionResult(ok=False, error=f"path is not a directory: {p}")
    if not os.access(p, os.R_OK | os.W_OK):
        return TestConnectionResult(ok=False, error=f"path is not read+writable: {p}")
    return TestConnectionResult(ok=True, latencyMs=0.0)

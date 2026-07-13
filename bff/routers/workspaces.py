"""Workspaces router stub — Phase 0 scaffold."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/workspaces")
async def list_workspaces() -> dict:
    return {"data": [], "stub": True}


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str) -> dict:
    return {"data": None, "stub": True}


@router.post("/workspaces/{workspace_id}/reset")
async def reset_workspace(workspace_id: str) -> dict:
    return {"ok": True, "stub": True}

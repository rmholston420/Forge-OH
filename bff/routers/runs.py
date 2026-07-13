"""Runs router — Phase 2 — adds /files endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class CreateRunRequest(BaseModel):
    title: str
    agentPresetId: str
    workspaceId: str
    contextPrompt: Optional[str] = None


@router.get("/runs")
async def list_runs() -> dict:
    return {"data": [], "stub": True}


@router.post("/runs")
async def create_run(body: CreateRunRequest) -> dict:
    return {"data": {
        "id": "run-new-001",
        "title": body.title,
        "status": "queued",
        "agentPresetName": body.agentPresetId,
        "workspaceId": body.workspaceId,
        "workspaceType": "local",
        "activeTool": None,
        "updatedAt": "2026-07-12T00:00:00Z",
        "createdAt": "2026-07-12T00:00:00Z",
        "elapsedMs": None,
        "estimatedCostUsd": None,
    }}


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    return {"data": None, "stub": True, "run_id": run_id}


@router.get("/runs/{run_id}/events")
async def get_run_events(run_id: str) -> dict:
    return {"data": [], "stub": True}


@router.get("/runs/{run_id}/plan")
async def get_run_plan(run_id: str) -> dict:
    return {"data": [], "stub": True}


@router.get("/runs/{run_id}/files")
async def get_run_files(run_id: str) -> dict:
    """GET /api/runs/:id/files — file change summary list."""
    return {"data": [], "stub": True}


@router.get("/runs/{run_id}/files/{file_path:path}")
async def get_run_file_diff(run_id: str, file_path: str) -> dict:
    """GET /api/runs/:id/files/:path — full diff for one file."""
    return {"data": None, "stub": True, "path": file_path}


@router.get("/runs/{run_id}/artifacts")
async def get_run_artifacts(run_id: str) -> dict:
    return {"data": [], "stub": True}


@router.get("/runs/{run_id}/commands")
async def get_run_commands(run_id: str) -> dict:
    return {"data": [], "stub": True}


@router.get("/runs/{run_id}/traces")
async def get_run_traces(run_id: str) -> dict:
    return {"data": [], "stub": True}


@router.post("/runs/{run_id}/pause")
async def pause_run(run_id: str) -> dict:
    return {"ok": True, "run_id": run_id, "status": "paused"}


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str) -> dict:
    return {"ok": True, "run_id": run_id, "status": "running"}


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str) -> dict:
    return {"ok": True, "run_id": run_id, "status": "failed"}


@router.post("/runs/{run_id}/approve")
async def approve_run(run_id: str) -> dict:
    return {"ok": True, "run_id": run_id, "status": "running"}


@router.post("/runs/{run_id}/reject")
async def reject_run(run_id: str) -> dict:
    return {"ok": True, "run_id": run_id, "status": "paused"}


@router.post("/runs/{run_id}/fork")
async def fork_run(run_id: str) -> dict:
    return {"ok": True, "run_id": run_id, "forked_id": f"{run_id}-fork-1"}

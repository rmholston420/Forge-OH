"""Runs router — Phase 2 — adds /files, /fork, and /compare endpoints."""
from fastapi import APIRouter, Query
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


@router.get("/runs/compare")
async def compare_runs(
    base: str = Query(..., description="Base run ID"),
    fork: str = Query(..., description="Fork run ID"),
) -> dict:
    """
    GET /api/runs/compare?base=<id>&fork=<id>

    Returns a file-level diff between a base run and its fork.
    Stub implementation — real implementation will proxy to OpenHandsClient
    workspace snapshot diffing once the OpenHands conversation/snapshot API
    is confirmed stable.
    """
    return {
        "data": {
            "baseRunId": base,
            "forkRunId": fork,
            "baseTitle": f"Run {base[:8]}",
            "forkTitle": f"Run {fork[:8]} (fork)",
            "files": [],
            "stats": {
                "totalFiles": 0,
                "additions": 0,
                "deletions": 0,
            },
        },
        "stub": True,
    }


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
    """
    POST /api/runs/:id/fork

    Creates a new run forked from an existing one. The fork copies the
    workspace snapshot, agent preset, and context prompt of the base run.
    Stub — real implementation will call OpenHandsClient.create_run with
    a fork_of parameter once the OpenHands fork API is confirmed.
    """
    return {"ok": True, "run_id": run_id, "forked_id": f"{run_id}-fork-1"}

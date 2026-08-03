"""Runs router — Stage 3: real conversation lifecycle via OpenHands agent-server.

Wired endpoints (real):
  GET  /runs            list conversations from agent-server as RunSummary
  POST /runs            start + run a conversation, return RunSummary (queued|blocked|running)
  GET  /runs/{id}       fetch a single conversation as RunSummary
  GET  /runs/{id}/events fetch persisted events (paged) as-is from agent-server

Still stub (deferred to later stages per Forge-OH-Action-Plan-v4.md):
  /runs/compare, /runs/{id}/plan, /files/*, /artifacts, /commands, /traces,
  /pause, /resume, /stop, /approve, /reject, /fork

Contract:
  run_id == conversation_id (agent-server UUID). No SQLite mapping layer.
  Model routing lives in bff.services.model_router; if it returns a model
  we call agent-server; if it raises ModelUnavailableError we short-circuit
  with status='blocked' and never touch agent-server.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from bff.openhands_client import get_client
from bff.services.event_relay import start_relay
from bff.services.file_diff_reconstruction import build_file_diff, build_summaries
from bff.services.model_router import route_request, ModelUnavailableError

log = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateRunRequest(BaseModel):
    title: str
    agentPresetId: str
    workspaceId: str
    taskPrompt: Optional[str] = None
    taskComplexity: Optional[str] = None
    contextLength: Optional[int] = None


# ---------------------------------------------------------------------------
# Agent-server -> RunSummary translation
# ---------------------------------------------------------------------------

# ConversationExecutionStatus (agent-server) -> RunSummary.status (frontend enum).
_STATUS_MAP = {
    "idle": "queued",
    "running": "running",
    "paused": "paused",
    "waiting_for_confirmation": "awaiting_approval",
    "finished": "succeeded",
    "error": "failed",
    "stuck": "failed",
    "deleting": "failed",
}

# Where agent-server should run each conversation. Q1(b): per-run isolation.
# Path is relative to the agent-server's CWD (Colossus: ~/dev/forge-oh).
_WORKSPACE_ROOT = Path(os.getenv("FORGE_WORKSPACE_ROOT", "workspace/runs"))
_USAGE_ID = os.getenv("FORGE_USAGE_ID", "colossus-ollama")
_OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")


def _translate_model(routed: str) -> str:
    """route_request returns 'ollama/<tag>' or 'vllm/<tag>'.
    Agent-server (LiteLLM) expects 'openai/<tag>' for the OpenAI-compat path."""
    _, _, tag = routed.partition("/")
    return f"openai/{tag}" if tag else f"openai/{routed}"


def _conv_to_run_summary(conv: dict[str, Any]) -> dict[str, Any]:
    """Translate an agent-server ConversationInfo dict into a RunSummary."""
    cid = conv.get("id", "")
    exec_status = conv.get("execution_status", "idle")
    status = _STATUS_MAP.get(exec_status, "queued")
    agent = conv.get("agent") or {}
    llm = (agent or {}).get("llm") or {}
    model = llm.get("model") or conv.get("current_model_id")
    return {
        "id": cid,
        "title": conv.get("title") or f"Run {cid[:8] if cid else ''}",
        "status": status,
        "agentPresetName": llm.get("usage_id") or "colossus-ollama",
        "workspaceId": (conv.get("workspace") or {}).get("working_dir") or "local",
        "workspaceType": "local",
        "activeTool": None,
        "updatedAt": conv.get("updated_at"),
        "createdAt": conv.get("created_at"),
        "elapsedMs": None,
        "estimatedCostUsd": None,
        "selectedModel": model,
        "executionStatus": exec_status,
    }


# ---------------------------------------------------------------------------
# GET /runs  — list
# ---------------------------------------------------------------------------

@router.get("/runs")
async def list_runs(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
) -> dict:
    # Agent-server 1.40.0: /api/conversations is batch-get by ids (422 without ids).
    # The real list endpoint is /api/conversations/search (paginated, cursor-based).
    client = get_client()
    try:
        resp = await client.get(
            "/api/conversations/search",
            params={"limit": pageSize, "sort_order": "CREATED_AT_DESC"},
        )
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        log.warning("list_runs: agent-server unreachable: %s", exc)
        return {"data": [], "pageInfo": {"total": 0, "page": page, "pageSize": pageSize}}

    payload = resp.json() or {}
    if isinstance(payload, list):
        convs = payload
    else:
        convs = payload.get("items") or payload.get("data") or payload.get("conversations") or []
    runs = [_conv_to_run_summary(c) for c in convs]
    return {
        "data": runs,
        "pageInfo": {"total": len(runs), "page": page, "pageSize": pageSize},
    }


# ---------------------------------------------------------------------------
# POST /runs  — start conversation + kick off + open event relay
# ---------------------------------------------------------------------------

@router.post("/runs")
async def create_run(body: CreateRunRequest) -> dict:
    task_complexity = body.taskComplexity or "agentic"
    context_length = body.contextLength if body.contextLength is not None else len(body.taskPrompt or "")

    # 1) Route.
    try:
        routed = await route_request(task_complexity, context_length)
    except ModelUnavailableError as exc:
        return {"data": {
            "id": "",
            "title": body.title,
            "status": "blocked",
            "agentPresetName": body.agentPresetId,
            "workspaceId": body.workspaceId,
            "workspaceType": "local",
            "selectedModel": None,
            "routing": {
                "taskComplexity": task_complexity,
                "contextLength": context_length,
                "selected": None,
                "error": str(exc),
            },
        }}

    litellm_model = _translate_model(routed)

    # 2) Create conversation on agent-server.
    working_dir_placeholder = str(_WORKSPACE_ROOT / "pending")
    create_body = {
        "workspace": {
            "working_dir": working_dir_placeholder,
            "kind": "LocalWorkspace",
        },
        "initial_message": {
            "content": [{"text": body.taskPrompt or ""}],
        },
        "agent": {
            "llm": {
                "model": litellm_model,
                "base_url": _OLLAMA_BASE,
                "api_key": "ollama",
                "usage_id": _USAGE_ID,
                "is_subscription": False,
                "native_tool_calling": False,
            },
            "tools": [
                {"name": "terminal"},
                {"name": "file_editor"},
                {"name": "task_tracker"},
                {"name": "browser_tool_set"},
            ],
            "kind": "Agent",
        },
        "title": body.title,
    }

    client = get_client()
    try:
        create_resp = await client.post("/api/conversations", json=create_body)
        create_resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        log.exception("create_run: /api/conversations failed")
        raise HTTPException(status_code=502, detail=f"agent-server create failed: {exc}") from exc

    conv = create_resp.json()
    cid = conv.get("id")
    if not cid:
        raise HTTPException(status_code=502, detail="agent-server returned no conversation id")

    # 3) Kick off in background.
    try:
        run_resp = await client.post(f"/api/conversations/{cid}/run")
        # 409 = already running (idempotent) — treat as success.
        if run_resp.status_code not in (200, 409):
            run_resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        log.warning("create_run: /api/conversations/%s/run failed: %s", cid, exc)

    # 4) Start the Socket.IO relay for this conversation.
    start_relay(cid)

    summary = _conv_to_run_summary(conv)
    summary["routing"] = {
        "taskComplexity": task_complexity,
        "contextLength": context_length,
        "selected": routed,
        "error": None,
    }
    return {"data": summary}


# ---------------------------------------------------------------------------
# GET /runs/{run_id}  — real status
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    try:
        resp = await get_client().get(f"/api/conversations/{run_id}")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"agent-server unreachable: {exc}") from exc
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="run not found")
    resp.raise_for_status()
    # Ensure a relay is running (in case BFF restarted after a run began).
    start_relay(run_id)
    return {"data": _conv_to_run_summary(resp.json())}


# ---------------------------------------------------------------------------
# GET /runs/{run_id}/events  — persisted events (paged)
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}/events")
async def get_run_events(
    run_id: str,
    page_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=100),
) -> dict:
    params: dict[str, Any] = {"limit": limit, "sort_order": "TIMESTAMP"}
    if page_id:
        params["page_id"] = page_id
    try:
        resp = await get_client().get(
            f"/api/conversations/{run_id}/events/search",
            params=params,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"agent-server unreachable: {exc}") from exc
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="run not found")
    resp.raise_for_status()
    payload = resp.json() or {}
    if isinstance(payload, list):
        return {"data": payload, "nextPageId": None}
    items = payload.get("items") or payload.get("data") or payload.get("events") or []
    next_page = payload.get("next_page_id") or payload.get("nextPageId")
    return {"data": items, "nextPageId": next_page}


# ---------------------------------------------------------------------------
# Deferred: still-stub endpoints (Steps 4 / 5 / 6)
# ---------------------------------------------------------------------------

@router.get("/runs/compare")
async def compare_runs(
    base: str = Query(..., description="Base run ID"),
    fork: str = Query(..., description="Fork run ID"),
) -> dict:
    return {
        "data": {
            "baseRunId": base,
            "forkRunId": fork,
            "baseTitle": f"Run {base[:8]}",
            "forkTitle": f"Run {fork[:8]} (fork)",
            "files": [],
            "stats": {"totalFiles": 0, "additions": 0, "deletions": 0},
        },
        "stub": True,
    }


@router.get("/runs/{run_id}/plan")
async def get_run_plan(run_id: str) -> dict:
    return {"data": [], "stub": True}


async def _fetch_all_events(run_id: str) -> list[dict[str, Any]]:
    """Page through /api/conversations/{run_id}/events/search (limit=100 per page)."""
    client = get_client()
    items: list[dict[str, Any]] = []
    page_id: Optional[str] = None
    # Safety: cap total pages to avoid runaway on malformed cursors.
    for _ in range(200):
        params: dict[str, Any] = {"limit": 100, "sort_order": "TIMESTAMP"}
        if page_id:
            params["page_id"] = page_id
        try:
            resp = await client.get(
                f"/api/conversations/{run_id}/events/search",
                params=params,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"agent-server unreachable: {exc}") from exc
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="run not found")
        resp.raise_for_status()
        payload = resp.json() or {}
        if isinstance(payload, list):
            items.extend(payload)
            break
        batch = payload.get("items") or payload.get("data") or payload.get("events") or []
        items.extend(batch)
        next_page = payload.get("next_page_id") or payload.get("nextPageId")
        if not next_page or not batch:
            break
        page_id = next_page
    return items


@router.get("/runs/{run_id}/files")
async def get_run_files(run_id: str) -> dict:
    events = await _fetch_all_events(run_id)
    return {"data": build_summaries(events)}


@router.get("/runs/{run_id}/files/{file_path:path}")
async def get_run_file_diff(run_id: str, file_path: str) -> dict:
    events = await _fetch_all_events(run_id)
    diff = build_file_diff(events, file_path)
    if diff is None:
        raise HTTPException(status_code=404, detail="file not found in run")
    return {"data": diff}


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
    return {"ok": True, "run_id": run_id, "status": "stopped"}


@router.post("/runs/{run_id}/approve")
async def approve_run(run_id: str) -> dict:
    return {"ok": True, "run_id": run_id, "status": "running"}


@router.post("/runs/{run_id}/reject")
async def reject_run(run_id: str) -> dict:
    return {"ok": True, "run_id": run_id, "status": "paused"}


@router.post("/runs/{run_id}/fork")
async def fork_run(run_id: str) -> dict:
    return {"ok": True, "run_id": run_id, "forked_id": f"{run_id}-fork-1", "stub": True}

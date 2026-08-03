"""Runs router — Stage 3+4+5: real conversation lifecycle via OpenHands agent-server.

Wired endpoints (real):
  GET  /runs            list conversations from agent-server as RunSummary
  POST /runs            start + run a conversation, return RunSummary (queued|blocked|running)
  GET  /runs/{id}       fetch a single conversation as RunSummary
  GET  /runs/{id}/events fetch persisted events (paged) as-is from agent-server
  GET  /runs/{id}/files, /runs/{id}/files/{path}   Stage 4 event-stream file diffs
  POST /runs/{id}/pause     → agent-server POST /conversations/{cid}/pause
  POST /runs/{id}/resume    → agent-server POST /conversations/{cid}/run
  POST /runs/{id}/stop      → agent-server POST /conversations/{cid}/interrupt
  POST /runs/{id}/approve   → agent-server POST /conversations/{cid}/events/respond_to_confirmation {accept:true}
  POST /runs/{id}/reject    → agent-server POST /conversations/{cid}/events/respond_to_confirmation {accept:false}

Slice 7A (derived from event stream):
  GET  /runs/{id}/plan       → task_tracker ActionEvent + ObservationEvent
  GET  /runs/{id}/commands   → bash ActionEvent + ObservationEvent pairs
  GET  /runs/{id}/artifacts  → file_editor mutating ActionEvents

Slice 7B (real passthrough):
  POST /runs/{id}/fork       → agent-server POST /api/conversations/{id}/fork

Slice 7F (derived from event stream):
  GET  /runs/{id}/traces     → spans from ActionEvents + MessageEvents

Still stub (later stage):
  /runs/compare

Contract:
  run_id == conversation_id (agent-server UUID). No SQLite mapping layer.
  Model routing lives in bff.services.model_router; if it returns a model
  we call agent-server; if it raises ModelUnavailableError we short-circuit
  with status='blocked' and never touch agent-server.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from bff.openhands_client import get_client
from bff.services.action_reconstruction import (
    build_artifacts,
    build_commands,
    build_plan,
)
from bff.services.event_relay import start_relay
from bff.services.file_diff_reconstruction import build_file_diff, build_summaries
from bff.services.model_router import ModelUnavailableError, route_request

log = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateRunRequest(BaseModel):
    title: str
    agentPresetId: str
    workspaceId: str
    taskPrompt: str | None = None
    taskComplexity: str | None = None
    contextLength: int | None = None
    # Stage 1E: when true, agent will pause before every tool call for HITL
    # approve/reject. Backed by APPROVAL_GATE feature flag in the frontend.
    requireApproval: bool | None = False


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
    except Exception as exc:
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
    context_length = (
        body.contextLength if body.contextLength is not None else len(body.taskPrompt or "")
    )

    # 1) Route.
    try:
        routed = await route_request(task_complexity, context_length)
    except ModelUnavailableError as exc:
        return {
            "data": {
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
            }
        }

    litellm_model = _translate_model(routed)

    # 2) Resolve working_dir from the selected workspace on agent-server.
    #    Stage 6: workspaces are stored on agent-server (GET /api/workspaces).
    #    Fall back to _WORKSPACE_ROOT/pending if the id can't be resolved
    #    (e.g. legacy runs referencing seeded fixture ids).
    client = get_client()
    working_dir = str(_WORKSPACE_ROOT / "pending")
    try:
        ws_resp = await client.get("/api/workspaces")
        if ws_resp.status_code < 400:
            for w in (ws_resp.json() or {}).get("workspaces", []):
                if w.get("id") == body.workspaceId:
                    working_dir = w["path"]
                    break
    except Exception as exc:
        log.warning("create_run: workspace lookup failed, using default: %s", exc)

    # 3) Create conversation on agent-server.
    create_body = {
        "workspace": {
            "working_dir": working_dir,
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

    try:
        create_resp = await client.post("/api/conversations", json=create_body)
        create_resp.raise_for_status()
    except Exception as exc:
        log.exception("create_run: /api/conversations failed")
        raise HTTPException(status_code=502, detail=f"agent-server create failed: {exc}") from exc

    conv = create_resp.json()
    cid = conv.get("id")
    if not cid:
        raise HTTPException(status_code=502, detail="agent-server returned no conversation id")

    # 3a) Stage 1E — apply confirmation policy BEFORE kicking the loop off.
    #     'AlwaysConfirm' makes agent-server enter waiting_for_confirmation
    #     at every tool call; user must click Approve/Reject in the UI.
    if body.requireApproval:
        try:
            pol_resp = await client.post(
                f"/api/conversations/{cid}/confirmation_policy",
                json={"policy": {"kind": "AlwaysConfirm"}},
            )
            if pol_resp.status_code >= 400:
                log.warning(
                    "create_run: setting AlwaysConfirm on %s failed: %s %s",
                    cid,
                    pol_resp.status_code,
                    pol_resp.text[:200],
                )
        except Exception as exc:
            log.warning("create_run: confirmation_policy call failed: %s", exc)

    # 3) Kick off in background.
    try:
        run_resp = await client.post(f"/api/conversations/{cid}/run")
        # 409 = already running (idempotent) — treat as success.
        if run_resp.status_code not in (200, 409):
            run_resp.raise_for_status()
    except Exception as exc:
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
# /runs/compare — artifacts diff + best-effort content diff.
# MUST be declared before /runs/{run_id} so FastAPI matches it first;
# otherwise "compare" is captured as a run_id.
# ---------------------------------------------------------------------------


@router.get("/runs/compare")
async def compare_runs(
    base: str = Query(..., description="Base run ID"),
    fork: str = Query(..., description="Fork run ID"),
) -> dict:
    from bff.services.run_compare import (
        compare_runs as _do_compare,  # local import to avoid cycles
    )

    client = get_client()

    base_events = await _fetch_all_events(base)
    fork_events = await _fetch_all_events(fork)

    async def _conv(cid: str) -> dict:
        try:
            resp = await client.get(f"/api/conversations/{cid}")
            if resp.status_code != 200:
                return {}
            return resp.json() or {}
        except Exception:
            return {}

    base_conv = await _conv(base)
    fork_conv = await _conv(fork)
    base_wd = (base_conv.get("workspace") or {}).get("working_dir")
    fork_wd = (fork_conv.get("workspace") or {}).get("working_dir")

    data = _do_compare(base, fork, base_events, fork_events, base_wd, fork_wd)
    if base_conv.get("title"):
        data["baseTitle"] = base_conv["title"]
    if fork_conv.get("title"):
        data["forkTitle"] = fork_conv["title"]
    return {"data": data}


# ---------------------------------------------------------------------------
# GET /runs/{run_id}  — real status
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    try:
        resp = await get_client().get(f"/api/conversations/{run_id}")
    except Exception as exc:
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
    page_id: str | None = Query(None),
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
    except Exception as exc:
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


@router.get("/runs/{run_id}/plan")
async def get_run_plan(run_id: str) -> dict:
    events = await _fetch_all_events(run_id)
    return {"data": build_plan(events, run_id)}


# _fetch_all_events was moved to bff.services.event_fetch for reuse by the
# observability router; this thin alias keeps existing call sites working.
from bff.services.event_fetch import fetch_all_events as _fetch_all_events


@router.get("/runs/{run_id}/files")
async def get_run_files(run_id: str) -> dict:
    events = await _fetch_all_events(run_id)
    return {"data": build_summaries(events)}


@router.get("/runs/{run_id}/files/{file_path:path}")
async def get_run_file_diff(run_id: str, file_path: str) -> dict:
    events = await _fetch_all_events(run_id)
    # Try the path as-received first (URL-decoded by FastAPI), then with a
    # leading '/' added. This tolerates both `%2Fworkspace%2Ffoo` (frontend
    # encodeURIComponent) and `workspace/foo` (raw path parameter) forms.
    diff = build_file_diff(events, file_path)
    if diff is None and not file_path.startswith("/"):
        diff = build_file_diff(events, "/" + file_path)
    if diff is None:
        raise HTTPException(status_code=404, detail="file not found in run")
    return {"data": diff}


@router.get("/runs/{run_id}/artifacts")
async def get_run_artifacts(run_id: str) -> dict:
    events = await _fetch_all_events(run_id)
    return {"data": build_artifacts(events, run_id)}


@router.get("/runs/{run_id}/commands")
async def get_run_commands(run_id: str) -> dict:
    events = await _fetch_all_events(run_id)
    return {"data": build_commands(events)}


@router.get("/runs/{run_id}/browser")
async def get_run_browser_frames(run_id: str) -> dict:
    """Return browser frames captured by the run (may be empty)."""
    from bff.services.action_reconstruction import build_browser_frames

    events = await _fetch_all_events(run_id)
    return {"data": build_browser_frames(events, run_id)}


@router.get("/runs/{run_id}/traces")
async def get_run_traces(run_id: str) -> dict:
    """Return spans for the given run (single trace per conversation)."""
    from bff.services.trace_reconstruction import (
        build_spans,  # local import (avoids cycle at module load)
    )

    events = await _fetch_all_events(run_id)
    spans = build_spans(events, run_id)
    return {"data": spans}


# ---------------------------------------------------------------------------
# Lifecycle helpers (Stage 5)
# ---------------------------------------------------------------------------


async def _call_lifecycle(
    run_id: str,
    subpath: str,
    json_body: dict | None = None,
) -> dict:
    """POST to `/api/conversations/{run_id}/{subpath}` on agent-server.

    Translates agent-server 404 → HTTP 404 and any other failure → 502.
    Returns agent-server's response payload (typically {"success": true}).
    """
    client = get_client()
    url = f"/api/conversations/{run_id}/{subpath}"
    try:
        resp = await client.post(url, json=json_body if json_body is not None else {})
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"agent-server unreachable: {exc}") from exc
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="run not found")
    if resp.status_code == 422:
        # Bad input (e.g. non-UUID run_id) — pass through as 422 rather than 502.
        raise HTTPException(status_code=422, detail=f"invalid run: {resp.text[:200]}")
    if resp.status_code == 409:
        # E.g. respond_to_confirmation when conversation isn’t waiting.
        raise HTTPException(status_code=409, detail=f"invalid state: {resp.text[:200]}")
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502, detail=f"agent-server error {resp.status_code}: {resp.text[:200]}"
        )
    try:
        return resp.json() or {}
    except Exception:
        return {}


class RejectRunRequest(BaseModel):
    reason: str | None = None


@router.post("/runs/{run_id}/pause")
async def pause_run(run_id: str) -> dict:
    result = await _call_lifecycle(run_id, "pause")
    return {"ok": True, "run_id": run_id, "status": "paused", "agent_server": result}


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str) -> dict:
    # Agent-server has no dedicated 'resume' — POST /run restarts the loop
    # from paused or idle.
    #
    # Race: /pause waits for the current LLM call to finish but returns
    # success:true as soon as execution_status transitions to 'paused'. The
    # underlying arun() coroutine may still be unwinding an in-flight LLM
    # request when the user hits Resume, causing /run to reply 409
    # 'conversation_already_running'. For long LLM turns this can take tens
    # of seconds.
    #
    # We poll agent-server's execution_status until the coroutine has finished
    # (status leaves 'running'), then POST /run. Bounded by 20s to keep the
    # request from blocking forever — if we hit the ceiling we surface 409 so
    # the user can hit Stop (which uses /interrupt) instead.
    client = get_client()
    deadline = asyncio.get_event_loop().time() + 20.0
    while True:
        try:
            result = await _call_lifecycle(run_id, "run")
            return {"ok": True, "run_id": run_id, "status": "running", "agent_server": result}
        except HTTPException as exc:
            if exc.status_code != 409:
                raise
            if asyncio.get_event_loop().time() >= deadline:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Cannot resume: previous LLM turn still finishing after 20s. "
                        "Use Stop (interrupt) to cancel it, then Resume."
                    ),
                )
            # Sleep, then check status; only retry /run when it leaves 'running'.
            await asyncio.sleep(0.5)
            try:
                info = await client.get(f"/api/conversations/{run_id}")
                if info.status_code < 400:
                    st = (info.json() or {}).get("execution_status")
                    if st in ("running",):
                        # Still finishing the prior turn; loop.
                        continue
            except Exception:
                pass
            # State suggests it should be resumable now; loop retries /run.


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str) -> dict:
    # Agent-server exposes hard cancel as /interrupt. If the conversation is
    # already paused (or idle/finished), /interrupt returns 400 because there
    # is nothing to cancel. Users pressing Stop on a paused run don't want to
    # see an error — the desired terminal state is 'paused' either way, so we
    # first ask agent-server for the current status and short-circuit.
    client = get_client()
    try:
        conv_resp = await client.get(f"/api/conversations/{run_id}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"agent-server unreachable: {exc}") from exc
    if conv_resp.status_code == 404:
        raise HTTPException(status_code=404, detail="run not found")
    exec_status = None
    if conv_resp.status_code < 400:
        exec_status = (conv_resp.json() or {}).get("execution_status")
    # Only 'running' or 'waiting_for_confirmation' can be interrupted.
    if exec_status in ("running", "waiting_for_confirmation"):
        result = await _call_lifecycle(run_id, "interrupt")
        return {"ok": True, "run_id": run_id, "status": "stopped", "agent_server": result}
    return {
        "ok": True,
        "run_id": run_id,
        "status": "stopped",
        "agent_server": {"success": True, "note": f"already terminal: {exec_status}"},
    }


@router.post("/runs/{run_id}/approve")
async def approve_run(run_id: str) -> dict:
    result = await _call_lifecycle(
        run_id,
        "events/respond_to_confirmation",
        json_body={"accept": True},
    )
    return {"ok": True, "run_id": run_id, "status": "running", "agent_server": result}


@router.post("/runs/{run_id}/reject")
async def reject_run(run_id: str, body: RejectRunRequest | None = None) -> dict:
    # Reject flow — verified against agent-server 1.40.0:
    #   respond_to_confirmation {accept: False} declines the pending tool call
    #   and returns the conversation to `idle` (not a terminal state). To match
    #   the user's intent ("reject this run"), we then attempt to hard-cancel
    #   via /interrupt. If the conversation is already idle/finished, /interrupt
    #   yields 400 which we silently swallow.
    payload: dict[str, Any] = {"accept": False}
    if body and body.reason:
        payload["reason"] = body.reason
    respond = await _call_lifecycle(
        run_id,
        "events/respond_to_confirmation",
        json_body=payload,
    )

    # Best-effort follow-up interrupt so the run reaches a terminal state.
    # Try /interrupt unconditionally with tolerance for 400 (idle/finished),
    # since polling status first introduces a race between respond and check.
    client = get_client()
    interrupt_note: str | None = None
    try:
        r = await client.post(f"/api/conversations/{run_id}/interrupt")
        if r.status_code < 400:
            interrupt_note = "interrupted"
        elif r.status_code == 400:
            interrupt_note = f"no interrupt needed: {r.text[:120]}"
        else:
            interrupt_note = f"interrupt HTTP {r.status_code}: {r.text[:120]}"
    except Exception as exc:
        log.warning("reject_run: post-reject interrupt failed: %s", exc)
        interrupt_note = f"interrupt error: {exc}"

    return {
        "ok": True,
        "run_id": run_id,
        "status": "rejected",
        "agent_server": {"respond": respond, "interrupt": interrupt_note},
    }


@router.post("/runs/{run_id}/fork")
async def fork_run(run_id: str) -> dict:
    """Fork a conversation via agent-server.

    Upstream: POST /api/conversations/{conversation_id}/fork
    Response shape (frontend contract): {ok, run_id, forked_id}.
    """
    client = get_client()
    try:
        resp = await client.post(f"/api/conversations/{run_id}/fork")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"agent-server unreachable: {exc}") from exc
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="run not found")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
    payload = resp.json() or {}
    # Upstream returns a ConversationInfo-shaped object; the fork's id is under
    # 'id' (matching the create-conversation contract).
    forked_id = payload.get("id") or payload.get("conversation_id") or payload.get("fork_id")
    if not forked_id:
        raise HTTPException(
            status_code=502,
            detail=f"agent-server fork response missing id: {str(payload)[:200]}",
        )
    return {"ok": True, "run_id": run_id, "forked_id": forked_id}

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

Stage 6.4b (ADR-025):
  DELETE /runs/{id}          → agent-server DELETE /api/conversations/{id}
                                + reap per-run worktree under WORKTREE_ROOT.

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

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from bff.openhands_client import get_client
from bff.services.action_reconstruction import (
    build_artifacts,
    build_commands,
    build_plan,
)
from bff.services import event_commit_ledger
from bff.services.event_normalize import normalize_events
from bff.services.event_relay import start_relay
from bff.services.file_diff_reconstruction import build_file_diff, build_summaries
from bff.services.hook_config import build_hook_config
from bff.services.model_router import (
    ModelUnavailableError,
    RoleRoute,
    route_by_role,
)
from bff.services.sidecar import seed_sidecar
from bff.services.restart import (
    RestartError,
    RestartResult,
    restart_from_here,
)
from bff.services.worktree import (
    WorktreeError,
    head_sha,
    provision_worktree,
    remove_worktree,
)

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
    # F.19.2b: optional explicit role. When set, wins over taskComplexity
    # mapping. Accepted values: "coder" | "planner".
    role: str | None = None
    contextLength: int | None = None
    # Stage 2.1.7 (amended plan): optional backend pin. When set, wins
    # over the AgentPreset's ``backendId`` (which itself is optional).
    # Forwarded to ``route_by_role(backend_id=...)``.
    backendId: str | None = None
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

# F.19.2b: taskComplexity → role map. Anything not listed defaults to "coder"
# (matches F.18 behavior: unknown complexity took the fast/coder path).
_TASK_COMPLEXITY_TO_ROLE: dict[str, str] = {
    "fast": "coder",
    "simple": "coder",
    "medium": "coder",
    "complex": "planner",
    "reasoning": "planner",
    "planning": "planner",
    "agentic": "planner",  # F.18 default; agentic multi-step work needs the planner.
}


def _build_confirmation_policy(require_approval: bool) -> tuple[dict[str, Any], str]:
    """Return the confirmation-policy body + a log label for a create-run call.

    Stage 3.2 default is ConfirmRisky(threshold=MEDIUM, confirm_unknown=True).
    ``require_approval=True`` on the per-run request escalates to AlwaysConfirm.

    Kept as a pure helper so it can be unit-tested without httpx mocking.
    The wire shape is the openhands-sdk discriminated union at
    openhands.sdk.security.confirmation_policy; verified against
    openhands-sdk==1.40.0 on Colossus.
    """
    if require_approval:
        return {"policy": {"kind": "AlwaysConfirm"}}, "AlwaysConfirm"
    return (
        {
            "policy": {
                "kind": "ConfirmRisky",
                "threshold": "MEDIUM",
                "confirm_unknown": True,
            }
        },
        "ConfirmRisky(MEDIUM, confirm_unknown=True)",
    )


def _resolve_role(body_role: str | None, task_complexity: str) -> str:
    """Explicit body.role wins; else map taskComplexity; else default coder."""
    if body_role:
        role = body_role.strip().lower()
        if role in ("coder", "planner"):
            return role
    return _TASK_COMPLEXITY_TO_ROLE.get(task_complexity.strip().lower(), "coder")


def _translate_model(route: RoleRoute) -> str:
    """Agent-server (LiteLLM) expects 'openai/<tag>' for the OpenAI-compat
    path regardless of whether the backend is vLLM or Ollama."""
    return f"openai/{route.model}"


def _resolve_workspace_id(
    conv: dict[str, Any],
    path_to_id: dict[str, str] | None,
) -> str:
    """Return the UUID for a conv's workspace, falling back to the path.

    Agent-server 1.40.0 populates ``conv.workspace.working_dir`` with the
    resolved filesystem path, not the workspace UUID. Callers pass a
    precomputed ``{path: uuid}`` map when available so we can echo the
    UUID that runs.py originally sent.
    """
    ws = conv.get("workspace") or {}
    working_dir = ws.get("working_dir") or "local"
    if path_to_id:
        wid = path_to_id.get(working_dir)
        if wid:
            return wid
    return working_dir


async def _workspace_path_to_id_map() -> dict[str, str]:
    """Build {resolved_path: workspace_id} from agent-server list.

    Used to reverse-map ``conv.workspace.working_dir`` (a filesystem
    path) back to the workspace UUID that runs.py originally sent.
    Safe on failure: returns {} so callers fall back to the raw path.
    """
    try:
        from bff.routers.workspaces import _list_agent_workspaces
        items = await _list_agent_workspaces()
    except Exception as exc:
        log.debug("workspace path->id map: %s", exc)
        return {}
    m: dict[str, str] = {}
    for w in items:
        wid = w.get("id")
        wpath = w.get("path")
        if wid and wpath:
            m[wpath] = wid
    return m


def _conv_to_run_summary(
    conv: dict[str, Any],
    workspace_path_to_id: dict[str, str] | None = None,
) -> dict[str, Any]:
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
        "workspaceId": _resolve_workspace_id(conv, workspace_path_to_id),
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
    path_to_id = await _workspace_path_to_id_map()
    runs = [_conv_to_run_summary(c, path_to_id) for c in convs]
    return {
        "data": runs,
        "pageInfo": {"total": len(runs), "page": page, "pageSize": pageSize},
    }


# ---------------------------------------------------------------------------
# POST /runs  — start conversation + kick off + open event relay
# ---------------------------------------------------------------------------


@router.post("/runs")
async def create_run(request: Request, body: CreateRunRequest) -> dict:
    task_complexity = body.taskComplexity or "agentic"
    context_length = (
        body.contextLength if body.contextLength is not None else len(body.taskPrompt or "")
    )
    role = _resolve_role(body.role, task_complexity)

    # Stage 2.1.7 (amended plan): resolve backend pin from request or
    # preset. Request wins over preset. When both are None the router
    # follows the pre-Stage-2 default (behavior byte-for-byte preserved).
    backend_id = body.backendId
    if backend_id is None:
        from bff.routers.agent_presets import _PRESETS  # local import: avoid cycle
        preset = _PRESETS.get(body.agentPresetId)
        if preset is not None and preset.backendId is not None:
            backend_id = preset.backendId
            # Preset can also pin the role; only apply when the request
            # didn't send an explicit role AND taskComplexity mapping
            # didn't already yield a stronger signal.
            if body.role is None and preset.role is not None:
                role = preset.role

    # 1) Route by role (F.19.2b + Stage 2.1.7 optional backend pin).
    try:
        route: RoleRoute = await route_by_role(
            role,
            context_length=context_length,
            backend_id=backend_id,
        )
    except (ModelUnavailableError, ValueError) as exc:
        return {
            "data": {
                "id": "",
                "title": body.title,
                "status": "blocked",
                "agentPresetId": body.agentPresetId,
                "agentPresetName": body.agentPresetId,
                "workspaceId": body.workspaceId,
                "workspaceType": "local",
                "selectedModel": None,
                "routing": {
                    "taskComplexity": task_complexity,
                    "role": role,
                    "contextLength": context_length,
                    "backendId": backend_id,
                    "selected": None,
                    "error": str(exc),
                },
            }
        }

    litellm_model = _translate_model(route)

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

    # 2.5) Stage 6.4b (ADR-025): provision an isolated per-run git worktree
    #      OFF the workspace path so concurrent runs against the same
    #      workspace get independent filesystem views.
    #
    #      A1 (fallback):   non-git workspaces log-and-pass-through with
    #                       the raw path.  Concurrent runs against them
    #                       still collide, but nothing NEW breaks.
    #      C1 (leak guard): on any create-path failure below, best-effort
    #                       remove_worktree(worktree_run_id, missing_ok=True).
    #
    #      Why we don't rename to <cid> after agent-server assigns it:
    #      agent-server has already been given the working_dir; renaming
    #      the filesystem path (or using `git worktree move`) invalidates
    #      the working_dir agent-server holds in memory.  We keep the
    #      pending name and recover it at delete time by reading
    #      ``conv.workspace.working_dir`` — the last path segment is
    #      the run_id we passed to provision_worktree.
    import uuid as _uuid  # local import to avoid polluting module top
    worktree_run_id = f"run-{_uuid.uuid4().hex[:12]}"
    worktree_provisioned: Path | None = None
    original_working_dir = working_dir
    try:
        info = provision_worktree(worktree_run_id, Path(working_dir))
        worktree_provisioned = info.path
        working_dir = str(info.path)
        log.info(
            "create_run: provisioned worktree %s off %s",
            worktree_run_id, original_working_dir,
        )
    except WorktreeError as exc:
        # Not a git repo, missing, or other structural failure.  A1:
        # log and continue with the raw path.  Cross-run isolation is
        # forfeited for this workspace until it's initialised.
        log.info(
            "create_run: skipping worktree for %s (%s); using raw path",
            body.workspaceId, exc,
        )

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
                # F.19.2b: base_url comes from the router, not hardcoded Ollama.
                # Previous code sent vLLM-routed traffic to the Ollama URL,
                # which silently 404'd. Now vLLM traffic goes to the role's
                # vLLM base_url and Ollama fallback traffic goes to Ollama.
                "base_url": route.base_url,
                # api_key is a required LiteLLM param but ignored by our
                # OpenAI-compat servers (vLLM ignores; Ollama ignores).
                "api_key": "ollama" if route.backend == "ollama" else "vllm",
                # F.19.2b: role-specific completion budget from ADR-009 §3b.
                # coder=2048, planner=8192. LiteLLM keys this as max_tokens.
                "max_tokens": route.max_tokens,
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
        # Slice F.8 runtime wiring: register verify + trajectory STOP hooks
        # on every conversation. Verify runs first (writes verify-state.json);
        # trajectory second (reads it + the sidecar). Both are subprocess
        # hooks; failures are non-blocking by SDK contract.
        "hook_config": build_hook_config(),
    }

    try:
        create_resp = await client.post("/api/conversations", json=create_body)
        create_resp.raise_for_status()
    except Exception as exc:
        # C1: agent-server create failed after we may have provisioned a
        # worktree.  Best-effort cleanup so we don't leak filesystem
        # state on every failed run creation.
        if worktree_provisioned is not None:
            try:
                remove_worktree(worktree_run_id, missing_ok=True)
                log.info(
                    "create_run: rolled back worktree %s after agent-server failure",
                    worktree_run_id,
                )
            except Exception as cleanup_exc:  # pragma: no cover - defensive
                log.warning(
                    "create_run: worktree cleanup for %s failed: %s",
                    worktree_run_id, cleanup_exc,
                )
        log.exception("create_run: /api/conversations failed")
        raise HTTPException(status_code=502, detail=f"agent-server create failed: {exc}") from exc

    conv = create_resp.json()
    cid = conv.get("id")
    if not cid:
        # C1: worktree leak protection on the missing-cid branch too.
        if worktree_provisioned is not None:
            try:
                remove_worktree(worktree_run_id, missing_ok=True)
            except Exception as cleanup_exc:  # pragma: no cover - defensive
                log.warning(
                    "create_run: worktree cleanup after missing cid failed: %s",
                    cleanup_exc,
                )
        raise HTTPException(status_code=502, detail="agent-server returned no conversation id")

    # Note on worktree naming: the worktree stays under its pending name
    # for the run's entire lifetime.  We do NOT rename it to <cid>
    # because agent-server has already been told its working_dir is the
    # pending path — a rename would break agent-server's file access.
    # `git worktree move` is functionally similar but the same constraint
    # applies.  On delete we recover the pending name by reading
    # ``conv.workspace.working_dir`` from agent-server; the last path
    # segment IS the run_id we passed to `provision_worktree`.

    # 3.5) Slice F.12 — seed the trajectory sidecar so the STOP hook has
    #     a real task_description to attribute the run to. Best-effort:
    #     any I/O failure is logged and swallowed — a missing sidecar
    #     degrades gracefully to empty fields, not a broken run.
    #     Session id in the sidecar file = agent-server conversation id
    #     (matches OPENHANDS_SESSION_ID as set by the SDK for LocalConversation).
    #     The outer try/except is defense-in-depth: seed_sidecar itself
    #     already swallows I/O errors, but a future refactor must not be
    #     able to sink run creation. See test_create_run_survives_sidecar_seeder_failure.
    try:
        seed_sidecar(
            workspace=working_dir,
            session_id=cid,
            task_description=body.taskPrompt or "",
        )
    except Exception as exc:
        log.warning("create_run: seed_sidecar raised (swallowed): %s", exc)

    # 3aa) Stage 3.1 — attach PatternSecurityAnalyzer so ActionEvents get
    #      a real `security_risk` value (LOW/MEDIUM/HIGH/UNKNOWN).
    #      Contract from openhands.sdk.conversation.impl.remote_conversation
    #      (set_security_analyzer): POST { security_analyzer: <dump> } to
    #      /api/conversations/{cid}/security_analyzer.
    #      PatternSecurityAnalyzer is deterministic (regex-based) and has
    #      no LLM cost. Best-effort: analyzer attach failure must not
    #      break run creation. Runtime import so BFF unit tests without the
    #      SDK installed still import this module.
    try:
        from openhands.sdk.security import PatternSecurityAnalyzer
        analyzer_body = {
            "security_analyzer": PatternSecurityAnalyzer().model_dump(mode="json"),
        }
        sa_resp = await client.post(
            f"/api/conversations/{cid}/security_analyzer",
            json=analyzer_body,
        )
        if sa_resp.status_code >= 400:
            log.warning(
                "create_run: attaching PatternSecurityAnalyzer to %s failed: %s %s",
                cid,
                sa_resp.status_code,
                sa_resp.text[:200],
            )
    except Exception as exc:
        log.warning("create_run: security_analyzer attach failed: %s", exc)

    # 3a) Stage 3.2 — apply confirmation policy BEFORE kicking the loop off.
    #     Default: ConfirmRisky(threshold=MEDIUM, confirm_unknown=True).
    #       - fail-closed on any ActionEvent the analyzer flags MEDIUM or HIGH
    #       - fail-closed on UNKNOWN so unannotated tool paths still hit HITL
    #     Opt-in strict: requireApproval=true (per-run) escalates to
    #     AlwaysConfirm which asks on every tool call (matches Stage 1E behavior).
    #     Discriminated union at openhands.sdk.security.confirmation_policy;
    #     wire shape verified on Colossus at openhands-sdk==1.40.0.
    _policy_body, _policy_label = _build_confirmation_policy(bool(body.requireApproval))
    try:
        pol_resp = await client.post(
            f"/api/conversations/{cid}/confirmation_policy",
            json=_policy_body,
        )
        if pol_resp.status_code >= 400:
            log.warning(
                "create_run: setting %s on %s failed: %s %s",
                _policy_label,
                cid,
                pol_resp.status_code,
                pol_resp.text[:200],
            )
    except Exception as exc:
        log.warning("create_run: confirmation_policy call failed: %s", exc)

    # 3b) Stage 6.4c (ADR-026 §Storage) — capture HEAD sha for the
    #     initial user MessageEvent so a future "Restart from here" can
    #     branch from the same tree state.  Best-effort P1 pattern:
    #       - GET /events?limit=20&sort_order=TIMESTAMP  (asc)
    #       - scan for the FIRST kind=MessageEvent source=user event.
    #         On agent-server 1.40 the initial page interleaves
    #         ConversationStateUpdateEvent + SystemPromptEvent BEFORE the
    #         user's MessageEvent — verified live on Colossus 2026-08-06.
    #         Step 1d shipped with limit=1 which never hit the user event
    #         in practice; step 1e fixes that.
    #     Any failure is logged and swallowed — downgrades gracefully to
    #     "no restart button on this event" per ADR-026.  The read path
    #     hides the button when no ledger row exists.
    try:
        ledger_ready = getattr(request.app.state, "event_commit_db", None) is not None
        if ledger_ready and worktree_provisioned is not None:
            events_resp = await client.get(
                f"/api/conversations/{cid}/events/search",
                params={"limit": 20, "sort_order": "TIMESTAMP"},
            )
            if events_resp.status_code < 400:
                epl = events_resp.json() or {}
                items = (
                    epl if isinstance(epl, list)
                    else (epl.get("items") or epl.get("data") or epl.get("events") or [])
                )
                anchor_id: str | None = None
                for ev in items:
                    if not isinstance(ev, dict):
                        continue
                    if (
                        ev.get("kind") == "MessageEvent"
                        and ev.get("source") == "user"
                    ):
                        anchor_id = ev.get("id") or ev.get("event_id")
                        if anchor_id:
                            break
                if anchor_id:
                    sha = head_sha(working_dir)
                    if sha:
                        await event_commit_ledger.record_sha(
                            request.app,
                            run_id=cid,
                            event_id=anchor_id,
                            commit_sha=sha,
                        )
                        log.info(
                            "create_run: captured sha for initial user event %s on run %s",
                            anchor_id, cid,
                        )
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("create_run: sha capture failed: %s", exc)

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
    # Caller sent a workspace UUID; agent-server echoes the resolved path
    # instead. Preserve the caller's UUID in the response.
    if body.workspaceId:
        summary["workspaceId"] = body.workspaceId
    # Stage 2.1.8 (amended plan): surface agentPresetId on the run
    # record so ``GET /api/runs/{id}`` no longer returns null for the
    # preset FK. See KNOWN_ISSUES 2026-08-05 "agentPresetId null".
    summary["agentPresetId"] = body.agentPresetId
    summary["routing"] = {
        "taskComplexity": task_complexity,
        "role": role,
        "contextLength": context_length,
        "backendId": backend_id,
        "selected": route.tagged,
        "backend": route.backend,
        "model": route.model,
        "baseUrl": route.base_url,
        "maxTokens": route.max_tokens,
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
    path_to_id = await _workspace_path_to_id_map()
    return {"data": _conv_to_run_summary(resp.json(), path_to_id)}


# ---------------------------------------------------------------------------
# DELETE /runs/{run_id}  — Stage 6.4b step 2 (B2): proxy to agent-server
# delete + reap the per-run worktree.
# ---------------------------------------------------------------------------


@router.delete("/runs/{run_id}", status_code=204, response_class=Response)
async def delete_run(request: Request, run_id: str):
    """Delete a run and reap its worktree.

    Order:
      1. Fetch conversation to recover working_dir (worktree path).
      2. Ask agent-server to delete the conversation.
      3. Remove the worktree (missing_ok=True; non-git or already-removed
         is fine).  Runs against non-git workspaces never provisioned a
         worktree in the first place, so this is a no-op there.

    Failures on step 3 log a warning but don't fail the request — the
    conversation is already gone; a stray worktree is discoverable via
    list_worktrees() and reapable by a future GC slice.
    """
    client = get_client()

    # 1) Fetch the conversation.  If agent-server is down we can't
    #    recover the worktree name reliably, so fail loudly.
    try:
        get_resp = await client.get(f"/api/conversations/{run_id}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"agent-server unreachable: {exc}") from exc
    if get_resp.status_code == 404:
        raise HTTPException(status_code=404, detail="run not found")
    get_resp.raise_for_status()

    conv = get_resp.json() or {}
    working_dir = (conv.get("workspace") or {}).get("working_dir") or ""
    # Only run_ids we minted ("run-<hex12>") should be reaped; treat any
    # other tail segment as a non-managed path and skip removal.
    tail = Path(working_dir).name if working_dir else ""
    worktree_run_id = tail if tail.startswith("run-") else None

    # 2) Delete on agent-server.  409/404 both mean "already gone" and
    #    we treat as success so we can still reap the worktree.
    try:
        del_resp = await client.delete(f"/api/conversations/{run_id}")
        if del_resp.status_code not in (200, 202, 204, 404, 409):
            del_resp.raise_for_status()
    except HTTPException:
        raise
    except Exception as exc:
        log.warning("delete_run: agent-server delete failed for %s: %s", run_id, exc)

    # 3) Reap worktree.  missing_ok=True: idempotent by design.
    if worktree_run_id:
        try:
            remove_worktree(worktree_run_id, missing_ok=True)
            log.info("delete_run: reaped worktree %s for run %s", worktree_run_id, run_id)
        except Exception as exc:
            log.warning(
                "delete_run: failed to reap worktree %s for run %s: %s",
                worktree_run_id, run_id, exc,
            )

    # 4) Stage 6.4c (ADR-026 §Storage) — cascade-delete every event_commit_shas
    #    row keyed to this run.  Idempotent; missing table / db-not-initialised
    #    both downgrade to a warning without failing the delete.
    if getattr(request.app.state, "event_commit_db", None) is not None:
        try:
            rows = await event_commit_ledger.delete_run(request.app, run_id)
            log.info(
                "delete_run: purged %d event_commit_shas rows for run %s",
                rows, run_id,
            )
        except Exception as exc:
            log.warning(
                "delete_run: event_commit_ledger.delete_run(%s) failed: %s",
                run_id, exc,
            )

    return Response(status_code=204)


# ---------------------------------------------------------------------------
# GET /runs/{run_id}/events  — persisted events (paged)
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}/events")
async def get_run_events(
    request: Request,
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
        items = payload
        next_page = None
    else:
        items = payload.get("items") or payload.get("data") or payload.get("events") or []
        next_page = payload.get("next_page_id") or payload.get("nextPageId")

    # Stage 6.4c (ADR-026 §Storage) — batch-hydrate commit shas for user
    # MessageEvents in this page.  Best-effort: ledger unavailable / empty
    # lookup downgrades to the pre-ADR-026 shape (no commit_sha_at_time_of_event
    # key), which hides the "Restart from here" button on those events.
    sha_lookup = None
    ledger_ready = getattr(request.app.state, "event_commit_db", None) is not None
    if ledger_ready and items:
        event_ids = [
            (it.get("id") or it.get("event_id"))
            for it in items
            if isinstance(it, dict)
        ]
        event_ids = [eid for eid in event_ids if eid]
        if event_ids:
            try:
                sha_map = await event_commit_ledger.bulk_get_shas(
                    request.app, event_ids
                )
                sha_lookup = sha_map.get
            except Exception as exc:  # pragma: no cover - defensive
                log.warning(
                    "get_run_events: bulk_get_shas(%s) failed: %s", run_id, exc
                )

    return {
        "data": normalize_events(items, sha_lookup=sha_lookup),
        "nextPageId": next_page,
    }


@router.get("/runs/{run_id}/plan")
async def get_run_plan(run_id: str) -> dict:
    events = await _fetch_all_events(run_id)
    return {"data": build_plan(events, run_id)}


@router.get("/runs/{run_id}/metrics")
async def get_run_metrics(run_id: str) -> dict:
    """Per-run KPIs (Metrics tab). Aggregates from the event stream so no
    additional agent-server endpoints are needed."""
    from bff.services.run_metrics import build_run_metrics

    events = await _fetch_all_events(run_id)
    return {"data": build_run_metrics(events, run_id)}


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


class SendMessageRequest(BaseModel):
    """Payload for POST /runs/{run_id}/message.

    The agent-server route ``POST /api/conversations/{cid}/events`` takes
    ``{role, content, run}``. We fix ``role='user'`` (only user messages
    make sense to inject mid-run from the operator UI) and wrap the plain
    text string as a single ``TextContent`` entry. ``run=False`` because
    Send-While-Running assumes the loop is already active — the message
    is appended to the event stream and the currently-running LLM turn
    (or the next one) will pick it up.
    """

    message: str = Field(min_length=1, max_length=32_000)


@router.post("/runs/{run_id}/message")
async def send_run_message(
    request: Request, run_id: str, body: SendMessageRequest
) -> dict:
    """Send a user message into a running (or paused) conversation.

    Mirrors the exact contract of agent-server 1.40.0's
    ``POST /api/conversations/{cid}/events`` with a fixed
    ``role='user'`` and a single ``TextContent`` payload.

    Stage 6.4c (ADR-026 §Storage): after the POST succeeds we do a
    best-effort follow-up GET with sort_order=CREATED_AT_DESC limit=1
    to discover the id agent-server assigned to the fresh event and
    stamp its HEAD sha in ``event_commit_ledger``.  Any capture failure
    logs and returns — the POST succeeded, the user’s message is
    persisted, and the "Restart from here" button simply won’t appear
    for that event.
    """
    result = await _call_lifecycle(
        run_id,
        "events",
        json_body={
            "role": "user",
            "content": [{"type": "text", "text": body.message}],
            "run": False,
        },
    )

    # Best-effort sha capture on the just-created user MessageEvent.
    try:
        ledger_ready = getattr(request.app.state, "event_commit_db", None) is not None
        if ledger_ready:
            client = get_client()
            conv_resp = await client.get(f"/api/conversations/{run_id}")
            working_dir = ""
            if conv_resp.status_code < 400:
                working_dir = (
                    (conv_resp.json() or {}).get("workspace") or {}
                ).get("working_dir") or ""
            if working_dir:
                # sort_order=CREATED_AT_DESC returns newest first.  Step 1d
                # trusted latest[0] to be the user MessageEvent we just
                # POSTed, but agent-server 1.40 may emit a follow-up
                # ConversationStateUpdateEvent between our POST and this
                # GET — same trap as create_run §3b.  Step 1e scans the
                # top of the DESC page for the first user MessageEvent
                # instead of blindly taking index 0.
                events_resp = await client.get(
                    f"/api/conversations/{run_id}/events/search",
                    params={"limit": 20, "sort_order": "CREATED_AT_DESC"},
                )
                if events_resp.status_code < 400:
                    epl = events_resp.json() or {}
                    latest = (
                        epl if isinstance(epl, list)
                        else (
                            epl.get("items")
                            or epl.get("data")
                            or epl.get("events")
                            or []
                        )
                    )
                    anchor_id: str | None = None
                    for ev in latest:
                        if not isinstance(ev, dict):
                            continue
                        if (
                            ev.get("kind") == "MessageEvent"
                            and ev.get("source") == "user"
                        ):
                            anchor_id = ev.get("id") or ev.get("event_id")
                            if anchor_id:
                                break
                    if anchor_id:
                        sha = head_sha(working_dir)
                        if sha:
                            await event_commit_ledger.record_sha(
                                request.app,
                                run_id=run_id,
                                event_id=anchor_id,
                                commit_sha=sha,
                            )
                            log.info(
                                "send_run_message: captured sha for %s on run %s",
                                anchor_id, run_id,
                            )
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("send_run_message: sha capture failed: %s", exc)

    return {"ok": True, "run_id": run_id, "agent_server": result}


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


class ForkRunRequest(BaseModel):
    """Optional body for POST /runs/{run_id}/fork.

    ``from_event_id`` scopes the fork to the branch up to and including that
    event — the SDK's native "revert to here" primitive.  Omit to full-fork.

    The upstream agent-server contract (openhands-agent-server 1.40.0,
    ``ForkConversationRequest``) requires the exact key ``from_event_id``.
    Any other key silently full-forks (verified 2026-08-06 05:53 EDT live
    probe — HTTP 201 with ``forked_from_event_id: null`` for ``at_event_id``,
    ``from_event``, ``event_id``, ``leaf_event_id``).  Do not rename.
    """

    from_event_id: str | None = None


@router.post("/runs/{run_id}/fork")
async def fork_run(run_id: str, body: ForkRunRequest | None = None) -> dict:
    """Fork a conversation via agent-server.

    Upstream: POST /api/conversations/{conversation_id}/fork
    Optional body: {from_event_id?} — forwarded verbatim (see ForkRunRequest).
    Response shape (frontend contract): {ok, run_id, forked_id, from_event_id}.
    """
    from_event_id = body.from_event_id if body is not None else None
    upstream_payload: dict[str, Any] = {}
    if from_event_id is not None:
        # Wire key must be exactly ``from_event_id`` — see ForkRunRequest
        # docstring for the silent-full-fork trap.
        upstream_payload["from_event_id"] = from_event_id

    client = get_client()
    try:
        resp = await client.post(
            f"/api/conversations/{run_id}/fork", json=upstream_payload
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"agent-server unreachable: {exc}") from exc
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="run not found")
    if resp.status_code == 400 and from_event_id and "from_event_id" in resp.text:
        # Upstream rejects unknown event ids explicitly — surface as 400
        # so the client can retell the user "that event doesn't exist".
        raise HTTPException(
            status_code=400,
            detail=f"unknown from_event_id: {from_event_id}",
        )
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
    return {
        "ok": True,
        "run_id": run_id,
        "forked_id": forked_id,
        "from_event_id": from_event_id,
    }


class RestartRunRequest(BaseModel):
    """Body for POST /runs/{run_id}/restart (ADR-026, Stage 6.4c).

    ``from_event_id`` must point at a user MessageEvent on the source
    run that carries a captured commit sha in the event-commit ledger.
    Restart-from-here creates a NEW run whose worktree lands at that
    sha and whose first user message is the anchor's text.
    """

    from_event_id: str


# Discriminator: RestartError.code → HTTP status
_RESTART_CODE_TO_STATUS: dict[str, int] = {
    "source_not_found": 404,
    "anchor_not_found": 404,
    "no_sha_anchor": 409,
    "not_user_message": 409,
    "source_no_working_dir": 409,
    "worktree_failed": 502,
    "create_failed": 502,
    "seed_failed": 502,
    "upstream_error": 502,
}


@router.post("/runs/{run_id}/restart")
async def restart_run(
    request: Request,
    run_id: str,
    body: RestartRunRequest,
) -> dict:
    """Restart-from-here on a user-message event (ADR-026).

    Delegates to ``bff.services.restart.restart_from_here`` for the
    ordered composition (source lookup → sha resolve → worktree
    provision → agent-server create → seed → best-effort ledger stamp).
    Maps ``RestartError.code`` to HTTP status via ``_RESTART_CODE_TO_STATUS``.

    Response shape (frontend contract):
        {ok, restarted_run_id, source_run_id, from_event_id,
         reset_to_sha, worktree_path}
    """
    try:
        result: RestartResult = await restart_from_here(
            request.app,
            source_run_id=run_id,
            anchor_event_id=body.from_event_id,
        )
    except RestartError as exc:
        status = _RESTART_CODE_TO_STATUS.get(exc.code, 502)
        raise HTTPException(status_code=status, detail=exc.detail) from exc

    return {
        "ok": True,
        "restarted_run_id": result.restarted_run_id,
        "source_run_id": result.source_run_id,
        "from_event_id": result.from_event_id,
        "reset_to_sha": result.reset_to_sha,
        "worktree_path": result.worktree_path,
    }

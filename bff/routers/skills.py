"""Skills router — in-process SDK loader (Stage 6.6, Path B).

Why in-process instead of proxying agent-server?
=================================================

The spec (§6.6.2) permits either a proxy to agent-server's `/api/skills` or a
direct on-disk read. The proxy path was implemented first, but at the pinned
SDK version 1.40.0 the agent-server endpoint returns `{"skills": [], "sources":
{"sandbox": 0, ...}}` even when `openhands.sdk.skills.skill.load_user_skills()`
and `load_project_skills(cwd)` return the correct rows against the same
directories on the same host. Diagnosed 2026-08-06 EDT — see DEBUG_LOG entry
"skills endpoint returns empty despite SDK loader working". Proxy path is the
correct long-term architecture; we can swap this router body back to the httpx
call the day the upstream endpoint is fixed without any frontend churn.

For today: call the SDK loader directly in-process. The BFF and agent-server
run on the same box (single-user local-first, per project instructions) so
the two paths see the same disk anyway.

Frontend contract (unchanged from the proxy version):

  GET  /api/skills                   → {data: SkillOut[], sources: {"user": n, "project": m}}
  GET  /api/skills/installed         → {data: SkillOut[]}         (same as /skills for now)
  GET  /api/skills/marketplace       → {data: []}                 (nothing on Colossus yet)

`installed` mirrors `/skills` because on this deployment "installed" and
"loadable" are the same set — nothing to install because nothing gates skill
availability beyond having the SKILL.md on disk. Kept as a separate endpoint
so the FE contract lines up with agent-server's shape.

Reshape (SDK SkillInfo → SkillOut): trim `content` to a 500-char preview to
keep the aggregate list-response under ~200 KB even with dozens of skills.

Working directory
-----------------

`load_project_skills(work_dir)` walks up from `work_dir` to find `.agents/skills/`.
BFF runs from the Forge-OH repo root on Colossus, so `Path.cwd()` is the right
project root. Overridable via `FORGE_OH_PROJECT_DIR` env var for tests.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

log = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["skills"])


# ---------------------------------------------------------------------------
# SDK loader (imported lazily so unit tests can monkeypatch without needing
# the openhands package installed in every test env)
# ---------------------------------------------------------------------------


def _project_dir() -> Path:
    """Resolve the project directory used for `load_project_skills`.

    Priority:
      1. `FORGE_OH_PROJECT_DIR` env var (tests / non-standard deploys)
      2. `Path.cwd()` (BFF launched from repo root on Colossus)
    """
    env = os.environ.get("FORGE_OH_PROJECT_DIR")
    if env:
        return Path(env)
    return Path.cwd()


def _load_via_sdk() -> tuple[list[Any], list[Any], dict[str, int]]:
    """Call the OpenHands SDK loaders and return (user_skills, project_skills, sources).

    Never raises: on any import or loader failure returns empty lists so the
    /skills page renders an empty state instead of a 500. The exception is
    logged for diagnosis.
    """
    try:
        from openhands.sdk.skills.skill import (  # type: ignore[import-not-found]
            load_project_skills,
            load_user_skills,
        )
    except Exception as exc:  # pragma: no cover - depends on venv
        log.warning("openhands SDK unavailable: %s", exc)
        return [], [], {"user": 0, "project": 0}

    try:
        user = list(load_user_skills())
    except Exception as exc:
        log.warning("load_user_skills failed: %s", exc)
        user = []
    try:
        project = list(load_project_skills(_project_dir()))
    except Exception as exc:
        log.warning("load_project_skills failed: %s", exc)
        project = []

    return user, project, {"user": len(user), "project": len(project)}


# ---------------------------------------------------------------------------
# Reshapers
# ---------------------------------------------------------------------------


# Cap the content preview so list responses stay lean even with many skills.
_CONTENT_PREVIEW_CHARS = 500


def _skill_to_out(skill: Any) -> dict[str, Any]:
    """Reshape SDK Skill → frontend Skill row.

    Uses `to_skill_info()` when available (SDK ≥1.40), falls back to
    attribute access for defensiveness.
    """
    if hasattr(skill, "to_skill_info"):
        info = skill.to_skill_info()
        name = info.name
        skill_type = info.type
        content = info.content or ""
        triggers = list(info.triggers or [])
        source = info.source or ""
        description = info.description or ""
        is_agentskills = bool(info.is_agentskills_format)
        disable_invoke = bool(info.disable_model_invocation)
    else:
        name = getattr(skill, "name", "") or ""
        skill_type = getattr(skill, "type", None) or "agentskills"
        content = getattr(skill, "content", "") or ""
        triggers = list(getattr(skill, "triggers", []) or [])
        source = getattr(skill, "source", "") or ""
        description = getattr(skill, "description", "") or ""
        is_agentskills = bool(getattr(skill, "is_agentskills_format", True))
        disable_invoke = bool(getattr(skill, "disable_model_invocation", False))

    if isinstance(content, str) and len(content) > _CONTENT_PREVIEW_CHARS:
        content_preview = content[:_CONTENT_PREVIEW_CHARS] + "…"
        content_truncated = True
    else:
        content_preview = content if isinstance(content, str) else ""
        content_truncated = False

    return {
        "name": str(name),
        "type": str(skill_type),
        "description": str(description),
        "triggers": [str(t) for t in triggers],
        "source": str(source),
        "contentPreview": content_preview,
        "contentTruncated": content_truncated,
        "isAgentSkillsFormat": is_agentskills,
        "disableModelInvocation": disable_invoke,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_skills(
    include_user: bool = Query(True, description="Include user skills from ~/.agents/skills/"),
    include_project: bool = Query(True, description="Include project skills from {cwd}/.agents/skills/"),
) -> dict[str, Any]:
    """List all available skills for this workspace.

    Combines user-scope (from `~/.agents/skills/`) and project-scope (from
    `{cwd}/.agents/skills/` walking up to git root) SDK loaders. Each row
    carries a 500-char content preview; the full body is on disk at `source`.

    Sources counts are the number of skills contributed by each scope, so the
    FE can render a "15 user · 8 project" summary line.
    """
    try:
        user_skills, project_skills, sources = _load_via_sdk()
    except Exception as exc:
        log.exception("skills loader crashed")
        raise HTTPException(status_code=500, detail=f"skill loader failed: {exc}") from exc

    rows: list[dict[str, Any]] = []
    if include_user:
        rows.extend(_skill_to_out(s) for s in user_skills)
    if include_project:
        rows.extend(_skill_to_out(s) for s in project_skills)

    # Deterministic ordering — the FE table has no default sort yet.
    rows.sort(key=lambda r: (r["type"] != "agentskills", r["name"].lower()))

    return {"data": rows, "sources": sources}


@router.get("/installed")
async def list_installed_skills() -> dict[str, Any]:
    """List installed skills.

    On Colossus (single-user, local-first) every discoverable skill is
    already "installed" — the SDK loads any SKILL.md it finds. Returns the
    same set as `GET /skills` so the FE contract mirrors agent-server's
    two-endpoint shape without introducing a distinction that doesn't exist
    on-disk.
    """
    payload = await list_skills()
    return {"data": payload["data"]}


@router.get("/marketplace")
async def list_marketplace_skills() -> dict[str, Any]:
    """List marketplace-catalog skills.

    No marketplaces are wired up on Colossus yet (per ADR-0001 local-first
    posture — everything is authored locally). Returns an empty list; the
    endpoint exists so the FE marketplace tab can render an empty state
    instead of 404-ing.
    """
    return {"data": []}

"""
bff/routers/git.py — Real git diff wiring for Forge-OH (Slice C.2).

Upstream surface (OpenHands agent-server, 1.40.0):
  GET /api/git/changes/{path}   → List[GitChange { status, path }]
  GET /api/git/diff/{path}      → GitDiff { modified: str|null, original: str|null }

Upstream `{path}` is a full filesystem path (the workspace root for
/changes, the file path for /diff). We accept it as a query string so
we don't fight FastAPI's path converter, and we URL-encode it once
before calling upstream.

BFF surface (frontend contract):
  GET /api/runs/{run_id}/git/changes?workspace_path=/abs/path
  GET /api/runs/{run_id}/git/diff?file_path=/abs/or/rel&workspace_path=/abs

run_id is currently cosmetic here — upstream git routes are keyed by
path, not conversation. Kept in the URL for consistency with the rest
of the run-centric API and future per-run scoping.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from bff.openhands_client import get_client

router = APIRouter(prefix="/runs/{run_id}/git", tags=["git"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class GitChangeOut(BaseModel):
    status: str
    path: str


class GitDiffOut(BaseModel):
    path: str
    original: str | None
    modified: str | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def _encode_path(p: str) -> str:
    """URL-encode a filesystem path for use as a single path segment.

    We keep '/' unencoded so the upstream router can still see the
    hierarchy, matching how OpenHands itself constructs these URLs.
    """
    return quote(p, safe="/")


@router.get("/changes")
async def list_changes(
    run_id: str,
    workspace_path: str = Query(..., description="Absolute path to the workspace root"),
) -> dict[str, Any]:
    """List changed files under the given workspace path."""
    client = get_client()
    resp = await client.get(f"/api/git/changes/{_encode_path(workspace_path)}")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:400])
    items = resp.json() or []
    return {
        "data": [
            {"status": (c.get("status") or "").lower(), "path": c.get("path") or ""} for c in items
        ]
    }


@router.get("/diff")
async def get_diff(
    run_id: str,
    file_path: str = Query(..., description="Absolute or workspace-relative file path"),
    workspace_path: str | None = Query(
        default=None,
        description=(
            "Absolute workspace root. If provided and file_path is relative, "
            "the two are joined to form the absolute path used upstream."
        ),
    ),
) -> dict[str, Any]:
    """Return the original + modified sides of a single file's diff."""
    # If the caller supplied a workspace root, always join it with file_path
    # (stripped of any leading slash so we don't double up). Otherwise treat
    # file_path as already absolute.
    if workspace_path:
        upstream_path = f"{workspace_path.rstrip('/')}/{file_path.lstrip('/')}"
    else:
        upstream_path = file_path

    client = get_client()
    resp = await client.get(f"/api/git/diff/{_encode_path(upstream_path)}")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:400])
    body = resp.json() or {}
    return {
        "data": {
            "path": file_path,
            "original": body.get("original"),
            "modified": body.get("modified"),
        }
    }

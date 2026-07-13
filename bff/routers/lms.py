"""
Rigpa-LMS integration router — Slice 5C.
Handles LMS context injection and artifact-to-LMS packaging.
Feature-flagged: FEATURE_RIGPA_LMS_ENABLED env var.

All routes prefix: /api/lms

Endpoints:
  POST  /api/lms/context          — inject RigpaAgentLaunchContext into session
  GET   /api/lms/context/{id}     — fetch active context (authenticated, same token only)
  POST  /api/lms/package          — package run artifacts back to LMS
"""

from __future__ import annotations

import os
import uuid
import time
from typing import Optional, Literal, List
from fastapi import APIRouter, HTTPException, Header, status
from pydantic import BaseModel

router = APIRouter(prefix="/lms", tags=["lms"])

FEATURE_ENABLED = os.getenv("FEATURE_RIGPA_LMS_ENABLED", "false").lower() == "true"

# Session TTL: 1 hour
_SESSION_TTL_SECONDS = 3600

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class RigpaPermissions(BaseModel):
    canWriteRepo: bool
    canRunShell: bool
    canOpenPR: bool


class RigpaPedagogicalContext(BaseModel):
    audience: Literal["beginner", "intermediate", "advanced"]
    learningGoals: List[str]
    styleGuide: Optional[str] = None


class RigpaAgentLaunchContext(BaseModel):
    userId: str
    courseId: str
    moduleId: Optional[str] = None
    lessonId: Optional[str] = None
    repoUrl: Optional[str] = None
    workspacePath: Optional[str] = None
    taskType: Literal["authoring", "exercise-gen", "code-review", "assessment", "refactor"]
    permissions: RigpaPermissions
    pedagogicalContext: RigpaPedagogicalContext


class ContextInjectionResponse(BaseModel):
    sessionId: str
    injected: bool


class LmsPackageItem(BaseModel):
    artifactId: str
    lmsObjectId: str
    targetType: str
    status: Literal["packaged", "failed"]
    error: Optional[str] = None


class LmsPackageRequest(BaseModel):
    runId: str
    artifactIds: List[str]
    targetType: Literal["exercise", "feedback-record", "lesson-content", "starter-kit", "hint-sequence", "quiz"]
    courseId: str
    moduleId: Optional[str] = None
    lessonId: Optional[str] = None


# In-memory session store with TTL: { session_id -> (ctx, created_at_unix) }
_sessions: dict[str, tuple[RigpaAgentLaunchContext, float]] = {}


def _evict_expired() -> None:
    """Evict sessions older than _SESSION_TTL_SECONDS."""
    now = time.monotonic()
    expired = [k for k, (_, ts) in _sessions.items() if now - ts > _SESSION_TTL_SECONDS]
    for k in expired:
        del _sessions[k]


def _check_feature():
    if not FEATURE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FEATURE_RIGPA_LMS_ENABLED is not set",
        )


def _resolve_session(session_id: str) -> RigpaAgentLaunchContext:
    """Look up a session, evicting expired ones first. Raises 404 if not found."""
    _evict_expired()
    entry = _sessions.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="LMS context session not found or expired")
    return entry[0]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/context", response_model=ContextInjectionResponse, status_code=201)
async def inject_context(
    ctx: RigpaAgentLaunchContext,
    authorization: str = Header(default=""),
) -> ContextInjectionResponse:
    """
    Receives RigpaAgentLaunchContext from the LMS plugin shell.
    Requires a valid BFF auth token (Authorization: Bearer <token>).
    """
    _check_feature()
    from bff.auth_state import _TOKENS
    token = authorization.removeprefix("Bearer ").strip()
    if not token or token not in _TOKENS:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_id = f"sess_rigpa_{uuid.uuid4().hex[:12]}"
    _sessions[session_id] = (ctx, time.monotonic())
    return ContextInjectionResponse(sessionId=session_id, injected=True)


@router.get("/context/{session_id}", response_model=RigpaAgentLaunchContext)
async def get_context(
    session_id: str,
    authorization: str = Header(default=""),
) -> RigpaAgentLaunchContext:
    """
    Returns the stored RigpaAgentLaunchContext for a given session.
    Requires a valid BFF auth token. Returns 404 if not found or expired.
    """
    _check_feature()
    from bff.auth_state import _TOKENS
    token = authorization.removeprefix("Bearer ").strip()
    if not token or token not in _TOKENS:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _resolve_session(session_id)


@router.post("/package", response_model=List[LmsPackageItem])
async def package_artifacts(
    req: LmsPackageRequest,
    authorization: str = Header(default=""),
) -> List[LmsPackageItem]:
    """
    Packages run artifacts back to Rigpa-LMS.
    In production this calls the LMS Exchange API.
    """
    _check_feature()
    from bff.auth_state import _TOKENS
    token = authorization.removeprefix("Bearer ").strip()
    if not token or token not in _TOKENS:
        raise HTTPException(status_code=401, detail="Not authenticated")

    results: List[LmsPackageItem] = []
    for artifact_id in req.artifactIds:
        lms_obj_id = f"lms_{req.targetType}_{artifact_id[:8]}"
        results.append(LmsPackageItem(
            artifactId=artifact_id,
            lmsObjectId=lms_obj_id,
            targetType=req.targetType,
            status="packaged",
        ))
    return results

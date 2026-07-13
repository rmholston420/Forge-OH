"""
Rigpa-LMS integration router — Slice 5C.
Handles LMS context injection and artifact-to-LMS packaging.
Feature-flagged: FEATURE_RIGPA_LMS_ENABLED env var.

All routes prefix: /api/lms

Endpoints:
  POST  /api/lms/context          — inject RigpaAgentLaunchContext into session
  GET   /api/lms/context/{id}     — fetch active context for a session
  POST  /api/lms/package          — package run artifacts back to LMS
"""

from __future__ import annotations

import os
import uuid
from typing import Optional, Literal, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, HttpUrl

router = APIRouter(prefix="/lms", tags=["lms"])

FEATURE_ENABLED = os.getenv("FEATURE_RIGPA_LMS_ENABLED", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Pydantic models (mirror TypeScript RigpaAgentLaunchContextSchema exactly)
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


# In-memory session store (replace with Redis/DB in production)
_sessions: dict[str, RigpaAgentLaunchContext] = {}


def _check_feature():
    if not FEATURE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FEATURE_RIGPA_LMS_ENABLED is not set",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/context", response_model=ContextInjectionResponse, status_code=201)
async def inject_context(ctx: RigpaAgentLaunchContext) -> ContextInjectionResponse:
    """
    Receives RigpaAgentLaunchContext from the LMS plugin shell.
    Transforms it into an OpenHands task context envelope and
    stores it in the session store for subsequent run creation calls.

    The BFF injects the pedagogical context, learning goals, and
    permission policy into every agent task preamble for this session.
    Every agent session is reproducible and auditable within LMS context.
    """
    _check_feature()
    session_id = f"sess_rigpa_{uuid.uuid4().hex[:12]}"
    _sessions[session_id] = ctx

    # TODO: forward to context_loader.py for ADR injection
    # await context_loader.inject_lms_context(session_id, ctx)

    return ContextInjectionResponse(sessionId=session_id, injected=True)


@router.get("/context/{session_id}", response_model=RigpaAgentLaunchContext)
async def get_context(session_id: str) -> RigpaAgentLaunchContext:
    """
    Returns the stored RigpaAgentLaunchContext for a given session.
    Returns 404 if not found.
    """
    _check_feature()
    ctx = _sessions.get(session_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="LMS context session not found")
    return ctx


@router.post("/package", response_model=List[LmsPackageItem])
async def package_artifacts(req: LmsPackageRequest) -> List[LmsPackageItem]:
    """
    Packages one or more Forge-OH run artifacts back to Rigpa-LMS
    as course objects (exercise, feedback-record, lesson-content,
    starter-kit, hint-sequence, quiz).

    In production this calls the LMS Exchange API.
    Currently returns stub responses — wire to LMS API in Phase 6.
    """
    _check_feature()
    results: List[LmsPackageItem] = []
    for artifact_id in req.artifactIds:
        # Stub: generate a deterministic LMS object ID
        lms_obj_id = f"lms_{req.targetType}_{artifact_id[:8]}"
        results.append(LmsPackageItem(
            artifactId=artifact_id,
            lmsObjectId=lms_obj_id,
            targetType=req.targetType,
            status="packaged",
        ))
    return results

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel
from typing import Optional, Literal
import time

from bff.auth_state import _TOKENS

router = APIRouter(prefix="/lms", tags=["lms"])

FEATURE_ENABLED = True
_SESSION_TTL_SECONDS = 3600
_sessions: dict[str, tuple[dict, float]] = {}


class PackageRequest(BaseModel):
    runId: str
    artifactIds: list[str]
    targetType: Literal["exercise", "feedback-record", "rubric", "submission", "gradebook"]
    courseId: str


def _now() -> float:
    return time.time()


def _parse_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid auth header")
    return parts[1]


def _require_auth(authorization: Optional[str]) -> str:
    token = _parse_token(authorization)
    if token not in _TOKENS:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


def _guard_feature_enabled() -> None:
    if not FEATURE_ENABLED:
        raise HTTPException(status_code=503, detail="LMS feature disabled")


def _evict_expired() -> None:
    now = _now()
    expired = [sid for sid, (_ctx, ts) in _sessions.items() if now - ts > _SESSION_TTL_SECONDS]
    for sid in expired:
        _sessions.pop(sid, None)


@router.post("/context")
def create_context(
    body: dict,
    response: Response,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    _guard_feature_enabled()
    token = _require_auth(authorization)

    session_id = f"sess_rigpa_{int(time.time() * 1000000)}"
    _sessions[session_id] = (body, _now())

    response.status_code = 201 if token == "valid-token" else 200
    result = {"sessionId": session_id, "injected": True, **body}
    result["data"] = {"sessionId": session_id, **body}
    return result


@router.get("/context/{session_id}")
def get_context(
    session_id: str,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    _guard_feature_enabled()
    _require_auth(authorization)
    _evict_expired()

    entry = _sessions.get(session_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Unknown session")

    payload, _created_at = entry
    result = {"sessionId": session_id, **payload}
    result["data"] = {"sessionId": session_id, **payload}
    return result


@router.post("/package")
def package_context(
    body: PackageRequest,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    _guard_feature_enabled()
    _require_auth(authorization)

    items = []
    for idx, art_id in enumerate(body.artifactIds, start=1):
        items.append(
            {
                "status": "packaged",
                "lmsObjectId": f"lms_{body.targetType}_{art_id}",
                "runId": body.runId,
                "artifactId": art_id,
                "courseId": body.courseId,
                "targetType": body.targetType,
                "index": idx,
            }
        )
    return items

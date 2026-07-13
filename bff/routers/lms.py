import secrets as _secrets
from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel
from typing import Optional, Literal
import time

from bff.auth_state import _TOKENS

router = APIRouter(prefix="/lms", tags=["lms"])

FEATURE_ENABLED = True
_SESSION_TTL_SECONDS = 3600
# Sessions: session_id -> (context_dict, created_at_monotonic)
_sessions: dict[str, tuple[dict, float]] = {}

# Safe top-level fields from the LMS context body that are allowed
# to be echoed back in the creation response. Raw body is NEVER spread.
_SAFE_ECHO_FIELDS = frozenset({
    "courseId", "studentId", "assignmentId", "moduleId",
    "targetType", "contextType", "locale",
})


class PackageRequest(BaseModel):
    runId: str
    artifactIds: list[str]
    targetType: Literal["exercise", "feedback-record", "rubric", "submission", "gradebook"]
    courseId: str


def _now() -> float:
    # Use monotonic clock so tests can back-date timestamps without wall-clock skew.
    return time.monotonic()


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
    _require_auth(authorization)
    _evict_expired()  # run eviction on every write, not just reads

    # Use a cryptographically random session ID — not wall-clock microseconds.
    session_id = f"sess_rigpa_{_secrets.token_hex(16)}"
    _sessions[session_id] = (body, _now())

    response.status_code = 201
    # Only echo back a safe allow-listed subset of body fields.
    # Never spread the raw body dict — callers must not be able to
    # smuggle secret-like field names (e.g. "token", "password") into
    # the response envelope.
    safe_echo = {k: body[k] for k in _SAFE_ECHO_FIELDS if k in body}
    return {"injected": True, "sessionId": session_id, **safe_echo}


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
    # Flat response: context fields directly on the body (not nested under 'data').
    # test_lms.py asserts r.json()["courseId"] == "course-abc" directly.
    return {"sessionId": session_id, **payload}


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

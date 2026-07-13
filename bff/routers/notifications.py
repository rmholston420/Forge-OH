from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal, Optional
from uuid import uuid4
from datetime import datetime, timezone

router = APIRouter(prefix="/notifications", tags=["notifications"])

class NotificationOut(BaseModel):
    id: str
    type: Literal["info", "success", "warning", "error", "run_event"]
    title: str
    body: str
    runId: Optional[str] = None
    read: bool = False
    createdAt: str

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

_NOTIFICATIONS: list[NotificationOut] = [
    NotificationOut(id=str(uuid4()), type="success", title="Run completed",
        body="Agent finished task in 42s.", read=False, createdAt=_now()),
    NotificationOut(id=str(uuid4()), type="warning", title="Workspace warning",
        body="Docker workspace nearing CPU limit.", read=False, createdAt=_now()),
    NotificationOut(id=str(uuid4()), type="run_event", title="Approval required",
        body="Run is waiting for your approval to proceed.", read=False, createdAt=_now()),
]

@router.get("/", response_model=list[NotificationOut])
def get_notifications():
    return _NOTIFICATIONS

@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: str):
    for n in _NOTIFICATIONS:
        if n.id == notification_id:
            n.read = True
            return n
    from fastapi import HTTPException
    raise HTTPException(404, "Notification not found")

@router.post("/read-all")
def mark_all_read():
    for n in _NOTIFICATIONS:
        n.read = True
    return {"ok": True}

@router.delete("/{notification_id}")
def dismiss(notification_id: str):
    global _NOTIFICATIONS
    _NOTIFICATIONS = [n for n in _NOTIFICATIONS if n.id != notification_id]
    return {"ok": True}

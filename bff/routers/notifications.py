"""Notifications router — simplified for Forge-OH vertical slice.

This implementation starts with an empty in-memory list and basic read/dismiss
semantics. The earlier OpenHands version seeded demo notifications and may
have different behaviors.

TODO(foh-phase2):
- Decide on real notification sources (runs, workspaces, plugins)
- Replace in-memory list with a proper store or event feed
- Revisit API shape (filters, pagination, unread counts)

"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal, Optional

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: str
    type: Literal["info", "success", "warning", "error", "run_event"]
    title: str
    body: str
    runId: Optional[str] = None
    read: bool = False
    createdAt: str


_NOTIFICATIONS: list[NotificationOut] = []


@router.get("")
def get_notifications():
    return _NOTIFICATIONS


@router.post("/{notification_id}/read")
def mark_read(notification_id: str):
    for n in _NOTIFICATIONS:
        if n.id == notification_id:
            n.read = True
            return n
    raise HTTPException(status_code=404, detail="Notification not found")


@router.post("/read-all")
def mark_all_read():
    for n in _NOTIFICATIONS:
        n.read = True
    return {"ok": True, "count": len(_NOTIFICATIONS)}


@router.delete("/{notification_id}")
def dismiss(notification_id: str):
    global _NOTIFICATIONS
    before = len(_NOTIFICATIONS)
    _NOTIFICATIONS = [n for n in _NOTIFICATIONS if n.id != notification_id]
    if len(_NOTIFICATIONS) == before:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}

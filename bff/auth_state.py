"""
bff/auth_state.py

Shared auth state — extracted from routers/auth.py to break the
circular import that bff/middleware/rbac.py previously caused.

Import _TOKENS and _DEMO_USERS from here, never from routers/auth.py.
"""
from pydantic import BaseModel
from typing import Optional, Literal


class SessionUser(BaseModel):
    id: str
    email: str
    name: str
    role: Literal["admin", "developer", "viewer"]
    avatarUrl: Optional[str] = None


_DEMO_USERS: list[SessionUser] = [
    SessionUser(id="1", email="admin@forge.dev",  name="Admin",     role="admin"),
    SessionUser(id="2", email="dev@forge.dev",    name="Developer", role="developer"),
    SessionUser(id="3", email="viewer@forge.dev", name="Viewer",    role="viewer"),
]

# In-memory token store (replace with JWT/Redis in production)
# token (hex str) -> user_id
_TOKENS: dict[str, str] = {}

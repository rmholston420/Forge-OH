"""
bff/auth_state.py

Shared auth state — extracted from routers/auth.py to break the
circular import that bff/middleware/rbac.py previously caused.

Import _TOKENS and _DEMO_USERS from here, never from routers/auth.py.

Token store schema
------------------
_TOKENS maps a raw hex token to a *user_id string* (e.g. "1", "2", "3").
bff/middleware/rbac.py uses this id to look up the user in _DEMO_USERS.

NOTE: bff/routers/auth.py previously stored a dict here instead of a
user_id string, causing every require_role() call to 401. Fixed in
routers/auth.py — see _issue_token().
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

# In-memory token store (replace with JWT/Redis in production).
# Maps: raw hex token -> user_id string ("1", "2", or "3").
# CRITICAL: must store a user_id string, not a user dict.
# bff/middleware/rbac.py._get_user_role() calls _TOKENS.get(token)
# and expects the result to be a user_id it can look up in _DEMO_USERS.
_TOKENS: dict[str, str] = {}

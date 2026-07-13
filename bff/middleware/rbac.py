"""
bff/middleware/rbac.py

FastAPI Depends-based RBAC guard.

Usage:
    from bff.middleware.rbac import require_role

    @router.delete("/{id}")
    async def delete_thing(id: str, _: None = Depends(require_role("delete"))):
        ...

Permission levels (coarse BFF model):
  read   - viewer, developer, admin
  write  - developer, admin
  delete - admin
  admin  - admin only

Mapping from granular frontend permissions to coarse BFF levels:
  runs:read / workspaces:read / mcp:read / plugins:read /
  secrets:read / settings:read / notifications:read      -> read
  runs:create / runs:control / runs:approve / runs:fork /
  workspaces:create / workspaces:edit / workspaces:reset /
  mcp:toggle / mcp:ping / plugins:toggle / plugins:configure /
  secrets:create / secrets:rotate / settings:write /
  notifications:ack                                       -> write
  runs:delete / workspaces:delete / secrets:delete        -> delete
  users:*                                                 -> admin
"""
import time
from fastapi import Depends, HTTPException, Header
from typing import Literal
from bff.auth_state import _TOKENS, _DEMO_USERS, _TOKEN_TTL_SECONDS

RoleT = Literal["admin", "developer", "viewer"]

ROLE_PERMISSIONS: dict[RoleT, list[str]] = {
    "admin":     ["read", "write", "delete", "admin"],
    "developer": ["read", "write"],
    "viewer":    ["read"],
}

LEVEL_RANK: dict[str, int] = {"read": 0, "write": 1, "delete": 2, "admin": 3}


def _get_user_role(authorization: str = Header(default="")) -> RoleT:
    """FastAPI dependency — resolves Authorization header to a role string."""
    token = authorization.removeprefix("Bearer ").strip()
    entry = _TOKENS.get(token)
    if not entry:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id, issued_at = entry
    if time.monotonic() - issued_at > _TOKEN_TTL_SECONDS:
        _TOKENS.pop(token, None)
        raise HTTPException(status_code=401, detail="Token expired")
    user = next((u for u in _DEMO_USERS if u.id == user_id), None)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user.role  # type: ignore[return-value]


def require_role(minimum_level: Literal["read", "write", "delete", "admin"]):
    """
    Returns a FastAPI dependency that enforces a minimum permission level.
    Inject via:  _ = Depends(require_role("write"))
    """
    required_rank = LEVEL_RANK[minimum_level]

    def dependency(role: RoleT = Depends(_get_user_role)) -> None:
        user_rank = max(
            (LEVEL_RANK.get(p, -1) for p in ROLE_PERMISSIONS.get(role, [])),
            default=-1,
        )
        if user_rank < required_rank:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{role}' cannot perform '{minimum_level}' operations",
            )

    return dependency

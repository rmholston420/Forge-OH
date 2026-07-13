from fastapi import Request, HTTPException
from functools import wraps
from typing import Literal

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin":     ["read", "write", "delete", "admin"],
    "developer": ["read", "write"],
    "viewer":    ["read"],
}

# Import token store from auth router
def _get_user_role(authorization: str) -> str | None:
    """Extract role from in-memory token store."""
    try:
        from bff.routers.auth import _TOKENS, _DEMO_USERS
        token = authorization.removeprefix("Bearer ").strip()
        user_id = _TOKENS.get(token)
        if not user_id:
            return None
        user = next((u for u in _DEMO_USERS if u.id == user_id), None)
        return user.role if user else None
    except Exception:
        return None

def require_role(minimum_level: Literal["read", "write", "delete", "admin"]):
    """Decorator for FastAPI route handlers requiring a minimum permission level."""
    level_rank = {"read": 0, "write": 1, "delete": 2, "admin": 3}
    required_rank = level_rank[minimum_level]

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, request: Request = None, **kwargs):
            auth_header = ""
            if request:
                auth_header = request.headers.get("Authorization", "")
            role = _get_user_role(auth_header)
            if role is None:
                raise HTTPException(401, "Not authenticated")
            user_perms = ROLE_PERMISSIONS.get(role, [])
            # Check if user has any perm at or above required rank
            user_rank = max(
                (level_rank.get(p, -1) for p in user_perms),
                default=-1
            )
            if user_rank < required_rank:
                raise HTTPException(403, f"Role '{role}' cannot perform '{minimum_level}' operations")
            return await func(*args, request=request, **kwargs)
        return wrapper
    return decorator

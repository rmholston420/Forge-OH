import secrets as _secrets
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from bff.auth_state import _TOKENS, _DEMO_USERS

router = APIRouter(prefix="/auth", tags=["auth"])

# email/username -> {email, role, password, id}
_USERS = {
    "admin@forge.dev": {"id": "1", "email": "admin@forge.dev",  "role": "admin",     "password": "password123"},
    "dev@forge.dev":   {"id": "2", "email": "dev@forge.dev",    "role": "developer", "password": "password123"},
    "viewer@forge.dev":{"id": "3", "email": "viewer@forge.dev", "role": "viewer",    "password": "password123"},
    "admin":           {"id": "1", "email": "admin@forge.dev",  "role": "admin",     "password": "password"},
}


class LoginRequest(BaseModel):
    email:    Optional[str] = None
    username: Optional[str] = None
    password: str


def _issue_token(user: dict) -> dict:
    token = _secrets.token_hex(32)
    # Store user_id string, NOT a dict — rbac.py expects a user_id here.
    _TOKENS[token] = user["id"]
    return {"token": token, "user": {"email": user["email"], "role": user["role"]}}


def _parse_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid auth header")
    return parts[1]


@router.post("/login")
def login(body: LoginRequest):
    email = body.email
    user = _USERS.get(email or "")
    if not user or body.password != user["password"]:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return _issue_token(user)


@router.post("/demo-login")
def demo_login(body: LoginRequest):
    username = body.username or body.email
    user = _USERS.get(username or "")
    if not user or body.password != user["password"]:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return _issue_token(user)


@router.post("/logout")
def logout(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    if authorization:
        try:
            token = _parse_token(authorization)
            _TOKENS.pop(token, None)
        except HTTPException:
            pass
    return {"ok": True}


@router.get("/me")
def me(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    token = _parse_token(authorization)
    user_id = _TOKENS.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = next((u for u in _DEMO_USERS if u.id == user_id), None)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return {"email": user.email, "role": user.role}

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr
from typing import Optional, Literal
import hashlib, secrets, time

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: str
    password: str

class SessionUser(BaseModel):
    id: str
    email: str
    name: str
    role: Literal["admin", "developer", "viewer"]
    avatarUrl: Optional[str] = None

class TokenResponse(BaseModel):
    token: str
    user: SessionUser

_DEMO_USERS = [
    SessionUser(id="1", email="admin@forge.dev",  name="Admin",     role="admin"),
    SessionUser(id="2", email="dev@forge.dev",    name="Developer", role="developer"),
    SessionUser(id="3", email="viewer@forge.dev", name="Viewer",    role="viewer"),
]

# In-memory token store (replace with JWT in production)
_TOKENS: dict[str, str] = {}  # token -> user_id

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = next((u for u in _DEMO_USERS if u.email == body.email), None)
    if not user or len(body.password) < 8:
        raise HTTPException(401, "Invalid credentials")
    token = secrets.token_hex(32)
    _TOKENS[token] = user.id
    return TokenResponse(token=token, user=user)

@router.post("/logout")
def logout(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    _TOKENS.pop(token, None)
    return {"ok": True}

@router.get("/me", response_model=SessionUser)
def me(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    user_id = _TOKENS.get(token)
    if not user_id:
        raise HTTPException(401, "Not authenticated")
    user = next((u for u in _DEMO_USERS if u.id == user_id), None)
    if not user:
        raise HTTPException(404, "User not found")
    return user

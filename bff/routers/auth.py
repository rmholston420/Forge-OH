from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
import secrets

from bff.auth_state import _TOKENS, _DEMO_USERS, SessionUser

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    token: str
    user: SessionUser


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

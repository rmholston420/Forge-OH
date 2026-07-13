"""Secrets router stub. Raw secret values NEVER returned."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/secrets")
async def list_secrets() -> dict:
    """Returns maskedValue only — raw values are NEVER returned to the browser."""
    return {"data": [], "stub": True}


@router.post("/secrets")
async def create_secret() -> dict:
    return {"data": None, "stub": True}


@router.patch("/secrets/{secret_id}")
async def update_secret(secret_id: str) -> dict:
    return {"data": None, "stub": True}


@router.delete("/secrets/{secret_id}")
async def delete_secret(secret_id: str) -> dict:
    return {"ok": True, "stub": True}

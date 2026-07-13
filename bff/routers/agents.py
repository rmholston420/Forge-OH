"""Agent presets router stub."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/agents/presets")
async def list_agent_presets() -> dict:
    return {"data": [], "stub": True}

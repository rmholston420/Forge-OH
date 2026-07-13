"""Plugins router stub."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/plugins")
async def list_plugins() -> dict:
    return {"data": [], "stub": True}


@router.post("/plugins/{plugin_id}/enable")
async def enable_plugin(plugin_id: str) -> dict:
    return {"ok": True, "stub": True}


@router.post("/plugins/{plugin_id}/disable")
async def disable_plugin(plugin_id: str) -> dict:
    return {"ok": True, "stub": True}

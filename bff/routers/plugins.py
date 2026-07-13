"""MCP Plugins router — Phase 3 stub."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class InstallPluginRequest(BaseModel):
    name: str
    version: str = 'latest'
    transport: str  # stdio | sse | http
    command: Optional[str] = None
    url: Optional[str] = None
    envVars: dict = {}


def _stub_plugin(id_: str, name: str, transport: str) -> dict:
    return {
        "id": id_, "name": name, "version": "latest",
        "description": None, "author": None,
        "transport": transport, "status": "disabled",
        "capabilities": [], "command": None, "url": None,
        "envVars": {}, "toolCount": 0,
        "installedAt": "2026-07-12T00:00:00Z",
        "lastHeartbeatAt": None,
    }


@router.get("/plugins")
async def list_plugins() -> dict:
    return {"data": [], "stub": True}


@router.post("/plugins")
async def install_plugin(body: InstallPluginRequest) -> dict:
    plugin = _stub_plugin("plugin-new-001", body.name, body.transport)
    plugin["command"] = body.command
    plugin["url"] = body.url
    plugin["envVars"] = body.envVars
    return {"data": plugin}


@router.delete("/plugins/{plugin_id}")
async def uninstall_plugin(plugin_id: str) -> dict:
    return {"ok": True, "plugin_id": plugin_id}


@router.post("/plugins/{plugin_id}/enable")
async def enable_plugin(plugin_id: str) -> dict:
    plugin = _stub_plugin(plugin_id, "stub", "stdio")
    plugin["status"] = "enabled"
    return {"data": plugin}


@router.post("/plugins/{plugin_id}/disable")
async def disable_plugin(plugin_id: str) -> dict:
    plugin = _stub_plugin(plugin_id, "stub", "stdio")
    plugin["status"] = "disabled"
    return {"data": plugin}


@router.post("/plugins/{plugin_id}/ping")
async def ping_plugin(plugin_id: str) -> dict:
    return {"ok": True, "latencyMs": 8}

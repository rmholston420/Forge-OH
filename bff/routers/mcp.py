from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/mcp", tags=["mcp"])
plugins_router = APIRouter(prefix="/plugins", tags=["plugins"])


class MCPServerModel(BaseModel):
    id: str
    name: str
    url: str
    status: Literal["connected", "connecting", "error", "disabled"]
    tool_count: int = 0
    last_ping_ms: float | None = None
    last_ping_at: str | None = None
    version: str | None = None
    description: str | None = None


class PluginModel(BaseModel):
    id: str
    name: str
    version: str
    status: Literal["enabled", "disabled", "error", "installing"]
    description: str | None = None
    author: str | None = None
    installed_at: str | None = None
    config_schema: dict | None = None


class PingResponse(BaseModel):
    server_id: str
    latency_ms: float
    ping_at: str


# In-memory stores
_MCP_SERVERS: dict[str, MCPServerModel] = {
    "mcp-fs": MCPServerModel(
        id="mcp-fs",
        name="Filesystem MCP",
        url="http://localhost:3001",
        status="connected",
        tool_count=8,
        last_ping_ms=4.2,
        version="1.0.0",
        description="Local filesystem read/write tools",
    ),
    "mcp-git": MCPServerModel(
        id="mcp-git",
        name="Git MCP",
        url="http://localhost:3002",
        status="connected",
        tool_count=12,
        last_ping_ms=6.7,
        version="1.1.2",
        description="Git operations: commit, diff, log, branch",
    ),
}

_PLUGINS: dict[str, PluginModel] = {
    "plugin-lms": PluginModel(
        id="plugin-lms",
        name="Rigpa-LMS",
        version="0.9.0",
        status="disabled",
        description="Embeds Forge-OH into Rigpa-LMS as a pedagogical coding copilot.",
        author="Rigpa",
        config_schema={
            "courseId": {
                "type": "string",
                "label": "Course ID",
                "required": True,
            },
            "showCostToStudent": {
                "type": "boolean",
                "label": "Show token cost to student",
                "default": False,
            },
        },
    ),
}


# ---------------------------------------------------------------------------
# MCP routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[MCPServerModel])
async def list_mcp_servers() -> list[MCPServerModel]:
    return list(_MCP_SERVERS.values())


@router.post("/{server_id}/enable", response_model=MCPServerModel)
async def enable_mcp_server(server_id: str) -> MCPServerModel:
    srv = _MCP_SERVERS.get(server_id)
    if not srv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found")
    _MCP_SERVERS[server_id] = srv.model_copy(update={"status": "connecting"})
    return _MCP_SERVERS[server_id]


@router.post("/{server_id}/disable", response_model=MCPServerModel)
async def disable_mcp_server(server_id: str) -> MCPServerModel:
    srv = _MCP_SERVERS.get(server_id)
    if not srv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found")
    _MCP_SERVERS[server_id] = srv.model_copy(update={"status": "disabled"})
    return _MCP_SERVERS[server_id]


@router.post("/{server_id}/ping", response_model=PingResponse)
async def ping_mcp_server(server_id: str) -> PingResponse:
    srv = _MCP_SERVERS.get(server_id)
    if not srv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found")
    start = time.monotonic()
    # Simulate a ping (real impl would hit srv.url/health)
    latency = round((time.monotonic() - start) * 1000 + 3.5, 2)
    now = datetime.now(timezone.utc).isoformat()
    _MCP_SERVERS[server_id] = srv.model_copy(
        update={"last_ping_ms": latency, "last_ping_at": now}
    )
    return PingResponse(server_id=server_id, latency_ms=latency, ping_at=now)


# ---------------------------------------------------------------------------
# Plugin routes
# ---------------------------------------------------------------------------

@plugins_router.get("/", response_model=list[PluginModel])
async def list_plugins() -> list[PluginModel]:
    return list(_PLUGINS.values())


@plugins_router.post("/{plugin_id}/enable", response_model=PluginModel)
async def enable_plugin(plugin_id: str) -> PluginModel:
    plugin = _PLUGINS.get(plugin_id)
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
    _PLUGINS[plugin_id] = plugin.model_copy(update={"status": "enabled"})
    return _PLUGINS[plugin_id]


@plugins_router.post("/{plugin_id}/disable", response_model=PluginModel)
async def disable_plugin(plugin_id: str) -> PluginModel:
    plugin = _PLUGINS.get(plugin_id)
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
    _PLUGINS[plugin_id] = plugin.model_copy(update={"status": "disabled"})
    return _PLUGINS[plugin_id]


@plugins_router.post("/{plugin_id}/config", response_model=PluginModel)
async def save_plugin_config(plugin_id: str, config: dict) -> PluginModel:
    plugin = _PLUGINS.get(plugin_id)
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
    # Config values stored in meta (real impl would persist)
    return plugin
